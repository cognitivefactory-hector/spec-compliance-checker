"""Structured-output schemas for requirement extraction.

The model fills these in; ``messages.parse`` validates the response against
them. There is deliberately **no verdict/status field** — the model returns
typed data (constraint values, a verbatim quote, a confidence), and the
deterministic checker (``app.check``) decides pass/fail.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RequirementKind = Literal["numeric", "temporal", "categorical", "presence", "conditional"]
# Consequents can't themselves be conditional — structured outputs forbids
# recursive schemas, so the nested type is a separate, flat one.
ConsequentKind = Literal["numeric", "temporal", "categorical", "presence"]


class ExtractedConsequent(BaseModel):
    """The 'then' part of a conditional requirement (non-recursive)."""

    kind: ConsequentKind
    description: str
    source_text: str
    min: float | None = None
    max: float | None = None
    units: str | None = None
    from_op: str | None = None
    to_op: str | None = None
    max_gap_hours: float | None = None
    min_gap_hours: float | None = None
    allowed_values: list[str] | None = None
    field: str | None = None


class ExtractedRequirement(BaseModel):
    """One requirement extracted from the spec. ``source_text`` must be a
    verbatim quote so code can locate and cite it."""

    kind: RequirementKind
    description: str
    source_text: str
    confidence: float
    # numeric
    min: float | None = None
    max: float | None = None
    units: str | None = None
    # temporal (gaps in hours; code converts to timedelta)
    from_op: str | None = None
    to_op: str | None = None
    max_gap_hours: float | None = None
    min_gap_hours: float | None = None
    # categorical
    allowed_values: list[str] | None = None
    # presence
    field: str | None = None
    # conditional
    condition_trigger_values: list[str] | None = None
    consequent: ExtractedConsequent | None = None


class ExtractionResult(BaseModel):
    requirements: list[ExtractedRequirement]
