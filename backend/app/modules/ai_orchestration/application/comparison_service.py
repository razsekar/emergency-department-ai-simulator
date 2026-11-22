"""Model comparison use cases.

Fairness rule: ONE scenario snapshot, ONE set of tool results and ONE retrieved policy context are produced first.
Every selected model then writes its final answer from the byte-identical frozen prompt. The prompt hash is recorded
per model and compared with the shared hash, and the simulation data version is re-checked after the model calls.

Tool results come from the same deterministic data-driven plan the agent's fallback mode uses (reused, not copied), so
the comparison isolates final-answer generation rather than each model's tool-planning skill.
"""
import hashlib
import json
import logging
import time
import uuid
from typing import Any

from app.modules.ai_orchestration.application import comparison_contracts as cc
from app.modules.ai_orchestration.application.agent import AgentOutcome, AgentRunner, _render_for_fallback
from app.modules.ai_orchestration.application.ports import LlmPort
from app.modules.ai_orchestration.application.service import _policies, _tool_view
from app.modules.ai_orchestration.application.snapshot import Snapshot, take_snapshot
from app.modules.ai_orchestration.domain import prompts
from app.modules.ai_orchestration.domain.citations import RetrievedRef
from app.modules.ai_orchestration.domain.comparison_scoring import ScoreInputs, score_answer
from app.modules.ai_orchestration.domain.plan import PLAN_HEAD, policy_topics
from app.modules.ai_orchestration.infrastructure.comparison_repository import ComparisonRepository
from app.modules.model_providers.public import ChatMessage, ChatRequest, Usage
from app.modules.simulation import public as simulation
from app.platform.audit_events import AuditEvent
from app.platform.db import unit_of_work
from app.platform.errors import AppError, NotFoundError
from app.platform.events import get_event_bus

log = logging.getLogger("app.ai_orchestration")


class NoModelAvailable(AppError):
    status_code = 409
    code = "no_model_available"


class DataChangedDuringComparison(AppError):
    status_code = 409
    code = "data_changed_during_comparison"


