"""Checks on the 6 fictional demonstration PDFs in /sample_docs (skipped if the folder is not available)."""
import os
from pathlib import Path

import pytest

from app.modules.knowledge_base.domain.cleaning import clean_pages
from app.modules.knowledge_base.infrastructure.pdf_extractor import extract_pdf
from app.modules.rag.domain.chunking import chunk_pages
from app.modules.rag.domain.injection import scan_text

_CANDIDATES = [os.environ.get("KB_SAMPLE_DOCS_DIR"), "/sample_docs", str(Path(__file__).resolve().parents[3] / "sample_docs")]
SAMPLE_DIR = next((Path(c) for c in _CANDIDATES if c and Path(c).is_dir() and list(Path(c).glob("*.pdf"))), None)
pytestmark = pytest.mark.skipif(SAMPLE_DIR is None, reason="sample_docs directory not available")

EXPECTED_TITLES = {
    "Emergency Department Workflow SOP", "Patient Registration and Admission Policy",
    "Investigation Workflow Guidelines", "Hospital Escalation Procedures",
    "Patient Discharge Coordination SOP", "Resource Management Guidelines",
}


def _pdfs():
    return sorted(SAMPLE_DIR.glob("*.pdf"))


def test_six_documents_with_expected_titles():
    assert len(_pdfs()) == 6
    assert {extract_pdf(p.read_bytes()).title for p in _pdfs()} == EXPECTED_TITLES


@pytest.mark.parametrize("pdf", _pdfs() if SAMPLE_DIR else [], ids=lambda p: p.name)
def test_document_is_fictional_multi_page_and_not_flagged_as_injection(pdf):
    ex = extract_pdf(pdf.read_bytes())
    assert ex.page_count >= 2
    assert "FICTIONAL" in ex.raw_pages[0][1] and "NOT A REAL CLINICAL PROTOCOL" in ex.raw_pages[0][1]
    chunks = chunk_pages([(p.page_number, p.text) for p in clean_pages(ex.raw_pages)], 700, 120)
    assert chunks and {c.page_number for c in chunks} <= set(range(1, ex.page_count + 1))
    assert not [c.text[:60] for c in chunks if scan_text(c.text).flagged], "false-positive injection flag"


def test_escalation_document_contains_the_operating_thresholds():
    esc = next(p for p in _pdfs() if "escalation" in p.name)
    text = " ".join(" ".join(t for _, t in extract_pdf(esc.read_bytes()).raw_pages).split())  # undo line wraps
    for needle in ("average waiting time above 60 minutes", "more than 30 patients waiting",
                   "1 or fewer available beds", "more than 20 pending investigation requests"):
        assert needle in text
