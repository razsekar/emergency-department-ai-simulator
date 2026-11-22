"""Citation verification: every [Source: <document>, p.<n>] in an answer must match a retrieved chunk."""
import re
from dataclasses import dataclass
from typing import Any

_CITATION = re.compile(r"\[Source:\s*([^,\]]+?)\s*,\s*p\.?\s*(\d+)\s*\]", re.IGNORECASE)


@dataclass(frozen=True)
class RetrievedRef:
    document_name: str
    page: int


def _norm(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\.pdf$", "", name)
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def _same_document(cited: str, retrieved: str) -> bool:
    a, b = _norm(cited), _norm(retrieved)
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def check_citations(answer: str | None, retrieved: list[RetrievedRef]) -> dict[str, Any]:
    """Flag (never rewrite) citations that do not correspond to an actually retrieved document and page."""
    found: list[dict[str, Any]] = []
    for doc, page in _CITATION.findall(answer or ""):
        ok = any(_same_document(doc, r.document_name) and r.page == int(page) for r in retrieved)
        found.append({"document": doc.strip(), "page": int(page), "verified": ok})
    unverified = [c for c in found if not c["verified"]]
    return {
        "citations": found,
        "verified_count": len(found) - len(unverified),
        "unverified_count": len(unverified),
        "unverified": unverified,
        "retrieved_count": len(retrieved),
    }
