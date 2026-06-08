"""Views for the Upload → Requirements → Results → Report flow.

Two entry points share the same Results/Report screens:

* Samples (M4 corpus) run offline via ``run_sample`` — driven by ``sample_id``
  in the URL, re-run per screen, no API cost.
* Uploads run the live pipeline once (``analyze_documents``); the raw extractions
  are carried in hidden form fields so the sign-off round-trip rebuilds the
  report deterministically without re-calling the model. No server-side state.
"""

from datetime import UTC, datetime

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from app.check.types import (
    CategoricalRequirement,
    ConditionalRequirement,
    NumericRequirement,
    PresenceRequirement,
    TemporalRequirement,
    VerdictStatus,
)
from app.data.corpus import SAMPLES, get_sample, run_sample
from app.extract.observations import RecordExtraction
from app.extract.schemas import ExtractionResult
from app.pipeline import (
    analyze_documents,
    build_report_from_extractions,
    review_requirements,
)
from app.report.render import render_markdown, render_pdf
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

_OVERRIDE_CHOICES = [(s.value, _STATUS[s][0]) for s in VerdictStatus]

_CASE_BLURB = {
    "clean": "A clean, compliant traveler — everything within spec.",
    "obvious": "An obvious noncompliance — coating thickness over the limit.",
    "subtle": "A subtle noncompliance — coated just past the time-between-ops limit.",
    "missing": "A missing field — no thickness recorded (must not read 'compliant').",
}

# Hidden fields carried from an upload analysis through sign-off / export.
_CARRY_KEYS = ("spec_text", "record_text", "extraction", "record_extraction")


def _kind_label(requirement) -> str:
    return _KIND_LABELS.get(type(requirement), "Requirement")


def _status_view(status: VerdictStatus) -> dict:
    label, css = _STATUS[status]
    return {"label": label, "css": css, "value": status.value}


def _sample_or_404(sample_id: str):
    if sample_id not in SAMPLES:
        raise Http404(f"unknown sample {sample_id!r}")
    return get_sample(sample_id)


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


# --- landing -----------------------------------------------------------------


def index(request):
    return render(request, "index.html", _index_context())


def healthz(request):
    return JsonResponse({"status": "ok"})


# --- sample flow -------------------------------------------------------------


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


def _results_context(report, *, form_action, carry, back_url, back_label, subtitle, error=""):
    return {
        "rows": _clause_rows(report),
        "override_choices": _OVERRIDE_CHOICES,
        "form_action": form_action,
        "carry": carry,
        "back_url": back_url,
        "back_label": back_label,
        "subtitle": subtitle,
        "error": error,
    }


def results(request, sample_id):
    sample = _sample_or_404(sample_id)
    context = _results_context(
        run_sample(sample_id),
        form_action=reverse("report", args=[sample_id]),
        carry={},
        back_url=reverse("requirements", args=[sample_id]),
        back_label="Back",
        subtitle=f"{sample.spec_id} → {sample.record_id}",
    )
    return render(request, "results.html", context)


# --- sign-off + export (shared) ----------------------------------------------


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


