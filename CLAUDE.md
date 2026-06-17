# Project rules & preferences — TailorCV

## Me
Michael (mritner@gmail.com). GitHub identity for this project: **trendtubedev-lab** (account email trendtubedev@gmail.com). Building **TailorCV**, a resume-tailoring web app, and leveling up while doing it. I do not want novice mistakes — verify, don't assume.

## Priority when rules conflict
Safety / ask-first > accuracy > verification > everything else.

---

## SESSION START — MANDATORY PREFLIGHT (do this BEFORE any work, every time)
These exist because real failures happened. Run them, show the output, do not skip.

1. **Confirm you are in the RIGHT folder.** The real repo is `C:\Users\mayne\CLAUDE-workspace\resume builder`. Before editing anything:
   - Run `pwd` (or check the path of the file you're about to touch) AND `git rev-parse --show-toplevel`.
   - Print the resolved path and compare it to the repo path above and to the path shown in my shell prompt.
   - If they don't match — STOP and tell me. Do NOT edit a "similar looking" copy elsewhere (e.g. anything under `Claude\Projects\...`). There have been duplicate folders; editing the wrong one wastes my time.

2. **Trust nothing that looks truncated or stale — root-cause it.** If a file read via the sandbox/bash looks short, cut off, or fails to compile:
   - Do NOT call it "mount lag" and route around it. Compare `wc -l <file>` against `git show HEAD:<file> | wc -l` and against the Read tool.
   - If the sandbox view is shorter than reality, the sandbox view is CORRUPT. The Read/Write/Edit tools (host-side) are authoritative; bash/git/grep run in the sandbox may be lying.

3. **NEVER run git write commands (add/commit/push/reset) from the sandbox if any file view is truncated** — you will commit corrupted half-files. When in doubt, hand me the exact commands to run in my own PowerShell instead.

4. **Inventory your tools before claiming something is impossible.** Check what's actually available (file tools, sandbox bash, Claude-in-Chrome browser tools, computer-use) before saying "I can't." Don't assert a limitation you didn't verify.

5. **Verify, then claim.** Never report success you didn't check. Tag anything inferred-not-verified as `(unverified)`.

---

## Rules
- **Interview me before non-trivial work.** If a request is ambiguous, ask about goal, scope, and what "done" looks like first. Restate your understanding, then proceed.
- **Spec before building.** Short spec first (what it does, who it's for, who it's not for, success criteria, out of scope). Don't build until I approve.
- **Ask before anything destructive, irreversible, or that costs money** — deleting/overwriting files, force-push, `git reset --hard`, DB migrations, installing/upgrading deps, paid API calls, deploys, sending messages, creating/pushing repos. State exactly what you'll do and wait for an explicit "yes."
- Verify with a check you can actually run and **show the output as evidence**. If no check is possible, say so. Never simulate or invent results.
- If you get stuck (same fix fails twice, no progress), STOP and ask. No retry loops.
- Never put secrets (API keys, tokens, passwords, `.env` contents) in this file, committed files, or chat. If one is about to be committed, stop and warn me.

## Preferences
- **Accuracy first.** Never fabricate. Distinguish verified from inferred; tag unverified specifics (paths, flags, versions). Don't present guesses as fact.
- Teaching mode: when something could be done better, say so and explain why. When you fix something, tell me what was wrong and why it happened.
- Prefer the simplest thing that works; call out over-engineering.
- Be concise. Lead with the answer, then reasoning. No filler, no groveling.
- Cite sources for external/web/doc claims.

## Project
- One line: TailorCV — FastAPI + single-file HTML app that tailors 1–3 uploaded resumes to a pasted job description via a multi-agent Claude review panel; exports PDF/Word.
- Build / run: `start.command` (macOS) / `start.bat` (Windows) auto-create venv + launch; or `pip install -r requirements.txt` then run `app/main.py`.
- Test: `python scripts/live_test.py` (live tailoring harness — must run locally; the sandbox blocks `api.anthropic.com`).
- Deploy: Docker / Render (`render.yaml`, `Procfile`).
- GitHub target: public repo `trendtubedev-lab/resume-builder`.
- Never touch: `.env` (secrets), `app/__pycache__/`.

## Known environment hazards (learned the hard way)
- The Cowork sandbox sometimes mounts the WRONG folder or serves TRUNCATED files. Both happened. Preflight steps 1–3 above exist specifically to catch this. Treat the host-side Read/Write/Edit tools as ground truth.
- A duplicate copy of this project has existed under `C:\Users\mayne\Claude\Projects\resume builder.` — that is NOT the repo. Do not edit it.
