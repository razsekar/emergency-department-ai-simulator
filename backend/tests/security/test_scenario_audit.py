"""Audit events for scenario changes and denied access, and safe failure recording."""
import pytest

from app.modules.simulation.application import service as sim_service
from app.modules.simulation.domain.errors import ScenarioValidationError
from app.platform.audit_events import AuditEvent
from app.platform.events import get_event_bus
from tests.simdb import module_client


@pytest.fixture()
def events(clean_state):
    """Collect every AuditEvent published during a test (the bus has no unsubscribe, so remove by hand)."""
    got: list[AuditEvent] = []
    handlers = get_event_bus()._handlers[AuditEvent]
    handlers.append(got.append)
    yield got
    handlers.remove(got.append)


def _by_action(events, action):
    return [e for e in events if e.action == action]


def test_apply_publishes_success_event_with_actor_and_data_version(events):
    r = module_client("presenter").post("/api/scenarios/apply", json={"scenario_key": "surge"})
    assert r.status_code == 200
    (event,) = _by_action(events, "scenario.apply")
    assert event.actor == "test_presenter" and event.outcome == "success"
    assert event.resource == "scenario:surge"
    assert event.detail["data_version"] == r.json()["state"]["data_version"] == 1
    assert event.detail["record_count"] == r.json()["run"]["record_count"] > 0


def test_reset_and_randomize_each_publish_exactly_one_event(events):
    client = module_client("admin")
    assert client.post("/api/scenarios/reset").status_code == 200
    assert client.post("/api/scenarios/randomize").status_code == 200
    assert [e.action for e in events if e.action.startswith("scenario.")] == ["scenario.reset", "scenario.randomize"]
    assert all(e.actor == "test_admin" and e.outcome == "success" for e in events if e.action.startswith("scenario."))


def test_randomize_retries_do_not_produce_one_event_per_attempt(events, monkeypatch):
    """Internal retries are an implementation detail: only the final outcome is audited."""
    real = sim_service._execute
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ScenarioValidationError("generated data did not match")
        return real(*args, **kwargs)

    monkeypatch.setattr(sim_service, "_execute", flaky)
    assert module_client("presenter").post("/api/scenarios/randomize").status_code == 200
    assert calls["n"] == 3
    assert len(_by_action(events, "scenario.randomize")) == 1


def test_randomize_that_never_succeeds_audits_one_failure(events, monkeypatch):
    def always_bad(*args, **kwargs):
        raise ScenarioValidationError("generated data did not match")

    monkeypatch.setattr(sim_service, "_execute", always_bad)
    assert module_client("presenter").post("/api/scenarios/randomize").status_code == 422
    (event,) = _by_action(events, "scenario.randomize")
    assert event.outcome == "failure"


def test_denied_apply_is_audited_and_changes_nothing(events):
    r = module_client("viewer").post("/api/scenarios/apply", json={"scenario_key": "surge"})
    assert r.status_code == 403
    (denied,) = _by_action(events, "authz.denied")
    assert denied.actor == "test_viewer" and denied.outcome == "denied"
    assert denied.detail["missing_permissions"] == ["scenario:apply"]
    assert not _by_action(events, "scenario.apply")
    assert module_client("viewer").get("/api/scenarios/current").json()["data_version"] == 0


def test_unexpected_failure_is_audited_and_internal_detail_is_not_stored_or_returned(events, monkeypatch):
    secret = "password=hunter2 SELECT * FROM identity.users"

    def boom(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(sim_service, "apply_params", boom)
    client = module_client("presenter", raise_server_exceptions=False)
    r = client.post("/api/scenarios/apply", json={"scenario_key": "surge"})
    assert r.status_code == 500 and secret not in r.text
    assert r.json()["error"]["message"] == "Internal server error"

    (event,) = _by_action(events, "scenario.apply")
    assert event.outcome == "failure" and event.detail["error_type"] == "RuntimeError"
    assert secret not in repr(event)

    history = client.get("/api/scenarios/history").json()
    failed = [x for x in history["items"] if x["status"] == "failed"]
    assert len(failed) == 1
    assert "hunter2" not in str(history) and "SELECT" not in str(history)
    assert failed[0]["error"] == "Unexpected internal error (see server logs)"


def test_domain_validation_errors_stay_visible_in_history(clean_state, monkeypatch):
    """Our own domain errors are safe and useful, so they are still recorded verbatim."""

    def bad(*args, **kwargs):
        raise ScenarioValidationError("beds_available must not exceed total beds")

    monkeypatch.setattr(sim_service, "apply_params", bad)
    client = module_client("presenter")
    assert client.post("/api/scenarios/apply", json={"scenario_key": "surge"}).status_code == 422
    failed = [x for x in client.get("/api/scenarios/history").json()["items"] if x["status"] == "failed"]
    assert failed[0]["error"] == "beds_available must not exceed total beds"


def test_internal_callers_without_actor_publish_no_scenario_event(events):
    """Demo mode applies scenarios through the public interface and audits the step itself."""
    sim_service.apply_scenario("normal")
    assert not [e for e in events if e.action.startswith("scenario.")]
