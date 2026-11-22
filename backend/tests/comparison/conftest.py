"""Comparison tests: agent fixtures plus the `comparison` migration branch and its own table cleanup."""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from tests.agentdb import *  # noqa: F401,F403
from tests.agentdb import agent_schema, agent_state  # noqa: F401


@pytest.fixture(scope="session")
def comparison_schema(agent_schema):  # noqa: F811
    command.upgrade(Config("alembic.ini"), "comparison@head")
    yield


@pytest.fixture()
def comparison_state(comparison_schema, agent_state):  # noqa: F811
    with create_engine(agent_state).begin() as c:
        c.execute(text("TRUNCATE ai_orchestration.ai_comparison_runs CASCADE"))
    yield agent_state
