"""Fixtures for the gap tests: reuse the e2e environment (real app, real login, all migration heads, isolated DB)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from tests.e2e.conftest import (  # noqa: F401  (fixtures re-exported for this package)
    ADMIN_PASSWORD,
    PRESENTER_PASSWORD,
    VIEWER_PASSWORD,
    admin,
    clean_e2e,
    client,
    e2e_db,
    llm_holder,
    login,
)


@pytest.fixture()
def real_rag_client(clean_e2e, llm_holder):
    """The real app with the REAL embedding model and vector search (only the LLM is a scripted fake)."""
    from app.main import app
    from app.modules.ai_orchestration.application.demo_service import DemoService
    from app.modules.ai_orchestration.application.demo_wiring import get_demo_service
    from app.modules.ai_orchestration.application.service import AgentService
    from app.modules.ai_orchestration.application.wiring import get_agent_service

    from app.modules.rag import public as rag

    assert rag.search.__module__.startswith("app.modules.rag"), "policy search must be the REAL implementation here"
    app.dependency_overrides[get_agent_service] = lambda: AgentService(llm_holder.llm)
    app.dependency_overrides[get_demo_service] = lambda: DemoService(AgentService(llm_holder.llm))
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_agent_service, None)
        app.dependency_overrides.pop(get_demo_service, None)


@pytest.fixture()
def engine(e2e_db):
    eng = create_engine(e2e_db)
    yield eng
    eng.dispose()
