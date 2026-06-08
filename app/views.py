"""Views for the Upload → Requirements → Results → Report flow.

The demo runs on the synthetic corpus (M4), driven by ``sample_id`` in the URL
and re-run per screen via the real pipeline offline (``run_sample``) — so there
is no fragile session state and no API cost. Confirm/override decisions are
carried in the POST form. (Custom upload via the live LLM lands in M8.)
"""

from datetime import UTC, datetime

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render

from app.check.types import (
    CategoricalRequirement,
    ConditionalRequirement,
    NumericRequirement,
    PresenceRequirement,
    TemporalRequirement,
    VerdictStatus,
)
from app.data.corpus import SAMPLES, get_sample, run_sample
from app.pipeline import review_requirements
from app.report.render import render_markdown
from app.report.sign_off import CONFIRM, OVERRIDE, Decision, sign_off

_KIND_LABELS = {
    NumericRequirement: "Numeric range",
    TemporalRequirement: "Time between operations",
    CategoricalRequirement: "Allowed values",
    PresenceRequirement: "Field present",
    ConditionalRequirement: "Conditional",
}

_STATUS = {
    VerdictStatus.COMPLIANT: ("Compliant", "ok"),
    VerdictStatus.NON_COMPLIANT: ("Non-compliant", "bad"),
    VerdictStatus.INSUFFICIENT_EVIDENCE: ("Insufficient evidence", "warn"),
}

# Override choices the engineer can pick (value, label).
_OVERRIDE_CHOICES = [(s.value, _STATUS[s][0]) for s in VerdictStatus]

_CASE_BLURB = {
    "clean": "A clean, compliant traveler — everything within spec.",
    "obvious": "An obvious noncompliance — coating thickness over the limit.",
    "subtle": "A subtle noncompliance — coated just past the time-between-ops limit.",
    "missing": "A missing field — no thickness recorded (must not read 'compliant').",
}


def _kind_label(requirement) -> str:
    return _KIND_LABELS.get(type(requirement), "Requirement")


def _status_view(status: VerdictStatus) -> dict:
    label, css = _STATUS[status]
    return {"label": label, "css": css, "value": status.value}


def _sample_or_404(sample_id: str):
    if sample_id not in SAMPLES:
        raise Http404(f"unknown sample {sample_id!r}")
    return get_sample(sample_id)


def index(request):
    cards = [
        {
            "id": sid,
            "label": sample.label,
            "spec_id": sample.spec_id,
            "record_id": sample.record_id,
            "blurb": _CASE_BLURB.get(sample.label, ""),
        }
        for sid, sample in SAMPLES.items()
    ]
    return render(request, "index.html", {"cards": cards})


def healthz(request):
    return JsonResponse({"status": "ok"})


def requirements(request, sample_id):
    sample = _sample_or_404(sample_id)
    items = review_requirements(sample.requirements())
    rows = [
        {
            "id": it.requirement.id,
            "description": it.requirement.description,
            "kind": _kind_label(it.requirement),
            "source_text": it.requirement.citation.source_text,
            "location": it.requirement.citation.source_location or "—",
            "confidence": it.requirement.citation.confidence,
            "needs_review": it.needs_review,
            "reason": it.reason,
        }
        for it in items
    ]
    context = {
        "sample_id": sample_id,
        "sample": sample,
        "rows": rows,
        "flagged": sum(1 for it in items if it.needs_review),
    }
    return render(request, "requirements.html", context)


def _clause_rows(report) -> list[dict]:
    rows = []
    for clause in report.results:
        req = clause.requirement
        rows.append(
            {
                "id": req.id,
                "description": req.description,
                "kind": _kind_label(req),
                "spec_text": req.citation.source_text,
                "spec_location": req.citation.source_location or "—",
                "confidence": req.citation.confidence,
                "needs_review": clause.needs_review,
                "status": _status_view(clause.status),
                "reason": clause.verdict.reason,
                "evidence": [
                    {"text": c.source_text, "location": c.source_location or "—"}
                    for c in clause.record_citations
                ],
            }
        )
    return rows


def _results_context(sample_id: str, *, error: str = "") -> dict:
    sample = _sample_or_404(sample_id)
    report = run_sample(sample_id)
    return {
        "sample_id": sample_id,
        "sample": sample,
        "rows": _clause_rows(report),
        "override_choices": _OVERRIDE_CHOICES,
        "error": error,
    }


def results(request, sample_id):
    return render(request, "results.html", _results_context(sample_id))


def _parse_decisions(post, requirements_list) -> list[Decision]:
    decisions = []
    for req in requirements_list:
        choice = post.get(f"disp_{req.id}", CONFIRM)
        if choice == CONFIRM:
            decisions.append(Decision(CONFIRM))
            continue
        try:
            status = VerdictStatus(choice)
        except ValueError:
            status = None
        note = post.get(f"note_{req.id}", "")
        decisions.append(Decision(OVERRIDE, final_status=status, note=note))
    return decisions


def report(request, sample_id):
    sample = _sample_or_404(sample_id)
    check_report = run_sample(sample_id)
    requirements_list = [c.requirement for c in check_report.results]
    decisions = _parse_decisions(request.POST, requirements_list)
    approver = request.POST.get("approver", "").strip()

    try:
        signed = sign_off(
            check_report, decisions, approver=approver, signed_at=datetime.now(UTC)
        )
    except ValueError as exc:
        context = _results_context(sample_id, error=str(exc))
        return render(request, "results.html", context, status=400)

    markdown = render_markdown(signed)

    if request.POST.get("export") == "md":
        response = HttpResponse(markdown, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="compliance-report-{sample_id}.md"'
        return response

    rows = []
    for disp in signed.dispositions:
        rows.append(
            {
                "id": disp.requirement.id,
                "description": disp.requirement.description,
                "verdict": _status_view(disp.clause.status),
                "disposition": _status_view(disp.final_status),
                "is_override": disp.is_override,
                "note": disp.note,
            }
        )
    carry = {k: v for k, v in request.POST.items() if k not in ("csrfmiddlewaretoken", "export")}
    context = {
        "sample_id": sample_id,
        "sample": sample,
        "signed": signed,
        "markdown": markdown,
        "rows": rows,
        "trail": signed.audit_trail,
        "carry": carry,
    }
    return render(request, "report.html", context)
