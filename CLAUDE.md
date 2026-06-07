# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Planning stage. The repo currently holds only design docs — `SPEC.md`, `PLAN.md`, `DECISIONS.md`, `WHITEBOARD-DRILL.md`, `README.md` — and **no application code yet**. The build follows `PLAN.md` milestones M0 → M9, starting from M0 (Django scaffold). When you add code, follow the planned layout in `PLAN.md` "Suggested repo layout."

This is a **job-search portfolio project**, not a shippable quality system. It has *three deliverables of equal weight*: the app, the Decision Record (`DECISIONS.md`), and a recorded whiteboard session. The judgment behind the design is the deliverable as much as the code is — see `SPEC.md` §0. Do not skip M9 (Decision Record + whiteboard) on the grounds that the app "looks done."

## What it is

Upload a process spec and a production record (synthetic, typed/text PDFs); the tool extracts each requirement (typed + cited), checks the record against it, and produces an audit-ready clause-by-clause report. Domain: regulated manufacturing compliance (the kind of check done before parts ship, against NADCAP-style scrutiny).

## Non-negotiable design invariants

These are the *point* of the project. Do not "simplify" them away — they are what the whiteboard session defends.

- **LLM extracts; deterministic code decides; a human signs.** The LLM is confined to *understanding* — extracting typed requirements and citing them. The pass/fail verdict for anything quantifiable (numeric, temporal, categorical, presence) is made by **deterministic code, never the model**. The model must never do arithmetic on safety-relevant numbers, and must never emit a verdict for a quantifiable requirement — only citations + structured data for the deterministic checker.
- **Three-state verdict:** `Compliant` / `Non-compliant` / `Insufficient evidence`. Insufficient-evidence is a first-class outcome, not a fallback.
- **A missing/unparsed record field is NEVER "Compliant"** — it yields "Insufficient evidence." This is a *tested invariant* (the asymmetry, encoded). It is the single most important rule in the codebase.
- **Bias toward catching the miss.** Uncertainty resolves to flag/insufficient, never to pass. The design consciously accepts more false positives (an engineer's five minutes) to avoid a false negative (an audit finding or field escape).
- **Everything is cited.** Every extracted requirement carries verbatim `source_text` + `source_location` + `confidence`. Every verdict ties requirement → spec citation → record evidence → verdict → human approver. No assertion without a citation.
- **No auto-disposition.** A human confirms/overrides every verdict; overrides are logged to an audit trail.
- **Synthetic data only.** No employer IP, ever — no real specs, records, part numbers, or clause text. Invent obviously fictional documents.

## Build order matters

Build the **deterministic verdict logic first** (M1) — it is where safety lives and is the "crown jewel" to test hardest — *then* layer the LLM extraction on top (M3), boxed in and cited. Do not invert this. See `PLAN.md` milestones.

## Planned architecture (per SPEC §6 / PLAN layout)

Django backend, organized by pipeline stage under `app/`:
- `ingest/` — PDF/text → text with **source locations preserved** for citation (`pdfplumber`/`pypdf`).
- `extract/` — Anthropic SDK (Claude): structured output of typed, cited requirements. Extraction only, no verdicts.
- `check/` — `types.py` (typed requirement model) + `verdict.py` (deterministic evaluators per type). The safety core.
- `report/` — audit-ready clause-by-clause render + sign-off + audit trail; export PDF/Markdown with approver + timestamp.
- `data/` — synthetic spec/record corpus (seeded, fixed sample IDs).
- Frontend: Django templates + HTMX. Flow: Upload/pick samples → Requirements (review gate) → Results (verdicts + confirm/override) → Report (export).

The **requirement review gate** (M5) is a deliberate compensating control: the engineer reviews the extracted requirement list (low-confidence ones flagged) *before* checking, so a missed/invented requirement is caught upfront — extraction recall is not assumed to be 100%.

## Requirement type model

`numeric` (min/max/units), `temporal` (max gap between named operations), `categorical` (allowed values), `presence` (field exists & non-empty), `conditional` (if X then Y). Each carries `source_text`, `source_location`, `confidence`. Verdict logic per type is deterministic where possible.

## Working with the Claude/Anthropic integration

When building or modifying the extraction layer (`extract/`), **invoke the `claude-api` skill** — do not answer Claude API / model-id / SDK questions from memory. Planned model: a current frontier model (`claude-opus-4-8` or `claude-sonnet-4-6`); use structured output for extraction and prompt caching for the system prompt + requirement-type guide. Record the model/cost reasoning in `DECISIONS.md` as you build.

`ANTHROPIC_API_KEY` lives in `.env` (gitignored) or host secrets — **never committed**.

## Testing strategy

- Test the deterministic verdict logic hardest. Required passing tests: numeric in/out of range; temporal gap over limit; categorical membership; presence; and **missing field → Insufficient evidence (never Compliant)**.
- Extraction-citation contract: every extracted requirement carries a citation; quantifiable requirements come back as data, not verdicts; output validates against the schema.
- **Mock the Anthropic API** in unit tests; keep the one live integration run out of CI.
- UI is demonstrated by the recording — don't chase UI coverage.

## Planned tooling

Per README/PLAN (commands to be created at M0; verify against the actual scaffold once it exists): pytest (tests), ruff (lint), Docker (one-command local run), GitHub Actions (CI). Python 3.11+.

## Deployment

Dockerized Django on Render, fronted by Cloudflare (planned subdomain `compliance.hector-garza.com`). No DB strictly required for the demo (session store); optional SQLite to persist reports. Cost guard: one extraction call per spec; cap tokens and cache.
