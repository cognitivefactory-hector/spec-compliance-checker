"""Flow smoke tests (M7): pick a sample -> requirements -> results -> report.

The plan demonstrates the UI via the recording, not exhaustive coverage — these
cover that the flow works and the asymmetry is visible (subtle catch +
insufficient evidence), and that sign-off/override/export behave.
"""

from django.urls import reverse


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
