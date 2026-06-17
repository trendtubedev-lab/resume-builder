---
name: release-check
description: TailorCV session-close ritual — verify exports, run the live panel, update CHANGELOG + MEMORY, reconcile docs, and confirm nothing sensitive is staged before commit. Use at the end of any work session, before committing, or when asked to "wrap up", "finalize", "ship", or "release".
---

# release-check

Prescriptive close-out for a TailorCV work session. Run these in order and show
the output of each gate — do not assert success you did not observe. Stop and
report if any gate fails; do not commit on a red gate.

## 1. Verify exports (offline, always runs)
```
.venv/Scripts/python.exe scripts/export_check.py
```
Must print `ALL EXPORTS OK` (exit 0). This needs no API key and catches a broken
PDF/DOCX renderer — the part users actually receive.

## 2. Run the live panel (only if an API key is present and AI code changed)
```
.venv/Scripts/python.exe scripts/live_test.py
```
- The sandbox blocks `api.anthropic.com` — this must be run in Michael's own shell.
- Must end `ALL CHECKS PASSED` with the fabrication check clean.
- Skip only if this session touched no agent/prompt/export logic; say so explicitly.

## 3. Safety sweep — nothing sensitive staged
```
git status --short
git diff --cached --name-only
git ls-files | grep -iE "\.env$|\.db$|\.pem|\.key|credentials|secrets" || echo "clean"
```
- `.env`, `data/`, `*.pem`, `*.key` must NOT appear as tracked/staged.
- If a secret is about to be committed, STOP and warn Michael — do not commit.

## 4. Update CHANGELOG.md
Prepend a dated entry (newest on top): what changed, why, and how it was verified
(quote the gate output, e.g. "export_check: ALL EXPORTS OK"). Create the file if
missing.

## 5. Update memory
Add/update the relevant file in the memory store and its `MEMORY.md` index line so
the next cold-start session inherits this work. If the store is unreachable, say so
and record the same notes in `CHANGELOG.md` as fallback — never silently skip.

## 6. Reconcile docs
If behavior changed, make sure `CLAUDE.md`, `README.md`, `DECISIONS.md`,
`CHANGELOG.md`, and memory do not contradict each other. Prose deliverables
(README, guides, narration) get a humanizer pass; code/config/data do not.

## 7. Commit (only after gates 1–6 pass)
Commit logical units with a clear message. Never `--no-verify`, never force-push,
never commit `.env`/logs/`data/`. Ask before pushing if Michael has not already
authorized it this session.
```
git add -A && git status --short
git commit -m "<clear message>"
```

## Done criteria
All gates green, CHANGELOG + memory updated, docs reconciled, working tree clean
or intentionally staged. Report what ran, what passed, and anything skipped (with
the reason).