def _download(content, content_type: str, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _finalize(request, report, *, report_action: str, filename_stem: str):
    """Apply decisions, sign off, and either export or render the report page.
    Returns (response, error). On a sign-off error, response is None."""
    requirements_list = [c.requirement for c in report.results]
    decisions = _parse_decisions(request.POST, requirements_list)
    approver = request.POST.get("approver", "").strip()
    try:
        signed = sign_off(
            report, decisions, approver=approver, signed_at=datetime.now(UTC)
        )
    except ValueError as exc:
        return None, str(exc)

    export = request.POST.get("export")
    if export == "md":
        return _download(
            render_markdown(signed), "text/markdown; charset=utf-8", f"{filename_stem}.md"
        ), None
    if export == "pdf":
        return _download(render_pdf(signed), "application/pdf", f"{filename_stem}.pdf"), None

    rows = [
        {
            "id": d.requirement.id,
            "description": d.requirement.description,
            "verdict": _status_view(d.clause.status),
            "disposition": _status_view(d.final_status),
            "is_override": d.is_override,
            "note": d.note,
        }
        for d in signed.dispositions
    ]
    carry = {k: v for k, v in request.POST.items() if k not in ("csrfmiddlewaretoken", "export")}
    context = {
        "signed": signed,
        "markdown": render_markdown(signed),
        "rows": rows,
        "trail": signed.audit_trail,
        "carry": carry,
        "report_action": report_action,
    }
    return render(request, "report.html", context), None


def report(request, sample_id):
    sample = _sample_or_404(sample_id)
    check_report = run_sample(sample_id)
    response, error = _finalize(
        request,
        check_report,
        report_action=reverse("report", args=[sample_id]),
        filename_stem=f"compliance-report-{sample_id}",
    )
    if error:
        context = _results_context(
            check_report,
            form_action=reverse("report", args=[sample_id]),
            carry={},
            back_url=reverse("requirements", args=[sample_id]),
            back_label="Back",
            subtitle=f"{sample.spec_id} → {sample.record_id}",
            error=error,
        )
        return render(request, "results.html", context, status=400)
    return response


# --- upload flow -------------------------------------------------------------


def _carry_from_analysis(analysis) -> dict:
    return {
        "spec_text": analysis.spec_text,
        "record_text": analysis.record_text,
        "extraction": analysis.extraction.model_dump_json(),
        "record_extraction": analysis.record_extraction.model_dump_json(),
    }


def _report_from_carry(post):
    extraction = ExtractionResult.model_validate_json(post["extraction"])
    record_extraction = RecordExtraction.model_validate_json(post["record_extraction"])
    return build_report_from_extractions(
        post["spec_text"], post["record_text"], extraction, record_extraction
    )


def analyze(request):
    if request.method != "POST":
        return render(request, "index.html", _index_context())

    spec_file = request.FILES.get("spec_file")
    record_file = request.FILES.get("record_file")
    if not spec_file or not record_file:
        context = _index_context("Choose both a spec and a record file.")
        return render(request, "index.html", context, status=400)
    if not settings.ANTHROPIC_API_KEY:
        return render(
            request,
            "index.html",
            _index_context("Set ANTHROPIC_API_KEY to analyze uploads — or try a sample above."),
            status=400,
        )

    try:
        analysis = analyze_documents(
            spec_file.read(),
            record_file.read(),
            spec_filename=spec_file.name,
            spec_content_type=spec_file.content_type,
            record_filename=record_file.name,
            record_content_type=record_file.content_type,
        )
    except Exception as exc:  # noqa: BLE001 - surface any extraction failure to the user
        return render(request, "index.html", _index_context(f"Analysis failed: {exc}"), status=502)

    report_obj = build_report_from_extractions(
        analysis.spec_text, analysis.record_text, analysis.extraction, analysis.record_extraction
    )
    context = _results_context(
        report_obj,
        form_action=reverse("analyze_report"),
        carry=_carry_from_analysis(analysis),
        back_url=reverse("index"),
        back_label="Start over",
        subtitle=f"{spec_file.name} → {record_file.name}",
    )
    return render(request, "results.html", context)


def analyze_report(request):
    try:
        report_obj = _report_from_carry(request.POST)
    except (KeyError, ValueError):
        context = _index_context("Lost the analysis — please re-upload.")
        return render(request, "index.html", context)

    response, error = _finalize(
        request,
        report_obj,
        report_action=reverse("analyze_report"),
        filename_stem="compliance-report",
    )
    if error:
        carry = {k: request.POST[k] for k in _CARRY_KEYS if k in request.POST}
        context = _results_context(
            report_obj,
            form_action=reverse("analyze_report"),
            carry=carry,
            back_url=reverse("index"),
            back_label="Start over",
            subtitle="Uploaded documents",
            error=error,
        )
        return render(request, "results.html", context, status=400)
    return response


def _index_context(error: str = "") -> dict:
    cards = [
        {
            "id": sid,
            "label": s.label,
            "spec_id": s.spec_id,
            "record_id": s.record_id,
            "blurb": _CASE_BLURB.get(s.label, ""),
        }
        for sid, s in SAMPLES.items()
    ]
    return {"cards": cards, "upload_enabled": bool(settings.ANTHROPIC_API_KEY), "error": error}
