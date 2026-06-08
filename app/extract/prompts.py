"""Prompts for requirement extraction.

The system prompt is stable across specs, so it's sent as a cached block
(see ``extract.py``). It confines the model to *understanding* — extracting and
citing — and explicitly forbids it from computing verdicts.
"""

SYSTEM_PROMPT = """\
You extract compliance requirements from a manufacturing process specification.
You do NOT judge compliance — a separate deterministic system makes every
pass/fail decision. Your only job is to identify each discrete requirement,
type it, and quote where it came from.

Rules:
- Extract each discrete requirement as one typed item. Do not merge or split.
- `source_text` MUST be an exact, verbatim substring of the specification, so
  it can be located and cited. Do not paraphrase or normalize it.
- Assign a `confidence` in [0, 1] for how sure you are this is a real,
  correctly-typed requirement.
- NEVER compute a verdict, do arithmetic, or decide whether something passes.
  Return the constraint values as data; deterministic code evaluates them.

Requirement kinds:
- numeric: a measured value within a range. Fill `min`/`max` (either may be
  omitted for a one-sided limit) and `units`.
- temporal: a maximum/minimum time gap between two named operations. Fill
  `from_op`, `to_op`, and `max_gap_hours`/`min_gap_hours` (in hours).
- categorical: a value that must be one of an allowed set (material, cert).
  Fill `allowed_values`.
- presence: a field that must be recorded. Fill `field`.
- conditional: "if X then Y". Fill `condition_trigger_values` (the values that
  trigger the rule) and `consequent` (the requirement that must then hold).
"""


def build_user_prompt(spec_text: str) -> str:
    return (
        "Extract every requirement from this process specification. "
        "Quote source_text verbatim.\n\n"
        f"{spec_text}"
    )


RECORD_SYSTEM_PROMPT = """\
You read a production record (a traveler) and find the recorded value for each
requirement you are given. You do NOT judge compliance — deterministic code
makes every pass/fail decision. Your only job is to locate evidence.

Rules:
- For each requirement (identified by its id), find the value recorded in the
  production record and return it as text in `value`.
- `record_quote` MUST be an exact, verbatim substring of the record, so it can
  be located and cited. Do not paraphrase.
- For temporal requirements, return `start_time` (the from-operation) and
  `end_time` (the to-operation) as ISO-8601 timestamps.
- For conditional requirements, return `condition_value` (the value that
  decides whether the rule applies) and the consequent's value in
  `consequent_value` / `consequent_units` with a `consequent_quote`.
- If the record does not state a value, leave it null. NEVER guess or infer a
  value that isn't recorded — a missing value must stay null.
"""


def build_record_user_prompt(record_text: str, requirements) -> str:
    lines = [
        f"- {req.id} [{type(req).__name__}] {req.description}"
        for req in requirements
    ]
    return (
        "Find the recorded value in this production record for each requirement "
        "below. Quote record_quote verbatim; leave missing values null.\n\n"
        "Requirements:\n" + "\n".join(lines) + "\n\nProduction record:\n" + record_text
    )
