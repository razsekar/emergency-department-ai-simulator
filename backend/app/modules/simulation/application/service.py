"""Scenario use cases. Applying a scenario is ONE transaction:

validate params -> (tx) generate -> owning modules replace their datasets via public interfaces
-> validate what was persisted -> bump data_version -> persist run history -> commit.
Any failure rolls everything back; a failed-run record is then written in a separate transaction.
"""
import logging
import secrets
import random
import time
import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.modules.patient_queue import public as queue
from app.modules.resource_management import public as resources
from app.modules.simulation.application import schemas as s
from app.modules.simulation.application.generator import generate
from app.modules.simulation.domain.builtin import BUILTIN, CUSTOM_DESCRIPTION, CUSTOM_KEY, CUSTOM_NAME
from app.modules.simulation.domain.errors import ScenarioNotFoundError, ScenarioValidationError
from app.modules.simulation.domain.params import ScenarioParams
from app.modules.simulation.domain.validation import ObservedState, validate_observed
from app.modules.simulation.infrastructure import repository as repo
from app.platform.audit_events import AuditEvent
from app.platform.db import unit_of_work
from app.platform.errors import AppError
from app.platform.events import get_event_bus

log = logging.getLogger("app.simulation")
MAX_RANDOMIZE_ATTEMPTS = 5


# ---------------------------------------------------------------- reads
def get_data_state(session: Session) -> s.DataState:
    r = repo.get_state(session)
    return s.DataState(
        data_version=r.data_version, scenario_key=r.scenario_key, scenario_name=r.scenario_name,
        applied_at=r.applied_at, last_run_id=r.last_run_id,
    )


def current_state() -> s.DataState:
    with unit_of_work() as session:
        return get_data_state(session)


def list_scenarios() -> list[s.ScenarioInfo]:
    current = current_state().scenario_key
    return [
        s.ScenarioInfo(key=b.key, name=b.name, description=b.description, is_builtin=True,
                       is_current=current == b.key, parameters=b.params)
        for b in BUILTIN.values()
    ]


def _run_info(r) -> s.ScenarioRunInfo:
    return s.ScenarioRunInfo(
        id=r.id, scenario_key=r.scenario_key, scenario_name=r.scenario_name, trigger=r.trigger, status=r.status,
        data_version=r.data_version, parameters=r.parameters, validation=r.validation, error=r.error,
        record_count=r.record_count, duration_ms=r.duration_ms, created_at=r.created_at,
    )


