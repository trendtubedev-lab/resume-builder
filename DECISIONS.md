# DECISIONS — TailorCV

Locked choices and open questions. Don't re-litigate LOCKED items without flagging me. Date new entries.

## Locked
- 2026-06-16 — **Two-phase rollout:** Phase 1 = a few friends download & run TailorCV locally on their OWN Claude Pro/Max plans (`PROVIDER=claude-code`, no API key); iterate; Phase 2 = host for the masses (API keys + billing/persistence). The `claude-code` local provider is a trial harness, not the final hosted architecture.
- 2026-06-16 — Memory & rules live repo-local (`CLAUDE.md` + `MEMORY.md` + `DECISIONS.md` + `CHANGELOG.md`), NOT the Cowork auto-memory (read-only/unreliable here).
- 2026-06-16 — Public GitHub repo `trendtubedev-lab/resume-builder`, branch `main`.
- Models default to `claude-sonnet-4-6` (`REVIEWER_MODEL` / `SYNTH_MODEL`, overridable via env).
- Per-user Anthropic keys stored in memory only — not on disk, not in the session cookie.
- 2026-06-23 — **claude-code only, permanently.** No Anthropic API key mode, no demo mode. App runs exclusively through the local `claude` CLI on the user's own Pro/Max plan. `app/demo.py` deleted; `anthropic` SDK removed from deps. Do not re-add an API key path without a new explicit decision.
- 2026-06-17 — **D RESOLVED — Monetization / key model:** **free/cheap tier = bring-your-own** (user supplies their own Anthropic key via `api` mode, or runs on their own Claude plan via `claude-code` mode — we pay nothing). **Paid tier = we host** on our own infrastructure with our key, eating the API cost; that's the paid offering. The free/BYO tier is this codebase; the paid/hosted tier is a future, separate build. → No `member`/tier concept belongs in this repo yet; it ships with the paid-hosting build.
- 2026-06-17 — **Phase 2 persistence:** **SQLite** (`data/tailorcv.db` via `app/db.py`), not Redis. Generated results persisted in a `results` table; **API keys stay in memory** (secrets never on disk). No TTL / tiers (keep forever) — revisit pruning + free-vs-member retention when the paid tier is built. Postgres swap is a contained `db.py` change if a high-write hosted tier needs it.
