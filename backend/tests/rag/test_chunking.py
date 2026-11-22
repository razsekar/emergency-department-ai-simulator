import pytest

from app.modules.rag.domain.chunking import chunk_pages

LOREM = " ".join(f"Sentence number {i} describes an operational step in the workflow." for i in range(60))


def test_chunks_respect_max_size_and_have_sequential_indices():
    chunks = chunk_pages([(1, LOREM)], chunk_size=300, overlap=60)
    assert len(chunks) > 3
    assert all(len(c.text) <= 300 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_consecutive_chunks_overlap():
    chunks = chunk_pages([(1, LOREM)], chunk_size=300, overlap=80)
    for a, b in zip(chunks, chunks[1:]):
        tail_words = a.text.split()[-4:]
        assert any(w in b.text.split()[:20] for w in tail_words), "no overlap between consecutive chunks"


def test_zero_overlap_does_not_repeat_text():
    chunks = chunk_pages([(1, LOREM)], chunk_size=300, overlap=0)
    joined = " ".join(c.text for c in chunks)
    assert joined.count("Sentence number 30 ") == 1


def test_chunks_never_span_pages_and_keep_page_numbers():
    chunks = chunk_pages([(1, "alpha " * 100), (3, "beta " * 100)], chunk_size=200, overlap=20)
    assert {c.page_number for c in chunks} == {1, 3}
    for c in chunks:
        assert ("alpha" in c.text) != ("beta" in c.text)
        assert (c.page_number == 1) == ("alpha" in c.text)


def test_short_text_is_a_single_chunk():
    chunks = chunk_pages([(2, "Short policy statement that fits easily within one chunk of text here.")], 500, 50)
    assert len(chunks) == 1 and chunks[0].page_number == 2


def test_all_words_are_covered():
    words = {f"w{i}" for i in range(400)}
    text = " ".join(sorted(words))
    covered = set(" ".join(c.text for c in chunk_pages([(1, text)], 200, 40)).split())
    assert words <= covered


def test_text_without_spaces_terminates():
    chunks = chunk_pages([(1, "x" * 1000)], chunk_size=100, overlap=20)
    assert len(chunks) >= 10 and all(c.text for c in chunks)


def test_empty_pages_yield_no_chunks():
    assert chunk_pages([(1, ""), (2, "   ")], 100, 10) == []


@pytest.mark.parametrize("size,overlap", [(10, 0), (100, 100), (100, 150), (100, -1)])
def test_invalid_parameters_are_rejected(size, overlap):
    with pytest.raises(ValueError):
        chunk_pages([(1, "text " * 50)], size, overlap)
