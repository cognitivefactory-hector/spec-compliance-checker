"""Flow smoke tests (M7): pick a sample -> requirements -> results -> report.

The plan demonstrates the UI via the recording, not exhaustive coverage — these
cover that the flow works and the asymmetry is visible (subtle catch +
insufficient evidence), and that sign-off/override/export behave.
"""

from django.urls import reverse

from app.data.corpus import get_sample


def test_landing_lists_samples_and_carries_disclaimer(client):
    body = client.get(reverse("index")).content.decode()
    assert "coating-subtle" in body or "Review" in body
    assert "FPS-1000" in body
    assert "not a quality system of record" in body


def test_requirements_page_shows_cited_list_and_flags_low_confidence(client):
    body = client.get(reverse("requirements", args=["coating-subtle"])).content.decode()
    assert "coating thickness range" in body
    assert "Coating thickness shall be between 0.50 and 1.50 mm." in body  # the citation
    assert "flagged for review" in body.lower() or "review:" in body.lower()  # R5 conditional


def test_results_page_shows_the_subtle_catch(client):
    body = client.get(reverse("results", args=["coating-subtle"])).content.decode()
    assert "Non-compliant" in body


def test_results_page_shows_insufficient_evidence_for_missing_field(client):
    body = client.get(reverse("results", args=["coating-missing"])).content.decode()
    assert "Insufficient evidence" in body


def test_report_confirm_all_is_signed_by_the_approver(client):
    resp = client.post(reverse("report", args=["coating-clean"]), {"approver": "H. Garza"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "H. Garza" in body
    assert "Audit trail" in body


def test_report_requires_an_approver(client):
    resp = client.post(reverse("report", args=["coating-clean"]), {})
    assert resp.status_code == 400
    assert "approver" in resp.content.decode().lower()


def test_override_clears_the_subtle_catch_with_justification(client):
    resp = client.post(
        reverse("report", args=["coating-subtle"]),
        {
            "approver": "H. Garza",
            "disp_R2": "compliant",
            "note_R2": "Within soak tolerance per FPS-1000 §7; cleared with justification.",
        },
    )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Within soak tolerance" in body  # the override note
    assert "1 override" in body


def test_override_without_a_note_is_rejected(client):
    resp = client.post(
        reverse("report", args=["coating-subtle"]),
        {"approver": "H. Garza", "disp_R2": "compliant"},
    )
    assert resp.status_code == 400


def test_markdown_export_downloads_a_file(client):
    resp = client.post(
        reverse("report", args=["coating-clean"]),
        {"approver": "H. Garza", "export": "md"},
    )
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/markdown")
    assert "attachment" in resp["Content-Disposition"]
    assert "not a quality system of record" in resp.content.decode()


def test_pdf_export_downloads_a_pdf(client):
    resp = client.post(
        reverse("report", args=["coating-clean"]),
        {"approver": "H. Garza", "export": "pdf"},
    )
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


# --- upload flow -------------------------------------------------------------


def test_landing_upload_is_disabled_without_an_api_key(client):
    # tests run with no ANTHROPIC_API_KEY set
    body = client.get(reverse("index")).content.decode()
    assert "ANTHROPIC_API_KEY" in body


def test_analyze_requires_both_files(client):
    resp = client.post(reverse("analyze"), {})
    assert resp.status_code == 400
    assert "both" in resp.content.decode().lower()


def _carry_payload(sample_id):
    sample = get_sample(sample_id)
    return {
        "spec_text": sample.spec_text,
        "record_text": sample.record_text,
        "extraction": sample.extraction.model_dump_json(),
        "record_extraction": sample.record_extraction.model_dump_json(),
    }


def test_analyze_report_signs_an_uploaded_analysis_round_trip(client):
    """The sign-off round-trip rebuilds the report from carried extractions — no LLM."""
    payload = _carry_payload("coating-subtle")
    payload["approver"] = "H. Garza"
    resp = client.post(reverse("analyze_report"), payload)
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "H. Garza" in body
    assert "Audit trail" in body


def test_analyze_report_pdf_export_round_trip(client):
    payload = _carry_payload("coating-clean")
    payload["approver"] = "H. Garza"
    payload["export"] = "pdf"
    resp = client.post(reverse("analyze_report"), payload)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_analyze_report_requires_an_approver(client):
    resp = client.post(reverse("analyze_report"), _carry_payload("coating-clean"))
    assert resp.status_code == 400
