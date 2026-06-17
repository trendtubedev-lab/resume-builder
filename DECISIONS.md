# DECISIONS — TailorCV

Locked choices and open questions. Don't re-litigate LOCKED items without flagging me. Date new entries.

## Locked
- 2026-06-16 — **Two-phase rollout:** Phase 1 = a few friends download & run TailorCV locally on their OWN Claude Pro/Max plans (`PROVIDER=claude-code`, no API key); iterate; Phase 2 = host for the masses (API keys + billing/persistence). The `claude-code` local provider is a trial harness, not the final hosted architecture.
- 2026-06-16 — Memory & rules live repo-local (`CLAUDE.md` + `MEMORY.md` + `DECISIONS.md` + `CHANGELOG.md`), NOT the Cowork auto-memory (read-only/unreliable here).
- 2026-06-16 — Public GitHub repo `trendtubedev-lab/resume-builder`, branch `main`.
- Models default to `claude-sonnet-4-6` (`REVIEWER_MODEL` / `SYNTH_MODEL`, overridable via env).
- Per-user Anthropic keys stored in memory only — not on disk, not in the session cookie.

## Open
- **D — Monetization / key model:** bring-your-own-key vs. you-provide-key-and-charge. Undecided. Blocks billing, rate limiting, and whether to keep the server-wide `ANTHROPIC_API_KEY` fallback in `auth.user_api_key()`.
- **Phase 2 persistence:** which datastore replaces in-memory `_STORE` / `USER_KEYS` (e.g. Redis vs. SQL DB).
