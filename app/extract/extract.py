"""Requirement extraction: spec text -> typed, cited M1 requirements.

The model extracts and cites (``app.extract.schemas``); this module maps its
structured output onto the deterministic requirement model (``app.check.types``)
and locates each verbatim quote via the parsed document. The model never issues
a verdict and never reports a location.
"""

from __future__ import annotations

from datetime import timedelta

from app.check.types import (
    CategoricalRequirement,
    Citation,
    Condition,
    ConditionalRequirement,
    NumericRequirement,
    PresenceRequirement,
    Requirement,
    TemporalRequirement,
)
from app.extract.prompts import SYSTEM_PROMPT, build_user_prompt
from app.extract.schemas import ExtractedConsequent, ExtractedRequirement, ExtractionResult
from app.ingest.parse import ParsedDocument

MAX_TOKENS = 8000


def extract_requirements(
    parsed: ParsedDocument, *, client=None, model: str | None = None
) -> list[Requirement]:
    """Extract typed, cited requirements from a parsed spec via Claude.

    ``client`` is injectable for testing; by default an ``anthropic.Anthropic``
    is constructed and the model is read from settings.
    """
    if client is None or model is None:
        client, model = _resolve_client_and_model(client, model)

    response = client.messages.parse(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": build_user_prompt(parsed.full_text)}],
        output_format=ExtractionResult,
    )
    return to_requirements(response.parsed_output, parsed)


def _resolve_client_and_model(client, model):
    import anthropic
    from django.conf import settings  # lazy: keep the pure mapper import-light

    return client or anthropic.Anthropic(), model or settings.ANTHROPIC_MODEL


def to_requirements(result: ExtractionResult, parsed: ParsedDocument) -> list[Requirement]:
    """Map extracted, validated output onto deterministic requirement objects,
    locating each verbatim quote for its citation. Pure — no I/O."""
    return [
        _to_requirement(ext, f"R{i}", parsed)
        for i, ext in enumerate(result.requirements, start=1)
    ]


def _citation(source_text: str, confidence: float, parsed: ParsedDocument) -> Citation:
    return Citation(
        source_text=source_text,
        source_location=parsed.locate(source_text),  # None if not found -> flagged
        confidence=confidence,
    )


def _hours(value: float | None) -> timedelta | None:
    return timedelta(hours=value) if value is not None else None


def _scalar_requirement(
    item: ExtractedRequirement | ExtractedConsequent, req_id: str, citation: Citation
) -> Requirement:
    """Map a non-conditional requirement (or a conditional's consequent)."""
    if item.kind == "numeric":
        return NumericRequirement(
            req_id, item.description, citation, item.min, item.max, item.units
        )
    if item.kind == "temporal":
        return TemporalRequirement(
            req_id,
            item.description,
            citation,
            item.from_op or "",
            item.to_op or "",
            _hours(item.max_gap_hours),
            _hours(item.min_gap_hours),
        )
    if item.kind == "categorical":
        return CategoricalRequirement(
            req_id, item.description, citation, tuple(item.allowed_values or ())
        )
    if item.kind == "presence":
        return PresenceRequirement(req_id, item.description, citation, item.field or "")
    raise ValueError(f"no mapping for requirement kind {item.kind!r}")


def _to_requirement(ext: ExtractedRequirement, req_id: str, parsed: ParsedDocument) -> Requirement:
    citation = _citation(ext.source_text, ext.confidence, parsed)

    if ext.kind == "conditional":
        consequent = None
        if ext.consequent is not None:
            consequent = _scalar_requirement(
                ext.consequent,
                f"{req_id}-c",
                _citation(ext.consequent.source_text, ext.confidence, parsed),
            )
        return ConditionalRequirement(
            req_id,
            ext.description,
            citation,
            Condition(trigger_values=tuple(ext.condition_trigger_values or ())),
            consequent,
        )

    return _scalar_requirement(ext, req_id, citation)
