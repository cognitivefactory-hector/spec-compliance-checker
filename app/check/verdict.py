"""Deterministic verdict evaluators — the safety core.

Pure functions: ``evaluate(requirement, observation) -> Verdict``, with no I/O,
so they are reproducible (the auditability argument) and trivially testable.

The encoded asymmetry: when the evidence is missing or can't be compared, the
verdict is INSUFFICIENT_EVIDENCE — never COMPLIANT. We accept more false
positives (an engineer's review) to avoid the costly false negative.
"""

from __future__ import annotations

from datetime import timedelta

from app.check.types import (
    CategoricalRequirement,
    Citation,
    ConditionalObservation,
    ConditionalRequirement,
    IntervalObservation,
    NumericRequirement,
    Observation,
    PresenceRequirement,
    Requirement,
    TemporalRequirement,
    Verdict,
    VerdictStatus,
)


def evaluate(requirement: Requirement, observation) -> Verdict:
    """Dispatch a requirement to its deterministic evaluator."""
    if isinstance(requirement, NumericRequirement):
        return _evaluate_numeric(requirement, observation)
    if isinstance(requirement, TemporalRequirement):
        return _evaluate_temporal(requirement, observation)
    if isinstance(requirement, CategoricalRequirement):
        return _evaluate_categorical(requirement, observation)
    if isinstance(requirement, PresenceRequirement):
        return _evaluate_presence(requirement, observation)
    if isinstance(requirement, ConditionalRequirement):
        return _evaluate_conditional(requirement, observation)
    raise TypeError(f"no evaluator for requirement type {type(requirement).__name__}")


def _cites(*citations: Citation | None) -> tuple:
    return tuple(c for c in citations if c is not None)


def _evaluate_numeric(req: NumericRequirement, obs: Observation) -> Verdict:
    cites = _cites(obs.citation)

    if obs.value is None:
        return Verdict(
            VerdictStatus.INSUFFICIENT_EVIDENCE,
            "no measured value found in the record",
            req.citation,
            cites,
        )

    if req.units is not None and obs.units != req.units:
        return Verdict(
            VerdictStatus.INSUFFICIENT_EVIDENCE,
            f"unit mismatch: requirement is in {req.units!r}, record is in {obs.units!r} "
            "(no silent conversion)",
            req.citation,
            cites,
        )

    if req.min is not None and obs.value < req.min:
        return Verdict(
            VerdictStatus.NON_COMPLIANT,
            f"{obs.value} {obs.units or ''}".strip() + f" is below minimum {req.min}",
            req.citation,
            cites,
        )

    if req.max is not None and obs.value > req.max:
        return Verdict(
            VerdictStatus.NON_COMPLIANT,
            f"{obs.value} {obs.units or ''}".strip() + f" is above maximum {req.max}",
            req.citation,
            cites,
        )

    return Verdict(
        VerdictStatus.COMPLIANT,
        f"{obs.value} {obs.units or ''}".strip() + " is within limits",
        req.citation,
        cites,
    )


def _evaluate_temporal(req: TemporalRequirement, obs: IntervalObservation) -> Verdict:
    cites = _cites(obs.start_citation, obs.end_citation)

    if obs.start is None or obs.end is None:
        return Verdict(
            VerdictStatus.INSUFFICIENT_EVIDENCE,
            f"missing timestamp for {req.from_op!r} or {req.to_op!r} in the record",
            req.citation,
            cites,
        )

    gap = obs.end - obs.start
    if gap < timedelta(0):
        return Verdict(
            VerdictStatus.INSUFFICIENT_EVIDENCE,
            f"timestamps are out of order: {req.to_op!r} precedes {req.from_op!r}",
            req.citation,
            cites,
        )

    if req.max_gap is not None and gap > req.max_gap:
        return Verdict(
            VerdictStatus.NON_COMPLIANT,
            f"gap {gap} between {req.from_op!r} and {req.to_op!r} exceeds maximum {req.max_gap}",
            req.citation,
            cites,
        )

    if req.min_gap is not None and gap < req.min_gap:
        return Verdict(
            VerdictStatus.NON_COMPLIANT,
            f"gap {gap} between {req.from_op!r} and {req.to_op!r} is below minimum {req.min_gap}",
            req.citation,
            cites,
        )

    return Verdict(
        VerdictStatus.COMPLIANT,
        f"gap {gap} between {req.from_op!r} and {req.to_op!r} is within limits",
        req.citation,
        cites,
    )


def _evaluate_categorical(req: CategoricalRequirement, obs: Observation) -> Verdict:
    cites = _cites(obs.citation)

    if obs.value is None:
        return Verdict(
            VerdictStatus.INSUFFICIENT_EVIDENCE,
            "no value found in the record",
            req.citation,
            cites,
        )

    if obs.value in req.allowed_values:
        return Verdict(
            VerdictStatus.COMPLIANT,
            f"{obs.value!r} is an allowed value",
            req.citation,
            cites,
        )

    return Verdict(
        VerdictStatus.NON_COMPLIANT,
        f"{obs.value!r} is not among the allowed values {tuple(req.allowed_values)}",
        req.citation,
        cites,
    )


def _evaluate_presence(req: PresenceRequirement, obs: Observation) -> Verdict:
    cites = _cites(obs.citation)

    if obs.value is None or (isinstance(obs.value, str) and not obs.value.strip()):
        return Verdict(
            VerdictStatus.NON_COMPLIANT,
            f"required field {req.field!r} is not recorded",
            req.citation,
            cites,
        )

    return Verdict(
        VerdictStatus.COMPLIANT,
        f"required field {req.field!r} is recorded",
        req.citation,
        cites,
    )


def _evaluate_conditional(req: ConditionalRequirement, obs: ConditionalObservation) -> Verdict:
    cond_cite = _cites(obs.condition_citation)

    if obs.condition_value is None:
        return Verdict(
            VerdictStatus.INSUFFICIENT_EVIDENCE,
            "cannot determine whether the condition applies (condition value missing)",
            req.citation,
            cond_cite,
        )

    if obs.condition_value not in req.condition.trigger_values:
        return Verdict(
            VerdictStatus.COMPLIANT,
            f"condition not met ({obs.condition_value!r}); rule does not apply",
            req.citation,
            cond_cite,
        )

    # Condition met: the consequent must hold. Reuse its evaluator, then re-tie
    # the verdict to the conditional rule's clause and merge the condition's cite.
    inner = evaluate(req.consequent, obs.consequent)
    return Verdict(
        inner.status,
        f"condition met ({obs.condition_value!r}); {inner.reason}",
        req.citation,
        cond_cite + inner.record_citations,
    )
