# Project rules & preferences

## Me
Michael Ritner — building TailorCV, a tool that rewrites people's resumes and lets them download in multiple styles to help them land jobs.

## Priority when rules conflict
Safety / ask-first > accuracy > verification > everything else.

---

## SESSION START — MANDATORY PREFLIGHT (do this BEFORE any work, every time)
These exist because real failures happened. Run them, show the output, do not skip.

0. **Load state before working.** Read `MEMORY.md`, `DECISIONS.md`, and the last ~5 entries of `CHANGELOG.md` to understand where things stand. Note any `[UNVERIFIED]` items. Then confirm the goal for the session before starting non-trivial work.

1. **Confirm you are in the RIGHT folder.** The real repo is `C:\Users\May Nerd\Claude Workspace\resume-builder\resume-builder`. Before editing anything:
   - Run `pwd` (or check the path of the file you're about to touch) AND `git rev-parse --show-toplevel`.
   - Print the resolved path and compare it to the repo path above and to the path shown in my shell prompt.
   - If they don't match — STOP and tell me. Do NOT edit a "similar looking" copy elsewhere. If duplicate folders exist on your system, editing the wrong one wastes time.

2. **Trust nothing that looks truncated or stale — root-cause it.** If a file read via the sandbox/bash looks short, cut off, or fails to compile:
   - Do NOT assume it's a transient issue and route around it. Compare `wc -l <file>` against `git show HEAD:<file> | wc -l` and against the Read tool.
   - If the sandbox view is shorter than reality, the sandbox view is suspect. The Read/Write/Edit tools (host-side) are authoritative; bash/git/grep run in the sandbox may return stale data.
   - **To run/verify just-edited Python in the sandbox, don't import it from the mount** (it's often null-padded or truncated right after a host edit). Run `python3 scripts/sandbox_verify.py` — it stages null-stripped copies under `/tmp/proj` and flags any file still CORRUPTED with the exact splice line. Then test with `PYTHONPATH=/tmp/proj`. (Full recipe in MEMORY.md gotchas.)

3. **NEVER run git write commands (add/commit/push/reset) from the sandbox if any file view is truncated** — you will commit corrupted half-files. When in doubt, hand me the exact commands to run in my own shell instead.

4. **Inventory your tools before claiming something is impossible.** Check what's actually available (file tools, sandbox bash, Claude-in-Chrome browser tools, computer-use) before saying "I can't." Don't assert a limitation you didn't verify.

5. **Verify, then claim.** Never report success you didn't check. Tag anything inferred-not-verified as `(unverified)`.

---

## AFTER EVERY CHANGE — MANDATORY (log it + remember it)
Do this as you go, not in a batch at the end.

1. **CHANGELOG.** After any code/config/rule change, prepend a dated entry to `CHANGELOG.md` (newest on top): what changed, why, and how it was verified. If `CHANGELOG.md` doesn't exist, create it.
2. **Memory.** At the end of meaningful work — and BEFORE any compaction — update the memory so the next cold-start session inherits it: add/update the relevant memory file and its `MEMORY.md` index line. If the memory store is read-only or unreachable that session, SAY SO and record the same notes in `CHANGELOG.md` as the fallback (never silently skip).
3. **Reconcile before finishing.** If you changed how things work, make sure `CLAUDE.md`, `CHANGELOG.md`, and memory don't contradict each other.

---

## Rules
- **Interview me before non-trivial work.** If a request is ambiguous, ask about goal, scope, and what "done" looks like first. Batch clarifying questions into one round. Restate your understanding, then proceed.
- **Spec before building.** Short spec first (what it does, who it's for, who it's not for, success criteria, out of scope). Don't build until I approve.
- **Ask before anything destructive, irreversible, or that costs money** — deleting/overwriting files, force-push, `git reset --hard`, DB migrations, installing/upgrading deps, paid API calls, deploys, sending messages, creating/pushing repos. State exactly what you'll do and wait for an explicit "yes."
- **Launching agents / subagents.** Use subagents liberally for: (a) heavy or parallel work — large searches, multi-file research, anything with big fan-out — so the main thread's context stays clean; (b) executing approved build steps in parallel where steps are independent; (c) a separate verification/review pass before claiming non-trivial work done. Proactively offer to launch agents when a task is large or multi-part, then let me decide. When spawning, pass the needed context explicitly (it inherits nothing), keep it scoped to one task, and relay only what matters back.
- Verify with a check you can actually run and **show the output as evidence**. If no check is possible, say so. Never simulate or invent results.
- If you get stuck (same fix fails twice, no progress), STOP and ask. No retry loops.
- **Secrets:** live in `.env` only — never hardcode defaults, and never print, commit, or copy them (not in this file, committed files, or chat). If one is about to be committed, stop and warn me.

## Preferences
- **Accuracy first.** Never fabricate. Distinguish verified from inferred; tag unverified specifics (paths, flags, versions). Don't present guesses as fact.
- Label example/demo/fake output as `[EXAMPLE — not real data]`; never present demo-mode output as real.
- Teaching mode: when something could be done better, say so and explain why. When you fix something, tell me what was wrong and why it happened.
- Prefer the simplest thing that works; call out over-engineering.
- Be concise. Lead with the answer, then reasoning. No filler, no groveling.
- Cite sources for external/web/doc claims.

## Project
- One line: TailorCV — rewrites users' resumes using AI (Anthropic) and lets them download in multiple style formats (DOCX, PDF, etc.) to improve their job search.
- Build / run: `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt` then `uvicorn app.main:app --host 0.0.0.0 --port 8000`. On Windows, double-click `start.bat`.
- Test / lint / typecheck: No test suite currently. Run the app manually to verify.
- Never touch: `.env`, `.venv/`, `debug.log`, `run.log`

## Environment-specific notes
- FastAPI backend (`app/main.py`), Python 3.11, dependencies in `requirements.txt`.
- AI calls route through the local `claude` CLI on the user's own Claude Pro/Max plan
  (`app/agents.py` → `_claude_code_complete`). The code does **not** read
  `ANTHROPIC_API_KEY`; no Anthropic API key is used. Designed to run locally / within
  Claude desktop.
- `.venv/` is local-only; not in version control. Re-run pip install if deps are missing.
- `start.bat` / `start.command` are convenience launchers; `Procfile` is for Render.com deploy.
