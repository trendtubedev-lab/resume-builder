# Changelog

Newest entries on top. Each entry: what changed, why, and how it was verified.

## 2026-06-16 (later 2) — code-review + security fixes on Pro/Max mode

Review of `b32c346` (high-effort code review + security review) found 7 issues;
fixed the blockers + hardening. Verified each below.

- **CR-1 (CRITICAL) — `PROVIDER` in `.env` was silently ignored.** `agents.py`
  read `PROVIDER` at *import* time, but `main.py` imported `agents` before
  `load_dotenv()` ran — so a friend setting `PROVIDER=claude-code` in `.env`
  (exactly what QUICKSTART says) got `api`/demo mode. Fixes: `using_claude_code()`
  now reads `os.getenv` lazily; `reviewer_model()`/`synth_model()` made lazy too;
  `main.py` moved `load_dotenv()` ABOVE the package imports. agents.py now has
  **zero import-time env reads**. Verified: temp `.env` with `PROVIDER=claude-code`
  → `using_claude_code()` True (was False); late-set `REVIEWER_MODEL` honored.
- **CR-2 (MED) — stray `</content>`/`</invoke>` tags** at the end of
  `QUICKSTART_FRIENDS.md` (leaked tool-call tags). Removed.
- **S1 (MED, security) — `claude -p` ran with all tools enabled over untrusted
  resume text.** Prompt-injection in a resume could induce tool use on the host
  (matters once hosted). Added `--tools ""` to the subprocess argv (verified the
  flag disables all tools and JSON still returns). Prompt was already piped via
  stdin, not argv — no shell/command injection.
- **S2 (LOW) — `claude` stderr was returned to the HTTP client** (path/info
  disclosure). Now logged server-side; client gets a generic message.
- **CR-3 (LOW) — Anthropic client rebuilt 5×/run** in api mode. `_client()` now
  `@lru_cache`d by key (raises aren't cached; thread-safe enough for the pool).
- **CR-4 (LOW) — bad `CLAUDE_CODE_TIMEOUT` crashed at import** via `int()`. Now
  `_cc_timeout()` try/excepts → falls back to 180 with a warning. Verified
  (`CLAUDE_CODE_TIMEOUT=180s` → warns, uses 180).
- **S3 (INFO)** — silent api fallback spending the operator's key was a
  consequence of CR-1; fixing CR-1 closes it. Long-term still gated by decision D.
- **Verified:** `py_compile` OK; end-to-end claude-code run WITH `--tools ""`
  (haiku) returned 4 scored reviewers (68/60/62/65) + full structured synth JSON;
  independent subagent review pass found no regressions.

## 2026-06-16 (later)

### Added — Pro/Max local mode (PROVIDER switch: api | claude-code)
- **What:** New provider abstraction so AI calls can route through the user's
  LOCAL Claude Code CLI on their own Pro/Max plan instead of an Anthropic API
  key. Selected by `PROVIDER` env (`api` default, `claude-code` for local).
  - `app/agents.py`: added `complete()` dispatcher + `_api_complete()` /
    `_claude_code_complete()` (shells out to `claude -p --output-format json`,
    prompt piped via stdin to dodge OS arg-length limits, runs in a neutral
    temp cwd so the repo's CLAUDE.md isn't injected, resolves the Windows `.cmd`
    shim via `shutil.which`). Added `using_claude_code()` and `preflight()`.
    Refactored `_review_one` / `run_panel` / `synthesize` off the raw SDK client
    onto `complete()`. max_tokens/temperature don't apply in claude-code mode
    (CLI doesn't expose them) — noted in code.
  - `app/main.py`: calls `agents.preflight()` at boot (fail-fast if `claude`
    missing in claude-code mode); `/api/tailor` treats claude-code as a real run
    (never demo, no key); `/api/me` returns `provider` and correct `demo` flag.
  - `app/static/index.html`: hides the API-key card + shows a green "Running on
    your Claude plan" banner in claude-code mode; wait/demo text keys off `demo`.
  - `.env.example`: documented `PROVIDER` / `CLAUDE_CODE_TIMEOUT`.
  - New `QUICKSTART_FRIENDS.md`: friend-facing setup (install Claude Code, sign
    in with subscription, set `PROVIDER=claude-code` + `AUTH_DISABLED=1`, run).
- **Why:** Phase-1 trial — a few friends download and run locally on their own
  Claude plans (no API key, no cost to operator) before hosting for the masses.
- **Verified (real, host-side):**
  - `claude -p --output-format json` shape confirmed (text in `.result`); stdin
    piping + `claude-sonnet-4-6` alias confirmed working.
  - `py_compile app/agents.py app/main.py` → COMPILE OK.
  - End-to-end in claude-code mode (haiku, no API key): `run_panel` returned 4
    scored reviewers (47/52/40/38, overall 44); `synthesize` returned full
    structured JSON (all expected keys, change_summary populated). END-TO-END OK.
  - `api` mode: preflight passes, `app.main` imports cleanly via `.venv`.
- Note: `claude -p` prints a `total_cost_usd` estimate even on a subscription;
  actual billing depends on the friend's Claude Code login (Pro/Max OAuth =
  covered by plan). `(unverified)` exact subscription usage-limit behavior.

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
