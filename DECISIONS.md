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
- **Backend:** Django — one stack across the portfolio.
- **Split:** LLM confined to **understanding** (typed, cited requirement extraction); **deterministic code** evaluates everything quantifiable. The model returns citations, not verdicts.
- **Tested invariant:** a missing record field yields "Insufficient evidence," never "compliant"; uncertainty never resolves to pass.
- **Host:** Render (Dockerized) behind Cloudflare. `ANTHROPIC_API_KEY` never committed.
