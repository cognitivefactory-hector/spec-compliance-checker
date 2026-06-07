"""Deterministic verdict logic — the safety core (M1).

The crown-jewel invariant, asserted throughout: a missing or unparseable
observation never resolves to COMPLIANT. Uncertainty resolves to
INSUFFICIENT_EVIDENCE (or, for presence, NON_COMPLIANT) — never to pass.
"""

from datetime import datetime, timedelta

from app.check.types import (
    CategoricalRequirement,
    Citation,
    Condition,
    ConditionalObservation,
    ConditionalRequirement,
    IntervalObservation,
    NumericRequirement,
    Observation,
    PresenceRequirement,
    TemporalRequirement,
    VerdictStatus,
)
from app.check.verdict import evaluate


def _cite(text="x", loc="§1", conf=1.0):
    return Citation(source_text=text, source_location=loc, confidence=conf)


# --- numeric -----------------------------------------------------------------


def _numeric(min=None, max=None, units="mm"):
    return NumericRequirement(
        id="R-NUM",
        description="coating thickness",
        citation=_cite("0.5-1.5 mm", "spec §3.1"),
        min=min,
        max=max,
        units=units,
    )


def test_numeric_within_range_is_compliant():
    req = _numeric(min=0.5, max=1.5)
    obs = Observation(value=1.2, units="mm", citation=_cite("1.2 mm", "rec field 7"))
    assert evaluate(req, obs).status is VerdictStatus.COMPLIANT


def test_numeric_at_boundary_is_compliant():
    req = _numeric(min=0.5, max=1.5)
    obs = Observation(value=1.5, units="mm", citation=_cite())
    assert evaluate(req, obs).status is VerdictStatus.COMPLIANT


def test_numeric_below_min_is_non_compliant():
    req = _numeric(min=0.5, max=1.5)
    obs = Observation(value=0.3, units="mm", citation=_cite())
    assert evaluate(req, obs).status is VerdictStatus.NON_COMPLIANT


def test_numeric_above_max_is_non_compliant():
    req = _numeric(min=0.5, max=1.5)
    obs = Observation(value=2.0, units="mm", citation=_cite())
    assert evaluate(req, obs).status is VerdictStatus.NON_COMPLIANT


def test_numeric_one_sided_max_only():
    req = _numeric(min=None, max=1.5)
    assert evaluate(req, Observation(value=9.0, units="mm")).status is VerdictStatus.NON_COMPLIANT
    assert evaluate(req, Observation(value=1.0, units="mm")).status is VerdictStatus.COMPLIANT


def test_numeric_missing_value_is_insufficient_never_compliant():
    """The asymmetry, encoded: no measurement -> we cannot say 'compliant'."""
    req = _numeric(min=0.5, max=1.5)
    verdict = evaluate(req, Observation(value=None))
    assert verdict.status is VerdictStatus.INSUFFICIENT_EVIDENCE
    assert verdict.status is not VerdictStatus.COMPLIANT


def test_numeric_unit_mismatch_is_insufficient_never_silent_conversion():
    req = _numeric(min=0.5, max=1.5, units="mm")
    obs = Observation(value=1.2, units="inch", citation=_cite())
    assert evaluate(req, obs).status is VerdictStatus.INSUFFICIENT_EVIDENCE


def test_numeric_verdict_carries_both_citations():
    req = _numeric(min=0.5, max=1.5)
    obs = Observation(value=1.2, units="mm", citation=_cite("1.2 mm", "rec field 7"))
    verdict = evaluate(req, obs)
    assert verdict.requirement_citation == req.citation
    assert obs.citation in verdict.record_citations


# --- temporal ----------------------------------------------------------------


def _temporal(max_gap=timedelta(hours=4), min_gap=None):
    return TemporalRequirement(
        id="R-TIME",
        description="coat within 4h of bake",
        citation=_cite("within 4 hours", "spec §4.2"),
        from_op="bake",
        to_op="coat",
        max_gap=max_gap,
        min_gap=min_gap,
    )


def test_temporal_within_limit_is_compliant():
    req = _temporal(max_gap=timedelta(hours=4))
    obs = IntervalObservation(
        start=datetime(2026, 1, 1, 9, 0),
        end=datetime(2026, 1, 1, 12, 0),  # 3h gap
    )
    assert evaluate(req, obs).status is VerdictStatus.COMPLIANT


def test_temporal_over_limit_is_non_compliant():
    req = _temporal(max_gap=timedelta(hours=4))
    obs = IntervalObservation(
        start=datetime(2026, 1, 1, 9, 0),
        end=datetime(2026, 1, 1, 13, 30),  # 4h30m gap — the subtle catch
    )
    assert evaluate(req, obs).status is VerdictStatus.NON_COMPLIANT


def test_temporal_below_min_gap_is_non_compliant():
    req = _temporal(max_gap=None, min_gap=timedelta(hours=1))
    obs = IntervalObservation(
        start=datetime(2026, 1, 1, 9, 0),
        end=datetime(2026, 1, 1, 9, 30),  # only 30m, min is 1h
    )
    assert evaluate(req, obs).status is VerdictStatus.NON_COMPLIANT


