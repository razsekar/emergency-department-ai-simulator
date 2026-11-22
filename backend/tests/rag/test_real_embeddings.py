"""Tests with the REAL local sentence-transformers model. Skipped (loudly) if it cannot be loaded."""
import math

import pytest

from app.modules.rag.infrastructure.embedder import SentenceTransformerEmbedder


@pytest.fixture(scope="module")
def real():
    emb = SentenceTransformerEmbedder()
    try:
        emb.embed(["warm up"])
    except Exception as exc:  # no network / model not cached / torch missing
        pytest.skip(f"real embedding model unavailable in this environment: {type(exc).__name__}: {exc}")
    return emb


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_embeddings_are_384_dimensional_and_normalized(real):
    v = real.embed(["Escalation procedure for surge conditions"])[0]
    assert len(v) == 384 and math.isclose(_dot(v, v), 1.0, rel_tol=1e-3)


def test_semantically_related_text_scores_higher(real):
    q, near, far = real.embed([
        "what should we do when there are no free beds",
        "When one or fewer beds are available the discharge lounge is opened.",
        "The cafeteria serves lunch from noon until two o'clock.",
    ])
    assert _dot(q, near) > _dot(q, far) + 0.1


def test_end_to_end_retrieval_with_real_model(app_db):
    from app.modules.knowledge_base import public as kb
    from app.modules.rag import public as rag
    from app.modules.rag.infrastructure.embedder import set_default_embedder
    from tests.rag.support import make_pdf

    emb = SentenceTransformerEmbedder()
    emb.embed(["warm up"])
    set_default_embedder(emb)
    try:
        rag.register_handlers()
        kb.upload_document("esc.pdf", make_pdf([
            "Escalation. When average waiting time is above 60 minutes and more than 30 patients are waiting, "
            "the department is at RED and the Administrator on Call is notified within 10 minutes."]),
            display_name="Escalation Procedures")
        kb.upload_document("park.pdf", make_pdf(["Visitor parking is available behind building two on weekdays."]),
                           display_name="Parking")
        hits = rag.search("Who must be told when the ED is overwhelmed with waiting patients?", k=2)
        assert hits[0].document_name == "Escalation Procedures"
    finally:
        set_default_embedder(None)
