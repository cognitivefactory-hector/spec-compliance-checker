"""Check pipeline: review gate -> deterministic check -> clause-by-clause report.

The review gate runs BEFORE checking (SPEC §4.3): an extraction that is
low-confidence or whose citation couldn't be located is flagged for the
engineer, so a missed or invented requirement is caught up front. The report
ties each requirement to its verdict and both citations (spec clause + record
field). ``check_documents`` wires ingest + extraction onto this core.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.check.types import Citation, Requirement, Verdict, VerdictStatus
from app.check.verdict import evaluate

DEFAULT_MIN_CONFIDENCE = 0.7


@dataclass(frozen=True)
class ReviewItem:
    requirement: Requirement
    needs_review: bool
    reason: str  # "" when not flagged


def review_requirements(
    requirements: list[Requirement], *, min_confidence: float = DEFAULT_MIN_CONFIDENCE
) -> list[ReviewItem]:
    """Flag each requirement the engineer should review before checking."""
    items = []
    for req in requirements:
        cite = req.citation
        if cite.source_location is None:
            items.append(ReviewItem(req, True, "citation could not be located in the spec"))
        elif cite.confidence < min_confidence:
            items.append(
                ReviewItem(req, True, f"low extraction confidence ({cite.confidence:.2f})")
            )
        else:
            items.append(ReviewItem(req, False, ""))
    return items


@dataclass(frozen=True)
class ClauseResult:
    requirement: Requirement
    verdict: Verdict
    needs_review: bool
    review_reason: str

    @property
    def status(self) -> VerdictStatus:
        return self.verdict.status

    @property
    def spec_citation(self) -> Citation:
        return self.requirement.citation

    @property
    def record_citations(self) -> tuple:
        return self.verdict.record_citations


@dataclass(frozen=True)
class CheckReport:
    results: list[ClauseResult]

    @property
    def needs_review_count(self) -> int:
        return sum(1 for r in self.results if r.needs_review)

    def count(self, status: VerdictStatus) -> int:
        return sum(1 for r in self.results if r.status is status)


def build_report(
    requirements: list[Requirement],
    observations: list,
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> CheckReport:
    """Apply the review gate and evaluate each (requirement, observation) pair
    into a cited, clause-by-clause report. Pure — no I/O."""
    review = review_requirements(requirements, min_confidence=min_confidence)
    results = [
        ClauseResult(
            item.requirement,
            evaluate(item.requirement, obs),
            item.needs_review,
            item.reason,
        )
        for item, obs in zip(review, observations, strict=True)
    ]
    return CheckReport(results)


@dataclass(frozen=True)
class AnalysisResult:
    """The LLM output of one analysis: the parsed document texts plus the raw,
    serializable extractions. Carrying these lets the sign-off round-trip rebuild
    the report deterministically without re-calling the model."""

    spec_text: str
    record_text: str
    extraction: object  # ExtractionResult
    record_extraction: object  # RecordExtraction


def analyze_documents(
    spec,
    record,
    *,
    client=None,
    model: str | None = None,
    spec_filename: str | None = None,
    spec_content_type: str | None = None,
    record_filename: str | None = None,
    record_content_type: str | None = None,
) -> AnalysisResult:
    """The two LLM calls: ingest both documents and extract the spec requirements
    and the record observations as raw structured results."""
    from app.extract.extract import extract_requirements_result, to_requirements
    from app.extract.observations import extract_observations_result
    from app.ingest.parse import parse

    spec_parsed = parse(spec, filename=spec_filename, content_type=spec_content_type)
    record_parsed = parse(record, filename=record_filename, content_type=record_content_type)

    extraction = extract_requirements_result(spec_parsed, client=client, model=model)
    requirements = to_requirements(extraction, spec_parsed)
    record_extraction = extract_observations_result(
        record_parsed, requirements, client=client, model=model
    )
    return AnalysisResult(
        spec_parsed.full_text, record_parsed.full_text, extraction, record_extraction
    )


def build_report_from_extractions(
    spec_text: str,
    record_text: str,
    extraction,
    record_extraction,
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> CheckReport:
    """Rebuild a report from already-extracted results — no LLM. Used by the
    sample demo and by the upload sign-off round-trip."""
    from app.extract.extract import to_requirements
    from app.extract.observations import to_observations
    from app.ingest.parse import parse_text

    spec_parsed = parse_text(spec_text)
    record_parsed = parse_text(record_text)
    requirements = to_requirements(extraction, spec_parsed)
    observations = to_observations(record_extraction, requirements, record_parsed)
    return build_report(requirements, observations, min_confidence=min_confidence)


def check_documents(
    spec,
    record,
    *,
    client=None,
    model: str | None = None,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    spec_filename: str | None = None,
    spec_content_type: str | None = None,
    record_filename: str | None = None,
    record_content_type: str | None = None,
) -> CheckReport:
    """End-to-end: analyze both documents (two LLM calls) then run the review
    gate + deterministic check."""
    analysis = analyze_documents(
        spec,
        record,
        client=client,
        model=model,
        spec_filename=spec_filename,
        spec_content_type=spec_content_type,
        record_filename=record_filename,
        record_content_type=record_content_type,
    )
    return build_report_from_extractions(
        analysis.spec_text,
        analysis.record_text,
        analysis.extraction,
        analysis.record_extraction,
        min_confidence=min_confidence,
    )
