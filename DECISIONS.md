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

### M4 — synthetic corpus (recorded as built)
- **Representation:** each `Sample` carries the spec *document text* plus the `ExtractionResult` the model *should* produce (verbatim quotes that really occur in the text). The corpus is exercised through the real deterministic path — `parse` (M2) → `to_requirements` + `locate` (M3) → `evaluate` (M1) — so it validates the pipeline, not just the data, **without a live API call**. Hand-authoring the expected extraction also gives M7 a reproducible, zero-cost demo path.
- **Scope:** **one** rich fictional spec (`FPS-1000`) exercising all five requirement types, paired with **four** records (`coating-clean/obvious/subtle/missing`) — fixed sample IDs. SPEC §5 suggests 2–3 specs; one spec already covers every type and both crown-jewel cases (the subtle temporal catch and the missing-field insufficient-evidence), so a second spec is deferred as easy, additive content rather than blocking M4.
- **The catchable cases (the domain-expertise display):** obvious = thickness 1.90 mm over the 1.50 mm max; **subtle = coating 4 h 30 m after prep, 30 min over the 4 h limit**; **missing = no thickness recorded → insufficient evidence, never compliant** (and the Ti conditional's consequent is likewise insufficient). All asserted by tests.
- **Record-side citations deferred to M5:** observations here carry values only; extracting cited record values is the M5 step (the "LLM extracts cited record values, code compares" decision).
- **No employer IP:** invented spec number, clauses, part numbers, materials, and cert numbers; documents are explicitly labelled synthetic.

### M5 — review gate + check pipeline (recorded as built)
- **Review gate runs *before* checking** (SPEC §4.3): `review_requirements` flags a requirement when its extraction confidence is below `min_confidence` (default **0.7**, configurable) **or** its citation couldn't be located (`source_location is None`). An unlocatable citation always flags, regardless of confidence — a requirement we can't tie to the spec is exactly what the engineer must eyeball.
- **Record-side extraction mirrors the spec side:** `app/extract/observations.py` adds a `RecordExtraction` schema (**no verdict field**) + a pure `to_observations()` mapper that builds the right `Observation`/`IntervalObservation`/`ConditionalObservation` per requirement kind, locating each verbatim record quote via `locate()`. This is what gives each verdict its **record-field citation**, so a verdict ties spec clause → record field → outcome.
- **Missing record evidence → missing observation:** a requirement with no matching record evidence yields an empty observation (value `None`), which the deterministic checker resolves to `INSUFFICIENT_EVIDENCE` (or `NON_COMPLIANT` for presence) — never compliant.
- **Type coercion lives in code, not the model:** the model returns record values as text; `to_observations` parses numbers (`float`) and ISO-8601 timestamps (`datetime`). An unparseable value becomes `None` → insufficient, never a bad comparison.
- **`check_documents(spec, record)` is the end-to-end seam** for M7: ingest both → extract requirements → extract observations → `build_report`. The client is injectable, so the whole pipeline is tested with a fake client + the M4 corpus; the live run stays out of CI.
- **`CheckReport` is the auditable artifact:** a list of `ClauseResult`s (requirement, verdict, `needs_review` + reason) plus status counts — the clause-by-clause structure M6 renders.

### M6 — report, sign-off, audit trail (recorded as built)
- **Nothing is dispositioned without sign-off:** `sign_off(report, decisions, *, approver, signed_at)` requires a named approver and exactly one `Decision` per clause. **Confirm** keeps the verdict's status; **override** sets the engineer's chosen final status and **requires a justification note** (raises otherwise). This encodes "a human signs every disposition."
- **The audit trail is the traceability chain:** every clause (confirm *and* override) becomes an immutable `AuditEvent` — `requirement_id`, action, original→final status, note, approver, timestamp. It shows an auditor that each clause was adjudicated by a named person, with overrides justified. Overrides flagged.
- **`signed_at` is injected, not `now()`:** the sign-off layer is pure and deterministic (testable, reproducible) — the view passes the timestamp.
- **Export format:** **Markdown** in M6 (auditor-recognizable, pure-string, fully testable). **PDF deferred to M8** polish — avoids promoting `reportlab` to a runtime dep before it's needed.
- **No persistence yet:** `SignedReport` is a data structure; persisting it (SQLite) stays optional (SPEC §9) and is an M7/M8 concern.
- **Record evidence renders as "—" when an observation has no record citation** (e.g. the value-only M4 corpus). In the live `check_documents` flow, record-side extraction supplies the citation and it renders. The renderer never fabricates evidence.

### M7 — UI: Upload / Requirements / Results / Report (recorded as built)
- **The demo runs the real pipeline offline.** Each corpus `Sample` gained a canned `RecordExtraction`; `run_sample()` feeds an `_OfflineClient` to the *actual* `check_documents`, so the demo exercises ingest → extract → review → check → cited report with **no API key and zero cost**, reproducibly. The corpus is the LLM stand-in.
- **No fragile session state:** flow is driven by `sample_id` in the URL and re-run per screen (offline runs are instant); confirm/override decisions ride in the POST form. Avoids serializing dataclasses into the session.
- **The review gate is made visible:** the conditional clause's extraction confidence is set to **0.62** (below the 0.70 threshold) — realistic, since "if X then Y" clauses are the hardest to extract — so the Requirements screen actually shows a flagged-for-review item.
- **Upload deferred to M8** (chosen): the upload control is present but shows a "live extraction — coming next" notice. The sample flow is the tested path and needs no key.
- **Frontend:** Django templates extending a small design system in `base.html` (cohesive palette, status pills ok/bad/warn), **HTMX** loaded with `hx-boost` for snappy navigation. Per `PLAN.md` testing strategy, the UI is covered by flow smoke tests (Django test client), not exhaustive coverage — the recorded walkthrough is the real UI demo.
- **Disposition UX:** a single per-clause select ("Confirm: <verdict>" or "Override → <status>") plus a justification field collapses action+status; the view parses it into `Decision`s, and `sign_off` enforces the justification rule. Export re-submits the carried form with `export=md`.

### M8 — polish, deploy-prep, PDF, live upload (recorded as built)
- **PDF export:** `render_pdf` (reportlab, promoted to a runtime dep) renders the same signed report as a PDF; the Report screen offers Markdown **and** PDF. Auditor-friendly artifact for the demo.
- **Live upload, state-free:** the upload runs the live pipeline **once** (`analyze_documents` → two LLM calls), then carries the raw extractions (`ExtractionResult`/`RecordExtraction` as JSON) in hidden form fields. The sign-off round-trip rebuilds the report deterministically via `build_report_from_extractions` — **no re-extraction, no server-side cache/session**, so it's correct across gunicorn workers. Upload is gated on `ANTHROPIC_API_KEY`; without it the form shows a notice and samples still work.
- **Refactor for reuse:** exposed `extract_requirements_result` / `extract_observations_result` (raw results) and added `analyze_documents` + `build_report_from_extractions`; `check_documents` and `run_sample` now compose these. The offline `_OfflineClient` trick from M7 was dropped in favour of `build_report_from_extractions` (cleaner).
- **CI:** GitHub Actions runs `ruff` + `pytest` on push/PR (unit tests mock the API; the live run stays out of CI by design).
- **Deploy:** `render.yaml` blueprint (Docker web service, `/healthz` health check, env vars; `ANTHROPIC_API_KEY` as a `sync:false` secret). Dockerfile already binds `$PORT` + serves static via whitenoise. The actual Render hookup + live URL is the owner's step (M8 acceptance "public URL works" completes on deploy).
- **README:** overhauled with the design-in-one-line, real screenshots of the four screens (captured from the running app), run + deploy instructions, and the disclaimer up top.
