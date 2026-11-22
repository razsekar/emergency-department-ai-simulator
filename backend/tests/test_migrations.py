from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

EXPECTED_SCHEMAS = {
    "identity", "simulation", "patient_queue", "resource_management", "analytics",
    "knowledge_base", "rag", "ai_orchestration", "agent_tools", "model_providers", "audit",
}


def _cfg(url: str, monkeypatch) -> Config:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
    return Config("alembic.ini")


def _schemas(url: str) -> set[str]:
    with create_engine(url).connect() as c:
        return {r[0] for r in c.execute(text("SELECT schema_name FROM information_schema.schemata"))}


def test_upgrade_creates_module_schemas_and_pgvector(test_db_url, monkeypatch):
    command.upgrade(_cfg(test_db_url, monkeypatch), "heads")
    assert EXPECTED_SCHEMAS <= _schemas(test_db_url)
    with create_engine(test_db_url).connect() as c:
        assert c.execute(text("SELECT count(*) FROM pg_extension WHERE extname='vector'")).scalar_one() == 1


def test_downgrade_removes_module_schemas(test_db_url, monkeypatch):
    cfg = _cfg(test_db_url, monkeypatch)
    command.upgrade(cfg, "heads")
    command.downgrade(cfg, "base")
    assert not (EXPECTED_SCHEMAS & _schemas(test_db_url))
