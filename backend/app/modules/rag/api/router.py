"""Thin HTTP layer for RAG search."""
from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.modules.identity.public import CurrentUser, Permission, require_permission
from app.modules.rag import public as rag
from app.modules.rag.api.schemas import ChunkOut, SearchRequest, SearchResponse

router = APIRouter(prefix="/api/rag", tags=["rag"])

# Subscribe to knowledge-base events so uploaded documents get indexed. Idempotent.
rag.register_handlers()


@router.post("/search", response_model=SearchResponse)
def search(
    body: SearchRequest, _: CurrentUser = Depends(require_permission(Permission.KNOWLEDGE_READ))
) -> SearchResponse:
    chunks = rag.search(body.query, body.k)
    return SearchResponse(
        query=body.query,
        embedding_model=str(rag.embedding_info()["model"]),
        results=[ChunkOut(**{**asdict(c), "injection_signals": list(c.injection_signals)}) for c in chunks],
        llm_context=rag.format_context(chunks),
    )
