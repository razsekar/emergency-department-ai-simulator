"""End-to-end fixtures: the REAL `app.main` app over HTTP, a real login, ALL migration heads, one isolated DB.

Only two things are faked: the LLM (a scripted fake injected through FastAPI dependency overrides, no network, no
paid calls) and policy vector search (a fake over `handlers.rag.search`, so these tests do not depend on the embedding
model; real vector retrieval is covered in tests/gaps).
"""
import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.platform import config, db
from tests.agentdb import AGENT_TABLES, make_fake_search, policy_chunk
from tests.simdb import TABLES

ADMIN_PASSWORD = "e2e-admin-password-1"
PRESENTER_PASSWORD = "e2e-presenter-password-1"
VIEWER_PASSWORD = "e2e-viewer-password-1"
JWT_SECRET = "e2e-jwt-secret-0123456789-abcdefghijklmnopqrstuvwxyz"

EXTRA_TABLES = "ai_orchestration.demo_runs, ai_orchestration.ai_comparison_runs, audit.audit_events"


def _clear_caches() -> None:
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db._session_factory.cache_clear()


@pytest.fixture(scope="module")
def e2e_db():
    """Isolated per-pid database with ALL alembic heads applied, demo users seeded through the identity seed."""
    base = make_url(os.environ["DATABASE_URL"])
    name = f"edsim_e2e_{os.getpid()}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {name}"))
    url = base.set(database=name).render_as_string(hide_password=False)

    mp = pytest.MonkeyPatch()
    mp.setenv("ALEMBIC_DATABASE_URL", url)
    mp.setenv("DATABASE_URL", url)
    mp.setenv("JWT_SECRET", JWT_SECRET)
    mp.setenv("DEMO_ADMIN_PASSWORD", ADMIN_PASSWORD)
    mp.setenv("DEMO_PRESENTER_PASSWORD", PRESENTER_PASSWORD)
    mp.setenv("DEMO_VIEWER_PASSWORD", VIEWER_PASSWORD)
    # The scripted flows make many agent calls in a few seconds; rate limiting has its own tests elsewhere.
    mp.setenv("RATE_LIMIT_ENABLED", "false")
    _clear_caches()
    try:
        command.upgrade(Config("alembic.ini"), "heads")
        from app.modules.identity.application.seed import seed_demo_users

        with db.unit_of_work() as s:
            statuses = seed_demo_users(s)
        assert set(statuses.values()) == {"created"}, statuses
        yield url
    finally:
        mp.undo()
        _clear_caches()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()


@pytest.fixture()
def clean_e2e(e2e_db):
    """Empty simulation/agent/demo/comparison/audit data and data_version = 0 before each test (users are kept)."""
    with create_engine(e2e_db).begin() as c:
        c.execute(text(f"TRUNCATE {TABLES}, {AGENT_TABLES}, {EXTRA_TABLES} CASCADE"))
        c.execute(text("UPDATE simulation.data_state SET data_version=0, scenario_key=NULL, "
                       "scenario_name=NULL, last_run_id=NULL, applied_at=NULL"))
    yield e2e_db


class LlmHolder:
    """Lets a test choose the scripted LLM per request while the app's dependency overrides stay installed."""

    def __init__(self) -> None:
        self.llm = None

    def use(self, llm):
        self.llm = llm
        return llm


@pytest.fixture()
def llm_holder():
    return LlmHolder()


@pytest.fixture()
def client(clean_e2e, llm_holder, monkeypatch):
    """TestClient over the real application with the LLM-facing dependencies overridden."""
    from app.main import app
    from app.modules.agent_tools.application import handlers
    from app.modules.ai_orchestration.application.comparison_service import ComparisonService
    from app.modules.ai_orchestration.application.comparison_wiring import get_comparison_service
    from app.modules.ai_orchestration.application.demo_service import DemoService
    from app.modules.ai_orchestration.application.demo_wiring import get_demo_service
    from app.modules.ai_orchestration.application.service import AgentService
    from app.modules.ai_orchestration.application.wiring import get_agent_service

    monkeypatch.setattr(handlers.rag, "search", make_fake_search([
        policy_chunk(), policy_chunk(document="Resource Management Guidelines", page=1, score=0.6)]))
    app.dependency_overrides[get_agent_service] = lambda: AgentService(llm_holder.llm)
    app.dependency_overrides[get_demo_service] = lambda: DemoService(AgentService(llm_holder.llm))
    app.dependency_overrides[get_comparison_service] = lambda: ComparisonService(llm_holder.llm)
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        for dep in (get_agent_service, get_demo_service, get_comparison_service):
            app.dependency_overrides.pop(dep, None)


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return login(client, "demo_admin", ADMIN_PASSWORD)
