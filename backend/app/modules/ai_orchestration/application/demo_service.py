"""Demonstration mode: apply a scenario, prove the data changed, ask the FIXED question, save Run N.

Each step is: record version -> apply scenario (simulation's own atomic transaction) -> verify the version and
metrics changed -> run the agent on live data (no caching) -> save the run. A demo run row is written only after
every check passed, so a failing step never leaves a partial saved run.
"""
import logging
import threading
import uuid
from typing import Any

from app.modules.ai_orchestration.application import demo_contracts as d
from app.modules.ai_orchestration.application.service import AgentService
from app.modules.ai_orchestration.application.snapshot import take_snapshot
from app.modules.ai_orchestration.domain import demo_diff
from app.modules.ai_orchestration.domain.prompts import FIXED_DEMO_QUESTION
from app.modules.ai_orchestration.infrastructure.demo_models import DemoRunRow
from app.modules.ai_orchestration.infrastructure.demo_repository import DemoRunRepository
from app.modules.model_providers.public import Usage
from app.modules.simulation import public as simulation
from app.platform.audit_events import AuditEvent
from app.platform.db import unit_of_work
from app.platform.errors import AppError
from app.platform.events import get_event_bus

log = logging.getLogger("app.ai_orchestration.demo")

_STEP_LOCK = threading.Lock()  # one demo step at a time: steps change the shared dataset


class DemoVerificationError(AppError):
    status_code = 409
    code = "demo_verification_failed"


def _view(row: DemoRunRow) -> d.DemoRunView:
    return d.DemoRunView(
        id=row.id, session_id=row.session_id, run_number=row.run_number, run_label=row.run_label,
        analysis_run_id=row.analysis_run_id, scenario_key=row.scenario_key, scenario_name=row.scenario_name,
        data_version=row.data_version, patient_record_count=row.patient_record_count, metrics=row.metrics_snapshot,
        verification=d.StepVerification(**row.verification) if row.verification else None,
        tools_executed=row.tools_executed, retrieved_policies=row.retrieved_policies, question=row.question,
        question_sha256=row.question_sha256, final_answer=row.final_answer, provider=row.provider, model=row.model,
        latency_ms=row.latency_ms,
        usage=Usage(prompt_tokens=row.prompt_tokens, completion_tokens=row.completion_tokens,
                    total_tokens=row.total_tokens),
        estimated_cost_usd=row.estimated_cost_usd, created_by=row.created_by, created_at=row.created_at,
    )


def _comparison(views: list[d.DemoRunView]) -> list[d.MetricComparisonRow]:
    return [d.MetricComparisonRow(**r) for r in demo_diff.metric_comparison([v.metrics for v in views])]


