"""Render a signed report to auditor-recognizable Markdown.

The report ties each requirement to its spec citation, the record evidence, the
deterministic verdict, and the engineer's disposition — plus the approver,
timestamp, and the audit trail. (PDF export is deferred to M8 polish.)
"""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from app.check.types import Citation, VerdictStatus
from app.report.sign_off import OVERRIDE, Disposition, SignedReport

_DISCLAIMER = (
    "Illustrative tool on synthetic documents — not a quality system of record. "
    "A qualified engineer signs every disposition."
)

_LABELS = {
    VerdictStatus.COMPLIANT: "Compliant",
    VerdictStatus.NON_COMPLIANT: "Non-compliant",
    VerdictStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
}


def _fmt_citation(citation: Citation) -> str:
    location = citation.source_location or "unlocated"
    return f'"{citation.source_text}" ({location})'


def _fmt_record(citations: tuple) -> str:
    if not citations:
        return "—"
    return "; ".join(_fmt_citation(c) for c in citations)


def _clause_section(disp: Disposition) -> list[str]:
    clause = disp.clause
    req = clause.requirement
    flag = "  ·  ⚠ flagged for review" if clause.needs_review else ""
    lines = [
        f"### {req.id} — {req.description}",
        f"- **Spec citation:** {_fmt_citation(req.citation)}",
        f"- **Record evidence:** {_fmt_record(clause.record_citations)}",
        f"- **Verdict:** {_LABELS[clause.status]}  ·  "
        f"**Disposition:** {_LABELS[disp.final_status]} ({disp.action})",
        f"- **Extraction confidence:** {req.citation.confidence:.2f}{flag}",
    ]
    if disp.is_override:
        lines.append(f"- **Override justification:** {disp.note}")
    lines.append("")
    return lines


def render_markdown(signed: SignedReport) -> str:
    lines = [
        "# Spec Compliance Report",
        "",
        f"**Approver:** {signed.approver}",
        f"**Signed at:** {signed.signed_at.isoformat()}",
        "",
        f"> {_DISCLAIMER}",
        "",
        "## Summary",
        f"- {_LABELS[VerdictStatus.COMPLIANT]}: {signed.count(VerdictStatus.COMPLIANT)}",
        f"- {_LABELS[VerdictStatus.NON_COMPLIANT]}: {signed.count(VerdictStatus.NON_COMPLIANT)}",
        f"- {_LABELS[VerdictStatus.INSUFFICIENT_EVIDENCE]}: "
        f"{signed.count(VerdictStatus.INSUFFICIENT_EVIDENCE)}",
        f"- Overrides: {signed.override_count}",
        "",
        "## Clauses",
        "",
    ]

    for disp in signed.dispositions:
        lines.extend(_clause_section(disp))

    lines.append("## Audit trail")
    for ev in signed.audit_trail:
        entry = (
            f"- {ev.timestamp.isoformat()} · {ev.approver} · {ev.requirement_id}: "
            f"{ev.action} ({_LABELS[ev.original_status]} → {_LABELS[ev.final_status]})"
        )
        if ev.action == OVERRIDE and ev.note:
            entry += f" — {ev.note}"
        lines.append(entry)

    return "\n".join(lines) + "\n"


def render_pdf(signed: SignedReport) -> bytes:
    """Render the same signed report as an auditor-friendly PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="Spec Compliance Report")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Spec Compliance Report", styles["Title"]),
        Paragraph(f"Approver: {escape(signed.approver)}", styles["Normal"]),
        Paragraph(f"Signed at: {signed.signed_at.isoformat()}", styles["Normal"]),
        Spacer(1, 8),
        Paragraph(f"<i>{escape(_DISCLAIMER)}</i>", styles["Normal"]),
        Spacer(1, 12),
        Paragraph(
            "Summary: "
            f"{signed.count(VerdictStatus.COMPLIANT)} compliant, "
            f"{signed.count(VerdictStatus.NON_COMPLIANT)} non-compliant, "
            f"{signed.count(VerdictStatus.INSUFFICIENT_EVIDENCE)} insufficient, "
            f"{signed.override_count} override(s).",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]

    rows = [["ID", "Requirement", "Verdict", "Disposition"]]
    for disp in signed.dispositions:
        rows.append(
            [
                disp.requirement.id,
                Paragraph(escape(disp.requirement.description), styles["Normal"]),
                _LABELS[disp.clause.status],
                _LABELS[disp.final_status] + (" (override)" if disp.is_override else ""),
            ]
        )
    table = Table(rows, colWidths=[40, 250, 110, 130], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14181f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e3e7ec")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f8fa")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Audit trail", styles["Heading3"]))
    for ev in signed.audit_trail:
        note = f" — {escape(ev.note)}" if (ev.action == OVERRIDE and ev.note) else ""
        transition = f"{_LABELS[ev.original_status]} &rarr; {_LABELS[ev.final_status]}"
        story.append(
            Paragraph(
                f"{ev.timestamp.isoformat()} · {escape(ev.approver)} · {ev.requirement_id}: "
                f"{ev.action} ({transition}){note}",
                styles["Normal"],
            )
        )

    doc.build(story)
    return buffer.getvalue()
