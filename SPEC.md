# Spec Compliance Checker — Design Spec

**Project 6 of the Hector Garza portfolio.** Self-contained: everything needed to start this as its own repository is in this file and its companion `PLAN.md`. You do not need any other file from the `career/` folder to build this.

- **Owner:** Hector Garza · hectorg@smartxchain.com · hector-garza.com
- **Status:** Spec — ready to build
- **Suggested repo name:** `spec-compliance-checker`
- **One-liner:** Upload a process spec and a production record; it extracts each requirement (cited), checks the record against it, and produces an audit-ready report — deliberately biased toward *catching the miss*, because a false negative is an audit finding and a false positive is five minutes of an engineer's time.

> **Illustrative tool on synthetic documents.** Not a quality-system of record; a human signs every disposition. No employer data, ever.

---

## 0. Read this first — what this project is *really* for

This is a job-search portfolio project, but it is **not** a "look, an LLM read two documents" demo. The hireable signal is **how you designed for a regulated failure mode**: which judgments you let a model make, which you forced into deterministic code, the asymmetry you optimized for, and the traceability that lets the output survive an auditor.

So this project has **three deliverables of equal weight**:

1. **The working app** (hosted, clickable).
2. **A Decision Record** (`DECISIONS.md`) structured around the four questions below.
3. **A recorded whiteboard session** (5–8 min) where you defend the false-negative-biased, human-signs design against push-back.

A hiring manager who opens this repo should learn that you think about compliance the way someone who's been through NADCAP audits does.

---

## 1. The spine — four questions that make judgment portable

Every project in this portfolio is organized around these four questions. They appear here, in `DECISIONS.md`, and on the project's page at hector-garza.com. Fill them in *as you build*, while the reasoning is still alive.

> **1 · Situation** — What's happening, who's involved, the constraints, the facts you have and the facts that are *missing*. Context is where judgment begins.
>
> **2 · Decision** — The plausible paths, the one you took, and the credible options you *rejected*. Rejection shows what you refused to hand-wave.
>
> **3 · Risk** — What could go wrong, what you removed, and what you *consciously accepted*. Prevented losses count — name the bad outcome that didn't happen.
>
> **4 · Change** — What's different now: clearer, safer, faster. Connect the judgment to a real change in the work, not a diary entry.

### 1.1 First-draft answers for Spec Compliance Checker (defend/revise these on camera)

Your starting position. The whiteboard session (§3) exists to pressure-test these — and you've run NADCAP and customer audits, so this asymmetry is *yours*.

