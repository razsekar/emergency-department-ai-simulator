"""Database design requirements (master prompt sections 7 and 13): structure after ALL migrations on a fresh database."""
from alembic import command
from alembic.config import Config
from sqlalchemy import text

SCHEMA_TABLES = {
    "identity": {"users", "roles", "permissions", "user_roles", "role_permissions"},
    "simulation": {"scenarios", "scenario_parameters", "scenario_runs", "data_state"},
    "resource_management": {"departments", "staff", "beds", "investigation_facilities"},
    "patient_queue": {"patient_visits", "investigation_requests", "dataset_clock"},
    "knowledge_base": {"knowledge_documents"},
    "rag": {"document_chunks"},
    "ai_orchestration": {"chat_sessions", "chat_messages", "analysis_runs", "ai_comparison_runs",
                         "ai_comparison_results", "demo_runs"},
    "agent_tools": {"agent_execution_logs"},
    "model_providers": {"model_configurations"},
    "audit": {"audit_events"},
}
# Mutable entity tables must carry both timestamps; append-only/reference tables only need created_at.
MUTABLE_ENTITIES = {
    ("identity", "users"), ("simulation", "scenarios"), ("simulation", "scenario_parameters"),
    ("simulation", "scenario_runs"), ("patient_queue", "patient_visits"), ("patient_queue", "investigation_requests"),
    ("resource_management", "beds"), ("resource_management", "staff"), ("resource_management", "departments"),
    ("resource_management", "investigation_facilities"), ("knowledge_base", "knowledge_documents"),
    ("rag", "document_chunks"), ("model_providers", "model_configurations"), ("ai_orchestration", "analysis_runs"),
    ("ai_orchestration", "chat_sessions"), ("ai_orchestration", "demo_runs"), ("ai_orchestration", "ai_comparison_runs"),
}
LINK_TABLES = {("identity", "user_roles"), ("identity", "role_permissions")}


def rows(engine, sql, **params):
    with engine.connect() as c:
        return c.execute(text(sql), params).all()


def test_every_module_owns_its_expected_tables(engine):
    found = {}
    for schema, table in rows(engine, "SELECT table_schema, table_name FROM information_schema.tables "
                                      "WHERE table_type='BASE TABLE' AND table_schema = ANY(:s)",
                              s=list(SCHEMA_TABLES)):
        found.setdefault(schema, set()).add(table)
    for schema, expected in SCHEMA_TABLES.items():
        assert expected <= found.get(schema, set()), f"{schema} is missing {expected - found.get(schema, set())}"


def test_no_foreign_keys_cross_module_schemas(engine):
    """Module boundaries in the database: cross-schema references are opaque ids, never foreign keys."""
    cross = rows(engine, """
        SELECT con.conrelid::regclass::text, con.confrelid::regclass::text
        FROM pg_constraint con
        JOIN pg_class a ON a.oid = con.conrelid JOIN pg_namespace na ON na.oid = a.relnamespace
        JOIN pg_class b ON b.oid = con.confrelid JOIN pg_namespace nb ON nb.oid = b.relnamespace
        WHERE con.contype = 'f' AND na.nspname <> nb.nspname""")
    assert cross == []


def test_foreign_keys_exist_inside_modules(engine):
    n = rows(engine, "SELECT count(*) FROM pg_constraint con JOIN pg_namespace n ON n.oid = con.connamespace "
                     "WHERE con.contype='f' AND n.nspname = ANY(:s)", s=list(SCHEMA_TABLES))[0][0]
    assert n >= 8  # visits->investigation requests, user_roles, role_permissions, chunks->..., results->runs, ...


def test_uuid_primary_keys_and_timestamps(engine):
    info = rows(engine, """
        SELECT c.table_schema, c.table_name, c.column_name, c.data_type
        FROM information_schema.columns c WHERE c.table_schema = ANY(:s)""", s=list(SCHEMA_TABLES))
    cols = {}
    for schema, table, column, dtype in info:
        cols.setdefault((schema, table), {})[column] = dtype
    for (schema, table), columns in cols.items():
        if (schema, table) in LINK_TABLES or table not in SCHEMA_TABLES.get(schema, set()):
            continue
        assert "created_at" in columns, f"{schema}.{table} has no created_at"
    for key in MUTABLE_ENTITIES:
        assert "updated_at" in cols[key], f"{key} has no updated_at"
        assert cols[key]["id"] == "uuid", f"{key} primary key is not a UUID"


def test_vector_column_is_384_dimensions_with_hnsw_cosine_index(engine):
    dim = rows(engine, "SELECT atttypmod FROM pg_attribute WHERE attrelid='rag.document_chunks'::regclass "
                       "AND attname='embedding'")[0][0]
    assert dim == 384
    defs = [r[0] for r in rows(engine, "SELECT indexdef FROM pg_indexes WHERE schemaname='rag' "
                                       "AND tablename='document_chunks'")]
    assert any("hnsw" in d and "vector_cosine_ops" in d and "embedding" in d for d in defs), defs


def test_useful_indexes_exist(engine):
    names = {r[0] for r in rows(engine, "SELECT indexname FROM pg_indexes WHERE schemaname = ANY(:s)",
                                s=["patient_queue", "audit", "rag"])}
    assert any("patient_visits" in n or "visits" in n for n in names), names
    assert any("audit" in n for n in names), names


def test_upgrade_is_idempotent_and_single_database_state_is_at_all_heads(e2e_db):
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "heads")  # already at heads: must be a no-op, not an error
    heads = {r[0] for r in rows_url(e2e_db, "SELECT version_num FROM alembic_version")}
    from alembic.script import ScriptDirectory

    assert heads == set(ScriptDirectory.from_config(cfg).get_heads())


def rows_url(url, sql):
    from sqlalchemy import create_engine

    eng = create_engine(url)
    try:
        with eng.connect() as c:
            return c.execute(text(sql)).all()
    finally:
        eng.dispose()


def test_demo_users_seed_is_idempotent_and_stores_no_plaintext_password(engine):
    from app.modules.identity.application.seed import seed_demo_users
    from app.platform import db
    from tests.e2e.conftest import ADMIN_PASSWORD, PRESENTER_PASSWORD, VIEWER_PASSWORD

    with db.unit_of_work() as s:
        assert set(seed_demo_users(s).values()) == {"exists"}
    stored = " ".join(r[0] for r in rows(engine, "SELECT password_hash FROM identity.users"))
    for plain in (ADMIN_PASSWORD, PRESENTER_PASSWORD, VIEWER_PASSWORD):
        assert plain not in stored
