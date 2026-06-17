# Changelog

Newest entries on top. Each entry: what changed, why, and how it was verified.

## 2026-06-16

### Added — repo-local memory system + subagent rule
- New `MEMORY.md` (current-state snapshot) and `DECISIONS.md` (locked/open decisions). `CLAUDE.md` preflight now starts by reading `MEMORY.md` / `DECISIONS.md` / recent `CHANGELOG.md` (step 0). Added a launching-agents rule (no subagents unless asked; high-stakes-verification exception requires approval), `[EXAMPLE — not real data]` labeling, stronger secrets wording (`.env` only, never hardcode/print/copy), and batch-clarifying-questions.
- Why: make memory durable and independent of the read-only Cowork auto-memory; prevent unrequested, token-expensive subagent spawns.
- Verified: files written host-side via Write/Edit and confirmed in context; commit/push pending (run locally).

### Added — project rules + memory/changelog discipline
- Created `CLAUDE.md` in the repo root (the real one — `CLAUDE-workspace\resume builder`). Includes a mandatory session-start preflight (confirm correct folder, root-cause truncated/stale files, never run sandbox git on truncated files, inventory tools before claiming limits, verify-then-claim) and an "after every change" rule to update this CHANGELOG and the memory store.
- Why: rules kept "vanishing" because prior sessions saved them to a non-repo / wrong-folder location; and a full session was wasted editing the wrong copy of the project and misdiagnosing truncated files as "mount lag."
- Verified: file written via host-side Write tool and confirmed on disk; committed in `abe48a0`.
- Memory note: the Cowork auto-memory store was READ-ONLY/unreachable this session, so per the fallback rule these notes are recorded here instead.

### Security — hardening pass (app/main.py, render.yaml)
- **SESSION_SECRET boot guard**: `resolve_session_secret()` refuses to start if the secret is unset or a known placeholder while auth is enabled; uses an ephemeral key only in local `AUTH_DISABLED=1` mode. Closes a forgeable-session-cookie auth bypass (and theft of any server-wide `ANTHROPIC_API_KEY`).
- **render.yaml**: provisions `SESSION_SECRET` via `generateValue: true`; adds `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` as `sync: false`.
- **Fix A — Content-Disposition sanitization**: `_safe_filename()` strips quotes/CRLF/separators from the download filename (used in `download()`); closes response-header injection.
- **Fix B — capped upload read**: `_read_capped()` reads uploads in 64 KB chunks and aborts at 5 MB/file; added a 12 MB per-request total cap. Memory is now bounded instead of buffering the whole file before the size check.
- Verified: each fix confirmed present and wired via the host-side Read tool; logic unit-tested in an isolated sandbox harness (filename cases safe; oversize read stopped at ~limit+chunk) — ALL PASS. NOTE: `py_compile`/`git` run inside the Cowork sandbox were unreliable because the sandbox mount served truncated files; final `python -m py_compile` should be run locally.

### Repo
- Initialized git and pushed to the public GitHub repo `trendtubedev-lab/resume-builder` (`main`). Commits: `2395b05` (initial), `abe48a0` (security hardening + rules).

### Open items (not yet done)
- C (low): harden untrusted PDF/DOCX parsing (caps + clean errors).
- D (decision): `auth.user_api_key()` falls back to a server-wide `ANTHROPIC_API_KEY` → any signed-in user spends the operator's money, no rate limit. Tied to the undecided bring-your-own-key vs. you-pay model.
