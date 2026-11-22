"""Shared fixtures for simulation-data tests: an isolated, migrated database per pytest process.

Import the fixtures into a module's conftest:  from tests.simdb import *  # noqa
"""
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.platform import config, db

TABLES = (
    "simulation.scenario_runs, simulation.scenario_parameters, simulation.scenarios, "
    "patient_queue.investigation_requests, patient_queue.patient_visits, patient_queue.dataset_clock, "
    "resource_management.beds, resource_management.staff, resource_management.investigation_facilities, "
    "resource_management.departments"
)


def _clear_caches() -> None:
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db._session_factory.cache_clear()


@pytest.fixture(scope="session")
def sim_db_url():
    base = make_url(os.environ["DATABASE_URL"])
    name = f"edsim_sim_{os.getpid()}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {name}"))
    url = base.set(database=name).render_as_string(hide_password=False)
    previous = os.environ.get("ALEMBIC_DATABASE_URL")
    os.environ["ALEMBIC_DATABASE_URL"] = url
    try:
        command.upgrade(Config("alembic.ini"), "sim@head")
        yield url
    finally:
        if previous is None:
            os.environ.pop("ALEMBIC_DATABASE_URL", None)
        else:
            os.environ["ALEMBIC_DATABASE_URL"] = previous
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()


@pytest.fixture(scope="module")
def sim_env(sim_db_url):
    """Point the application's engine at the isolated database for the duration of a module."""
    original = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = sim_db_url
    _clear_caches()
    yield sim_db_url
    os.environ["DATABASE_URL"] = original
    _clear_caches()


@pytest.fixture()
def clean_state(sim_env):
    """Empty datasets and reset data_version to 0 before each test."""
    with create_engine(sim_env).begin() as c:
        c.execute(text(f"TRUNCATE {TABLES} CASCADE"))
        c.execute(text("UPDATE simulation.data_state SET data_version=0, scenario_key=NULL, "
                       "scenario_name=NULL, last_run_id=NULL, applied_at=NULL"))
    yield sim_env


@pytest.fixture()
def session(clean_state):
    with db.unit_of_work() as s:
        yield s


def user_for_role(role: str):
    """A CurrentUser with exactly the permissions the role has in the reference matrix."""
    from uuid import uuid4

    from app.modules.identity.public import ROLE_PERMISSIONS, CurrentUser

    return CurrentUser(id=uuid4(), username=f"test_{role}", display_name=role, roles=(role,),
                       permissions=frozenset(str(p) for p in ROLE_PERMISSIONS[role]))


def module_client(role: str | None = "admin", raise_server_exceptions: bool = True):
    """TestClient over an app containing only the simulation-data module routers (no other modules needed).

    `role` injects a signed-in user with that role's permissions (RBAC is still enforced, which is the
    point); `role=None` sends requests anonymously so the 401 behaviour can be tested.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.modules.analytics.api.router import router as analytics_router
    from app.modules.identity.public import get_current_user
    from app.modules.patient_queue.api.router import router as queue_router
    from app.modules.resource_management.api.router import router as resources_router
    from app.modules.simulation.api.router import router as simulation_router
    from app.platform.errors import install_error_handlers

    api = FastAPI()
    install_error_handlers(api)
    for r in (simulation_router, queue_router, resources_router, analytics_router):
        api.include_router(r)
    if role is not None:
        user = user_for_role(role)
        api.dependency_overrides[get_current_user] = lambda: user
    return TestClient(api, raise_server_exceptions=raise_server_exceptions)
