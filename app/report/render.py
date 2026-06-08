"""Render a signed report to auditor-recognizable Markdown.

The report ties each requirement to its spec citation, the record evidence, the
deterministic verdict, and the engineer's disposition — plus the approver,
timestamp, and the audit trail. (PDF export is deferred to M8 polish.)
"""

from __future__ import annotations

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
