"""Thin HTTP layer: validation and delegation only (no persistence or business logic)."""
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.modules.identity.public import CurrentUser, Permission, require_permission
from app.modules.knowledge_base import public as kb
from app.modules.knowledge_base.api.schemas import DocumentOut, DocumentPage, SampleLoadResult

router = APIRouter(prefix="/api/knowledge/documents", tags=["knowledge-base"])

_READ_CHUNK = 1024 * 1024


@router.post("", response_model=DocumentOut, status_code=201)
async def upload(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    user: CurrentUser = Depends(require_permission(Permission.KNOWLEDGE_UPLOAD)),
) -> DocumentOut:
    # Read at most limit+1 bytes so oversized uploads are rejected without buffering them fully.
    from app.modules.knowledge_base.application.config import max_upload_bytes

    limit = max_upload_bytes()
    data = await file.read(limit + 1)
    return DocumentOut(**asdict(kb.upload_document(file.filename, data, display_name=name, actor=user.username)))


@router.post("/load-samples", response_model=SampleLoadResult)
def load_samples(user: CurrentUser = Depends(require_permission(Permission.KNOWLEDGE_UPLOAD))) -> SampleLoadResult:
    return SampleLoadResult(**kb.load_sample_documents(actor=user.username))


@router.get("", response_model=DocumentPage)
def list_documents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: CurrentUser = Depends(require_permission(Permission.KNOWLEDGE_READ)),
) -> DocumentPage:
    items, total = kb.list_documents(limit, offset)
    return DocumentPage(items=[DocumentOut(**asdict(i)) for i in items], total=total, limit=limit, offset=offset)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: UUID, _: CurrentUser = Depends(require_permission(Permission.KNOWLEDGE_READ))
) -> DocumentOut:
    return DocumentOut(**asdict(kb.get_document(document_id)))


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: UUID, user: CurrentUser = Depends(require_permission(Permission.KNOWLEDGE_UPLOAD))
) -> None:
    kb.delete_document(document_id, actor=user.username)