def _sha256(messages: list[ChatMessage]) -> str:
    payload = json.dumps([[m.role, m.content] for m in messages], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.message
    return f"Unexpected error ({type(exc).__name__})"


def _result_view(r) -> cc.ModelResultView:
    return cc.ModelResultView(
        position=r.position, provider=r.provider, model=r.model, temperature=r.temperature, status=r.status,
        error=r.error, answer=r.answer, latency_ms=r.latency_ms,
        usage=Usage(prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens, total_tokens=r.total_tokens),
        estimated_cost_usd=r.estimated_cost_usd, tool_calling_supported=r.tool_calling_supported,
        data_disclosure=r.data_disclosure, context_sha256=r.context_sha256, scores=r.scores,
        citation_check=r.citation_check,
    )


def _to_response(run, rows) -> cc.ComparisonRunResponse:
    verified = all(r.context_sha256 == run.context_sha256 for r in rows if r.status != "not_configured")
    return cc.ComparisonRunResponse(
        id=run.id, question=run.question, status=run.status, data_version_consistent=run.data_version_consistent,
        identical_context_verified=verified,
        shared_context=cc.SharedContextView(
            scenario_key=run.scenario_key, scenario_name=run.scenario_name, data_version=run.data_version,
            snapshot_metrics=run.snapshot_metrics, tools_executed=run.shared_tools,
            retrieved_policies=run.shared_policies, context_sha256=run.context_sha256,
        ),
        results=[_result_view(r) for r in rows], created_by=run.created_by, created_at=run.created_at,
    )


class ComparisonService:
    def __init__(self, llm: LlmPort) -> None:
        self._llm = llm

    # ------------------------------------------------------------------ run
    def run(self, *, question: str, selections: list[cc.ModelSelection], actor: str = "system"
            ) -> cc.ComparisonRunResponse:
        configured, skipped = self._split_by_configuration(selections)
        if not configured:
            reasons = "; ".join(f"{s.provider}/{s.model}: {msg}" for s, msg in skipped)
            raise NoModelAvailable(f"None of the selected models can be used. {reasons}")

        snapshot = take_snapshot()  # ONE fresh snapshot for the whole comparison
        shared_run_id = uuid.uuid4()
        outcome = self._collect_shared_tool_results(shared_run_id)
        results = outcome.results
        self._abort_if_data_moved(snapshot, results)

        policies = _policies(results)
        retrieved = [RetrievedRef(p["document_name"], p["page"]) for p in policies if not p["flagged"]]
        messages = self._shared_messages(question, results)
        shared_hash = _sha256(messages)

        rows: list[dict[str, Any]] = []
        for position, selection in enumerate(selections):
            skip = next((msg for s, msg in skipped if s is selection), None)
            if skip is not None:
                rows.append(self._not_configured_row(position, selection, skip))
            else:
                rows.append(self._ask_model(position, selection, messages, snapshot, retrieved))

        consistent = self._unchanged(snapshot, results)  # data must not have moved while the models were answering
        completed = sum(r["status"] == "completed" for r in rows)
        status = "completed" if completed == len(rows) else "partial" if completed else "failed"

        with unit_of_work() as session:
            run, saved = ComparisonRepository(session).add(
                dict(question=question, scenario_key=snapshot.scenario_key, scenario_name=snapshot.scenario_name,
                     data_version=snapshot.data_version, data_version_consistent=consistent,
                     snapshot_metrics=snapshot.metrics, shared_tools=[_tool_view(r) for r in results],
                     shared_policies=policies, context_sha256=shared_hash,
                     selections=[s.model_dump(mode="json") for s in selections], status=status, created_by=actor),
                rows,
            )
            response = _to_response(run, saved)

        self._audit(actor, response)
        return response

    # ------------------------------------------------------------------ steps
    def _split_by_configuration(self, selections):
        configured: list[cc.ModelSelection] = []
        skipped: list[tuple[cc.ModelSelection, str]] = []
        for s in selections:
            try:
                self._llm.ensure_configured(s.provider, s.model)
                configured.append(s)
            except AppError as exc:  # not configured: reported in the result, never silently dropped
                skipped.append((s, exc.message))
        return configured, skipped

    def _collect_shared_tool_results(self, run_id: uuid.UUID) -> AgentOutcome:
        outcome = AgentOutcome(mode="fallback")
        runner = AgentRunner(self._llm)
        outputs: dict[str, dict[str, Any] | None] = {}
        for name, args in PLAN_HEAD:
            outputs[name] = runner._run_planned(outcome, name, args, run_id)
        topics = policy_topics(outputs)
        if topics:
            runner._run_planned(outcome, "retrieve_hospital_protocol", {"topics": topics, "k": 2}, run_id)
        return outcome

    @staticmethod
    def _unchanged(snapshot: Snapshot, results) -> bool:
        if any(r.data_version is not None and r.data_version != snapshot.data_version for r in results):
            return False
        return simulation.current_state().data_version == snapshot.data_version

    def _abort_if_data_moved(self, snapshot: Snapshot, results) -> None:
        if not self._unchanged(snapshot, results):
            raise DataChangedDuringComparison(
                "The simulation data changed while the shared context was being prepared. "
                "No model was called; run the comparison again."
            )

    @staticmethod
    def _shared_messages(question: str, results) -> list[ChatMessage]:
        body = "\n\n".join(_render_for_fallback(r) for r in results)
        user = f"Question: {question}\n\nVerified tool results (fetched just now from the live simulation):\n\n{body}"
        return [ChatMessage(role="system", content=prompts.FALLBACK_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user)]

    @staticmethod
    def _not_configured_row(position: int, s: cc.ModelSelection, message: str) -> dict[str, Any]:
        return dict(position=position, provider=s.provider, model=s.model, temperature=s.temperature,
                    status="not_configured", error=message, scores={}, citation_check={})

    def _ask_model(self, position, s: cc.ModelSelection, messages, snapshot: Snapshot, retrieved) -> dict[str, Any]:
        request = ChatRequest(provider=s.provider, model=s.model, messages=messages, temperature=s.temperature)
        base: dict[str, Any] = dict(position=position, provider=s.provider, model=s.model, temperature=s.temperature,
                                    tool_calling_supported=self._llm.supports_tools(s.provider, s.model),
                                    context_sha256=_sha256(request.messages))
        started = time.perf_counter()
        try:
            resp = self._llm.complete(request)
        except Exception as exc:  # noqa: BLE001 - one model failing must not fail the comparison
            log.info("Comparison model %s/%s failed: %s", s.provider, s.model, type(exc).__name__)
            return {**base, "status": "failed", "error": _safe_error(exc), "scores": {}, "citation_check": {},
                    "latency_ms": int((time.perf_counter() - started) * 1000)}
        latency_ms = int((time.perf_counter() - started) * 1000)  # same wall-clock measure for every model

        answer = (resp.content or "").strip()
        if not answer:
            return {**base, "status": "failed", "error": "The model returned an empty answer.", "scores": {},
                    "citation_check": {}, "latency_ms": latency_ms, "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens, "total_tokens": resp.usage.total_tokens,
                    "estimated_cost_usd": resp.estimated_cost_usd, "data_disclosure": resp.data_disclosure}
        scores = score_answer(ScoreInputs(answer=answer, metrics=snapshot.metrics, retrieved=retrieved,
                                          scenario_name=snapshot.scenario_name, data_version=snapshot.data_version))
        return {**base, "status": "completed", "answer": answer, "latency_ms": latency_ms,
                "prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens, "estimated_cost_usd": resp.estimated_cost_usd,
                "tool_calling_supported": base["tool_calling_supported"]
                if base["tool_calling_supported"] is not None else resp.tool_calling_supported,
                "data_disclosure": resp.data_disclosure, "scores": scores,
                "citation_check": scores["citation_correctness"]["check"]}

    @staticmethod
    def _audit(actor: str, response: cc.ComparisonRunResponse) -> None:
        try:
            get_event_bus().publish(AuditEvent(
                actor=actor, action="comparison.run", outcome="failure" if response.status == "failed" else "success",
                resource=str(response.id),
                detail={"data_version": response.shared_context.data_version, "status": response.status,
                        "models": [f"{r.provider}/{r.model}" for r in response.results],
                        "data_version_consistent": response.data_version_consistent},
            ))
        except Exception as exc:  # noqa: BLE001 - auditing must never break the request
            log.warning("Audit publish failed: %s", type(exc).__name__)


# ------------------------------------------------------------------ history
def list_comparisons(limit: int = 20, offset: int = 0, data_version: int | None = None) -> cc.ComparisonPage:
    with unit_of_work() as session:
        entries, total = ComparisonRepository(session).list(limit=limit, offset=offset, data_version=data_version)
        items = [
            cc.ComparisonSummary(
                id=r.id, question=r.question, status=r.status, scenario_name=r.scenario_name,
                data_version=r.data_version, data_version_consistent=r.data_version_consistent, models=models,
                created_at=r.created_at,
            )
            for r, models in entries
        ]
    return cc.ComparisonPage(items=items, total=total, limit=limit, offset=offset)


def get_comparison(comparison_id: uuid.UUID) -> cc.ComparisonRunResponse:
    with unit_of_work() as session:
        found = ComparisonRepository(session).get(comparison_id)
        if found is None:
            raise NotFoundError("Comparison run not found")
        return _to_response(*found)
