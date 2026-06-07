"""Ingest: parse a spec or production record into text with source locations
preserved for citation.

A ``ParsedDocument`` exposes the ``full_text`` (sent to the extractor / shown
to the engineer) and ordered ``TextSpan``s. Given a verbatim quote, ``locate``
computes an auditor-friendly locator like ``"p.2 L14"`` — deterministically,
so the model never has to count lines or pages.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pdfplumber
from pypdf import PdfReader


@dataclass(frozen=True)
class TextSpan:
    """One line of the document, located. ``char_start``/``char_end`` index
    into the owning ``ParsedDocument.full_text``."""

    page: int  # 1-based
    line: int  # 1-based within the page
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ParsedDocument:
    full_text: str
    spans: tuple[TextSpan, ...]

    def _span_at(self, offset: int) -> TextSpan | None:
        for span in self.spans:
            if span.char_start <= offset <= span.char_end:
                return span
        return None

    def locate(self, snippet: str) -> str | None:
        """Return an auditor locator for a verbatim quote, or None if the quote
        can't be found (a signal it wasn't quoted verbatim)."""
        start = self.full_text.find(snippet)
        if start == -1:
            return None
        end = start + len(snippet) - 1
        start_span = self._span_at(start)
        end_span = self._span_at(end)
        if start_span is None or end_span is None:
            return None
        return _format_locator(start_span, end_span)


def _format_locator(start: TextSpan, end: TextSpan) -> str:
    if start.page == end.page and start.line == end.line:
        return f"p.{start.page} L{start.line}"
    if start.page == end.page:
        return f"p.{start.page} L{start.line}–L{end.line}"
    return f"p.{start.page} L{start.line}–p.{end.page} L{end.line}"


def _spans_from_pages(pages: list[str]) -> tuple[str, tuple[TextSpan, ...]]:
    """Build full_text + located spans from a list of page texts. Lines are
    joined with newlines; offsets index into the returned full_text."""
    spans: list[TextSpan] = []
    pieces: list[str] = []
    offset = 0
    for page_no, page_text in enumerate(pages, start=1):
        for line_no, line in enumerate(page_text.split("\n"), start=1):
            char_start = offset
            char_end = offset + len(line)
            spans.append(TextSpan(page_no, line_no, line, char_start, char_end))
            pieces.append(line)
            offset = char_end + 1  # account for the joining newline
    return "\n".join(pieces), tuple(spans)


def parse_text(text: str) -> ParsedDocument:
    full_text, spans = _spans_from_pages([text])
    return ParsedDocument(full_text=full_text, spans=spans)


def _extract_pdf_pages(data: bytes) -> list[str]:
    """Primary extractor: pdfplumber (per-line positional fidelity)."""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def _extract_pdf_pages_pypdf(data: bytes) -> list[str]:
    """Fallback extractor when pdfplumber yields no text."""
    reader = PdfReader(io.BytesIO(data))
    return [page.extract_text() or "" for page in reader.pages]


def _has_text(pages: list[str]) -> bool:
    return any(page.strip() for page in pages)


def parse_pdf(data: bytes) -> ParsedDocument:
    pages = _extract_pdf_pages(data)
    if not _has_text(pages):
        pages = _extract_pdf_pages_pypdf(data)
    full_text, spans = _spans_from_pages(pages)
    return ParsedDocument(full_text=full_text, spans=spans)


def _resolve_kind(source, filename: str | None, content_type: str | None) -> str | None:
    """Decide 'pdf' or 'text'. An explicit but unrecognized hint -> None
    (unsupported); with no hints, sniff bytes / treat strings as text."""
    if content_type:
        if "pdf" in content_type:
            return "pdf"
        return "text" if content_type.startswith("text") else None
    if filename:
        lower = filename.lower()
        if lower.endswith(".pdf"):
            return "pdf"
        return "text" if lower.endswith((".txt", ".text", ".md")) else None
    if isinstance(source, bytes) and source[:5] == b"%PDF-":
        return "pdf"
    if isinstance(source, (str, bytes)):
        return "text"
    return None


def parse(
    source, *, filename: str | None = None, content_type: str | None = None
) -> ParsedDocument:
    """Parse a spec or record into a ``ParsedDocument``, choosing the PDF or
    text path from content_type, then filename, then a magic-byte sniff."""
    kind = _resolve_kind(source, filename, content_type)
    if kind == "pdf":
        if isinstance(source, str):
            raise ValueError("PDF source must be bytes, not str")
        return parse_pdf(source)
    if kind == "text":
        text = source.decode("utf-8", errors="replace") if isinstance(source, bytes) else source
        return parse_text(text)
    raise ValueError(
        f"unsupported document type (filename={filename!r}, content_type={content_type!r})"
    )
