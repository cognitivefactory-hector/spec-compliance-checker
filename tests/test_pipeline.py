"""Review gate + check pipeline (M5).

The gate runs BEFORE checking: a low-confidence or unlocatable extraction is
flagged for the engineer to review. The report is clause-by-clause and carries
both citations (spec clause + record field). Corpus drives the end-to-end path.
"""

from datetime import timedelta

from app.check.types import (
    Citation,
    ConditionalObservation,
    IntervalObservation,
    NumericRequirement,
    Observation,
    VerdictStatus,
)
from app.check.verdict import evaluate
from app.data.corpus import SPEC_EXTRACTION, SPEC_TEXT, get_sample
from app.extract.observations import ExtractedObservation, RecordExtraction, to_observations
from app.extract.schemas import ExtractionResult
from app.ingest.parse import parse_text
from app.pipeline import (
    build_report,
    build_report_from_extractions,
    check_documents,
    review_requirements,
)


def _req(confidence: float, location: str | None = "p.1 L1") -> NumericRequirement:
    return NumericRequirement(
        "R1", "coating thickness", Citation("q", location, confidence), 0.0, 1.5, "mm"
    )


# --- review gate -------------------------------------------------------------


def test_low_confidence_requirement_is_flagged():
    items = review_requirements([_req(0.4)], min_confidence=0.7)
    assert items[0].needs_review is True


def test_confident_located_requirement_is_not_flagged():
    items = review_requirements([_req(0.95)], min_confidence=0.7)
    assert items[0].needs_review is False


def test_unlocatable_citation_is_always_flagged_even_when_confident():
    items = review_requirements([_req(0.99, location=None)], min_confidence=0.7)
    assert items[0].needs_review is True


# --- report ------------------------------------------------------------------


def test_build_report_produces_clause_by_clause_verdicts_for_a_sample():
    sample = get_sample("coating-subtle")
    reqs = sample.requirements()
    observations = [c.observation for c in sample.checks]
    report = build_report(reqs, observations)
    assert len(report.results) == len(reqs)
    assert [r.status for r in report.results] == [c.expected for c in sample.checks]
    for r in report.results:
        assert r.spec_citation is not None  # every clause cites the spec


def test_report_counts_summarize_statuses():
    sample = get_sample("coating-missing")
    report = build_report(sample.requirements(), [c.observation for c in sample.checks])
    assert report.count(VerdictStatus.INSUFFICIENT_EVIDENCE) >= 1


def test_low_confidence_clause_is_marked_needs_review_in_report():
    report = build_report([_req(0.3)], [Observation(value=0.5, units="mm")])
    assert report.results[0].needs_review is True
    assert report.needs_review_count == 1


# --- record-side extraction --------------------------------------------------


def test_record_extraction_schema_has_no_verdict_field():
    fields = set(ExtractedObservation.model_fields)
    assert not ({"verdict", "status", "compliant", "result"} & fields)


def _clean_record_extraction() -> RecordExtraction:
    return RecordExtraction(
        observations=[
            ExtractedObservation(
                requirement_id="R1",
                record_quote="Coating thickness measured: 1.20 mm",
                value="1.20",
                units="mm",
            ),
            ExtractedObservation(
                requirement_id="R2",
                record_quote="Coating operation started: 2026-03-01 12:00",
                start_time="2026-03-01T09:00",
                end_time="2026-03-01T12:00",
            ),
            ExtractedObservation(
                requirement_id="R3",
                record_quote="Substrate material: Ti-6Al-4V",
                value="Ti-6Al-4V",
            ),
            ExtractedObservation(
                requirement_id="R4",
                record_quote="Operator certification number: CERT-7782",
                value="CERT-7782",
            ),
            ExtractedObservation(
                requirement_id="R5",
                record_quote="Substrate material: Ti-6Al-4V",
                condition_value="Ti-6Al-4V",
                consequent_value="1.20",
                consequent_units="mm",
                consequent_quote="Coating thickness measured: 1.20 mm",
            ),
        ]
    )


