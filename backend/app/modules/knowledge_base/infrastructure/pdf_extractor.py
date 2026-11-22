"""PDF text extraction with PyMuPDF (page-level)."""
from dataclasses import dataclass

import pymupdf

from app.modules.knowledge_base.domain.validation import UnreadableDocument


@dataclass(frozen=True)
class ExtractedPdf:
    title: str | None
    page_count: int
    raw_pages: list[tuple[int, str]]  # (1-based page number, raw text)


def extract_pdf(data: bytes, max_pages: int = 300) -> ExtractedPdf:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several error types for corrupt input
        raise UnreadableDocument("The PDF could not be opened (corrupt or encrypted).") from exc
    try:
        if doc.needs_pass:
            raise UnreadableDocument("Password-protected PDFs are not supported.")
        if doc.page_count > max_pages:
            raise UnreadableDocument(f"PDF has more than {max_pages} pages.")
        pages = [(i + 1, page.get_text("text")) for i, page in enumerate(doc)]
        title = (doc.metadata or {}).get("title") or None
        return ExtractedPdf(title=title, page_count=doc.page_count, raw_pages=pages)
    finally:
        doc.close()
