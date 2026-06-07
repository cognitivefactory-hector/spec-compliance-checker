"""Ingest / parsing (M2): PDF/text -> text with source locations preserved.

Locations are recoverable for citation: given a verbatim quote, the parsed
document computes an auditor locator ("p.2 L14"). The model never counts
lines — code locates the quote.
"""

from io import BytesIO

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.ingest.parse import ParsedDocument, TextSpan, parse, parse_pdf, parse_text


def _make_pdf(pages: list[list[str]]) -> bytes:
    """Build a typed PDF (one drawn line per list item) for ingest tests."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _, height = letter
    for page_lines in pages:
        y = height - 72
        for line in page_lines:
            c.drawString(72, y, line)
            y -= 18
        c.showPage()
    c.save()
    return buf.getvalue()


def test_parse_text_splits_into_located_lines():
    doc = parse_text("line one\nline two\nline three")
    assert isinstance(doc, ParsedDocument)
    assert [s.text for s in doc.spans] == ["line one", "line two", "line three"]
    second = doc.spans[1]
    assert isinstance(second, TextSpan)
    assert second.page == 1
    assert second.line == 2


def test_text_span_offsets_index_full_text():
    doc = parse_text("alpha\nbeta\ngamma")
    for span in doc.spans:
        assert doc.full_text[span.char_start : span.char_end] == span.text


def test_locate_returns_page_line_locator():
    doc = parse_text("alpha\nbeta\ngamma")
    assert doc.locate("beta") == "p.1 L2"


def test_locate_absent_snippet_returns_none():
    """An unlocatable quote is never given a fabricated location."""
    doc = parse_text("alpha\nbeta\ngamma")
    assert doc.locate("delta") is None


def test_locate_multiline_snippet_returns_line_range():
    doc = parse_text("alpha\nbeta\ngamma")
    assert doc.locate("beta\ngamma") == "p.1 L2–L3"


# --- PDF ---------------------------------------------------------------------


def test_parse_pdf_extracts_lines_with_page_numbers():
    pdf = _make_pdf(
        [
            ["Coating thickness 0.5-1.5 mm", "Material: Ti-6Al-4V"],
            ["Operator certification required"],
        ]
    )
    doc = parse_pdf(pdf)
    texts = [s.text for s in doc.spans]
    assert any("Coating thickness 0.5-1.5 mm" in t for t in texts)
    page2 = [s for s in doc.spans if "Operator certification required" in s.text]
    assert page2 and page2[0].page == 2


def test_parse_pdf_locations_are_citable():
    pdf = _make_pdf([["Coating thickness 0.5-1.5 mm", "Material: Ti-6Al-4V"]])
    doc = parse_pdf(pdf)
    locator = doc.locate("Material: Ti-6Al-4V")
    assert locator is not None
    assert locator.startswith("p.1 L")


def test_parse_pdf_span_offsets_index_full_text():
    pdf = _make_pdf([["alpha line", "beta line"]])
    doc = parse_pdf(pdf)
    for span in doc.spans:
        assert doc.full_text[span.char_start : span.char_end] == span.text


def test_parse_pdf_falls_back_to_pypdf_when_pdfplumber_finds_no_text(monkeypatch):
    """When pdfplumber yields nothing, pypdf is used so we still get text."""
    import app.ingest.parse as parse_mod

    pdf = _make_pdf([["Fallback content line"]])
    monkeypatch.setattr(parse_mod, "_extract_pdf_pages", lambda data: [""])
    doc = parse_mod.parse_pdf(pdf)
    assert any("Fallback content line" in s.text for s in doc.spans)


# --- parse() dispatcher ------------------------------------------------------


def test_parse_dispatches_pdf_by_filename():
    pdf = _make_pdf([["Spec clause text"]])
    doc = parse(pdf, filename="spec.pdf")
    assert any("Spec clause text" in s.text for s in doc.spans)


def test_parse_dispatches_text_by_filename():
    doc = parse("one\ntwo", filename="record.txt")
    assert [s.text for s in doc.spans] == ["one", "two"]


def test_parse_sniffs_pdf_magic_bytes_without_hints():
    pdf = _make_pdf([["Sniffed by magic bytes"]])
    doc = parse(pdf)
    assert any("Sniffed by magic bytes" in s.text for s in doc.spans)


def test_parse_accepts_plain_string_as_text():
    doc = parse("hello\nworld")
    assert isinstance(doc, ParsedDocument)
    assert [s.text for s in doc.spans] == ["hello", "world"]


def test_parse_decodes_text_bytes_by_content_type():
    doc = parse(b"alpha\nbeta", content_type="text/plain")
    assert [s.text for s in doc.spans] == ["alpha", "beta"]


def test_parse_unsupported_type_raises():
    with pytest.raises(ValueError):
        parse(b"\x00\x01\x02", filename="report.docx")