def test_to_observations_builds_typed_observations_with_record_citations():
    sample = get_sample("coating-clean")
    reqs = sample.requirements()
    record_parsed = parse_text(sample.record_text)

    obs = to_observations(_clean_record_extraction(), reqs, record_parsed)

    assert len(obs) == 5
    assert isinstance(obs[0], Observation) and obs[0].value == 1.20 and obs[0].units == "mm"
    assert obs[0].citation.source_location is not None  # located in the record
    assert isinstance(obs[1], IntervalObservation)
    assert obs[1].end - obs[1].start == timedelta(hours=3)
    assert isinstance(obs[4], ConditionalObservation)
    assert obs[4].condition_value == "Ti-6Al-4V"
    assert obs[4].consequent.value == 1.20


def test_verdict_cites_both_spec_clause_and_record_field():
    sample = get_sample("coating-clean")
    reqs = sample.requirements()
    record_parsed = parse_text(sample.record_text)
    obs = to_observations(_clean_record_extraction(), reqs, record_parsed)

    verdict = evaluate(reqs[0], obs[0])
    assert verdict.requirement_citation.source_location is not None  # spec clause
    assert verdict.record_citations  # record field
    assert verdict.record_citations[0].source_location is not None


def test_missing_record_evidence_yields_a_missing_observation():
    """A requirement with no matching record evidence -> missing observation."""
    sample = get_sample("coating-clean")
    reqs = sample.requirements()
    record_parsed = parse_text(sample.record_text)
    obs = to_observations(RecordExtraction(observations=[]), reqs, record_parsed)
    assert evaluate(reqs[0], obs[0]).status is VerdictStatus.INSUFFICIENT_EVIDENCE


# --- end-to-end --------------------------------------------------------------


def _subtle_record_extraction() -> RecordExtraction:
    return RecordExtraction(
        observations=[
            ExtractedObservation(
                requirement_id="R1",
                record_quote="Coating thickness measured: 1.10 mm",
                value="1.10",
                units="mm",
            ),
            ExtractedObservation(
                requirement_id="R2",
                record_quote="Coating operation started: 2026-03-01 13:30",
                start_time="2026-03-01T09:00",
                end_time="2026-03-01T13:30",  # 4.5 h -> over the 4 h limit
            ),
            ExtractedObservation(
                requirement_id="R3",
                record_quote="Substrate material: Ti-6Al-4V",
                value="Ti-6Al-4V",
            ),
            ExtractedObservation(
                requirement_id="R4",
                record_quote="Operator certification number: CERT-7782",
                value="CERT-7782",
            ),
            ExtractedObservation(
                requirement_id="R5",
                record_quote="Substrate material: Ti-6Al-4V",
                condition_value="Ti-6Al-4V",
                consequent_value="1.10",
                consequent_units="mm",
                consequent_quote="Coating thickness measured: 1.10 mm",
            ),
        ]
    )


def test_check_documents_end_to_end_catches_the_subtle_noncompliance():
    sample = get_sample("coating-subtle")
    record_extraction = _subtle_record_extraction()

    class _FakeMessages:
        def parse(self, **kwargs):
            out = ExtractionResult if kwargs["output_format"] is ExtractionResult else None

            class _Resp:
                parsed_output = SPEC_EXTRACTION if out is ExtractionResult else record_extraction

            return _Resp()

    class _FakeClient:
        messages = _FakeMessages()

    report = check_documents(
        SPEC_TEXT, sample.record_text, client=_FakeClient(), model="claude-sonnet-4-6"
    )
    assert [r.status for r in report.results] == [c.expected for c in sample.checks]
    assert report.count(VerdictStatus.NON_COMPLIANT) == 1  # the temporal catch


def test_build_report_from_extractions_rebuilds_without_the_llm():
    sample = get_sample("coating-subtle")
    report = build_report_from_extractions(
        sample.spec_text, sample.record_text, sample.extraction, sample.record_extraction
    )
    assert [r.status for r in report.results] == [c.expected for c in sample.checks]
