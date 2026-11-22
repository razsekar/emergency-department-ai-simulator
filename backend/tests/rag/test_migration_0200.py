from alembic import command
from sqlalchemy import create_engine, text

from tests.rag.support import alembic_config, create_database


def test_rag_branch_upgrades_and_downgrades_cleanly():
    url, drop = create_database("mig0200")
    try:
        cfg = alembic_config(url)
        command.upgrade(cfg, "rag@head")
        eng = create_engine(url)
        with eng.connect() as c:
            tables = {(r[0], r[1]) for r in c.execute(text(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema IN ('knowledge_base','rag')"))}
            assert ("knowledge_base", "knowledge_documents") in tables and ("rag", "document_chunks") in tables
            col = c.execute(text(
                "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
                "WHERE a.attrelid = 'rag.document_chunks'::regclass AND a.attname = 'embedding'")).scalar_one()
            assert col == "vector(384)"
            assert c.execute(text("SELECT count(*) FROM pg_indexes WHERE indexname='ix_document_chunks_embedding_hnsw'")).scalar_one() == 1
            # status constraint
            try:
                c.execute(text("INSERT INTO knowledge_base.knowledge_documents (name, original_filename, content_sha256, size_bytes, page_count, status) "
                               "VALUES ('x','x.pdf', repeat('a',64), 1, 1, 'bogus')"))
                raise AssertionError("invalid status accepted")
            except Exception as exc:
                assert "check" in str(exc).lower()
        eng.dispose()

        command.downgrade(cfg, "0001")
        eng = create_engine(url)
        with eng.connect() as c:
            left = c.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('knowledge_base','rag')")).scalar_one()
        eng.dispose()
        assert left == 0
    finally:
        drop()
