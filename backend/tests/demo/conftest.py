"""Fixtures for demonstration-mode tests: isolated DB with the sim, agent and demo migration branches."""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.modules.agent_tools.application import handlers
from tests.agentdb import *  # noqa: F401,F403
from tests.agentdb import make_fake_search, policy_chunk


@pytest.fixture(scope="session")
def demo_schema(agent_schema):  # noqa: F811
    command.upgrade(Config("alembic.ini"), "demo@head")
    yield


@pytest.fixture()
def demo_state(agent_state, demo_schema):  # noqa: F811
    """Empty simulation data, agent tables and demo runs before each test."""
    with create_engine(agent_state).begin() as c:
        c.execute(text("TRUNCATE ai_orchestration.demo_runs"))
    yield agent_state


@pytest.fixture(autouse=True)
def fake_policy_search(monkeypatch):
    fake = make_fake_search([policy_chunk(), policy_chunk(document="Resource Management Guidelines", page=1, score=0.6)])
    monkeypatch.setattr(handlers.rag, "search", fake)
    return fake
