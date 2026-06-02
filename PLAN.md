# Spec Compliance Checker — Implementation Plan

Companion to `SPEC.md`. The build sequence: milestones, concrete tasks, acceptance criteria, and the definition of done. Self-contained — hand this repo to a fresh session and start.

- **Repo:** `spec-compliance-checker` (public, under `cognitivefactory-hector`)
- **Approach:** build the **deterministic verdict logic first** (it's where safety lives), then the LLM extraction layer on top (boxed in, cited, human-reviewed). The model understands; the code decides; the human signs.

> **Illustrative on synthetic documents. Not a QMS.** Keep the disclaimer in the footer and README.

---

## The spine (carry through every milestone)

Keep `DECISIONS.md` open and capture reasoning live:

> **Situation** · **Decision** (incl. what you *rejected* — auto-disposition, free-form summary) · **Risk** (incl. what you *accepted* — more false positives) · **Change**.

The hardest decisions (false-negative bias; LLM-extracts/code-decides/human-signs) are the spine of the **recorded whiteboard session** — see `SPEC.md` §3.

---

## Prerequisites
- Python 3.11+, Docker, a GitHub account (`gh` authenticated).
- An `ANTHROPIC_API_KEY` (in `.env`, gitignored — **never committed**) for extraction.

---

## Milestones

### M0 — Repo scaffold *(½ day)*
- [ ] Folder + `SPEC.md` + `PLAN.md`.
- [ ] `README.md` (stub + disclaimer), `DECISIONS.md` (paste template from `SPEC.md` §10), `.gitignore` (Python **+ `.env`**), `LICENSE` (MIT).
- [ ] Django project; `pyproject.toml`/`requirements.txt`; `Dockerfile`; serves a page.
- [ ] Record framework + model choice in `DECISIONS.md`.
- [ ] `gh repo create … --public --push`.
- **Acceptance:** app serves a page; repo on GitHub; disclaimer present.

### M1 — Requirement model + deterministic verdict logic (TDD) *(1–2 days)* — **safety core**
- [ ] `check/types.py`: typed requirement model — `numeric`, `temporal`, `categorical`, `presence`, `conditional` (each with `source_text`, `source_location`, `confidence`).
- [ ] `check/verdict.py`: deterministic evaluators per type returning **Compliant / Non-compliant / Insufficient evidence**.
- [ ] **Tests first (the crown jewels):**
  - numeric in/out of range → Compliant / Non-compliant;
  - temporal gap over limit → Non-compliant;
  - **missing record field → Insufficient evidence (never Compliant)**;
  - categorical membership; presence check.
- **Acceptance:** `pytest` green; the missing-field → insufficient-evidence rule is a passing test (this is the asymmetry, encoded).

### M2 — Ingest (parse spec + record) *(1 day)*
- [ ] `ingest/parse.py`: PDF/text → text with **source locations preserved** for citation (`pdfplumber`/`pypdf`).
- [ ] Tests: a sample PDF parses; locations are recoverable for citation.
- **Acceptance:** `pytest` green; sample docs parse to citable text.

### M3 — LLM requirement extraction (cited, structured) *(1–2 days)*
- [ ] `extract/extract.py`: Anthropic SDK; **structured output** — list of typed requirements, each with **verbatim source text + location + confidence**. The model extracts; it does **not** issue numeric verdicts.
- [ ] **Tests (mocked API):** every extracted requirement carries a citation; output validates against the schema; quantifiable requirements come back as data for the deterministic checker, not as verdicts.
- **Acceptance:** extraction returns typed, cited requirements on the sample specs.
- **Note:** if building in Claude Code, invoke the `claude-api` skill here.

### M4 — Synthetic corpus *(½ day)*
- [ ] Author 2–3 specs + matching records per `SPEC.md` §5: a clean compliant, an obvious noncompliance, a **subtle** one, and a **missing-field** case.
- [ ] Fixed sample IDs.
- **Acceptance:** corpus loads; the subtle and missing-field cases behave correctly through M1+M3.

### M5 — Requirement review gate + check pipeline *(1 day)*
- [ ] Wire ingest → extract → **engineer reviews requirement list (low-confidence flagged)** → run deterministic check → verdicts with citations.
- [ ] Tests: low-confidence extractions are flagged for review; verdicts cite both spec clause and record field.
- **Acceptance:** end-to-end produces a clause-by-clause verdict set with citations; review gate works.

### M6 — Report + sign-off + audit trail *(1 day)*
- [ ] `report/render.py`: audit-ready, clause-by-clause report (requirement, source citation, record evidence, verdict, confidence); export PDF/Markdown with approver + timestamp.
- [ ] Confirm/override per verdict; overrides logged to an audit trail.
- **Acceptance:** export produces an auditor-recognizable report; overrides are recorded.

### M7 — UI: Upload / Requirements / Results / Report *(1–2 days)*
- [ ] Upload or pick samples; requirement list (cited, confidence, reviewable); results with verdicts + evidence + confirm/override; export.
- [ ] Footer disclaimer: "Illustrative; synthetic documents; not a quality system of record. A qualified engineer signs every disposition."
- **Acceptance:** pick a sample → review requirements → see verdicts (incl. subtle catch + insufficient-evidence) → confirm → export.

### M8 — Polish, README, deploy *(1 day)*
- [ ] `README.md`: what/why, one-command run, screenshots/GIF, links to live demo + `DECISIONS.md` + whiteboard video; disclaimers prominent.
- [ ] Deploy with `ANTHROPIC_API_KEY` as a host secret; token cap + caching; smoke-test.
- [ ] Optional: `compliance.hector-garza.com`.
- **Acceptance:** public URL works from a fresh browser; full flow runs deployed.

### M9 — Decision Record + Whiteboard session *(½ day)* — **do not skip; this is the differentiator**
- [ ] Complete `DECISIONS.md` (Situation/Decision/Risk/Change; rejected auto-disposition; accepted more-false-positives).
- [ ] Record the 5–8 min whiteboard session using `SPEC.md` §3.1 — center challenge #3 (why bias toward over-flagging) and the LLM-extracts/code-decides split.
- [ ] Embed/link the recording in README and on hector-garza.com.
- **Acceptance:** a stranger can read `DECISIONS.md` + watch the video and explain *why a missing field is never "compliant."*

---

## Testing strategy
- **The deterministic verdict logic is the crown jewel — test it hardest.** Especially: missing field → insufficient evidence; out-of-range → non-compliant; uncertainty never resolves to "compliant."
- **Extraction-citation contract:** every extracted requirement must carry a citation; quantifiable requirements return as data, not verdicts.
- Mock the Anthropic API in unit tests; one live integration run for extraction, kept out of CI.
- UI is demonstrated by the recording; don't chase UI coverage.

## Suggested repo layout
```
spec-compliance-checker/
├── README.md  SPEC.md  PLAN.md  DECISIONS.md
├── Dockerfile  .env.example  pyproject.toml
├── app/
│   ├── main.py
│   ├── ingest/   parse.py
│   ├── extract/  extract.py prompts.py schemas.py
│   ├── check/    types.py verdict.py
│   ├── report/   render.py
│   ├── data/     corpus.py        # synthetic specs + records (seeded)
│   └── views.py / templates/ (or web/)
└── tests/ test_verdict.py test_extract_contract.py test_ingest.py
```

## Risk register (project execution)
| Risk | Mitigation |
|---|---|
| LLM hallucinates/misses a requirement | Cited extraction + human review gate before checking; flag low-confidence; the model never issues numeric verdicts. |
| Trusting the model to do arithmetic on safety numbers | Deterministic verdict code for everything quantifiable; LLM confined to understanding. |
| Uncertainty silently passes as "compliant" | Default-to-insufficient/flag is a tested invariant. |
| Mistaken for a quality system of record | Disclaimer in footer + README; non-goals forbid auto-disposition; a human signs. |
| Real-doc messiness (scans/handwriting) overlooked | MVP is typed PDFs; name the limitation honestly in README + whiteboard. |
| Leaking `ANTHROPIC_API_KEY` / employer data | `.env` gitignored; host secrets; synthetic docs only. |
| Skipping M9 because the app "looks done" | M9 *is* the portfolio. The false-negative-asymmetry story is the whole point. |

## Definition of Done
See `SPEC.md` §8 — all three deliverables (app, decision record, whiteboard recording) exist and are linked from the README; the asymmetry is visible and tested (missing field never reads "compliant"); and the extraction-citation contract holds.
