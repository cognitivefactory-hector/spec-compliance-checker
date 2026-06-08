"""Report, sign-off, and audit trail (M6).

Nothing is dispositioned without sign-off; every clause is confirmed or
overridden, and overrides (with justification) are recorded in the audit trail.
The rendered report is auditor-recognizable: approver, timestamp, clause-by-
clause citations, verdict, disposition.
"""

from datetime import datetime

import pytest

from app.check.types import VerdictStatus
from app.data.corpus import get_sample
from app.pipeline import build_report
from app.report.render import render_markdown, render_pdf
from app.report.sign_off import CONFIRM, OVERRIDE, Decision, sign_off

SIGNED_AT = datetime(2026, 6, 7, 14, 30)


def _report(sample_id="coating-subtle"):
    sample = get_sample(sample_id)
    return build_report(sample.requirements(), [c.observation for c in sample.checks])


def _confirm_all(report):
    return [Decision(CONFIRM) for _ in report.results]


def test_confirm_keeps_the_verdict_status():
    report = _report()
    signed = sign_off(report, _confirm_all(report), approver="H. Garza", signed_at=SIGNED_AT)
    for clause, disp in zip(report.results, signed.dispositions, strict=True):
        assert disp.final_status is clause.status
        assert disp.action == CONFIRM


def test_override_sets_final_status_and_requires_a_note():
    report = _report()
    decisions = _confirm_all(report)
    decisions[1] = Decision(
        OVERRIDE,
        final_status=VerdictStatus.COMPLIANT,
        note="Time exceedance dispositioned: within material soak tolerance per FPS-1000 §7.",
    )
    signed = sign_off(report, decisions, approver="H. Garza", signed_at=SIGNED_AT)
    assert signed.dispositions[1].final_status is VerdictStatus.COMPLIANT
    assert signed.dispositions[1].is_override


def test_override_without_a_note_is_rejected():
    report = _report()
    decisions = _confirm_all(report)
    decisions[1] = Decision(OVERRIDE, final_status=VerdictStatus.COMPLIANT, note="   ")
    with pytest.raises(ValueError):
        sign_off(report, decisions, approver="H. Garza", signed_at=SIGNED_AT)


def test_override_without_a_final_status_is_rejected():
    report = _report()
    decisions = _confirm_all(report)
    decisions[1] = Decision(OVERRIDE, note="justified")
    with pytest.raises(ValueError):
        sign_off(report, decisions, approver="H. Garza", signed_at=SIGNED_AT)


def test_sign_off_requires_an_approver():
    report = _report()
    with pytest.raises(ValueError):
        sign_off(report, _confirm_all(report), approver="  ", signed_at=SIGNED_AT)


def test_one_decision_required_per_clause():
    report = _report()
    with pytest.raises(ValueError):
        sign_off(report, [Decision(CONFIRM)], approver="H. Garza", signed_at=SIGNED_AT)


def test_audit_trail_records_every_clause_with_original_and_final():
    report = _report()
    decisions = _confirm_all(report)
    decisions[1] = Decision(
        OVERRIDE, final_status=VerdictStatus.COMPLIANT, note="dispositioned with justification"
    )
    signed = sign_off(report, decisions, approver="H. Garza", signed_at=SIGNED_AT)

    assert len(signed.audit_trail) == len(report.results)
    override_events = [e for e in signed.audit_trail if e.action == OVERRIDE]
    assert len(override_events) == 1
    ev = override_events[0]
    assert ev.original_status is VerdictStatus.NON_COMPLIANT  # the subtle temporal catch
    assert ev.final_status is VerdictStatus.COMPLIANT
    assert ev.approver == "H. Garza"
    assert ev.timestamp == SIGNED_AT
    assert signed.override_count == 1


# --- rendering ---------------------------------------------------------------


def _signed_with_override():
    report = _report()
    decisions = _confirm_all(report)
    decisions[1] = Decision(
        OVERRIDE,
        final_status=VerdictStatus.COMPLIANT,
        note="Soak tolerance applies; cleared with engineering justification.",
    )
    return report, sign_off(report, decisions, approver="H. Garza", signed_at=SIGNED_AT)


def test_markdown_report_is_auditor_recognizable():
    report, signed = _signed_with_override()
    md = render_markdown(signed)

    # header: approver, timestamp, disclaimer
    assert "H. Garza" in md
    assert SIGNED_AT.isoformat() in md
    assert "not a quality system of record" in md

    # clause-by-clause: requirement + spec citation + record-evidence label + verdict
    for clause in report.results:
        assert clause.requirement.id in md
        assert clause.requirement.description in md
        assert clause.requirement.citation.source_text in md
    assert "Record evidence" in md


def test_markdown_report_shows_override_justification_and_audit_trail():
    _, signed = _signed_with_override()
    md = render_markdown(signed)
    assert "Soak tolerance applies" in md  # the override note
    assert "Audit trail" in md
    assert "override" in md.lower()


def test_markdown_report_summarizes_counts():
    _, signed = _signed_with_override()
    md = render_markdown(signed)
    assert "Summary" in md
    # after the override, the subtle sample's one non-compliant clause is cleared
    assert signed.count(VerdictStatus.NON_COMPLIANT) == 0


def test_pdf_export_returns_a_pdf_document():
    _, signed = _signed_with_override()
    pdf = render_pdf(signed)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000  # a real, non-trivial document
