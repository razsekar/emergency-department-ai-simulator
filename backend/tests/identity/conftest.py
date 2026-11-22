"""Fixtures shared by identity and audit tests (imported via tests/audit/conftest.py too)."""
import os
from contextlib import contextmanager

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.modules.audit.api.router import router as audit_router
from app.modules.identity.api.router import router as identity_router
from app.modules.identity.application.seed import seed_demo_users
from app.modules.identity.domain.permissions import Permission
from app.modules.identity.public import require_permission
from app.platform import db as platform_db
from app.platform.errors import install_error_handlers

JWT_SECRET = "test-secret-" + "x" * 40
PASSWORDS = {"demo_admin": "admin-pass-123", "demo_presenter": "presenter-pass-123",
             "demo_viewer": "viewer-pass-123"}


@pytest.fixture(scope="session")
def ident_engine():
    """Isolated database migrated only to revision 0400 (identity + audit branch)."""
    base = make_url(os.environ["DATABASE_URL"])
    name = f"edsim_ident_{os.getpid()}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {name}"))
    url = base.set(database=name).render_as_string(hide_password=False)
    os.environ["ALEMBIC_DATABASE_URL"] = url
    try:
        command.upgrade(Config("alembic.ini"), "0400")
    finally:
        del os.environ["ALEMBIC_DATABASE_URL"]
    engine = create_engine(url)
    yield engine
    engine.dispose()
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    admin.dispose()


@pytest.fixture
def db(ident_engine, monkeypatch):
    """Route platform unit_of_work (used by get_session and audit.record) to the test database."""
    factory = sessionmaker(bind=ident_engine, expire_on_commit=False)

    @contextmanager
    def uow():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(platform_db, "unit_of_work", uow)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", PASSWORDS["demo_admin"])
    monkeypatch.setenv("DEMO_PRESENTER_PASSWORD", PASSWORDS["demo_presenter"])
    monkeypatch.setenv("DEMO_VIEWER_PASSWORD", PASSWORDS["demo_viewer"])
    with ident_engine.begin() as conn:
        conn.execute(text("TRUNCATE identity.user_roles, identity.users, audit.audit_events CASCADE"))
    with uow() as session:
        seed_demo_users(session)
    return uow


@pytest.fixture
def client(db):
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(identity_router)
    app.include_router(audit_router)
    for perm in Permission:
        path = "/_perm/" + perm.value.replace(":", "-")
        app.add_api_route(path, lambda _u=Depends(require_permission(perm)): {"ok": True}, methods=["GET"])
    return TestClient(app, raise_server_exceptions=False)


def login(client: TestClient, username: str, password: str | None = None):
    return client.post("/api/auth/login",
                       json={"username": username, "password": password or PASSWORDS[username]})


def auth_headers(client: TestClient, username: str) -> dict[str, str]:
    token = login(client, username).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
