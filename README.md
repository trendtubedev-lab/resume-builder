# TailorCV

A local web app that tailors a resume to a specific job. The user uploads 1–3
resumes and pastes a target job description; a **panel of AI reviewers**
(recruiter, ATS/keyword specialist, hiring manager, and editor) critiques the
resume independently, then a synthesizer rewrites it into a single tailored
version the user can download as **PDF or Word**.

Built so it runs locally for a friend today, and deploys online as a service
with no code changes.

---

## Accounts & API keys

- **Sign-in:** users log in with **Google**. Set up a Google OAuth client (see
  "Google sign-in setup" below). For quick local use without Google, set
  `AUTH_DISABLED=1` in `.env` and the app runs as a single local user.
- **API keys:** each signed-in user pastes their **own Anthropic API key** in
  the app (stored in memory for their session only, never written to disk).
  Users without a key get the free **demo mode** preview. You can optionally set
  a server-wide `ANTHROPIC_API_KEY` as a fallback.

## Run it locally (for a friend)

You need **Python 3.10+**.

1. Create your config:
   ```
   cp .env.example .env        # then edit .env (see below)
   ```
   For the simplest local run, set `AUTH_DISABLED=1` and a `SESSION_SECRET`.
   Your friend can then paste their Anthropic key right in the app.
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
  it at `render.yaml`. Set `ANTHROPIC_API_KEY` as a secret in the dashboard.
- **Docker** (Fly.io, Railway, Cloud Run, any VPS):
  ```bash
  docker build -t tailorcv .
  docker run -e ANTHROPIC_API_KEY=sk-ant-... -p 8000:8000 tailorcv
  ```
- **Heroku-style** hosts read the included `Procfile`.

All hosting config comes from environment variables — nothing in the code
changes between local and production.

### Before charging real users (productionization checklist)
Generated resumes are **persisted to SQLite** (`data/tailorcv.db`, via `app/db.py`),
so they survive a restart. Per-user Anthropic keys are still kept **in memory only**
(by design — secrets never hit disk). To productionize further:
- For a multi-instance / high-write deployment, swap SQLite for Postgres (the app
  only talks to `app/db.py`, so it's a contained change).
- Add auth + per-user API usage metering / billing (e.g. Stripe).
- Add rate limiting and request size caps (basic 5 MB/file, 3-file caps exist).
- Consider a job queue for the API calls if traffic is high.
- Add logging/error tracking (e.g. Sentry).

---

## Demo mode (no API key needed)

If no `ANTHROPIC_API_KEY` is set (or you set `DEMO_MODE=1`), the app runs in
**demo mode**: it shows a yellow banner and produces a lightweight *offline*
preview instead of calling Claude. This lets anyone click through the whole
flow — upload, review panel, PDF/Word download — for free.

Use the **"⚡ Try a sample…"** picker to load one of three bundled fake resumes
(entry-level, mid-career, senior) plus a matching job description. Great for
demos and screenshots. Demo output is clearly labelled "· demo"; add a real key
to get the full multi-agent rewrite.

## Behind a corporate proxy

Standard `HTTPS_PROXY` / `HTTP_PROXY` env vars are honored automatically — most
setups need nothing extra. If your proxy inspects TLS (a self-signed cert in the
chain), point the app at your corporate root CA:

```
ANTHROPIC_CA_BUNDLE=/path/to/corporate-root-ca.pem
```

You can also force a proxy with `ANTHROPIC_PROXY=...`. As a last resort only,
`ANTHROPIC_SKIP_TLS_VERIFY=1` disables certificate verification (insecure — the
app logs a warning when it's on). When none of these are set, the app uses the
SDK's default client, so normal deployments are unaffected.

## Configuration (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required for API mode.** Your Claude API key. |
| `PROVIDER` | `api` | `api` uses the Anthropic API (per-call billing). `claude-code` routes through your local Claude Code CLI on your own Pro/Max plan — no API key, no per-run charge. |
| `REVIEWER_MODEL` | `claude-sonnet-4-6` | Model for the review panel. |
| `SYNTH_MODEL` | `claude-sonnet-4-6` | Model for the final rewrite. |
| `PORT` | `8000` | Port to serve on (most hosts set this automatically). |
| `ANTHROPIC_PROXY` | — | Explicit proxy URL (else standard `HTTPS_PROXY` is used). |
| `ANTHROPIC_CA_BUNDLE` | — | Path to a corporate root CA for TLS-inspecting proxies. |
| `ANTHROPIC_SKIP_TLS_VERIFY` | `0` | `1` disables TLS verification (insecure, last resort). |

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

After adding your key, sanity-check the AI against the bundled samples:

```bash
python scripts/live_test.py          # all 3 samples
python scripts/live_test.py mid      # just one
```

It prints each reviewer's score and the tailored result, and runs a
**fabrication check** — every employer, school, and year in the output must
appear in the original resume. Use it after changing prompts or models.

## Cost note
Each tailoring run makes 5 model calls: 4 reviewers in parallel plus 1
synthesis. Two ways to pay for them:

- **API mode** (`PROVIDER=api`, the default): billed per call against your
  Anthropic key. The cost depends on `REVIEWER_MODEL` / `SYNTH_MODEL` and your
  resume/JD length — check current rates at
  https://www.anthropic.com/pricing and watch usage at
  https://console.anthropic.com. Default models are Sonnet; switch to Haiku in
  `.env` for cheaper runs, or to a larger model for quality-critical output.
- **Local mode** (`PROVIDER=claude-code`): routes the same 5 calls through your
  local Claude Code CLI on your existing Pro/Max plan. No API key and no
  per-run charge — best when you (or a friend with a plan) run it on your own
  machine. Demo mode (no key, no plan) stays free but produces only the offline
  preview, not the full rewrite.
