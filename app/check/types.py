"""Typed requirement model and verdict types — pure data, no logic.

A requirement is extracted (and cited) from the spec. An observation is the
evidence pulled (and cited) from the production record. The deterministic
evaluators in ``verdict.py`` turn a (requirement, observation) pair into a
``Verdict``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any


class VerdictStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class Citation:
    """Where a claim comes from — verbatim text plus a locator. ``confidence``
    is the extractor's confidence; deterministic verdicts don't depend on it,
    but it drives the human review gate (M5)."""

    source_text: str
    source_location: str
    confidence: float = 1.0


@dataclass(frozen=True)
class Requirement:
    """Base requirement: identity plus the spec citation it was extracted from."""

    id: str
    description: str
    citation: Citation


@dataclass(frozen=True)
class NumericRequirement(Requirement):
    """A measured value must fall within [min, max]. Either bound may be None
    for a one-sided limit. ``units`` must match the observation's units."""

    min: float | None = None
    max: float | None = None
    units: str | None = None


@dataclass(frozen=True)
class TemporalRequirement(Requirement):
    """The gap between two named operations must fall within [min_gap, max_gap].
    Either bound may be None. The record supplies the two timestamps."""

    from_op: str = ""
    to_op: str = ""
    max_gap: timedelta | None = None
    min_gap: timedelta | None = None


@dataclass(frozen=True)
class CategoricalRequirement(Requirement):
    """The recorded value must be one of an allowed set (e.g. material, cert)."""

    allowed_values: tuple = ()


@dataclass(frozen=True)
class PresenceRequirement(Requirement):
    """A named field must be recorded and non-empty. Absence is a definite
    failure of this requirement (NON_COMPLIANT), not 'insufficient'."""

    field: str = ""


@dataclass(frozen=True)
class Observation:
    """Scalar evidence from the record (numeric / categorical / presence).

    ``value is None`` means the field was absent from the (parsed) record —
    evaluators must never read that as COMPLIANT.
    """

    value: Any | None = None
    units: str | None = None
    citation: Citation | None = None


@dataclass(frozen=True)
class Condition:
    """A predicate over a record value: met when the observed condition value
    is one of ``trigger_values``."""

    trigger_values: tuple = ()
    description: str = ""


@dataclass(frozen=True)
class ConditionalRequirement(Requirement):
    """If ``condition`` is met, ``consequent`` must hold. If not met, the
    requirement is satisfied vacuously (the rule doesn't apply)."""

    condition: Condition = None
    consequent: Requirement = None


@dataclass(frozen=True)
class IntervalObservation:
    """Temporal evidence: the timestamps of two operations from the record.
    A None timestamp means that operation's time was absent — evaluators must
    never read that as COMPLIANT."""

    start: datetime | None = None
    end: datetime | None = None
    start_citation: Citation | None = None
    end_citation: Citation | None = None


@dataclass(frozen=True)
class ConditionalObservation:
    """Evidence for a conditional requirement: the value that decides whether
    the condition is met, plus the observation for the consequent requirement.
    ``condition_value is None`` means we can't tell if the rule applies."""

    condition_value: Any | None = None
    consequent: Any | None = None  # Observation | IntervalObservation for the consequent
    condition_citation: Citation | None = None


@dataclass(frozen=True)
class Verdict:
    """The result of checking one requirement against the record. Carries the
    citations that make it auditable: the spec clause and the record field(s)."""

    status: VerdictStatus
    reason: str
    requirement_citation: Citation | None = None
    record_citations: tuple[Citation, ...] = ()
