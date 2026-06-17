# MEMORY — TailorCV (current state)

Read at session start. Keep it short; update in the SAME session as any real change.

## What it is
FastAPI backend + single-file HTML frontend (`app/static/index.html`). Upload 1–3 resumes + paste a job description → a multi-agent Claude review panel (recruiter, ATS, hiring manager, editor) critiques independently → a synthesizer rewrites into structured JSON → export as PDF or Word. Google OAuth; each user supplies their own Anthropic key (kept in memory). Demo mode (offline, fake panel + bundled sample resumes) when no key.

**Two providers** (`PROVIDER` env): `api` (default — Anthropic API key, hosted path) or `claude-code` (local Claude Code CLI on the user's own Pro/Max plan, no API key — the Phase-1 friends-trial path). See `QUICKSTART_FRIENDS.md`.

## Code map
- `app/main.py` — routes, session-secret guard, upload handling, download
- `app/agents.py` — review panel + synthesis (Claude API)
- `app/auth.py` — Google OAuth + per-user API keys
- `app/parsing.py` — PDF/DOCX/TXT text extraction
- `app/export.py` — PDF/Word rendering
- `app/demo.py` — offline demo mode
- `scripts/export_check.py` — OFFLINE export self-test (no API key); validates docx/pdf magic headers + size. Run first in `live_test.py`.
- `scripts/live_test.py` — live tailoring harness (run locally only)
- `.claude/skills/release-check/SKILL.md` — session-close ritual as a skill
- Deploy: `Dockerfile`, `Procfile`, `render.yaml`

## Status (2026-06-16)
- Security hardening done & committed (`abe48a0`): SESSION_SECRET boot guard; Content-Disposition filename sanitization; chunked/capped upload read. `render.yaml` provisions `SESSION_SECRET` (`generateValue`) + Google creds.
- Pushed to public repo `trendtubedev-lab/resume-builder` (branch `main`).
- **Phase 2 DONE (2026-06-17): tailored results persisted to SQLite.** `_STORE` dict removed from `main.py`; new `results` table + `save_result`/`get_result` in `db.py`. Results survive restart. `auth.USER_KEYS` deliberately STAYS in memory (no secrets at rest). No TTL/tiers — defers to paid tier. NOT yet committed/pushed.
- **Pro/Max local mode** (`PROVIDER=claude-code` routes via local `claude -p`): committed+pushed in `b32c346`. Files: `app/agents.py` (provider layer + `preflight()`), `app/main.py`, `app/static/index.html`, `.env.example`, `QUICKSTART_FRIENDS.md`. Plan = friends trial locally on own plans, then host (Phase 2).
- **Review fixes committed+pushed in `56ca56d`:** code+security review of b32c346 found CR-1 (CRITICAL: `.env` PROVIDER ignored due to import-time env read before `load_dotenv` → fixed: all agents.py env reads now lazy + `load_dotenv` moved above imports), plus `--tools ""` hardening (S1), stderr-leak fix (S2), client caching (CR-3), bad-timeout guard (CR-4), removed stray tags in QUICKSTART (CR-2). All verified incl. end-to-end. See CHANGELOG "later 2".
- **Browser-tested in claude-code mode (2026-06-16): WORKS — Michael ran a real tailoring via the UI, "looks good."** Green banner + real panel + downloads confirmed. He's continuing in Claude Desktop next session and has an IMAGE to show.

## Open / next
- claude-code mode speed: Michael says it's no longer slow (2026-06-17). Perf item closed; no wait-text/Haiku change made.
- **C DONE (2026-06-17): untrusted PDF/DOCX parsing hardened.** `parsing.py` (zip-bomb guard, text cap, broad error→generic ValueError) + `main.py` (parse off-loop via `asyncio.to_thread` with `PARSE_TIMEOUT`, default 15s). Env knobs: `PARSE_TIMEOUT_SECONDS`, `MAX_DOCX_UNCOMPRESSED_MB`, `MAX_DOCX_ZIP_RATIO`, `MAX_RESUME_CHARS`. Verified locally; committed+pushed `4bb171a`.
- D RESOLVED (2026-06-17): free/cheap = bring-your-own-key (or own Claude plan); paid = we host on our own infra with our key. Free/BYO = this codebase; paid/hosted = future separate build (where member tiers + retention live). See `DECISIONS.md`.
- Live API validation must run locally (`python scripts/live_test.py`); the Cowork sandbox blocks `api.anthropic.com`. (claude-code mode worked from here — `claude` CLI present + signed in on this machine.)

## AI-firstify follow-ups (2026-06-17, NOT yet committed)
Ran `ai-firstify` audit; actioned top-5. (#2) git sweep clean — nothing sensitive tracked. (#4) `.gitignore` broadened (`.env.*`, `*.pem`, `*.key`, `credentials*`, `secrets*`; `!.env.example` kept). (#3) `scripts/export_check.py` offline export gate, wired into `live_test.py` first. (#1) `release-check` skill added. (#5) README cost note rewritten (API vs free local `claude-code` vs demo; `PROVIDER` in config table). All verified except live API (sandbox-blocked). Uncommitted.

## Gotchas
- The Cowork auto-memory store is read-only/unreachable here → these repo files are the source of truth.
- The Cowork sandbox has served the WRONG folder and TRUNCATED files — host-side Read/Write/Edit are authoritative; never run git from the sandbox on truncated files. See `CLAUDE.md` preflight.
