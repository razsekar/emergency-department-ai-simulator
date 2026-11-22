"""Server-side RBAC: every endpoint of the simulation-data modules, per role, plus a completeness check
over every route of the real application (the frontend is never the security boundary)."""
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.simdb import module_client

# (method, path, json body, minimum role that may call it)
ENDPOINTS = [
    ("GET", "/api/scenarios", None, "viewer"),
    ("GET", "/api/scenarios/current", None, "viewer"),
    ("GET", "/api/scenarios/history", None, "viewer"),
    ("POST", "/api/scenarios/apply", {"scenario_key": "normal"}, "presenter"),
    ("POST", "/api/scenarios/randomize", None, "presenter"),
    ("POST", "/api/scenarios/reset", None, "presenter"),
    ("GET", "/api/dashboard/metrics", None, "viewer"),
    ("GET", "/api/dashboard/resource-utilization", None, "viewer"),
    ("GET", "/api/patient-queue", None, "viewer"),
    ("GET", "/api/patient-queue/waiting-metrics", None, "viewer"),
    ("GET", "/api/patient-queue/pending-investigations", None, "viewer"),
    ("GET", "/api/resources/beds/availability", None, "viewer"),
    ("GET", "/api/resources/staff/availability", None, "viewer"),
    ("GET", "/api/resources/departments", None, "viewer"),
    ("GET", "/api/resources/facilities", None, "viewer"),
    ("GET", "/api/resources/beds", None, "viewer"),
    ("GET", "/api/resources/staff", None, "viewer"),
]
RANK = {"viewer": 0, "presenter": 1, "admin": 2}
IDS = [f"{m} {p}" for m, p, _, _ in ENDPOINTS]


@pytest.mark.parametrize("method,path,body,_min", ENDPOINTS, ids=IDS)
def test_anonymous_requests_get_401(clean_state, method, path, body, _min):
    r = module_client(role=None).request(method, path, json=body)
    assert r.status_code == 401, r.text
    assert r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize("role", ["viewer", "presenter", "admin"])
@pytest.mark.parametrize("method,path,body,minimum", ENDPOINTS, ids=IDS)
def test_role_matrix(clean_state, role, method, path, body, minimum):
    client = module_client(role=role)
    if RANK[role] < RANK[minimum]:
        r = client.request(method, path, json=body)
        assert r.status_code == 403, f"{role} must not call {method} {path}: {r.status_code} {r.text}"
        assert r.json()["error"]["code"] == "forbidden"
    else:
        r = client.request(method, path, json=body)
        assert r.status_code == 200, f"{role} should call {method} {path}: {r.status_code} {r.text}"


def test_denied_write_does_not_change_data(clean_state):
    """A forbidden apply must leave the data untouched (the dependency runs before the use case)."""
    viewer = module_client(role="viewer")
    assert viewer.post("/api/scenarios/apply", json={"scenario_key": "surge"}).status_code == 403
    state = module_client(role="viewer").get("/api/scenarios/current").json()
    assert state["data_version"] == 0


# --- completeness over the real application -------------------------------------------------------

PUBLIC = {("GET", "/api/health"), ("GET", "/api/health/db"), ("POST", "/api/auth/login")}


def _sample_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda m: str(uuid.uuid4()) if "id" in m.group(0) else "x", path)


def test_every_api_route_except_the_public_ones_requires_authentication():
    from app.main import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    # The OpenAPI document lists every routed operation, however routers were nested or included.
    paths = client.get("/api/openapi.json").json()["paths"]
    unprotected, checked = [], 0
    for path, operations in paths.items():
        for method in (m.upper() for m in operations if m.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}):
            if (method, path) in PUBLIC:
                continue
            checked += 1
            r = client.request(method, _sample_path(path), json={})
            if r.status_code != 401:
                unprotected.append(f"{method} {path} -> {r.status_code}")
    assert checked >= 40, f"expected to inspect the whole API, only saw {checked} routes"
    assert not unprotected, "endpoints reachable without authentication:\n" + "\n".join(unprotected)