def test_temporal_missing_timestamp_is_insufficient_never_compliant():
    req = _temporal(max_gap=timedelta(hours=4))
    obs = IntervalObservation(start=datetime(2026, 1, 1, 9, 0), end=None)
    verdict = evaluate(req, obs)
    assert verdict.status is VerdictStatus.INSUFFICIENT_EVIDENCE
    assert verdict.status is not VerdictStatus.COMPLIANT


def test_temporal_end_before_start_is_insufficient():
    """Out-of-order timestamps are a data-integrity problem, not a pass."""
    req = _temporal(max_gap=timedelta(hours=4))
    obs = IntervalObservation(
        start=datetime(2026, 1, 1, 12, 0),
        end=datetime(2026, 1, 1, 9, 0),
    )
    assert evaluate(req, obs).status is VerdictStatus.INSUFFICIENT_EVIDENCE


# --- categorical -------------------------------------------------------------


def _categorical(allowed=("Ti-6Al-4V", "Inconel 718")):
    return CategoricalRequirement(
        id="R-CAT",
        description="approved material",
        citation=_cite("approved materials", "spec §2.1"),
        allowed_values=allowed,
    )


def test_categorical_allowed_value_is_compliant():
    req = _categorical()
    obs = Observation(value="Ti-6Al-4V", citation=_cite())
    assert evaluate(req, obs).status is VerdictStatus.COMPLIANT


def test_categorical_disallowed_value_is_non_compliant():
    req = _categorical()
    obs = Observation(value="6061 Aluminum", citation=_cite())
    assert evaluate(req, obs).status is VerdictStatus.NON_COMPLIANT


def test_categorical_missing_value_is_insufficient_never_compliant():
    req = _categorical()
    verdict = evaluate(req, Observation(value=None))
    assert verdict.status is VerdictStatus.INSUFFICIENT_EVIDENCE
    assert verdict.status is not VerdictStatus.COMPLIANT


# --- presence ----------------------------------------------------------------


def _presence(field="operator certification"):
    return PresenceRequirement(
        id="R-PRES",
        description="operator certification must be recorded",
        citation=_cite("operator cert recorded", "spec §5.0"),
        field=field,
    )


def test_presence_recorded_value_is_compliant():
    req = _presence()
    obs = Observation(value="CERT-4471", citation=_cite())
    assert evaluate(req, obs).status is VerdictStatus.COMPLIANT


def test_presence_absent_field_is_non_compliant():
    """A required field that simply isn't there is a definite failure of the
    'must be present' requirement — not merely 'insufficient'."""
    req = _presence()
    verdict = evaluate(req, Observation(value=None))
    assert verdict.status is VerdictStatus.NON_COMPLIANT
    assert verdict.status is not VerdictStatus.COMPLIANT


def test_presence_empty_string_is_non_compliant():
    req = _presence()
    assert evaluate(req, Observation(value="   ")).status is VerdictStatus.NON_COMPLIANT


# --- conditional -------------------------------------------------------------


def _conditional():
    """If material is Ti-6Al-4V, coating thickness must be >= 1.0 mm."""
    return ConditionalRequirement(
        id="R-COND",
        description="if Ti-6Al-4V then thickness >= 1.0 mm",
        citation=_cite("if titanium then ...", "spec §6.0"),
        condition=Condition(trigger_values=("Ti-6Al-4V",)),
        consequent=NumericRequirement(
            id="R-COND-c",
            description="thickness when titanium",
            citation=_cite("thickness >= 1.0 mm", "spec §6.1"),
            min=1.0,
            max=None,
            units="mm",
        ),
    )


def test_conditional_not_triggered_is_compliant_even_if_consequent_would_fail():
    req = _conditional()
    obs = ConditionalObservation(
        condition_value="Inconel 718",  # not titanium -> rule does not apply
        consequent=Observation(value=0.8, units="mm", citation=_cite()),  # would fail if checked
    )
    assert evaluate(req, obs).status is VerdictStatus.COMPLIANT


def test_conditional_triggered_and_consequent_compliant():
    req = _conditional()
    obs = ConditionalObservation(
        condition_value="Ti-6Al-4V",
        consequent=Observation(value=1.4, units="mm", citation=_cite()),
    )
    assert evaluate(req, obs).status is VerdictStatus.COMPLIANT


def test_conditional_triggered_and_consequent_non_compliant():
    req = _conditional()
    obs = ConditionalObservation(
        condition_value="Ti-6Al-4V",
        consequent=Observation(value=0.8, units="mm", citation=_cite()),
    )
    assert evaluate(req, obs).status is VerdictStatus.NON_COMPLIANT


def test_conditional_unknown_condition_is_insufficient_never_compliant():
    """If we can't tell whether the rule applies, we can't clear it."""
    req = _conditional()
    obs = ConditionalObservation(
        condition_value=None,
        consequent=Observation(value=1.4, units="mm", citation=_cite()),
    )
    verdict = evaluate(req, obs)
    assert verdict.status is VerdictStatus.INSUFFICIENT_EVIDENCE
    assert verdict.status is not VerdictStatus.COMPLIANT
