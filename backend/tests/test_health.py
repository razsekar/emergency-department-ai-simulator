from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_live():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_db_health_reports_pgvector():
    assert client.get("/api/health/db").json() == {"status": "ok", "pgvector": True}


def test_openapi_available():
    assert client.get("/api/openapi.json").status_code == 200
