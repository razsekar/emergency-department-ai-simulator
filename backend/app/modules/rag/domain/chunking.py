"""Page-aware text chunking with configurable size and overlap. Pure functions.

Chunks never span pages, so every chunk maps to exactly one page number (citation accuracy).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    page_number: int
    chunk_index: int  # unique and increasing across the whole document
    text: str


def validate_params(chunk_size: int, overlap: int) -> None:
    if chunk_size < 50:
        raise ValueError("chunk_size must be at least 50 characters")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")


def _split_page(text: str, chunk_size: int, overlap: int) -> list[str]:
    pieces: list[str] = []
    n = len(text)
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            # Prefer breaking at paragraph, then sentence, then word boundary in the last 30% of the window.
            floor = start + int(chunk_size * 0.7)
            window = text[floor:end]
            for sep in ("\n\n", ". ", "\n", " "):
                idx = window.rfind(sep)
                if idx != -1:
                    end = floor + idx + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= n:
            break
        next_start = max(end - overlap, start + 1)  # always make progress
        # Snap forward to a word boundary so a chunk does not begin mid-word.
        if 0 < next_start < n and not text[next_start - 1].isspace():
            nxt = text.find(" ", next_start)
            next_start = next_start if nxt == -1 or nxt >= end else nxt + 1
        start = next_start
    return pieces


def chunk_pages(pages: list[tuple[int, str]], chunk_size: int, overlap: int) -> list[Chunk]:
    """Chunk (page_number, text) pairs. Output order follows page order."""
    validate_params(chunk_size, overlap)
    chunks: list[Chunk] = []
    for page_number, text in pages:
        for piece in _split_page(text, chunk_size, overlap):
            chunks.append(Chunk(page_number, len(chunks), piece))
    return chunks
