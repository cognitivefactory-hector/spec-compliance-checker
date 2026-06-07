"""Synthetic corpus (M4).

Drives the fictional spec/record pairs end-to-end through the deterministic
path: parse (M2) -> map extracted requirements + locate citations (M3) ->
evaluate (M1). No live API. The crown-jewel cases — the subtle catch and the
missing field — are asserted explicitly.
"""

import pytest

from app.check.types import VerdictStatus
from app.check.verdict import evaluate
from app.data.corpus import SAMPLES, get_sample

EXPECTED_IDS = {"coating-clean", "coating-obvious", "coating-subtle", "coating-missing"}


def test_corpus_loads_with_fixed_sample_ids():
    assert set(SAMPLES) == EXPECTED_IDS


def test_spec_citations_resolve_through_extraction_and_locate():
    """Every verbatim quote in the corpus is a real substring of its spec, so
    to_requirements + locate produce a resolved citation (exercises M2 + M3)."""
    for sample in SAMPLES.values():
        for req in sample.requirements():
            assert req.citation.source_location is not None, (
                sample.spec_id,
                req.citation.source_text,
            )


@pytest.mark.parametrize("sample_id", sorted(EXPECTED_IDS))
def test_each_sample_produces_its_expected_verdicts(sample_id):
    sample = get_sample(sample_id)
    reqs = sample.requirements()
    assert len(reqs) == len(sample.checks)
    for req, check in zip(reqs, sample.checks, strict=True):
        verdict = evaluate(req, check.observation)
        assert verdict.status is check.expected, (sample_id, req.id, verdict.reason)


def test_obvious_noncompliance_is_flagged():
    sample = get_sample("coating-obvious")
    statuses = [
        evaluate(r, c.observation).status
        for r, c in zip(sample.requirements(), sample.checks, strict=True)
    ]
    assert VerdictStatus.NON_COMPLIANT in statuses


def test_subtle_noncompliance_is_caught():
    sample = get_sample("coating-subtle")
    statuses = [
        evaluate(r, c.observation).status
        for r, c in zip(sample.requirements(), sample.checks, strict=True)
    ]
    assert VerdictStatus.NON_COMPLIANT in statuses


def test_missing_field_is_insufficient_never_compliant():
    """The asymmetry, through the corpus: a missing thickness never reads compliant."""
    sample = get_sample("coating-missing")
    reqs = sample.requirements()
    r1_status = evaluate(reqs[0], sample.checks[0].observation).status
    assert r1_status is VerdictStatus.INSUFFICIENT_EVIDENCE
    assert r1_status is not VerdictStatus.COMPLIANT
