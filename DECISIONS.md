# Decision Record — Spec Compliance Checker

The four questions that make judgment portable. These are **first-draft answers** (from `SPEC.md` §1.1) — pressure-test and revise them in the recorded whiteboard session, then keep what survives.

## Situation
Before parts ship, the production record / traveler must be verified against the process spec — every requirement checked: coating-thickness ranges, time-between-operations, operator certifications, materials, process parameters. Done by hand it's slow, tedious, and inconsistent; a single missed noncompliance becomes an **audit finding or an escape to the customer.** Facts I have: the spec and the record. Facts I'm missing: a fast, *consistent* way to check every requirement and a clean record of what was checked.

## Decision
Extract discrete, cited requirements from the spec; check each against the record with a **three-state verdict — Compliant / Non-compliant / Insufficient evidence**; produce an **audit-ready, clause-by-clause report.** Crucially, **the LLM extracts and understands; deterministic code makes the numeric/temporal pass-fail call** wherever possible. The system is **biased toward surfacing-for-review, not auto-pass.**
**Rejected:** an auto-disposition design (an unsigned machine "compliant" is a liability); and a free-form summary (an auditor needs structured, cited, clause-by-clause output).

## Risk
The killer is a **false negative** — a real noncompliance the tool calls "compliant," that ships and becomes an audit finding or a field escape. Mitigations: when uncertain, **default to "Insufficient evidence" or flag, never to "compliant"**; **cite every verdict** to the spec clause *and* the record field; **require human confirmation**; surface low-confidence extractions.
**Consciously accepted:** more false positives (an engineer's five minutes) to protect against the costly miss — that asymmetry is the whole design.

## Change
Audit prep drops from hours to minutes; every requirement is checked **consistently**; a human confirms each flag and signs; there's a record of exactly what was checked against what. The prevented loss: the missed noncompliance that would have shipped.

## Whiteboard session
- Recording: _TBD_
- The borderline flag/clear call: _…_
- Why the LLM extracts but code decides: _shrinks the hallucination surface to "did it extract right," which the human review gate catches._
- What I revised under push-back / held the line on: _…_

---

## Engineering decisions (recorded as built)
- **Backend:** Django — one stack across the portfolio. **Django 5.2 LTS** on **Python 3.12**.
- **Split:** LLM confined to **understanding** (typed, cited requirement extraction); **deterministic code** evaluates everything quantifiable. The model returns citations, not verdicts.
- **Tested invariant:** a missing record field yields "Insufficient evidence," never "compliant"; uncertainty never resolves to pass.
- **Host:** Render (Dockerized) behind Cloudflare. `ANTHROPIC_API_KEY` never committed.

### M0 — scaffold (recorded as built)
- **Model choice:** default **`claude-sonnet-4-6`**, switchable to `claude-opus-4-8` via the `ANTHROPIC_MODEL` env var. Reasoning: extraction is **one call per spec** over short, structured documents, and the model's job is the *narrow, verifiable* task of typed extraction with verbatim citations — not open-ended reasoning. Sonnet is the cost/quality fit; the human review gate plus deterministic verdicts mean we don't need the top tier to be safe. Opus stays one env var away if extraction recall on harder specs warrants it. (Revisit with real numbers at M3/M5.)
- **Project layout:** Django project in `config/` (settings/urls/wsgi/asgi); single app in `app/` that will hold the pipeline packages (`ingest/`, `extract/`, `check/`, `report/`, `data/`) added at their milestones. Settings are env-driven (`config/settings.py` + `.env.example`) so one image runs locally and on Render.
- **Dependency management:** `pyproject.toml` (single source of truth for deps + `ruff` + `pytest` config). Runtime deps are added at the milestone that first needs them (`pdfplumber`/`pypdf` at M2, `anthropic` at M3) to keep the image lean and the build sequence honest.
- **Deploy runtime:** `gunicorn` + `whitenoise` (static without a separate web server), `python:3.12-slim` base image, binds `$PORT` for Render. A `/healthz` JSON probe is exposed for uptime checks.
- **DB:** SQLite configured but the demo needs no DB (session/in-memory); kept so reports can optionally be persisted later (SPEC §9).

### M1 — requirement model + deterministic verdicts (recorded as built)
- **Evidence model:** the LLM extracts cited candidate values **from the record** too (same extract-and-cite discipline as spec requirements); **deterministic code does the comparison and the verdict.** This preserves "the model understands, the code decides." `check/` defines the `Observation` shape and pure evaluators in M1; the record-extraction wiring lands in M3/M5.
- **Verdict states:** exactly three — `COMPLIANT` / `NON_COMPLIANT` / `INSUFFICIENT_EVIDENCE`. A conditional whose condition isn't triggered resolves to `COMPLIANT` (with reason "condition not met"), not a fourth state.
- **The encoded asymmetry (tested invariant):** any missing or unparseable observation value defaults to `INSUFFICIENT_EVIDENCE`, **never `COMPLIANT`**. Uncertainty never resolves to pass.
- **Units:** numeric units must match between requirement and observation. A unit mismatch or a missing unit → `INSUFFICIENT_EVIDENCE` — **no silent conversion**, because a conversion bug is exactly the false negative we guard against.
- **Presence is special:** for a `presence` requirement (a field that *must* be recorded), an **absent field → `NON_COMPLIANT`** (the requirement is "be present"; absence is a definite failure). This differs from numeric/temporal/categorical, where a missing value → `INSUFFICIENT_EVIDENCE`. An unparseable record → `INSUFFICIENT_EVIDENCE`.
- **Conditional:** modeled as a condition + a consequent requirement. Condition data missing → `INSUFFICIENT_EVIDENCE`; condition false → `COMPLIANT` (not triggered); condition true → evaluate the consequent.
- **Pure functions:** `check/verdict.py` evaluators are pure `(requirement, observation) -> Verdict` with no I/O, so they are trivially testable and reproducible (the auditability argument).

### M2 — ingest / parsing (recorded as built)
- **Parsed shape:** `parse()` returns a `ParsedDocument` with `full_text` (what M3 sends to Claude / what we display) and ordered `TextSpan`s (page, line, text, char offsets into `full_text`). `.txt` and `.pdf` produce the same shape so downstream code (M3/M5) is format-agnostic.
- **Citations are code-located, not model-reported:** the M3 model returns a **verbatim** `source_text` quote; `ParsedDocument.locate(snippet)` finds it deterministically and computes the auditor locator (e.g. `"p.2 L14"`). The model never counts lines or pages — keeps it out of arithmetic, and a quote that can't be located is a signal the model didn't quote verbatim (→ flag, never silently trusted).
- **PDF library:** **pdfplumber primary** (per-line positional fidelity for accurate locations), **pypdf fallback** when pdfplumber yields no text. MVP is typed/text PDFs; scanned/handwriting OCR remains a named limitation (SPEC §4.4).
- **Match policy:** `locate()` uses exact substring match for M2; whitespace-normalized matching is a noted future improvement (PDF extraction spacing can differ from a model quote). An unlocatable quote returns `None`, never a fabricated location.

### M3 — LLM requirement extraction (recorded as built)
- **Structured output:** `client.messages.parse(output_format=ExtractionResult)` with Pydantic models (`anthropic` SDK). The SDK validates the response against the schema and retries on mismatch — no hand-rolled JSON parsing. **The extraction schema has no verdict/status field**: the model returns typed *data* (constraint values + verbatim `source_text` + `confidence`), and deterministic code (M1) decides pass/fail. Enforced by a test.
- **Model:** `claude-sonnet-4-6` (the M0 choice), overridable via `ANTHROPIC_MODEL`. System prompt (the requirement-type guide) is sent as a cached block (`cache_control: ephemeral`) since it's stable across specs.
- **Citations are code-located:** the model quotes `source_text` verbatim; `to_requirements()` builds each `Citation` by calling `ParsedDocument.locate(source_text)`. The model never reports a location.
- **Unlocatable quote → kept, not dropped:** if `locate()` returns `None`, the requirement is still produced with `source_location=None` (flagged for the M5 review gate). Silently dropping a requirement is exactly the miss the system guards against, so we surface it instead. (`Citation.source_location` is now `str | None`.)
- **Temporal units:** the model returns gaps in hours (`max_gap_hours`/`min_gap_hours`); code converts to `timedelta`. Keeps the model out of arithmetic.
- **Conditional:** extracted with a non-recursive nested `consequent` (one of numeric/temporal/categorical/presence) — structured outputs forbids recursion, so the consequent type is a separate, flat schema.
- **Testability:** the pure mapper `to_requirements(result, parsed)` is unit-tested without the API; the API call (`extract_requirements`) is tested with an injected fake client. Per `PLAN.md`, the live integration run stays out of CI.