def get_history(limit: int = 50, offset: int = 0) -> s.RunPage:
    with unit_of_work() as session:
        total, rows = repo.list_runs(session, limit, offset)
        return s.RunPage(items=[_run_info(r) for r in rows], total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------- apply
def _observe(session: Session) -> ObservedState:
    beds = resources.get_bed_availability(session)
    staff = resources.get_staff_availability(session)
    waiting = queue.get_waiting_metrics(session)
    pending = queue.get_pending_investigations(session, limit=1)
    counts = queue.get_visit_counts(session)
    on_duty = {t.role: t.on_duty for t in staff.totals_by_role}
    return ObservedState(
        beds_available=beds.available_beds, beds_occupied=beds.occupied_beds,
        doctors_on_duty=on_duty.get("doctor", 0), nurses_on_duty=on_duty.get("nurse", 0),
        waiting_patients=waiting.waiting_patients, avg_wait_minutes=waiting.avg_wait_minutes,
        pending_investigations=pending.pending_count, avg_pending_age_minutes=pending.avg_age_minutes,
        total_visits=counts.total_visits,
    )


def apply_params(
    session: Session, key: str, name: str, params: ScenarioParams, trigger: str,
    reference_time: datetime | None = None,
) -> s.ApplyResponse:
    """Core of the atomic apply; runs inside the caller's transaction."""
    started = time.perf_counter()
    ref = (reference_time or datetime.now(timezone.utc)).replace(microsecond=0)

    for b in BUILTIN.values():
        repo.ensure_scenario(session, b.key, b.name, b.description, True, b.params.model_dump())
    scenario_id = repo.ensure_scenario(
        session, key, name if key != CUSTOM_KEY else CUSTOM_NAME,
        BUILTIN[key].description if key in BUILTIN else CUSTOM_DESCRIPTION, key in BUILTIN, None,
    )

    resource_spec, queue_spec = generate(params, ref)
    resources.replace_dataset(session, resource_spec)
    queue.replace_dataset(session, queue_spec)
    observed = _observe(session)
    checks = validate_observed(params, observed)  # raises -> whole transaction rolls back

    run_id = uuid.uuid4()
    version = repo.bump_version(session, key, name, run_id, ref)
    repo.insert_run(
        session, id=run_id, scenario_id=scenario_id, scenario_key=key, scenario_name=name, trigger=trigger,
        status="applied", data_version=version, parameters=params.model_dump(), validation=checks,
        record_count=observed.total_visits, duration_ms=int((time.perf_counter() - started) * 1000),
    )
    state = get_data_state(session)
    return s.ApplyResponse(state=state, run=_run_info(repo.get_run(session, run_id)))


def _record_failure(key: str, name: str, params: ScenarioParams | dict, trigger: str, exc: Exception) -> None:
    """Best-effort audit of a failed attempt, in its own transaction (the apply tx was rolled back)."""
    try:
        with unit_of_work() as session:
            repo.insert_run(
                session, scenario_key=key, scenario_name=name, trigger=trigger, status="failed",
                parameters=params.model_dump() if isinstance(params, ScenarioParams) else params,
                # Only our own domain errors are safe to show in history; anything else (e.g. a database
                # driver error) may contain SQL or connection details and stays in the server log.
                error=str(exc)[:500] if isinstance(exc, AppError) else "Unexpected internal error (see server logs)",
                record_count=0, duration_ms=0,
            )
    except Exception:  # noqa: BLE001 - never mask the original error
        log.exception("could not record failed scenario run")


def _audit(actor: str | None, trigger: str, key: str, outcome: str, detail: dict) -> None:
    """Publish after the transaction has ended. No actor (internal caller such as demo mode) = no event;
    those callers publish their own audit record."""
    if actor:
        get_event_bus().publish(AuditEvent(actor=actor, action=f"scenario.{trigger}", outcome=outcome,
                                           resource=f"scenario:{key}", detail=detail))


def _execute(key: str, name: str, params: ScenarioParams, trigger: str,
             reference_time: datetime | None = None, actor: str | None = None) -> s.ApplyResponse:
    try:
        with unit_of_work() as session:
            result = apply_params(session, key, name, params, trigger, reference_time)
    except Exception as exc:
        _record_failure(key, name, params, trigger, exc)
        _audit(actor, trigger, key, "failure", {"scenario": name, "error_type": type(exc).__name__})
        raise
    _audit(actor, trigger, key, "success", {"scenario": name, "data_version": result.state.data_version,
                                            "record_count": result.run.record_count})
    return result


def resolve_params(key: str, overrides: s.ScenarioOverrides | None) -> tuple[str, str, ScenarioParams]:
    if key != CUSTOM_KEY and key not in BUILTIN:
        raise ScenarioNotFoundError(f"Unknown scenario '{key}'")
    base = BUILTIN[key if key in BUILTIN else "normal"]
    changes = overrides.model_dump(exclude_unset=True, exclude_none=True) if overrides else {}
    if not changes and key != CUSTOM_KEY:
        return base.key, base.name, base.params
    try:
        params = ScenarioParams.model_validate({**base.params.model_dump(), **changes})
    except ValidationError as exc:
        msg = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ScenarioValidationError(f"Invalid scenario parameters ({msg})") from exc
    label = CUSTOM_NAME if key == CUSTOM_KEY else f"Custom (based on {base.name})"
    return CUSTOM_KEY, label, params


def apply_scenario(
    key: str, overrides: s.ScenarioOverrides | None = None, trigger: str = "apply",
    reference_time: datetime | None = None, actor: str | None = None,
) -> s.ApplyResponse:
    skey, name, params = resolve_params(key, overrides)
    return _execute(skey, name, params, "manual" if skey == CUSTOM_KEY and trigger == "apply" else trigger,
                    reference_time, actor)


def reset_database(reference_time: datetime | None = None, actor: str | None = None) -> s.ApplyResponse:
    """Reset = replace all synthetic data with the baseline scenario (data_version still increases)."""
    b = BUILTIN["normal"]
    return _execute(b.key, b.name, b.params, "reset", reference_time, actor)


def random_params(rng: random.Random) -> ScenarioParams:
    waiting = rng.randint(3, 45)
    occupied = rng.randint(4, 18)
    return ScenarioParams(
        seed=rng.randrange(2**31), arrival_rate_per_hour=rng.randint(5, 30),
        beds_available=rng.randint(0, 12), beds_occupied=occupied, doctors_on_duty=rng.randint(2, 9),
        nurses_on_duty=rng.randint(3, 14), waiting_patients=waiting, avg_wait_minutes=rng.randint(8, 90),
        pending_investigations=rng.randint(0, min(30, waiting + occupied)),
        investigation_delay_minutes=rng.randint(10, 75), window_minutes=240,
    )


def randomize_scenario(seed: int | None = None, actor: str | None = None) -> s.ApplyResponse:
    rng = random.Random(seed if seed is not None else secrets.randbits(31))
    last: Exception | None = None
    for _ in range(MAX_RANDOMIZE_ATTEMPTS):
        try:
            result = _execute(CUSTOM_KEY, "Randomized Scenario", random_params(rng), "randomize")
        except ScenarioValidationError as exc:
            last = exc
            continue
        # Audit the final outcome once, not once per internal retry.
        _audit(actor, "randomize", CUSTOM_KEY, "success",
               {"scenario": "Randomized Scenario", "data_version": result.state.data_version,
                "record_count": result.run.record_count})
        return result
    _audit(actor, "randomize", CUSTOM_KEY, "failure", {"scenario": "Randomized Scenario",
                                                       "error_type": "ScenarioValidationError"})
    raise ScenarioValidationError(f"Could not generate a valid random scenario: {last}")