class DemoService:
    def __init__(self, agent: AgentService) -> None:
        self._agent = agent

    # ------------------------------------------------------------------ step
    def step(self, req: d.DemoStepRequest, actor: str = "system") -> d.DemoStepResponse:
        with _STEP_LOCK:
            return self._step(req, actor)

    def _step(self, req: d.DemoStepRequest, actor: str) -> d.DemoStepResponse:
        # fail fast on provider configuration BEFORE touching the data
        self._agent._llm.ensure_configured(req.provider, req.model)  # noqa: SLF001 - same module

        with unit_of_work() as session:
            previous = DemoRunRepository(session).latest()
            previous_metrics = dict(previous.metrics_snapshot) if previous else None
        before_state = simulation.current_state()
        before_metrics = take_snapshot().metrics

        try:
            applied = simulation.apply_scenario(req.scenario)  # atomic in simulation's own transaction
        except Exception as exc:
            self._audit(actor, "demo.step", "failure", {"scenario": req.scenario, "stage": "apply",
                                                         "error": type(exc).__name__})
            raise
        after_version = applied.state.data_version
        if after_version <= before_state.data_version:
            self._audit(actor, "demo.step", "failure", {"scenario": req.scenario, "stage": "verify_version"})
            raise DemoVerificationError(
                f"Data version did not change ({before_state.data_version} -> {after_version}); "
                "the question was not asked."
            )
        after_metrics = take_snapshot().metrics
        compare_to, baseline = ("previous_run", previous_metrics) if previous_metrics is not None \
            else ("state_before_step", before_metrics)
        changes = demo_diff.changed_metrics(baseline, after_metrics)

        # ask the fixed question on live data (the agent takes its own fresh snapshot; nothing is reused)
        try:
            run = self._agent.demo_run(provider=req.provider, model=req.model, temperature=req.temperature,
                                       mode=req.mode, actor=actor)
        except Exception as exc:
            self._audit(actor, "demo.step", "failure", {"scenario": req.scenario, "stage": "agent",
                                                         "error": type(exc).__name__})
            raise

        question_identical = run.question == FIXED_DEMO_QUESTION
        matches = run.data_version == after_version
        if not question_identical or not matches:
            self._audit(actor, "demo.step", "failure", {"scenario": req.scenario, "stage": "verify_run"})
            raise DemoVerificationError(
                "Run rejected: the agent did not use the fixed question on the data version this step produced."
            )
        note = None if changes else (
            "Metrics are identical to the compared state (the scenario was already loaded); "
            "the data version still advanced."
        )
        verification = d.StepVerification(
            data_version_before=before_state.data_version, data_version_after=after_version,
            data_version_changed=True, compared_to=compare_to, metrics_changed=bool(changes),
            changed_metrics=[d.MetricChange(**c) for c in changes], question_identical=True,
            analysis_data_version_matches=True, note=note,
        )

        with unit_of_work() as session:
            repo = DemoRunRepository(session)
            session_id = repo.current_session_id() or uuid.uuid4()
            number = len(repo.runs(session_id)) + 1
            row = repo.add(
                session_id=session_id, run_number=number, run_label=f"Run {number}", analysis_run_id=run.id,
                scenario_key=run.scenario_key, scenario_name=run.scenario_name, data_version=run.data_version,
                patient_record_count=int(run.snapshot_metrics.get("total_visits", 0)),
                metrics_snapshot=run.snapshot_metrics, verification=verification.model_dump(mode="json"),
                tools_executed=[t.model_dump(mode="json") for t in run.tools_executed],
                retrieved_policies=[p.model_dump(mode="json") for p in run.retrieved_policies],
                question=run.question, question_sha256=demo_diff.question_sha256(run.question),
                final_answer=run.answer, provider=run.provider, model=run.model, latency_ms=run.latency_ms,
                prompt_tokens=run.usage.prompt_tokens, completion_tokens=run.usage.completion_tokens,
                total_tokens=run.usage.total_tokens, estimated_cost_usd=run.estimated_cost_usd, created_by=actor,
            )
            view = _view(row)
            views = [_view(r) for r in repo.runs(session_id)]

        self._audit(actor, "demo.step", "success", {
            "scenario": req.scenario, "run": view.run_label, "data_version": view.data_version,
            "provider": req.provider, "model": req.model})
        return d.DemoStepResponse(run=view, run_count=len(views), metric_comparison=_comparison(views))

    # ------------------------------------------------------------------ session
    def session(self) -> d.DemoSessionView:
        with unit_of_work() as session:
            repo = DemoRunRepository(session)
            sid = repo.current_session_id()
            views = [_view(r) for r in repo.runs(sid)] if sid else []
        return d.DemoSessionView(
            session_id=sid, question=FIXED_DEMO_QUESTION, question_sha256=demo_diff.question_sha256(FIXED_DEMO_QUESTION),
            run_count=len(views), runs=views, metric_comparison=_comparison(views),
        )

    def reset(self, actor: str = "system") -> d.DemoResetResponse:
        with _STEP_LOCK:
            applied = simulation.reset_database()  # baseline reload, atomic in simulation's own transaction
            with unit_of_work() as session:
                cleared = DemoRunRepository(session).clear()
        self._audit(actor, "demo.reset", "success", {"cleared_runs": cleared,
                                                     "data_version": applied.state.data_version})
        return d.DemoResetResponse(cleared_runs=cleared, baseline_scenario=applied.state.scenario_name or "",
                                   data_version=applied.state.data_version)

    @staticmethod
    def _audit(actor: str, action: str, outcome: str, detail: dict[str, Any]) -> None:
        try:
            get_event_bus().publish(AuditEvent(actor=actor, action=action, outcome=outcome, resource="demo",
                                               detail=detail))
        except Exception as exc:  # noqa: BLE001 - auditing must never break the request
            log.warning("Audit publish failed: %s", type(exc).__name__)
