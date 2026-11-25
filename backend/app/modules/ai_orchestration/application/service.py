"""Agent run use cases: execute, persist (traceable to the data version), audit, and read history.

Nothing here caches an answer or a metric: every run takes a fresh snapshot and every tool reads live data.
"""
import logging
import time
import uuid
from typing import Any

from app.modules.agent_tools.public import ToolResult
from app.modules.ai_orchestration.application import contracts as c
from app.modules.ai_orchestration.application.agent import AgentFailure, AgentIncomplete, AgentOutcome, AgentRunner
from app.modules.ai_orchestration.application.ports import LlmPort
from app.modules.ai_orchestration.application.briefing import assess, build_briefing
from app.modules.ai_orchestration.application.snapshot import take_snapshot
from app.modules.ai_orchestration.domain.citations import RetrievedRef, check_citations
from app.modules.ai_orchestration.domain.prompts import FIXED_DEMO_QUESTION
from app.modules.ai_orchestration.infrastructure.models import AnalysisRunRow
from app.modules.ai_orchestration.infrastructure.repository import RunRepository
from app.modules.model_providers.public import ProviderCallError, Usage
from app.modules.simulation import public as simulation
from app.platform.audit_events import AuditEvent
from app.platform.db import unit_of_work
from app.platform.errors import AppError, NotFoundError
from app.platform.events import get_event_bus

log = logging.getLogger("app.ai_orchestration")


class AgentRunFailed(AppError):
    status_code = 502
    code = "agent_run_failed"


def _tool_view(r: ToolResult) -> dict[str, Any]:
    return c.ToolExecutionView(
        sequence=r.sequence, tool_name=r.tool_name, status=r.status, arguments=r.arguments, output=r.output,
        error=r.error.message if r.error else None, duration_ms=r.duration_ms, data_version=r.data_version,
    ).model_dump(mode="json")


def _policies(results: list[ToolResult]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, int, str], dict[str, Any]] = {}
    for r in results:
        if r.tool_name == "retrieve_hospital_protocol" and r.status == "ok" and r.output:
            for ch in r.output.get("chunks", []):
                key = (ch["document_name"], ch["page"], ch["excerpt"][:80])
                if key not in seen or ch["score"] > seen[key]["score"]:
                    seen[key] = c.RetrievedPolicyView(
                        document_name=ch["document_name"], page=ch["page"], score=ch["score"], excerpt=ch["excerpt"],
                        matched_query=ch["matched_query"], flagged=ch["flagged"],
                    ).model_dump(mode="json")
    return sorted(seen.values(), key=lambda p: p["score"], reverse=True)


def _to_response(row: AnalysisRunRow) -> c.AgentRunResponse:
    return c.AgentRunResponse(
        id=row.id, run_type=row.run_type, question=row.question, status=row.status, error=row.error, answer=row.answer,
        mode=row.mode, fallback_reason=row.fallback_reason, scenario_key=row.scenario_key,
        scenario_name=row.scenario_name, data_version=row.data_version,
        data_version_consistent=row.data_version_consistent, snapshot_metrics=row.snapshot_metrics,
        tools_executed=row.tools_executed, retrieved_policies=row.retrieved_docs, citation_check=row.citation_check,
        provider=row.provider, model=row.model, temperature=row.temperature, llm_calls=row.llm_calls,
        latency_ms=row.latency_ms,
        usage=Usage(prompt_tokens=row.prompt_tokens, completion_tokens=row.completion_tokens,
                    total_tokens=row.total_tokens),
        estimated_cost_usd=row.estimated_cost_usd, data_disclosure=row.data_disclosure,
        created_by=row.created_by, created_at=row.created_at,
    )


