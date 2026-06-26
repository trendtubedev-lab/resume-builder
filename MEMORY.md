# MEMORY — TailorCV (current state)

Read at session start. Keep it short; update in the SAME session as any real change.

## What it is
FastAPI backend + single-file HTML frontend (`app/static/index.html`). Upload 1–3 resumes + paste a job description → a multi-agent Claude review panel critiques independently → a synthesizer rewrites into structured JSON → export as PDF or Word. Google OAuth; `AUTH_DISABLED=1` for local single-user use.

**Provider:** Local `claude` CLI only (user's own Pro/Max plan). No API key, no demo mode — both removed permanently. See `QUICKSTART_FRIENDS.md`.

## Code map
- `app/main.py` — routes, session-secret guard, upload handling, download
- `app/agents.py` — review panel + synthesis (claude-code or API)
- `app/personas.py` — 15 preset reviewer personas (4 default-enabled, 11 opt-in)
- `app/auth.py` — Google OAuth (no key storage)
- `app/parsing.py` — PDF/DOCX/TXT text extraction
- `app/export.py` — PDF/Word rendering (3 templates: classic/banner/minimal)
- `app/db.py` — SQLite persistence for tailored results
- `scripts/export_check.py` — OFFLINE export self-test (asserts magic bytes)
- `scripts/render_samples.py` — OFFLINE: renders all 3 templates × PDF/DOCX to `output/samples/` for visual review
- `scripts/live_test.py` — live tailoring harness (run locally only)
- `.claude/skills/release-check/SKILL.md` — session-close ritual

## Status (2026-06-25)
- **Latest push:** `e7fa9a8` — clickable contact hyperlinks in PDF + DOCX
  (`_classify_contact`/`_canvas_contact`/`_add_hyperlink`; `_shade` promoted to
  module scope). Pushed to `trendtubedev-lab/resume-builder` main.
  Prior pushes: `23cbb6c` (export professionalism pass: PDF bullet fix +
  right-aligned dates, em dash, DOCX heading rules, unified margins, middot),
  `1fdd038` (claude-code-only finalize + dev tooling), then the
  caching/robustness commit, then `b0db009`.
- PROVIDER=claude-code confirmed working end-to-end; all 3 live_test samples pass fabrication check
- **Per-user API key storage PERMANENTLY REMOVED** — USER_KEYS, /api/key routes, key card UI all gone. No billing path for any user.
- **15 reviewer personas** in pool: original 4 (default on) + 11 new opt-in (Engineering Bar-Raiser, Leveling Calibrator, Career Narrative Strategist, Transferable Skills Interpreter, Attention & Perception Specialist, Domain Credentialing Auditor, Industry Format & Culture Fit Auditor, Competitive Field Analyst, Executive Presence Assessor, Commitment Signal Analyst, First-Impression Clarity Analyst)
- **Inline persona selector** on main form — chip cards, click to toggle, original 4 pre-checked, selected keys sent with each tailor request
- SQLite persistence: tailored results survive restart. No TTL/tiers yet.
- Parsing hardened: zip-bomb guard, text cap, timeout via asyncio.to_thread
- Security: SESSION_SECRET boot guard, Content-Disposition sanitization, chunked upload read

## Current focus (2026-06-23)
**Caching + robustness + resume output quality** — pass completed this session (see CHANGELOG 2026-06-23 "Caching, robustness, and resume-output fixes"). Verified by running cache/retry logic and re-rendering+re-parsing sample resumes.

Done this session:
- **Completion cache** (`app/db.py` `completion_cache` table + `app/agents.py` `_complete_json` / `_cache_key`): identical (model,system,user) calls served from SQLite — re-running the same resume+JD is free/instant. NOTE: true prompt-caching (`cache_control`) is NOT possible on the `claude` CLI / Pro-Max path — API-only. Result cache is the provider-independent win.
- **Retries** (`COMPLETION_ATTEMPTS=2`) around each model call incl. synthesizer (no more single-bad-parse 502).
- **Concurrency cap** (`MAX_PANEL_WORKERS=6`) on the reviewer pool.
- **Event loop**: `/api/tailor` runs panel+synth via `asyncio.to_thread`.
- Default model stays **Sonnet** for reviewers + synth (per Michael's instruction).

## Export polish (2026-06-24) — DONE, verified visually
`app/export.py` professionalism pass (see CHANGELOG 2026-06-24). All fixed + eyeballed via `scripts/render_samples.py`:
- **PDF bullet bug fixed.** `ListFlowable(..., start="bullet")` rendered the LITERAL WORD "bullet" over each item — it does NOT mean "use a bullet glyph". Now `start="•"`, `bulletFontSize=10`. (A prior MEMORY entry wrongly recorded `start="bullet"` as the fix — that was the bug.)
- PDF dates right-aligned via borderless 2-col table (`_role_flowable`), matching DOCX.
- Em dash (`EM = " — "`) between title/company + degree/school (was ` - `).
- DOCX classic/minimal section headings get a bottom-border rule (`_bottom_border`) to match the PDF `HRFlowable`.
- Margins unified to 0.75" PDF + DOCX (`_set_margins`; `_right_tab` moved 6.5"→7.0").
- Minimal contact separator is now a middot `·` (`MIDDOT`), was a baseline `.`.
- **Clickable contact hyperlinks (done).** `_classify_contact` → mailto for email,
  https for URLs/bare domains, plain for phone/location. PDF classic uses Paragraph
  `<a>`; PDF banner/minimal use `_canvas_contact` (canvas links can't be done via
  Paragraph — draw per-bit + `canvas.linkURL` rect). DOCX uses `_add_hyperlink`
  (w:hyperlink OXML + external rel; no native python-docx API). `_shade` promoted
  to module scope. Verified via /URI count (PDF) + w:hyperlink targets (DOCX).

Still open in `app/export.py` (lower priority):
- No render-time length/page-count control.
- Skills still a single comma blob (categorising needs an AI-output schema change).

## Open / next
- Resume output quality improvements (see Current focus above)
- No TTL on SQLite results — deferred to paid tier
- Live API validation must run locally (`python scripts/live_test.py`); sandbox blocks api.anthropic.com

## Gotchas
- **claude-code only** — no API key mode, no demo mode (both permanently removed 2026-06-23). See DECISIONS.md.
- **`httpx` stays in requirements.txt** — it was also used by `anthropic` SDK but is still needed by `authlib`'s starlette OAuth integration. Don't remove it.
- **Cowork sandbox shows corrupted/truncated files (RECURRING — have a recipe ready).** After the host Edit/Write tools touch a file, the sandbox mount often serves a corrupted view: null bytes inserted (file still ~right length, `tr -cd '\000' | wc -c` > 0) or truncated at a byte offset. `import`/`py_compile` in the sandbox then fails with "source code string cannot contain null bytes" or a SyntaxError mid-line. Waiting/retrying does NOT reliably clear it — a given file can stay wedged.
  - **Truth:** host-side Read/Write/Edit are authoritative. A clean `Read` of the file = the file is fine; the failure is purely the mount.
  - **AVOID:** don't verify just-edited Python by importing it through the project mount. Either (a) trust a host `Read` for syntax, or (b) run behavioral tests from a null-stripped COPY, not the mount original.
  - **FAST FIX (≈1 step):** `scripts/sandbox_verify.py` — run `python3 scripts/sandbox_verify.py` (reads each app/*.py from the mount, strips nulls into `/tmp/proj/app/`, compiles, and reports which files are CORRUPTED + the break line). For any flagged file, paste the authoritative tail from a host `Read` to splice (`head -N stripped > clean; cat >> clean <<EOF ...host lines N+1..end... EOF`), then run tests with `PYTHONPATH=/tmp/proj`.
  - This session that whole diagnose-and-splice loop took ~10 tool calls; with the helper it's 1-2.
- **File deletion in sandbox** — `rm` fails with "Operation not permitted" by default. Call `mcp__cowork__allow_cowork_file_delete` first, then `rm`.
