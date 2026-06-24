# TailorCV

A local web app that tailors a resume to a specific job. The user uploads 1–3
resumes and pastes a target job description; a **panel of AI reviewers**
(recruiter, ATS/keyword specialist, hiring manager, and editor) critiques the
resume independently, then a synthesizer rewrites it into a single tailored
version the user can download as **PDF or Word**.

Built so it runs locally for a friend today, and deploys online as a service
with no code changes.

---

## Accounts & sign-in

- **Sign-in:** users log in with **Google**. Set up a Google OAuth client (see
  "Google sign-in setup" below). For quick local use without Google, set
  `AUTH_DISABLED=1` in `.env` and the app runs as a single local user.
- **AI calls:** route through the local `claude` CLI on the user's own **Claude
  Pro/Max plan**. No Anthropic API key required.
  See [QUICKSTART_FRIENDS.md](QUICKSTART_FRIENDS.md) for the one-time setup (~10 min).

## Run it locally (for a friend)

You need **Python 3.10+** and **Claude Code** installed and signed in
(see [QUICKSTART_FRIENDS.md](QUICKSTART_FRIENDS.md)).

1. Create your config:
   ```
   cp .env.example .env        # then edit .env (see below)
   ```
   At minimum, set `AUTH_DISABLED=1` and a `SESSION_SECRET`.

2. Start it:
   - **macOS/Linux:** double-click `start.command` (or run `./start.command`)
   - **Windows:** double-click `start.bat`

   The first run creates a virtual environment and installs dependencies
   automatically. When it's ready, open **http://localhost:8000**.

### Manual start (alternative)
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

---

## Google sign-in setup

1. Go to https://console.cloud.google.com/apis/credentials → **Create
   Credentials → OAuth client ID → Web application**.
2. Under **Authorized redirect URIs** add:
   - local: `http://localhost:8000/auth/callback`
   - hosted: `https://YOUR_DOMAIN/auth/callback`
3. Copy the **Client ID** and **Client secret** into `.env`
   (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`).
4. Set a `SESSION_SECRET` (any long random string).
5. (Hosted only) set `HTTPS_ONLY=1`.

If `GOOGLE_CLIENT_ID`/`SECRET` are missing, the sign-in page explains that auth
isn't configured. Use `AUTH_DISABLED=1` to bypass it locally.

## Publish it online (turn it into a service)

The app is a standard ASGI (FastAPI) web app, so any Python host works. Pick one:

- **Render** — push this folder to a Git repo, then "New > Blueprint" and point
  it at `render.yaml`.
- **Docker** (Fly.io, Railway, Cloud Run, any VPS):
  ```bash
  docker build -t tailorcv .
  docker run -p 8000:8000 tailorcv
  ```
- **Heroku-style** hosts read the included `Procfile`.

All hosting config comes from environment variables — nothing in the code
changes between local and production.

### Before charging real users (productionization checklist)
Generated resumes are **persisted to SQLite** (`data/tailorcv.db`, via `app/db.py`),
so they survive a restart. To productionize further:
- For a multi-instance / high-write deployment, swap SQLite for Postgres (the app
  only talks to `app/db.py`, so it's a contained change).
- Add rate limiting and request size caps (basic 5 MB/file, 3-file caps exist).
- Consider a job queue for AI calls if traffic is high.
- Add logging/error tracking (e.g. Sentry).

---

## Configuration (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `REVIEWER_MODEL` | `claude-sonnet-4-6` | Model for the review panel. |
| `SYNTH_MODEL` | `claude-sonnet-4-6` | Model for the final rewrite. |
| `CLAUDE_CODE_TIMEOUT` | `180` | Seconds to wait per claude CLI call before timing out. |
| `PORT` | `8000` | Port to serve on (most hosts set this automatically). |

---

## How it works

```
app/
  main.py      FastAPI routes: /, /api/tailor, /api/download/{id}
  parsing.py   Extract text from PDF / DOCX / TXT uploads
  agents.py    Review panel (parallel personas) + synthesizer  -> structured JSON
  export.py    Render that JSON to .docx (python-docx) and .pdf (reportlab)
  static/
    index.html Single-file frontend (upload, job box, results, PDF/Word toggle)
```

The reviewers run **in parallel**, each with no knowledge of the others, so you
get independent perspectives rather than groupthink. The synthesizer is
instructed to use only information grounded in the original resume — it won't
fabricate employers, dates, or metrics.

## Validate output quality (live test)

Sanity-check the AI against the bundled samples:

```bash
python scripts/live_test.py          # all 3 samples
python scripts/live_test.py mid      # just one
```

It prints each reviewer's score and the tailored result, and runs a
**fabrication check** — every employer, school, and year in the output must
appear in the original resume. Use it after changing prompts or models.

## Usage note
Each tailoring run makes ~5 calls through your local Claude plan (4 reviewers in
parallel + 1 synthesis). These count against your Claude Pro/Max plan's usage
limits. Runs take 1–3 minutes in local Claude plan mode. Raise
`CLAUDE_CODE_TIMEOUT` in `.env` if you hit timeouts.
