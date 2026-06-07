# Spec Compliance Checker

Upload a process spec and a production record; it extracts each requirement (cited), checks the record against it, and produces an audit-ready report — deliberately biased toward *catching the miss*, because a false negative is an audit finding and a false positive is five minutes of an engineer's time.

> **Status:** scaffolded (spec + plan in place). Build follows `PLAN.md` (M0 → M9).
> **Illustrative tool on synthetic documents — not a quality system of record; a qualified engineer signs every disposition.**

Part of [hector-garza.com](https://hector-garza.com)'s portfolio. One of three equal deliverables: the app, a **Decision Record** ([`DECISIONS.md`](./DECISIONS.md)), and a recorded whiteboard session. A working demo no longer proves competence — the judgment behind it does. See [`SPEC.md`](./SPEC.md) §0.

## What it does
- Extracts discrete, **typed, cited** requirements from a spec (numeric range, temporal/time-between-ops, categorical, presence, conditional).
- Checks each against the production record → **Compliant / Non-compliant / Insufficient evidence.**
- **Deterministic code makes the numeric/temporal verdicts; the LLM only extracts and cites** — so a model never does arithmetic on safety numbers.
- A missing field is **never** "compliant." Human confirms every verdict; audit-ready report export with approver + timestamp.

## Tech stack
- **Backend:** Django
- **AI:** Anthropic SDK (Claude) — structured, cited requirement extraction (not verdicts), prompt caching
- **Docs:** `pdfplumber` / `pypdf` (typed/text PDFs)
- **Frontend:** Django templates + HTMX
- **Packaging:** Docker · **Quality:** pytest + ruff + GitHub Actions CI

## Run locally
With Docker (one command):
```bash
docker build -t scc . && docker run --rm -p 8000:8000 -e DJANGO_SECRET_KEY=dev scc
# → http://localhost:8000
```

Or with a virtualenv:
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # then edit as needed
python manage.py runserver    # → http://localhost:8000
pytest                        # run the tests
ruff check .                  # lint
```

## Deployment
- **Live demo:** Dockerized Django app on **Render**, fronted by **Cloudflare** (planned subdomain `compliance.hector-garza.com`).
- `ANTHROPIC_API_KEY` lives in `.env` (gitignored) / host secrets — **never committed.**

## Links (filled in as the build progresses)
- 🔗 Live demo: _TBD_
- 🧠 Decision record: [`DECISIONS.md`](./DECISIONS.md)
- 🎥 Whiteboard walkthrough: _TBD_

## Build
See [`PLAN.md`](./PLAN.md) — M0 (scaffold) → M9. The deterministic verdict logic (incl. missing-field → insufficient-evidence) is built first; the cited extraction layer goes on top.
