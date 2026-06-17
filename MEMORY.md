# MEMORY — TailorCV (current state)

Read at session start. Keep it short; update in the SAME session as any real change.

## What it is
FastAPI backend + single-file HTML frontend (`app/static/index.html`). Upload 1–3 resumes + paste a job description → a multi-agent Claude review panel (recruiter, ATS, hiring manager, editor) critiques independently → a synthesizer rewrites into structured JSON → export as PDF or Word. Google OAuth; each user supplies their own Anthropic key (kept in memory). Demo mode (offline, fake panel + bundled sample resumes) when no key.

## Code map
- `app/main.py` — routes, session-secret guard, upload handling, download
- `app/agents.py` — review panel + synthesis (Claude API)
- `app/auth.py` — Google OAuth + per-user API keys
- `app/parsing.py` — PDF/DOCX/TXT text extraction
- `app/export.py` — PDF/Word rendering
- `app/demo.py` — offline demo mode
- `scripts/live_test.py` — live tailoring harness (run locally only)
- Deploy: `Dockerfile`, `Procfile`, `render.yaml`

## Status (2026-06-16)
- Security hardening done & committed (`abe48a0`): SESSION_SECRET boot guard; Content-Disposition filename sanitization; chunked/capped upload read. `render.yaml` provisions `SESSION_SECRET` (`generateValue`) + Google creds.
- Pushed to public repo `trendtubedev-lab/resume-builder` (branch `main`).
- Storage is in-memory (`_STORE`, `auth.USER_KEYS`) — not persistent. Phase 2 = real datastore.

## Open / next
- C: harden untrusted PDF/DOCX parsing (low priority).
- D: bring-your-own-key vs. you-pay — OPEN (see `DECISIONS.md`); gates billing/rate-limit work.
- Live API validation must run locally (`python scripts/live_test.py`); the Cowork sandbox blocks `api.anthropic.com`.

## Gotchas
- The Cowork auto-memory store is read-only/unreachable here → these repo files are the source of truth.
- The Cowork sandbox has served the WRONG folder and TRUNCATED files — host-side Read/Write/Edit are authoritative; never run git from the sandbox on truncated files. See `CLAUDE.md` preflight.
