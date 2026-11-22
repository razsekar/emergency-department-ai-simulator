"""Request size limit, error-response hygiene, and CORS restrictions, on the real application factory."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.platform.config import Settings, get_settings
from app.platform.errors import install_error_handlers


@pytest.fixture()
def real_app(monkeypatch):
    def build(**env: str) -> TestClient:
        monkeypatch.setenv("JWT_SECRET", "test-secret-" + "x" * 40)  # auth must be configured to reach 401s
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        return TestClient(create_app(), raise_server_exceptions=False)

    yield build
    monkeypatch.undo()
    get_settings.cache_clear()


# --- request body size ------------------------------------------------------------------------------

def test_oversized_body_is_rejected_with_413_before_authentication_or_parsing(real_app):
    client = real_app(MAX_REQUEST_BODY_MB="1")
    r = client.post("/api/knowledge/documents", files={"file": ("big.pdf", b"%PDF" + b"0" * (2 * 1024 * 1024))})
    assert r.status_code == 413
    assert r.json() == {"error": {"code": "payload_too_large", "message": "Request body is too large."}}


def test_body_within_the_limit_reaches_the_endpoint(real_app):
    client = real_app(MAX_REQUEST_BODY_MB="1")
    r = client.post("/api/knowledge/documents", files={"file": ("ok.pdf", b"%PDF-1.4 small")})
    assert r.status_code == 401  # got past the size check and was stopped by authentication


def test_malformed_content_length_is_rejected(real_app):
    client = real_app()
    r = client.post("/api/auth/login", content=b"{}", headers={"content-length": "not-a-number",
                                                               "content-type": "application/json"})
    assert r.status_code in (400, 413)


def test_default_request_cap_leaves_room_above_the_upload_limit():
    s = Settings()
    assert s.max_request_body_mb >= 11  # KB_MAX_UPLOAD_MB defaults to 10; multipart overhead needs headroom


# --- error responses --------------------------------------------------------------------------------

def test_validation_errors_use_the_standard_shape_and_never_echo_input(real_app):
    client = real_app()
    r = client.post("/api/auth/login", json={"username": ["leaky-value-123"], "password": {"x": "leaky-value-456"}})
    assert r.status_code == 422
    body = r.json()
    assert set(body) == {"error"} and body["error"]["code"] == "validation_error"
    assert "leaky-value" not in r.text
    assert "username" in body["error"]["message"] and "password" in body["error"]["message"]


def test_unknown_route_and_wrong_method_use_the_standard_shape(real_app):
    client = real_app()
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = client.delete("/api/health")
    assert r.status_code == 405 and r.json()["error"]["code"] == "method_not_allowed"


def test_unhandled_exceptions_return_a_generic_500(monkeypatch):
    app = FastAPI()
    install_error_handlers(app)

    def boom():
        raise RuntimeError("could not connect: password=hunter2 host=10.0.0.5")

    app.add_api_route("/boom", boom)
    r = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message": "Internal server error"}}
    assert "hunter2" not in r.text and "10.0.0.5" not in r.text and "Traceback" not in r.text


def test_auth_failures_do_not_reveal_which_part_was_wrong(real_app):
    client = real_app()
    r = client.post("/api/auth/me")
    assert r.status_code in (401, 405)
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401 and r.json()["error"]["message"] == "Invalid or expired token"


# --- CORS ------------------------------------------------------------------------------------------

def _preflight(client, origin):
    return client.options("/api/scenarios", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})


def test_cors_allows_only_the_configured_origin(real_app):
    client = real_app(CORS_ORIGINS='["https://app.example.org"]')
    ok = _preflight(client, "https://app.example.org")
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == "https://app.example.org"
    bad = _preflight(client, "https://evil.example.com")
    assert bad.status_code == 400
    assert "access-control-allow-origin" not in bad.headers


def test_cors_never_uses_a_wildcard_or_credentials_and_limits_methods_and_headers(real_app):
    client = real_app(CORS_ORIGINS='["https://app.example.org"]')
    r = _preflight(client, "https://app.example.org")
    assert r.headers["access-control-allow-origin"] != "*"
    assert "access-control-allow-credentials" not in r.headers
    assert set(r.headers["access-control-allow-methods"].replace(" ", "").split(",")) == {
        "GET", "POST", "PUT", "PATCH", "DELETE"}
    assert "x-custom-anything" not in r.headers["access-control-allow-headers"].lower()
    odd = client.options("/api/scenarios", headers={
        "Origin": "https://app.example.org", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-custom-anything"})
    assert odd.status_code == 400  # headers outside the allow-list are refused


def test_wildcard_cors_origin_is_refused_at_startup():
    with pytest.raises(ValidationError, match="explicit origins"):
        Settings(cors_origins=["*"])