class AgentService:
    def __init__(self, llm: LlmPort) -> None:
        self._llm = llm
        self._runner = AgentRunner(llm)

    # ------------------------------------------------------------------ run
    def run(self, *, question: str, provider: str, model: str, temperature: float | None = None,
            mode: str = "auto", run_type: str = "agent", actor: str = "system") -> c.AgentRunResponse:
        self._llm.ensure_configured(provider, model)  # config problems fail fast, before any tool runs
        snapshot = take_snapshot()  # fresh: the exact data state this analysis is about
        run_id = uuid.uuid4()
        started = time.perf_counter()

        outcome = AgentOutcome()
        failure: str | None = None
        error_to_raise: Exception | None = None
        try:
            outcome = self._runner.run(question=question, provider=provider, model=model, temperature=temperature,
                                       mode=mode, run_id=run_id,
                                       briefing=build_briefing(snapshot, assess(snapshot)))
        except AgentFailure as fail:
            outcome = fail.outcome  # keep the tools that did run and the tokens already spent
            if isinstance(fail.cause, ProviderCallError):
                failure, error_to_raise = fail.cause.message, fail.cause
            else:
                failure, error_to_raise = str(fail.cause), AgentRunFailed(str(fail.cause))

        latency_ms = int((time.perf_counter() - started) * 1000)
        results = outcome.results
        policies = _policies(results)
        citation = check_citations(
            outcome.answer, [RetrievedRef(p["document_name"], p["page"]) for p in policies if not p["flagged"]]
        )
        consistent = self._consistent(snapshot.data_version, results)

        with unit_of_work() as session:
            row = RunRepository(session).add(
                id=run_id, run_type=run_type, question=question, scenario_key=snapshot.scenario_key,
                scenario_name=snapshot.scenario_name, data_version=snapshot.data_version,
                data_version_consistent=consistent, snapshot_metrics=snapshot.metrics, mode=outcome.mode,
                fallback_reason=outcome.fallback_reason, tools_executed=[_tool_view(r) for r in results],
                retrieved_docs=policies, citation_check=citation, provider=provider, model=model,
                # None (shown as "provider default") when the model rejected the value and it was not sent
                temperature=temperature if outcome.temperature_applied else None, llm_calls=outcome.llm_calls, latency_ms=latency_ms,
                prompt_tokens=outcome.prompt_tokens, completion_tokens=outcome.completion_tokens,
                total_tokens=outcome.total_tokens, estimated_cost_usd=outcome.cost_usd,
                data_disclosure=outcome.data_disclosure, answer=outcome.answer,
                status="failed" if failure else "completed", error=failure, created_by=actor,
            )
            response = _to_response(row)

        self._audit(actor, run_id, run_type, provider, model, snapshot.data_version, results,
                    "failure" if failure else "success")
        if error_to_raise is not None:
            raise error_to_raise
        return response

    def demo_run(self, *, provider: str, model: str, temperature: float | None = None, mode: str = "auto",
                 actor: str = "system") -> c.AgentRunResponse:
        return self.run(question=FIXED_DEMO_QUESTION, provider=provider, model=model, temperature=temperature,
                        mode=mode, run_type="demo", actor=actor)

    @staticmethod
    def _consistent(start_version: int, results: list[ToolResult]) -> bool:
        """True only if every tool saw the snapshot's data version and the data did not change during the run."""
        if any(r.data_version is not None and r.data_version != start_version for r in results):
            return False
        return simulation.current_state().data_version == start_version

    @staticmethod
    def _audit(actor, run_id, run_type, provider, model, version, results, outcome) -> None:
        try:
            get_event_bus().publish(AuditEvent(
                actor=actor, action=f"agent.{run_type}_run", outcome=outcome, resource=str(run_id),
                detail={"provider": provider, "model": model, "data_version": version,
                        "tools": [r.tool_name for r in results], "refused": sum(r.status == "refused" for r in results)},
            ))
        except Exception as exc:  # noqa: BLE001 - auditing must never break the request
            log.warning("Audit publish failed: %s", type(exc).__name__)


def demo_question() -> str:
    """The fixed demonstration question (identical for every scenario and every model)."""
    return FIXED_DEMO_QUESTION


# ------------------------------------------------------------------ history
def list_runs(limit: int = 20, offset: int = 0, run_type: str | None = None, scenario_key: str | None = None,
              data_version: int | None = None) -> c.RunPage:
    with unit_of_work() as session:
        rows, total = RunRepository(session).list(limit=limit, offset=offset, run_type=run_type,
                                                  scenario_key=scenario_key, data_version=data_version)
        items = [
            c.RunSummary(
                id=r.id, run_type=r.run_type, question=r.question, scenario_name=r.scenario_name,
                data_version=r.data_version, provider=r.provider, model=r.model, mode=r.mode, status=r.status,
                tool_names=[t["tool_name"] for t in r.tools_executed], latency_ms=r.latency_ms,
                total_tokens=r.total_tokens, created_at=r.created_at,
            )
            for r in rows
        ]
    return c.RunPage(items=items, total=total, limit=limit, offset=offset)


def get_run(run_id: uuid.UUID) -> c.AgentRunResponse:
    with unit_of_work() as session:
        row = RunRepository(session).get(run_id)
        if row is None:
            raise NotFoundError("Run not found")
        return _to_response(row)
