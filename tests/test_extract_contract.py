"""Extraction-citation contract (M3).

The model extracts and cites; it never issues verdicts. Every extracted
requirement carries a verbatim source_text; quantifiable requirements come back
as data for the deterministic checker (M1), not as pass/fail. The API is mocked
here — the live integration run is kept out of CI (PLAN.md).
"""

from datetime import timedelta

from app.check.types import (
    CategoricalRequirement,
    ConditionalRequirement,
    NumericRequirement,
    PresenceRequirement,
    TemporalRequirement,
)
from app.extract.extract import extract_requirements, to_requirements
from app.extract.schemas import ExtractedConsequent, ExtractedRequirement, ExtractionResult
from app.ingest.parse import parse_text

SPEC = (
    "Coating thickness 0.5-1.5 mm\n"
    "Coat within 4 hours of bake\n"
    "Approved materials: Ti-6Al-4V, Inconel 718\n"
    "Operator certification must be recorded\n"
    "If Ti-6Al-4V then thickness at least 1.0 mm"
)
PARSED = parse_text(SPEC)


def test_numeric_extracted_maps_to_numeric_requirement_with_located_citation():
    result = ExtractionResult(
        requirements=[
            ExtractedRequirement(
                kind="numeric",
                description="coating thickness",
                source_text="Coating thickness 0.5-1.5 mm",
                confidence=0.97,
                min=0.5,
                max=1.5,
                units="mm",
            )
        ]
    )
    reqs = to_requirements(result, PARSED)
    assert len(reqs) == 1
    r = reqs[0]
    assert isinstance(r, NumericRequirement)
    assert (r.min, r.max, r.units) == (0.5, 1.5, "mm")
    assert r.citation.source_text == "Coating thickness 0.5-1.5 mm"
    assert r.citation.source_location == "p.1 L1"
    assert r.citation.confidence == 0.97


def test_every_requirement_carries_a_verbatim_source_text():
    result = ExtractionResult(
        requirements=[
            ExtractedRequirement(
                kind="numeric",
                description="x",
                source_text="Coating thickness 0.5-1.5 mm",
                confidence=0.9,
                min=0.5,
                max=1.5,
                units="mm",
            )
        ]
    )
    for r in to_requirements(result, PARSED):
        assert r.citation is not None
        assert r.citation.source_text  # non-empty verbatim quote


def test_extraction_schema_has_no_verdict_field():
    """The model returns data, never a verdict — enforced at the schema level."""
    fields = set(ExtractedRequirement.model_fields)
    assert not ({"verdict", "status", "compliant", "result"} & fields)


def test_temporal_extracted_converts_hours_to_timedelta():
    result = ExtractionResult(
        requirements=[
            ExtractedRequirement(
                kind="temporal",
                description="coat after bake",
                source_text="Coat within 4 hours of bake",
                confidence=0.9,
                from_op="bake",
                to_op="coat",
                max_gap_hours=4,
            )
        ]
    )
    r = to_requirements(result, PARSED)[0]
    assert isinstance(r, TemporalRequirement)
    assert r.max_gap == timedelta(hours=4)
    assert (r.from_op, r.to_op) == ("bake", "coat")


def test_categorical_and_presence_map():
    result = ExtractionResult(
        requirements=[
            ExtractedRequirement(
                kind="categorical",
                description="material",
                source_text="Approved materials: Ti-6Al-4V, Inconel 718",
                confidence=0.95,
                allowed_values=["Ti-6Al-4V", "Inconel 718"],
            ),
            ExtractedRequirement(
                kind="presence",
                description="operator cert",
                source_text="Operator certification must be recorded",
                confidence=0.92,
                field="operator certification",
            ),
        ]
    )
    cat, pres = to_requirements(result, PARSED)
    assert isinstance(cat, CategoricalRequirement)
    assert cat.allowed_values == ("Ti-6Al-4V", "Inconel 718")
    assert isinstance(pres, PresenceRequirement)
    assert pres.field == "operator certification"


def test_conditional_extracted_maps_with_nested_consequent():
    result = ExtractionResult(
        requirements=[
            ExtractedRequirement(
                kind="conditional",
                description="if Ti then thickness >= 1.0",
                source_text="If Ti-6Al-4V then thickness at least 1.0 mm",
                confidence=0.85,
                condition_trigger_values=["Ti-6Al-4V"],
                consequent=ExtractedConsequent(
                    kind="numeric",
                    description="thickness when titanium",
                    source_text="thickness at least 1.0 mm",
                    min=1.0,
                    units="mm",
                ),
            )
        ]
    )
    r = to_requirements(result, PARSED)[0]
    assert isinstance(r, ConditionalRequirement)
    assert r.condition.trigger_values == ("Ti-6Al-4V",)
    assert isinstance(r.consequent, NumericRequirement)
    assert r.consequent.min == 1.0


def test_unlocatable_quote_is_kept_but_flagged_with_no_location():
    """A quote that isn't a verbatim substring is surfaced, never dropped."""
    result = ExtractionResult(
        requirements=[
            ExtractedRequirement(
                kind="numeric",
                description="x",
                source_text="THIS PHRASE IS NOT IN THE SPEC",
                confidence=0.4,
                min=0.5,
                max=1.5,
                units="mm",
            )
        ]
    )
    reqs = to_requirements(result, PARSED)
    assert len(reqs) == 1  # kept, not dropped
    assert reqs[0].citation.source_location is None


def test_extract_requirements_calls_parse_with_structured_output_and_maps():
    captured = {}

    class _FakeMessages:
        def parse(self, **kwargs):
            captured.update(kwargs)

            class _Resp:
                parsed_output = ExtractionResult(
                    requirements=[
                        ExtractedRequirement(
                            kind="numeric",
                            description="coating thickness",
                            source_text="Coating thickness 0.5-1.5 mm",
                            confidence=0.9,
                            min=0.5,
                            max=1.5,
                            units="mm",
                        )
                    ]
                )

            return _Resp()

    class _FakeClient:
        messages = _FakeMessages()

    reqs = extract_requirements(PARSED, client=_FakeClient(), model="claude-sonnet-4-6")

    assert len(reqs) == 1 and isinstance(reqs[0], NumericRequirement)
    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["output_format"] is ExtractionResult
    # The spec text is actually sent to the model.
    assert any("Coating thickness" in str(m.get("content", "")) for m in captured["messages"])
