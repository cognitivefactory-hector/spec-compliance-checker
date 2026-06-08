"""Synthetic spec/record corpus — fixed sample IDs for reproducible demos.

Everything here is **fictional and illustrative**. There is no employer IP: the
specification number, clauses, part numbers, materials, and certification
numbers are invented. Authoring a realistic spec/record pair with a *subtle,
catchable* noncompliance is itself a domain-expertise display (SPEC §5).

Each ``Sample`` pairs the same fictional spec (FPS-1000) with one production
record. The spec is represented as the document text plus the ``ExtractionResult``
the model *should* produce (verbatim quotes that really occur in the text, so
``to_requirements`` + ``locate`` yield resolved citations). Each record carries
hand-authored observations + the expected three-state verdict, aligned with the
requirement order. Record-side value extraction and citation are wired in M5;
here the observations carry values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.check.types import (
    ConditionalObservation,
    IntervalObservation,
    Observation,
    Requirement,
    VerdictStatus,
)
from app.extract.extract import to_requirements
from app.extract.observations import ExtractedObservation, RecordExtraction
from app.extract.schemas import ExtractedConsequent, ExtractedRequirement, ExtractionResult
from app.ingest.parse import ParsedDocument, parse_text

# --- The fictional specification ---------------------------------------------

SPEC_ID = "FPS-1000"

SPEC_TEXT = """\
FICTIONAL PROCESS SPECIFICATION FPS-1000 — Protective Coating Application
Illustrative synthetic document. Not a real specification.

