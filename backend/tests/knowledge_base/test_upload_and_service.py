import pytest
from fastapi.testclient import TestClient

from app.modules.knowledge_base import public as kb
from app.modules.knowledge_base.domain.validation import (
    DuplicateDocument,
    FileTooLarge,
    UnreadableDocument,
    UnsupportedFileType,
    UploadRejected,
    validate_pdf_upload,
)
from app.platform.errors import NotFoundError
from tests.rag.support import make_pdf

PDF = make_pdf(["Registration must be completed within 10 minutes of arrival."])


# ---- pure validation (no DB) -------------------------------------------------------------
@pytest.mark.parametrize("name", [None, "", "notes.txt", "report.docx", "archive.pdf.exe", "pdf"])
def test_non_pdf_filenames_rejected(name):
    with pytest.raises(UnsupportedFileType):
        validate_pdf_upload(name, PDF, 1_000_000)


def test_empty_file_rejected():
    with pytest.raises(UploadRejected):
        validate_pdf_upload("a.pdf", b"", 1_000_000)


def test_oversized_file_rejected_with_413():
    with pytest.raises(FileTooLarge) as exc:
        validate_pdf_upload("a.pdf", PDF + b"0" * 2000, 1000)
    assert exc.value.status_code == 413


def test_pdf_extension_with_non_pdf_content_rejected():
    with pytest.raises(UnsupportedFileType):
        validate_pdf_upload("fake.pdf", b"MZ\x90\x00 this is an executable", 1_000_000)


def test_uppercase_extension_accepted():
    validate_pdf_upload("DOC.PDF", PDF, 1_000_000)


def test_error_status_codes():
    assert UnsupportedFileType.status_code == 415
    assert FileTooLarge.status_code == 413
    assert UnreadableDocument.status_code == 422
    assert DuplicateDocument.status_code == 409


def test_corrupt_pdf_is_unreadable_and_nothing_is_stored():
    with pytest.raises(UnreadableDocument):
        kb.upload_document("broken.pdf", b"%PDF-1.7\nthis is not a real pdf body")


def test_image_only_pdf_without_text_is_rejected():
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    blank = doc.tobytes()
    with pytest.raises(UnreadableDocument, match="No extractable text"):
        kb.upload_document("scan.pdf", blank)


# ---- API layer: RBAC is enforced (frontend is not the security boundary) -----------------
def test_upload_and_list_endpoints_require_authentication():
    from app.main import app

    client = TestClient(app)
    assert client.post("/api/knowledge/documents", files={"file": ("a.pdf", PDF, "application/pdf")}).status_code in (401, 403)
    assert client.get("/api/knowledge/documents").status_code in (401, 403)
    assert client.delete("/api/knowledge/documents/00000000-0000-0000-0000-000000000000").status_code in (401, 403)
    assert client.post("/api/rag/search", json={"query": "beds"}).status_code in (401, 403)


# ---- service with DB (no RAG subscriber: KB works standalone) -----------------------------
def test_upload_stores_metadata_and_stays_processing_without_indexer(app_db):
    doc = kb.upload_document("03_investigation_workflow_guidelines.pdf", PDF)
    assert doc.status == "processing" and doc.page_count == 1 and doc.chunk_count == 0
    assert doc.name == "Investigation Workflow Guidelines"  # humanized from the filename
    assert kb.get_document(doc.id).id == doc.id


def test_duplicate_content_is_rejected(app_db):
    kb.upload_document("a.pdf", PDF)
    with pytest.raises(DuplicateDocument):
        kb.upload_document("b.pdf", PDF)
    assert kb.list_documents()[1] == 1


def test_list_is_paginated_newest_first(app_db):
    for i in range(5):
        kb.upload_document(f"doc{i}.pdf", make_pdf([f"Unique page content number {i} for pagination."]))
    page1, total = kb.list_documents(limit=2, offset=0)
    page2, _ = kb.list_documents(limit=2, offset=2)
    assert total == 5 and len(page1) == 2 and len(page2) == 2
    assert {d.id for d in page1}.isdisjoint({d.id for d in page2})
    assert page1[0].name == "Doc4"


def test_mark_indexed_and_failed(app_db):
    doc = kb.upload_document("a.pdf", PDF)
    kb.mark_document_indexed(doc.id, 7)
    assert (kb.get_document(doc.id).status, kb.get_document(doc.id).chunk_count) == ("indexed", 7)
    kb.mark_document_failed(doc.id, "boom")
    assert kb.get_document(doc.id).status == "failed" and kb.get_document(doc.id).error_message == "boom"


def test_delete_and_not_found(app_db):
    doc = kb.upload_document("a.pdf", PDF)
    kb.delete_document(doc.id)
    with pytest.raises(NotFoundError):
        kb.get_document(doc.id)
    with pytest.raises(NotFoundError):
        kb.delete_document(doc.id)


def test_sql_injection_in_display_name_is_stored_literally(app_db):
    evil = "x'); DROP TABLE knowledge_base.knowledge_documents; --"
    doc = kb.upload_document("a.pdf", PDF, display_name=evil)
    assert kb.get_document(doc.id).name == evil
    assert kb.list_documents()[1] == 1  # table still exists


def test_load_samples_missing_directory_is_a_clean_error(app_db, tmp_path):
    with pytest.raises(NotFoundError):
        kb.load_sample_documents(str(tmp_path / "nope"))
