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
    """End-to-end: ingest both documents, extract requirements (spec) and cited
    observations (record), then run the review gate + deterministic check."""
    from app.extract.extract import extract_requirements
    from app.extract.observations import extract_observations
    from app.ingest.parse import parse

    spec_parsed = parse(spec, filename=spec_filename, content_type=spec_content_type)
    record_parsed = parse(record, filename=record_filename, content_type=record_content_type)

    requirements = extract_requirements(spec_parsed, client=client, model=model)
    observations = extract_observations(record_parsed, requirements, client=client, model=model)
    return build_report(requirements, observations, min_confidence=min_confidence)