3.1 Coating thickness shall be between 0.50 and 1.50 mm.
3.2 The coating operation shall begin no more than 4 hours after surface preparation.
3.3 The substrate material shall be one of: Ti-6Al-4V, Inconel 718.
3.4 The operator certification number shall be recorded on the traveler.
3.5 If the substrate material is Ti-6Al-4V, the coating thickness shall be at least 1.00 mm.
"""

# What a correct extraction of FPS-1000 looks like. Each source_text is a
# verbatim substring of SPEC_TEXT (so locate() resolves it). Order is the
# requirement order the records' checks align to.
SPEC_EXTRACTION = ExtractionResult(
    requirements=[
        ExtractedRequirement(
            kind="numeric",
            description="coating thickness range",
            source_text="Coating thickness shall be between 0.50 and 1.50 mm.",
            confidence=0.98,
            min=0.50,
            max=1.50,
            units="mm",
        ),
        ExtractedRequirement(
            kind="temporal",
            description="coat within 4 hours of surface preparation",
            source_text=(
                "The coating operation shall begin no more than 4 hours after surface preparation."
            ),
            confidence=0.95,
            from_op="surface preparation",
            to_op="coating operation",
            max_gap_hours=4,
        ),
        ExtractedRequirement(
            kind="categorical",
            description="approved substrate material",
            source_text="The substrate material shall be one of: Ti-6Al-4V, Inconel 718.",
            confidence=0.97,
            allowed_values=["Ti-6Al-4V", "Inconel 718"],
        ),
        ExtractedRequirement(
            kind="presence",
            description="operator certification recorded",
            source_text="The operator certification number shall be recorded on the traveler.",
            confidence=0.96,
            field="operator certification number",
        ),
        ExtractedRequirement(
            kind="conditional",
            description="titanium substrate requires thicker coating",
            source_text=(
                "If the substrate material is Ti-6Al-4V, "
                "the coating thickness shall be at least 1.00 mm."
            ),
            # conditional clauses are the hardest to extract -> review gate flags it
            confidence=0.62,
            condition_trigger_values=["Ti-6Al-4V"],
            consequent=ExtractedConsequent(
                kind="numeric",
                description="minimum coating thickness for titanium",
                source_text="the coating thickness shall be at least 1.00 mm",
                min=1.00,
                units="mm",
            ),
        ),
    ]
)


# --- Records ------------------------------------------------------------------


@dataclass(frozen=True)
class Check:
    """One record observation paired with the verdict it should produce."""

    observation: object  # Observation | IntervalObservation | ConditionalObservation
    expected: VerdictStatus


@dataclass(frozen=True)
class Sample:
    spec_id: str
    record_id: str
    label: str  # clean | obvious | subtle | missing
    spec_text: str
    record_text: str
    extraction: ExtractionResult
    checks: tuple[Check, ...]
    record_extraction: RecordExtraction  # canned record evidence for the offline demo

    def parsed_spec(self) -> ParsedDocument:
        return parse_text(self.spec_text)

    def requirements(self) -> list[Requirement]:
        return to_requirements(self.extraction, self.parsed_spec())


def _record_extraction(
    *, thickness_value: str | None, thickness_quote: str, coat_quote: str, coat_end_iso: str
) -> RecordExtraction:
    """Canned record evidence, aligned to SPEC_EXTRACTION's requirement order
    (R1..R5). Quotes are verbatim substrings of the traveler so they locate."""
    material_quote = "Substrate material: Ti-6Al-4V"
    units = "mm" if thickness_value else None
    return RecordExtraction(
        observations=[
            ExtractedObservation(
                requirement_id="R1",
                record_quote=thickness_quote,
                value=thickness_value,
                units=units,
            ),
            ExtractedObservation(
                requirement_id="R2",
                record_quote=coat_quote,
                start_time="2026-03-01T09:00",
                end_time=coat_end_iso,
            ),
            ExtractedObservation(
                requirement_id="R3", record_quote=material_quote, value="Ti-6Al-4V"
            ),
            ExtractedObservation(
                requirement_id="R4",
                record_quote="Operator certification number: CERT-7782",
                value="CERT-7782",
            ),
            ExtractedObservation(
                requirement_id="R5",
                record_quote=material_quote,
                condition_value="Ti-6Al-4V",
                consequent_value=thickness_value,
                consequent_units=units,
                consequent_quote=thickness_quote if thickness_value else None,
            ),
        ]
    )


C = VerdictStatus.COMPLIANT
N = VerdictStatus.NON_COMPLIANT
I = VerdictStatus.INSUFFICIENT_EVIDENCE  # noqa: E741 - terse on purpose for the tables below

_PREP = datetime(2026, 3, 1, 9, 0)


def _traveler(trv: str, *, thickness_line: str, coat_time: datetime, material: str = "Ti-6Al-4V",
              cert: str = "CERT-7782") -> str:
    return (
        f"FICTIONAL PRODUCTION RECORD / TRAVELER {trv} (synthetic)\n"
        "Part: FICTIONAL-PART-A\n"
        f"Substrate material: {material}\n"
        "Surface preparation completed: 2026-03-01 09:00\n"
        f"Coating operation started: {coat_time:%Y-%m-%d %H:%M}\n"
        f"{thickness_line}"
        f"Operator certification number: {cert}\n"
    )


def _checks(*, thickness, coat_end, material="Ti-6Al-4V", cert="CERT-7782",
           thickness_expected, temporal_expected, conditional_expected) -> tuple[Check, ...]:
    """Build the five checks aligned to SPEC_EXTRACTION's requirement order."""
    return (
        Check(Observation(value=thickness, units="mm"), thickness_expected),
        Check(IntervalObservation(start=_PREP, end=coat_end), temporal_expected),
        Check(Observation(value=material), C if material else I),
        Check(Observation(value=cert), C if cert else N),
        Check(
            ConditionalObservation(
                condition_value=material,
                consequent=Observation(value=thickness, units="mm"),
            ),
            conditional_expected,
        ),
    )


