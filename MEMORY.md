# MEMORY — TailorCV (current state)

Read at session start. Keep it short; update in the SAME session as any real change.

## What it is
FastAPI backend + single-file HTML frontend (`app/static/index.html`). Upload 1–3 resumes + paste a job description → a multi-agent Claude review panel critiques independently → a synthesizer rewrites into structured JSON → export as PDF or Word. Google OAuth; demo mode (offline, fake panel) when no real provider.

**Provider:** `PROVIDER=claude-code` (local Claude Code CLI on user's own Pro/Max plan). No API key UI, no per-user key storage — removed permanently. Server-level `ANTHROPIC_API_KEY` in `.env` is the only API path (for future hosted mode). See `QUICKSTART_FRIENDS.md`.

## Code map
- `app/main.py` — routes, session-secret guard, upload handling, download
- `app/agents.py` — review panel + synthesis (claude-code or API)
- `app/personas.py` — 15 preset reviewer personas (4 default-enabled, 11 opt-in)
- `app/auth.py` — Google OAuth (no key storage)
- `app/parsing.py` — PDF/DOCX/TXT text extraction
- `app/export.py` — PDF/Word rendering
- `app/demo.py` — offline demo mode
- `app/db.py` — SQLite persistence for tailored results
- `scripts/export_check.py` — OFFLINE export self-test
- `scripts/live_test.py` — live tailoring harness (run locally only)
- `.claude/skills/release-check/SKILL.md` — session-close ritual

## Status (2026-06-17)
- **Latest push: b0db009** on `trendtubedev-lab/resume-builder` main
- PROVIDER=claude-code confirmed working end-to-end; all 3 live_test samples pass fabrication check
- **Per-user API key storage PERMANENTLY REMOVED** — USER_KEYS, /api/key routes, key card UI all gone. No billing path for any user.
- **15 reviewer personas** in pool: original 4 (default on) + 11 new opt-in (Engineering Bar-Raiser, Leveling Calibrator, Career Narrative Strategist, Transferable Skills Interpreter, Attention & Perception Specialist, Domain Credentialing Auditor, Industry Format & Culture Fit Auditor, Competitive Field Analyst, Executive Presence Assessor, Commitment Signal Analyst, First-Impression Clarity Analyst)
- **Inline persona selector** on main form — chip cards, click to toggle, original 4 pre-checked, selected keys sent with each tailor request
- SQLite persistence: tailored results survive restart. No TTL/tiers yet.
- Parsing hardened: zip-bomb guard, text cap, timeout via asyncio.to_thread
- Security: SESSION_SECRET boot guard, Content-Disposition sanitization, chunked upload read

## Open / next
- Project MEMORY.md in repo is authoritative; auto-memory store at ~/.claude/projects/.../memory/ is the cold-start backup
- No TTL on SQLite results — deferred to paid tier
- Live API validation must run locally (`python scripts/live_test.py`); sandbox blocks api.anthropic.com

## Gotchas
- PROVIDER=claude-code must be in .env — if missing, app falls to demo mode (no API key = no real run)
- When changing provider/mode: always audit stored creds, open billing paths, and stale UI — don't just flip the setting
- Cowork sandbox has served wrong/truncated files — host-side Read/Write/Edit are authoritative
