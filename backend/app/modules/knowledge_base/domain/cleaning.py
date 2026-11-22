"""Text normalization for extracted PDF pages. Pure functions, no I/O."""
import re
import unicodedata
from collections import Counter

from app.modules.knowledge_base.domain.models import PageText

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_PAGE_NUMBER_LINE = re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE)
_SPACES = re.compile(r"[ \t ]+")
_BLANKS = re.compile(r"\n{3,}")


def clean_text(raw: str) -> str:
    """Normalize unicode, drop control chars, repair hyphenated line breaks, collapse whitespace."""
    text = unicodedata.normalize("NFKC", raw)
    text = _CONTROL.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if not _PAGE_NUMBER_LINE.match(line)]
    return _BLANKS.sub("\n\n", "\n".join(lines)).strip()


def strip_repeated_boilerplate(pages: list[PageText], min_pages: int = 3, ratio: float = 0.6) -> list[PageText]:
    """Remove short lines (running headers/footers) that appear on most pages of a document."""
    if len(pages) < min_pages:
        return pages
    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({line for line in page.text.split("\n") if 0 < len(line) < 120})
    repeated = {line for line, n in counts.items() if n / len(pages) >= ratio}
    if not repeated:
        return pages
    return [
        PageText(p.page_number, clean_text("\n".join(l for l in p.text.split("\n") if l not in repeated)))
        for p in pages
    ]


def clean_pages(raw_pages: list[tuple[int, str]]) -> list[PageText]:
    """Clean every page, strip running headers/footers, and drop pages left empty."""
    pages = [PageText(n, clean_text(t)) for n, t in raw_pages]
    pages = strip_repeated_boilerplate(pages)
    return [p for p in pages if p.text]
