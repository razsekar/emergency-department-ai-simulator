from app.modules.knowledge_base.domain.cleaning import clean_pages, clean_text


def test_whitespace_control_chars_and_unicode_are_normalized():
    raw = "Hello\x00   world  ①\n\n\n\nNext\tparagraph  "
    out = clean_text(raw)
    assert "\x00" not in out and "  " not in out
    assert "1" in out  # NFKC maps the circled digit to a plain digit
    assert "\n\n\n" not in out and out.endswith("paragraph")


def test_hyphenated_line_breaks_are_repaired():
    assert clean_text("investi-\ngation workflow") == "investigation workflow"


def test_page_number_lines_are_removed():
    assert clean_text("Policy text\nPage 3\nMore text\nPage 4 of 9") == "Policy text\nMore text"


def test_repeated_header_footer_lines_are_stripped_for_long_documents():
    pages = [(i, f"FICTIONAL DEMONSTRATION DOCUMENT\nBody of page {i} with unique content\nPage {i}") for i in range(1, 5)]
    cleaned = clean_pages(pages)
    assert len(cleaned) == 4
    assert all("FICTIONAL DEMONSTRATION" not in p.text for p in cleaned)
    assert cleaned[2].text == "Body of page 3 with unique content"


def test_short_documents_keep_their_banner_lines():
    cleaned = clean_pages([(1, "FICTIONAL BANNER\nBody one"), (2, "FICTIONAL BANNER\nBody two")])
    assert "FICTIONAL BANNER" in cleaned[0].text


def test_empty_pages_are_dropped_but_numbers_preserved():
    cleaned = clean_pages([(1, "Real text"), (2, "  \n Page 2 \n"), (3, "More text")])
    assert [p.page_number for p in cleaned] == [1, 3]
