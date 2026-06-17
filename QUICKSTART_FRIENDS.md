# TailorCV — Quick Start (run it on your own Claude plan)

This lets you run TailorCV **locally** using **your own Claude Pro or Max
subscription** — no Anthropic API key, no per-use cost beyond your plan.

You'll do this once. Takes about 10 minutes. Steps 1–2 are the only "new" part;
if you already use Claude Code, skip to step 3.

---

## What you need
- A **Claude Pro or Max** subscription (the normal claude.ai paid plan).
- **Node.js 18+** — https://nodejs.org (download the LTS installer, click through).
- **Python 3.10+** — https://www.python.org/downloads (on Windows, tick
  *"Add Python to PATH"* during install).

---

## Step 1 — Install Claude Code
Open a terminal (Windows: **PowerShell**; Mac: **Terminal**) and run:

```
npm install -g @anthropic-ai/claude-code
```

Check it worked:

```
claude --version
```

You should see a version number.

## Step 2 — Sign in with your Claude plan
Run:

```
claude
```

It opens a sign-in flow in your browser. Choose **"Subscription"** (your
Pro/Max account) — **not** an API key. Once it says you're logged in, you can
close that prompt (type `/exit` or press Ctrl+C). You only do this once.

> This is the important bit: TailorCV runs on **whatever account Claude Code is
> signed into**. Signing in with your subscription means it uses your plan.

## Step 3 — Get TailorCV and configure it
Download/unzip the TailorCV folder (or `git clone` it), then in that folder:

```
cp .env.example .env
```

(Windows PowerShell: `Copy-Item .env.example .env`)

Open `.env` in any text editor and set these three lines:

```
PROVIDER=claude-code
AUTH_DISABLED=1
SESSION_SECRET=any-long-random-text-you-make-up-here
```

- `PROVIDER=claude-code` → use your local Claude plan.
- `AUTH_DISABLED=1` → skip Google login; run as a single local user.
- `SESSION_SECRET` → just mash some random characters; it only needs to exist.

## Step 4 — Start it
- **Windows:** double-click `start.bat`
- **Mac:** double-click `start.command` (or run `./start.command` in Terminal)

The first run builds a small environment and may take a minute. When it's ready,
open **http://localhost:8000** in your browser.

You should see a green banner: **"Running on your Claude plan."** Upload a resume,
paste a job description, and hit **Tailor my resume**.

---

## How do I know it worked?
- Green "Running on your Claude plan" banner at the top (not a yellow demo banner).
- After you click Tailor, you wait ~30–60s and get a real review panel with
  scores, plus a tailored resume you can download as PDF or Word.

## Common errors
| You see | Fix |
|---|---|
| App won't start, mentions `claude` not found | Claude Code isn't installed or not on PATH. Redo Step 1, then **open a new terminal** and try again. |
| "Are you signed in? Run `claude` once to log in." | Redo Step 2 — run `claude`, sign in with your subscription. |
| A **yellow demo banner** instead of green | `.env` doesn't have `PROVIDER=claude-code`. Check Step 3, then restart. |
| "timed out" | A single run took too long. Re-run; if it keeps happening, raise `CLAUDE_CODE_TIMEOUT` in `.env`. |

## A couple of honest notes
- Your Claude subscription has **usage limits**. Heavy use can hit them; normal
  trial use is fine. Each tailoring run makes ~5 model calls.
- This subscription mode is for **local, personal use** while we trial the app.
  The hosted version (later) will work differently.
