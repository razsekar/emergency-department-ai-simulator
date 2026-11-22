"""Migration 0300 and the model_configurations repository, against an isolated database."""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.model_providers.infrastructure import repository


@pytest.fixture(scope="module")
def session_factory(test_db_url):
    import os
    os.environ["ALEMBIC_DATABASE_URL"] = test_db_url
    command.upgrade(Config("alembic.ini"), "0300")  # 0300 depends only on 0001; applies both
    engine = create_engine(test_db_url)
    yield lambda: Session(engine)
    engine.dispose()
    os.environ.pop("ALEMBIC_DATABASE_URL", None)


def test_table_has_no_secret_columns(session_factory):
    with session_factory() as s:
        cols = {r[0] for r in s.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='model_providers' AND table_name='model_configurations'"))}
    assert {"api_key_env_var", "api_base_env_var"} <= cols  # env var NAMES only
    assert not {c for c in cols if c in {"api_key", "secret", "token", "password"}}


def test_upsert_list_disable_roundtrip(session_factory):
    with session_factory() as s:
        repository.upsert(s, "openai", "m-1", "First")
        repository.upsert(s, "openai", "m-1", "Renamed")  # idempotent upsert
        repository.upsert(s, "gemini", "g-1", None)
        s.commit()
        rows = repository.list_enabled(s)
        assert [(r["provider"], r["model_id"], r["display_name"]) for r in rows] == [
            ("gemini", "g-1", "g-1"), ("openai", "m-1", "Renamed")]
        assert repository.disable(s, "openai", "m-1") is True
        assert repository.disable(s, "openai", "m-1") is False
        s.commit()
        assert [r["model_id"] for r in repository.list_enabled(s)] == ["g-1"]
        repository.upsert(s, "openai", "m-1", "Back")  # re-registering re-enables
        s.commit()
        assert len(repository.list_enabled(s)) == 2


def test_unknown_provider_rejected_by_constraint(session_factory):
    with session_factory() as s:
        with pytest.raises(IntegrityError):
            repository.upsert(s, "mistral", "x", None)
            s.commit()