SAMPLES: dict[str, Sample] = {
    # Clean: everything in spec; titanium at 1.20 mm, coated 3 h after prep.
    "coating-clean": Sample(
        spec_id=SPEC_ID,
        record_id="TRV-0001",
        label="clean",
        spec_text=SPEC_TEXT,
        record_text=_traveler(
            "TRV-0001",
            thickness_line="Coating thickness measured: 1.20 mm\n",
            coat_time=datetime(2026, 3, 1, 12, 0),
        ),
        extraction=SPEC_EXTRACTION,
        checks=_checks(
            thickness=1.20,
            coat_end=datetime(2026, 3, 1, 12, 0),
            thickness_expected=C,
            temporal_expected=C,
            conditional_expected=C,
        ),
        record_extraction=_record_extraction(
            thickness_value="1.20",
            thickness_quote="Coating thickness measured: 1.20 mm",
            coat_quote="Coating operation started: 2026-03-01 12:00",
            coat_end_iso="2026-03-01T12:00",
        ),
    ),
    # Obvious: thickness 1.90 mm is over the 1.50 mm maximum.
    "coating-obvious": Sample(
        spec_id=SPEC_ID,
        record_id="TRV-0002",
        label="obvious",
        spec_text=SPEC_TEXT,
        record_text=_traveler(
            "TRV-0002",
            thickness_line="Coating thickness measured: 1.90 mm\n",
            coat_time=datetime(2026, 3, 1, 12, 0),
        ),
        extraction=SPEC_EXTRACTION,
        checks=_checks(
            thickness=1.90,
            coat_end=datetime(2026, 3, 1, 12, 0),
            thickness_expected=N,  # over max
            temporal_expected=C,
            conditional_expected=C,  # 1.90 >= 1.00, so the Ti rule still holds
        ),
        record_extraction=_record_extraction(
            thickness_value="1.90",
            thickness_quote="Coating thickness measured: 1.90 mm",
            coat_quote="Coating operation started: 2026-03-01 12:00",
            coat_end_iso="2026-03-01T12:00",
        ),
    ),
    # Subtle: coating began 4 h 30 m after prep — 30 minutes over the 4 h limit.
    "coating-subtle": Sample(
        spec_id=SPEC_ID,
        record_id="TRV-0003",
        label="subtle",
        spec_text=SPEC_TEXT,
        record_text=_traveler(
            "TRV-0003",
            thickness_line="Coating thickness measured: 1.10 mm\n",
            coat_time=datetime(2026, 3, 1, 13, 30),
        ),
        extraction=SPEC_EXTRACTION,
        checks=_checks(
            thickness=1.10,
            coat_end=datetime(2026, 3, 1, 13, 30),  # 4.5 h gap
            thickness_expected=C,
            temporal_expected=N,  # the subtle catch
            conditional_expected=C,
        ),
        record_extraction=_record_extraction(
            thickness_value="1.10",
            thickness_quote="Coating thickness measured: 1.10 mm",
            coat_quote="Coating operation started: 2026-03-01 13:30",
            coat_end_iso="2026-03-01T13:30",
        ),
    ),
    # Missing: the record never states a thickness — must be insufficient, not compliant.
    "coating-missing": Sample(
        spec_id=SPEC_ID,
        record_id="TRV-0004",
        label="missing",
        spec_text=SPEC_TEXT,
        record_text=_traveler(
            "TRV-0004",
            thickness_line="",  # no thickness recorded
            coat_time=datetime(2026, 3, 1, 12, 0),
        ),
        extraction=SPEC_EXTRACTION,
        checks=_checks(
            thickness=None,  # absent
            coat_end=datetime(2026, 3, 1, 12, 0),
            thickness_expected=I,  # never compliant
            temporal_expected=C,
            conditional_expected=I,  # Ti triggers the rule, but thickness is absent
        ),
        record_extraction=_record_extraction(
            thickness_value=None,  # no thickness recorded
            thickness_quote="",
            coat_quote="Coating operation started: 2026-03-01 12:00",
            coat_end_iso="2026-03-01T12:00",
        ),
    ),
}


def get_sample(sample_id: str) -> Sample:
    return SAMPLES[sample_id]


# --- offline pipeline run (no API) -------------------------------------------


def run_sample(sample_id: str, *, min_confidence: float | None = None):
    """Build the report for a sample from its canned extractions — a reproducible,
    zero-cost demo path that still exercises the real deterministic pipeline
    (parse -> map + locate -> review gate -> check)."""
    from app.pipeline import DEFAULT_MIN_CONFIDENCE, build_report_from_extractions

    sample = get_sample(sample_id)
    return build_report_from_extractions(
        sample.spec_text,
        sample.record_text,
        sample.extraction,
        sample.record_extraction,
        min_confidence=DEFAULT_MIN_CONFIDENCE if min_confidence is None else min_confidence,
    )
