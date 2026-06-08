"""Record-side extraction: production record -> cited observations.

Mirrors the spec-side extraction (``extract.py``): the model finds and quotes
the recorded value for each requirement; this module maps that onto the M1
observation types and locates each verbatim record quote for its citation.
The model never judges compliance and never reports a location.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

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
)
from app.extract.extract import MAX_TOKENS, _resolve_client_and_model
from app.extract.prompts import RECORD_SYSTEM_PROMPT, build_record_user_prompt
from app.ingest.parse import ParsedDocument


class ExtractedObservation(BaseModel):
    """Evidence found in the record for one requirement (by id). No verdict."""

    requirement_id: str
    record_quote: str = ""  # verbatim substring of the record, for citation
    value: str | None = None  # scalar value as text (numeric/categorical/presence)
    units: str | None = None
    start_time: str | None = None  # ISO-8601, temporal from-operation
    end_time: str | None = None  # ISO-8601, temporal to-operation
    condition_value: str | None = None  # conditional: value deciding if the rule applies
    consequent_value: str | None = None
    consequent_units: str | None = None
    consequent_quote: str | None = None


class RecordExtraction(BaseModel):
    observations: list[ExtractedObservation]


def extract_observations_result(
    record: ParsedDocument,
    requirements: list[Requirement],
    *,
    client=None,
    model: str | None = None,
) -> RecordExtraction:
    """The raw structured record extraction from Claude (before mapping)."""
    if client is None or model is None:
        client, model = _resolve_client_and_model(client, model)

    response = client.messages.parse(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[
            {"type": "text", "text": RECORD_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[
            {"role": "user", "content": build_record_user_prompt(record.full_text, requirements)}
        ],
        output_format=RecordExtraction,
    )
    return response.parsed_output


def extract_observations(
    record: ParsedDocument,
    requirements: list[Requirement],
    *,
    client=None,
    model: str | None = None,
) -> list:
    """Find cited observations in the record for each requirement via Claude."""
    result = extract_observations_result(record, requirements, client=client, model=model)
    return to_observations(result, requirements, record)


def to_observations(
    extraction: RecordExtraction, requirements: list[Requirement], record: ParsedDocument
) -> list:
    """Map extracted record evidence onto observation types, aligned to the
    requirement order. A requirement with no matching evidence -> missing
    observation (value None). Pure — no I/O."""
    by_id = {obs.requirement_id: obs for obs in extraction.observations}
    return [_to_observation(req, by_id.get(req.id), record) for req in requirements]


def _cite(quote: str | None, record: ParsedDocument) -> Citation | None:
    if not quote:
        return None
    return Citation(source_text=quote, source_location=record.locate(quote))


def _to_float(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_datetime(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _to_observation(req: Requirement, eo: ExtractedObservation | None, record: ParsedDocument):
    if isinstance(req, NumericRequirement):
        if eo is None:
            return Observation(value=None)
        return Observation(
            value=_to_float(eo.value), units=eo.units, citation=_cite(eo.record_quote, record)
        )

    if isinstance(req, (CategoricalRequirement, PresenceRequirement)):
        if eo is None:
            return Observation(value=None)
        return Observation(value=eo.value, citation=_cite(eo.record_quote, record))

    if isinstance(req, TemporalRequirement):
        if eo is None:
            return IntervalObservation()
        cite = _cite(eo.record_quote, record)
        return IntervalObservation(
            start=_to_datetime(eo.start_time),
            end=_to_datetime(eo.end_time),
            start_citation=cite,
            end_citation=cite,
        )

    if isinstance(req, ConditionalRequirement):
        if eo is None:
            return ConditionalObservation(condition_value=None, consequent=None)
        return ConditionalObservation(
            condition_value=eo.condition_value,
            consequent=_consequent_observation(req.consequent, eo, record),
            condition_citation=_cite(eo.record_quote, record),
        )

    raise TypeError(f"no observation mapping for requirement type {type(req).__name__}")


def _consequent_observation(consequent: Requirement | None, eo: ExtractedObservation, record):
    cite = _cite(eo.consequent_quote, record)
    if isinstance(consequent, NumericRequirement):
        return Observation(
            value=_to_float(eo.consequent_value), units=eo.consequent_units, citation=cite
        )
    # categorical / presence consequents carry the raw value; temporal consequents
    # are out of scope for the MVP corpus.
    return Observation(value=eo.consequent_value, citation=cite)
