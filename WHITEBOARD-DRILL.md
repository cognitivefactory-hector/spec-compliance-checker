# Whiteboard Drill — Spec Compliance Checker (design-stage)

> Rehearsal for the recorded whiteboard session. **The push** is me playing tough reviewer; **Defense** is the position that survives; **⚠ Your move** is what only you can answer once you've built/measured it. Fold the survivors into `DECISIONS.md`, then record.
> Scope: design-stage. Re-run after **M5** with a real subtle-catch + insufficient-evidence example.

## Q1 — "This is just an LLM reading two documents. Where's the engineering?"
**The push:** Upload, prompt, done.
**Defense (survives):** The engineering is the **split**: the LLM does *typed, cited requirement extraction*; **deterministic code makes every numeric/temporal pass-fail call.** Plus the three-state verdict (Compliant / Non-compliant / **Insufficient evidence**), the false-negative-biased threshold, and the requirement-review gate. The model understands; code decides; a human signs.
**⚠ Your move:** Point at the deterministic verdict module as the safety core.

## Q2 — "The LLM will miss a requirement or invent one. In a regulated audit that's catastrophic."
**The push:** One missed clause = an escape.
**Defense (survives):** Extraction is **grounded and cited** (verbatim source text + location), low-confidence extractions are **flagged**, and the engineer **reviews the requirement list before checking** — so a miss/invention is caught upfront, not buried in a verdict. Nothing is asserted without a citation back to the spec.
**⚠ Your move:** Be honest that extraction recall isn't 100% — the review gate is the compensating control; say so.

## Q3 (the killer) — "Why bias toward over-flagging? Engineers will drown in false positives and tune it out."
**The push:** Alarm fatigue kills your tool.
**Defense (survives):** Because the costs are **asymmetric**: a false negative is an audit finding or a field escape; a false positive is ~five minutes of an engineer's time. I optimize for that asymmetry — uncertainty resolves to flag/insufficient, never to "compliant." But I keep the signal usable: most clauses are clean deterministic passes, so flags concentrate on the genuinely ambiguous, textual ones.
**⚠ Your move:** Quantify the asymmetry (cost of an audit finding vs. minutes per review) and show flags aren't the majority of clauses.

## Q4 — "How does this pass NADCAP scrutiny? Auditors distrust black boxes."
**The push:** AI-generated compliance won't fly.
**Defense (survives):** Every verdict cites the **spec clause and the record field**; there's an audit trail and a human approver of record. The quantifiable verdicts are deterministic (not model opinion), so they're reproducible. It's objective evidence with a human signature — exactly what an auditor wants.
**⚠ Your move:** Name the specific "objective evidence" standard this satisfies (your audit experience).

## Q5 — "Synthetic, clean PDFs — real records are scanned, handwritten, weirdly formatted."
**The push:** It'll choke on reality.
**Defense (survives):** True — MVP is typed/text PDFs; scanned/handwriting (OCR) is a named limitation, not a hidden one. The method (extract→check→cite→sign) holds regardless of ingest; OCR is an additive front-end. Honesty about the boundary is the senior move.
**⚠ Your move:** Note what fraction of real records are clean PDFs vs. scans in your world.

## Q6 — "Show me a case the tool flagged that a human cleared — or cleared that a human flagged."
**The push:** Where's the judgment line?
**Defense (survives):** The borderline case proves I understand where "flag vs. fail" sits: e.g., a time-between-ops exceeded by a hair that the tool flags and a human clears with documented justification — or a missing field the tool refuses to call compliant. The point is the tool surfaces; the human adjudicates.
**⚠ Your move:** Build the subtle-noncompliance + missing-field fixtures so you have real borderline cases to narrate.

## Verdict — SDRC after the drill
- **Holds:** LLM-extracts/code-decides split; false-negative asymmetry; human-signs.
- **Sharpen:** lead with the **split** (Q1) and the **asymmetry numbers** (Q3); make the review gate the answer to "it'll miss a requirement" (Q2); have the borderline + missing-field demos ready (Q6).
- **Land this line in the room:** *"A missing field is never 'compliant' — the model extracts and cites, deterministic code judges the numbers, and a qualified engineer signs."*
