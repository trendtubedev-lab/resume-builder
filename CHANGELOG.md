# Changelog

Newest entries on top. Each entry: what changed, why, and how it was verified.

## 2026-06-17 — AI-firstify audit follow-ups (top-5 recs)

Ran the `ai-firstify` skill (audit mode) on the project, then actioned its
top-5 recommendations. No destructive changes; all additive.

- **What:**
  - **Git safety check (rec #2):** confirmed nothing sensitive is tracked —
    `.env`, `data/`, `tailorcv.db` all properly ignored; `data/` never committed
    historically. No leak, no history scrub needed. (investigation only)
  - **`.gitignore` hardening (rec #4):** added `.env.*` (+ `!.env.example`),
    `*.pem`, `*.key`, `credentials*`, `secrets*`. Verified `.env.example` still
    tracked and `.env.local` now ignored via `git check-ignore`.
  - **Export validation gate (rec #3):** new `scripts/export_check.py` — offline
    (no API key) self-test that renders `build_docx`/`build_pdf` from a sample
    resume dict and asserts non-empty output with correct magic headers (`PK..`
    for docx, `%PDF` for pdf). Wired into `scripts/live_test.py` to run first,
    before the API gate. ASCII-only output (Windows cp1252 console safe).
  - **`release-check` skill (rec #1):** new `.claude/skills/release-check/SKILL.md`
    codifying the session-close ritual (export check → live panel → secret sweep
    → CHANGELOG → memory → doc reconcile → commit) as prescriptive steps.
  - **README cost/model docs (rec #5):** added `PROVIDER` to the config table and
    rewrote the Cost note to cover API mode (pricing/console links) vs. free local
    `claude-code` mode vs. demo mode. Removed the unverified "a few cents" figure.
- **Why:** align with AI-first principles surfaced by the audit — safety
  defense-in-depth, validate the artifact users actually receive, capture the
  repeated session-close workflow as a skill, and document the $0 local path.
- **Verified:** `python scripts/export_check.py` → `[OK] docx: 35,733 bytes` /
  `[OK] pdf: 2,323 bytes` / `ALL EXPORTS OK` (exit 0). `git check-ignore` confirms
  `.env.example` un-ignored, `.env.local` ignored. Git tracking sweep clean.

## 2026-06-17 — Phase 2: persist tailored results to SQLite

- **What:** Generated resumes now survive a server restart. Replaced the
  in-memory `_STORE` dict in `app/main.py` with a `results` table in the
  existing SQLite DB (`data/tailorcv.db`).
  - **db.py:** new `results` table (`job_id PK, owner, resume_json, created_at`)
    in `init_db()`, plus `save_result(job_id, owner, resume)` (JSON-serializes
    the resume dict) and `get_result(job_id) -> {'resume', 'owner'} | None`.
  - **main.py:** removed `_STORE`; `/api/tailor` calls `db.save_result(...)`,
    `/api/download` reads `db.get_result(...)`. Ownership check unchanged. The
    "Result expired" copy is now "Result not found" (results no longer expire).
- **Scope decisions (see DECISIONS.md):** API keys deliberately stay in memory
  (safest — no secrets at rest; `api`-mode users re-enter after restart,
  `claude-code` needs none). No TTL / no free-vs-member tiers — that ships with
  the future paid/hosted tier, not this codebase. SQLite chosen over Redis;
  Postgres swap later is a contained `db.py` change since nothing else touches SQL.
- **Decision D resolved:** free/cheap = bring-your-own-key (or own Claude plan);
  paid = we host on our own infra with our key. Logged in DECISIONS.md.
- **Verified (local, .venv):** `py_compile app/db.py app/main.py` OK; save →
  fresh connection read (simulates restart) round-trips the dict + owner;
  missing job_id → None. Test row deleted from the DB afterward.

## 2026-06-17 — Harden untrusted PDF/DOCX parsing (item C)

- **What:** Made `app/parsing.py` safe against hostile/malformed uploads, and
  changed `app/main.py` to parse off the event loop with a timeout.
  - **Timeout + offload (main.py):** `parsing.extract_text` now runs via
    `asyncio.wait_for(asyncio.to_thread(...), PARSE_TIMEOUT)` (default 15s, env
    `PARSE_TIMEOUT_SECONDS`). A crafted file that hangs pypdf/python-docx can no
    longer block the event loop or freeze the server → returns 400.
  - **DOCX zip-bomb guard:** `_check_docx_bomb` inspects the zip directory
    before python-docx decompresses; rejects if uncompressed total >50 MB
    (`MAX_DOCX_UNCOMPRESSED_MB`) or compression ratio >100× (`MAX_DOCX_ZIP_RATIO`).
  - **Extracted-text cap:** per-file text truncated to 200k chars
    (`MAX_RESUME_CHARS`); PDF loop stops early once the cap is hit.
  - **Broadened error handling:** `_guard` wraps each parser; any unexpected
    exception → generic user-facing ValueError (→400), real details logged
    server-side only (no stack-trace/info leak, matching the S2 fix pattern).
  - **XXE/billion-laughs:** verified python-docx's lxml parser does NOT expand
    DTD entities (`&a;` → None), so entity-expansion attacks are already blunted
    at the parser; the size/ratio caps bound any residual memory blow-up.
- **Why:** open hardening item C — uploads are untrusted input.
- **Verified (local, .venv):** normal TXT/DOCX/PDF parse unchanged; zip-bomb,
  bad-zip-as-docx, garbage-PDF, and over-cap text each return a clean ValueError
  with no stack trace (pypdf's own error stays in server logs); text cap honored
  (500→100 chars). `py_compile app/parsing.py app/main.py` OK. Timeout path is
  by-construction (not exercised with a real hanging file).

## 2026-06-17 — Add TailorCV logo (header, favicon, PDF cover)

- **What:** Integrated the brand logo across the app. New assets in `app/static/`: `logo.png` (full 2048×2048 master from Nano Banana), `logo_icon.png` (655×655 transparent square icon, cropped from master), `logo_icon_flat.png` (same icon flattened on white for print), `favicon.ico`. Mounted `/static` via `StaticFiles` in `app/main.py`. Header (`index.html`) shows the icon mark + "TailorCV" wordmark; browser tab uses the favicon; PDF cover (`scripts/generate_install_guide.py`) shows the flat icon above the title banner.
- **Why:** Branding for the public release.
- **Gotcha fixed:** First pass used the full master image (contained both icon + wordmark variants + transparency) → showed a checkerboard and double "TailorCV" in both header and PDF. Fixed by detecting the navy square's bounding box programmatically and cropping a tight 655×655 icon; flat (RGB, no alpha) version used in PDF to avoid the transparency checkerboard.
- **Verified:** Crop confirmed square (ratio 1.0), flat version is RGB with navy edge-to-edge corners (no transparency). Michael visually approved both the rendered PDF cover and the webpage header.

## 2026-06-16 — Add GitHub installation guide PDF

- **What:** `docs/TailorCV_Install_Guide.pdf` — generated via `scripts/generate_install_guide.py` (reportlab). Covers: what TailorCV is, two setup paths (Claude plan vs API key), download/install steps, usage walkthrough, FAQ (8 questions), troubleshooting table, stop/restart instructions.
- **Why:** User-requested downloadable guide for the public GitHub repo.
- **Verified:** PDF generated successfully at `docs/TailorCV_Install_Guide.pdf`.

## 2026-06-16 — Add in-app Help modal

- **What:** Tabbed Help modal (How to use / Review panel / Troubleshooting / FAQ) triggered by a `?` button in the app header. Vanilla JS + CSS only, no new dependencies. Modal closes on overlay click or Escape key. Tabs scroll horizontally on narrow screens. All content written for end users, not developers.
- **Why:** User-requested in-app documentation.
- **Verified:** (unverified — requires browser check)

## 2026-06-16 — Add Manage Reviewers feature

- **What:** Full CRUD UI for reviewer personas. New files: `app/db.py` (SQLite at `data/tailorcv.db`), `app/personas.py` (preset + custom merge). Four new API routes (`GET/POST/PUT/DELETE /api/personas`). `agents.py` now loads personas dynamically per user. `index.html` gets a collapsible "Manage Reviewers" card: click any reviewer to view/edit, lock icon on presets, reset-to-default for presets, delete for custom, Add button for new ones.
- **Why:** User requested ability to view, edit, add, and delete reviewers. Designed with paywall tiers in mind (free/paid limits enforced at API layer later).
- **Verified:** Server boots clean; `GET /api/personas` returns all 4 presets correctly.

## 2026-06-16 — Fix em-dash mojibake in review panel

- **What:** Added `encoding="utf-8"` to `subprocess.run` in `app/agents.py:248`.
- **Why:** On Windows, `text=True` without an explicit encoding uses the system default (cp1252). Claude's output contains UTF-8 em-dashes (`—`) which were decoded as `â€"` garbage.
- **Verified:** (unverified — requires a live run through the tailor endpoint)

## 2026-06-16 (later 3) — browser test passed; perf note

- **Browser-tested claude-code mode end-to-end via the UI** (server on :8000,
  `PROVIDER=claude-code`, fixed code `56ca56d`): real tailoring run completed,
  `POST /api/tailor` → 200, Michael confirmed "looks good." Green banner, real
  panel, downloads all working.
- **Observed: claude-code mode is SLOW (~1–3 min/run), not the "~20–40s" the UI
  shows.** Cause: each run spawns 5 separate `claude -p` processes (Node startup
  + agent loop ×4 reviewers + synth). Not a bug — but the wait-text is misleading
  and made it look hung. PENDING fix next session: (a) honest wait-text for
  claude-code mode, and/or (b) default reviewers to Haiku in claude-code mode for
  speed (Michael leaned (b), unconfirmed). See MEMORY "Open / next".
- Background dev server stopped at end of session.

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
