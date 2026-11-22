import pytest

from app.modules.rag.infrastructure.embedder import set_default_embedder
from tests.rag.support import FakeEmbedder, app_db_fixture_body, truncate_all


@pytest.fixture(scope="module")
def app_db():
    yield from app_db_fixture_body("rag")


@pytest.fixture(autouse=True)
def _clean_tables(request):
    """Reset tables between tests (only for tests that use the DB)."""
    if "app_db" in request.fixturenames:
        truncate_all(request.getfixturevalue("app_db"))
    yield


@pytest.fixture
def fake_embedder():
    emb = FakeEmbedder()
    set_default_embedder(emb)
    yield emb
    set_default_embedder(None)


@pytest.fixture
def wired(app_db, fake_embedder):
    """DB + fake embedder + RAG subscribed to knowledge-base events."""
    from app.modules.rag.public import register_handlers

    register_handlers()
    return app_db