- **Situation.** Before parts ship, the production record / traveler must be verified against the process spec — every requirement checked: coating-thickness ranges, time-between-operations, operator certifications, materials, process parameters. Done by hand it's slow, tedious, and inconsistent; a single missed noncompliance becomes an **audit finding or an escape to the customer.** Facts you have: the spec and the record. Facts you're missing: a fast, *consistent* way to check every requirement and a clean record of what was checked.
- **Decision.** Build a tool that **extracts discrete, cited requirements** from the spec, **checks each against the record** with a **three-state verdict — Compliant / Non-compliant / Insufficient evidence** — and produces an **audit-ready, clause-by-clause report.** Crucially, **the LLM extracts and understands; deterministic code makes the numeric/temporal pass-fail call** wherever possible (a thickness range is math, not a language task). **You biased the system toward surfacing-for-review, not auto-pass.** **You rejected** an auto-disposition design (an unsigned machine "compliant" is a liability) and a free-form summary (an auditor needs structured, cited, clause-by-clause output).
- **Risk.** The killer is a **false negative** — a real noncompliance the tool calls "compliant," that ships and becomes an audit finding or a field escape. Mitigations: when uncertain, **default to "Insufficient evidence" or flag, never to "compliant"**; **cite every verdict** to the spec clause *and* the record field; **require human confirmation** on every disposition; surface **low-confidence extractions** for review. You **consciously accept more false positives** (an engineer's five minutes) to protect against the costly miss — that's the asymmetry, and it's the whole design.
- **Change.** Audit prep drops from hours to minutes; every requirement is checked **consistently**; a human confirms each flag and signs; and there's a record of exactly what was checked against what. Prevented loss: the missed noncompliance that would have shipped.

---

## 2. Why this project (market fit)

- **Document AI + compliance automation** is a real, funded category, and regulated manufacturing (aerospace, medical, auto) feels this pain acutely.
- It pairs naturally with **RCCA Copilot** as the "regulated-quality" half of your portfolio — together they say "I automate quality work without breaking the rules that govern it."
- **Your unfair advantage is rare:** you've *been the auditor and the audited.* You know why an auditor rejects a report, what "objective evidence" means, and why "probably compliant" is unacceptable. Almost no AI engineer can author a believable spec/record pair, let alone design for the false-negative asymmetry. The judgment in §1.1 is yours.

---

## 3. The staged whiteboard session (recorded deliverable)

**Format.** 5–8 minutes. Screen + voice (Loom, or OBS → MP4), at the "whiteboard" (a requirement-extraction diagram or the running app), defending the design while an adversary pushes back. Use a strong engineer friend, or answer the scripted challenges below on camera as if defending to an auditor. Preserve the surviving reasoning in `DECISIONS.md`.

### 3.1 Adversarial challenge script (the push-back)

1. **"This is just an LLM reading two documents. Where's the engineering?"**
   *(Defend: typed requirement extraction with citations, deterministic verdict logic for numeric/temporal, the three-state output, the false-negative-biased threshold, the insufficient-evidence path.)*
2. **"The LLM will miss a requirement or invent one. In a regulated audit that's catastrophic."**
   *(Defend: extraction is grounded + cited; the engineer reviews the extracted requirement list before checking; low-confidence extractions are flagged; nothing is asserted without a citation.)*
3. **"Why bias toward over-flagging? Won't engineers drown in false positives and tune it out?"**
   *(Defend the asymmetry with numbers — audit-finding cost vs. five minutes — while keeping the signal usable; where you'd set the line.)*
4. **"How does this pass NADCAP scrutiny? Auditors distrust black boxes."**
   *(Defend traceability: every verdict cites the spec clause and the record field; an audit trail; a human approver of record. It's a prep aid; a person signs.)*
5. **"Synthetic, clean PDFs — real records are scanned, handwritten, weirdly formatted. Why believe it?"**
   *(Be honest about OCR/extraction limits; what you'd validate first on real documents; where it breaks.)*
6. **"Show me a case the tool flagged that a human cleared — or cleared that a human flagged."**
   *(The borderline call — the judgment that proves you understand where the line sits.)*

### 3.2 What the recording must show
- The **Situation → Decision → Risk → Change** arc (§1.1), in your words.
- The **LLM-extracts / code-decides / human-signs** split, and *why*.
- At least one place you **revised** under push-back (or a crisp reason you held).
- A pointer to where the surviving reasoning lives (`DECISIONS.md`).

---

## 4. Product specification

### 4.1 Users
- **Primary:** a quality/process engineer verifying a production record against a spec before disposition.
- **Demo viewer:** a hiring manager who must "get it" in 60 seconds and see that a human signs.

### 4.2 Core features (MVP)
1. **Ingest.** Upload (or pick a sample) a **spec** and a **production record** (PDF or text); parse to text with locations preserved for citation.
2. **Requirement extraction (LLM, cited).** Extract discrete, typed requirements from the spec — each with the **verbatim source text + location** it came from. Types: **numeric range/limit**, **temporal** (e.g., time-between-operations), **categorical** (material, operator certification), **presence/absence**, **conditional**.
3. **Requirement review gate.** The engineer reviews the extracted requirement list (low-confidence ones flagged) **before** checking — catches missed/invented requirements early.
4. **Compliance check.** For each requirement, compare against the record and assign **Compliant / Non-compliant / Insufficient evidence**, citing the record field. **Numeric/temporal/categorical verdicts are computed by deterministic code; only genuinely textual requirements use the LLM (and still cite).**
5. **Audit-ready report.** A structured, clause-by-clause report: requirement, source citation, record evidence, verdict, confidence. Exportable (PDF/Markdown) with the approver's name + timestamp.
6. **Human sign-off.** The engineer confirms/overrides each verdict; nothing is "dispositioned" without sign-off; overrides are logged.
7. **Insufficient-evidence handling (visible).** When the record lacks the data, the verdict is **"Insufficient evidence — verify,"** never a guessed "compliant."

### 4.3 Screens
- **Upload / pick samples** → **Requirements** (extracted, cited, reviewable) → **Results** (clause-by-clause verdicts, evidence, confirm/override) → **Report** (export).
- **About / Decision Record** (or link to hector-garza.com): the SDRC story + embedded whiteboard recording.

### 4.4 Explicit non-goals (YAGNI)
- No QMS/PLM integration; synthetic documents only.
- **No auto-disposition.** A human signs every verdict. By design.
- No handwriting OCR / scanned-image pipeline in MVP (typed/text PDFs); note it as a known limitation and extension.
- No multi-user approval routing; one engineer session.
- The LLM does not invent a verdict it can't cite; "insufficient evidence" is a first-class outcome, not a fallback to "compliant."

---

## 5. Synthetic data (no employer IP — ever)

Hand-built, obviously fictional document pairs. **No TAT/MSI specs, records, part numbers, or clause text.**

- **2–3 fictional specs** (generic requirement text; invent clause numbers) covering a mix of requirement types — at least one numeric range, one time-between-operations, one operator-cert, one material.
- **Matching production records**, including:
  - a **clean compliant** record,
  - a record with an **obvious noncompliance** (thickness out of range),
  - a record with a **subtle** one (time-between-ops exceeded by a little),
  - a record **missing a field** (→ should yield "insufficient evidence," not "compliant").
- Fixed sample IDs for reproducible demos.

> Authoring a realistic spec/record pair with a subtle, catchable noncompliance is itself a domain-expertise display — note it in `DECISIONS.md`.

---

## 6. Architecture & stack

Matches the owner's stack (Django · Docker) with Claude for extraction and PDF parsing for ingest.

```
┌──────────────────────────────────────────────────────────┐
│  Browser — Upload / Requirements / Results / Report         │
│   • requirement list (cited, confidence, reviewable)         │
│   • clause-by-clause verdicts + evidence + confirm/override  │
│   • export report (approver + timestamp)                     │
└───────────────▲──────────────────────────┬──────────────────┘
                │                            │
┌───────────────┴──────────────────────────▼──────────────────┐
│  Backend — Django                                             │
│   • ingest/    PDF/text parse, keep source locations          │
│   • extract/   Claude: typed requirements + citations          │
│   • check/     DETERMINISTIC verdicts (numeric/temporal/cat);  │
│                LLM only for textual reqs (still cited)         │
│   • report/    audit-ready render + sign-off + audit trail     │
│   • data/      synthetic spec/record corpus (seeded)          │
└────────────────────────────────────────────────────────────────┘
```

**Key design (lead with this in the whiteboard):** the LLM is confined to **understanding** (extracting and citing requirements); the **pass/fail judgment for anything quantifiable is deterministic code.** This shrinks the hallucination surface to "did it extract the requirement correctly," which the human review gate catches — rather than trusting a model to do arithmetic on safety-relevant numbers.

**Claude integration (decide details at build, then record them):**
- Current frontier model — **`claude-opus-4-8`** or **`claude-sonnet-4-6`** (record cost/quality reasoning).
- **Structured output** for extracted requirements (typed schema + verbatim citation + location + confidence).
- **Prompt caching** for the system prompt + requirement-type guide.
- The model returns **citations**, not verdicts, for quantifiable requirements.
- When building the Claude layer, follow Anthropic SDK best practices; in Claude Code, invoke the `claude-api` skill.

**Libraries:** `anthropic`, Django, `pdfplumber`/`pypdf` (text PDFs), a PDF/Markdown report renderer.

---

## 7. Compliance substance (get it right — you'll be asked)

- **Requirement model (typed):** `numeric` (min/max/units), `temporal` (max gap between named operations), `categorical` (allowed values: material, cert), `presence` (a field must exist/be recorded), `conditional` (if X then Y). Each carries `source_text`, `source_location`, `confidence`.
- **Verdict logic (deterministic where possible):**
  - numeric → compare measured vs. range/limit;
  - temporal → compute the gap from record timestamps vs. the limit;
  - categorical → membership check;
  - presence → field exists & non-empty;
  - if the needed record field is absent/unparued → **Insufficient evidence**, never "compliant."
- **Confidence & the line:** extraction confidence drives the review gate; the verdict bias is explicit — uncertainty resolves toward flag/insufficient, not pass.
- **Traceability:** the report ties requirement → spec citation → record evidence → verdict → human approver. That chain is what makes it auditable.

---

## 8. Definition of Done

Portfolio-ready when **all three** exist and are linked together:

- [ ] **App** deployed at a public URL: pick a sample spec + record → see extracted, cited requirements → review them → see clause-by-clause verdicts (incl. a **subtle catch** and an **insufficient-evidence** case) → confirm/override → export an audit-ready report with your name on it.
- [ ] **The asymmetry is visible:** uncertain cases resolve to flag/insufficient, not "compliant"; a missing field never reads "compliant."
- [ ] **`README.md`** — what/why, one-command local run (Docker), screenshots/GIF, links to live demo + `DECISIONS.md` + whiteboard video, synthetic-data + not-a-QMS disclaimers.
- [ ] **`DECISIONS.md`** — the §1 template completed, including the rejected auto-disposition option and the accepted more-false-positives trade.
- [ ] **Whiteboard recording** (5–8 min) linked from README and on hector-garza.com, including the borderline flag/clear call.
- [ ] Tests pass for the deterministic verdict logic (incl. the missing-field → insufficient-evidence rule) and the extraction-citation contract (see `PLAN.md`).

---

## 9. Hosting / deployment
- Containerize (`Dockerfile`); Django runs on Render / Railway / Fly.io / VPS. No DB strictly required for the demo (session store) — add SQLite to persist reports if desired.
- `ANTHROPIC_API_KEY` as a host secret — **never committed** (`.env` gitignored).
- Optional subdomain: `compliance.hector-garza.com`; link from the resume's future "Selected Work" section.
- Cost guard: extraction is one call per spec; cache and cap tokens.

---

## 10. Repo bootstrap (how to start this as its own repo)

```bash
mkdir spec-compliance-checker && cd spec-compliance-checker
cp /path/to/06-spec-compliance-checker/SPEC.md .
cp /path/to/06-spec-compliance-checker/PLAN.md .
# seed: README.md, DECISIONS.md (paste template below), .gitignore (python + .env!), LICENSE (MIT)

git init && git add -A && git commit -m "chore: scaffold spec-compliance-checker (spec + plan)"
git branch -M main
gh repo create cognitivefactory-hector/spec-compliance-checker --public --source=. --remote=origin --push
```

> PUBLIC repo. **Never commit `ANTHROPIC_API_KEY`** (`.env` gitignored). Synthetic documents only.

### `DECISIONS.md` starter (paste into the new repo)

```markdown
# Decision Record — Spec Compliance Checker

## Situation
<records must be checked against specs before ship; manual is slow/inconsistent; a miss = audit finding/escape; missing: fast consistent checking + a record of what was checked>

## Decision
<extract cited requirements; deterministic verdicts (numeric/temporal); 3-state incl. insufficient-evidence; bias to flag; auto-disposition you REJECTED; free-form summary you REJECTED>

## Risk
<false negative ships a noncompliance; default-to-flag/insufficient, cite everything, human signs, flag low-confidence extractions; the more-false-positives trade you ACCEPTED>

## Change
<audit prep hours→minutes; consistent checks; human confirms each; a record of what was checked; the prevented escape>

## Whiteboard session
- Recording: <link>
- The borderline flag/clear call: <…>
- Why the LLM extracts but code decides: <…>
- What I revised under push-back / held the line on: <…>
```

---

## 11. Open questions to resolve in the plan
- PDF parsing scope: typed/text PDFs only for MVP (note scanned/handwriting as a limitation) — confirm.
- How much verdict logic is deterministic vs. LLM for genuinely textual requirements — keep the deterministic share as large as possible.
- Report format first pass: Markdown (fast) vs. PDF (auditor-friendly).
- Django templates/HTMX vs. a small JS front end for the review/override UI.
