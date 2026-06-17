"""TailorCV — local web app that tailors resumes to a job using a Claude review panel.

Run locally:  python -m app.main   (or: uvicorn app.main:app --reload)
Deploy:       it's a standard ASGI app — see README for Render/Fly/Docker.

Auth: Google sign-in (Authlib). Set AUTH_DISABLED=1 to bypass for local use.
AI: PROVIDER=claude-code routes through the user's local Claude plan (no API key).
    For hosted mode, set ANTHROPIC_API_KEY in .env (server-level only).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Load .env BEFORE importing our packages: agents/auth read env vars (PROVIDER,
# REVIEWER_MODEL, ANTHROPIC_API_KEY, ...) at import time, so .env must be in
# os.environ first or those values silently fall back to defaults.
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Body
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import agents, auth, db, demo, export, parsing, personas

log = logging.getLogger("tailorcv")

# Session cookies are signed with SESSION_SECRET. If it's missing or left at a
# placeholder, anyone could forge a cookie for any user (full auth bypass, and
# with a server-wide ANTHROPIC_API_KEY, free use of the operator's key). So we
# refuse to boot insecurely when auth is enabled.
_PLACEHOLDER_SECRETS = {
    "",
    "dev-insecure-change-me",            # old hardcoded default
    "change-me-to-a-long-random-string",  # the value shipped in .env.example
}


def resolve_session_secret() -> str:
    """Return a safe session signing key, or fail fast in production.

    - A real, non-placeholder SESSION_SECRET is used as-is.
    - In local AUTH_DISABLED mode an ephemeral random key is generated (sessions
      simply reset on restart, which is fine for single-user local use).
    - Otherwise (auth enabled + no real secret) we raise, refusing to start with
      a forgeable cookie.
    """
    secret = (os.getenv("SESSION_SECRET") or "").strip()
    if secret and secret not in _PLACEHOLDER_SECRETS:
        return secret
    if auth.auth_disabled():
        log.warning(
            "SESSION_SECRET is unset or a placeholder; using an ephemeral random "
            "key (OK for local AUTH_DISABLED mode — sessions reset on restart)."
        )
        return secrets.token_hex(32)
    raise RuntimeError(
        "SESSION_SECRET is unset or still a placeholder. Set it to a long random "
        'value (python -c "import secrets; print(secrets.token_hex(32))") before '
        "running with authentication enabled, or set AUTH_DISABLED=1 for local "
        "single-user use."
    )


app = FastAPI(title="TailorCV")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.add_middleware(
    SessionMiddleware,
    secret_key=resolve_session_secret(),
    same_site="lax",
    https_only=os.getenv("HTTPS_ONLY", "").lower() in {"1", "true", "yes", "on"},
)
app.include_router(auth.router)

# Validate the selected completion provider at boot (e.g. claude-code mode
# requires the `claude` CLI on PATH). Fails fast with a friendly message.
agents.preflight()

# Ensure DB tables exist.
db.init_db()

FRONTEND = Path(__file__).parent / "static" / "index.html"
SAMPLES_DIR = Path(__file__).parent / "samples"
MAX_FILES = 3
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
MAX_TOTAL_BYTES = 12 * 1024 * 1024  # 12 MB across all files in one request
CHUNK_SIZE = 64 * 1024
# Hard wall-clock cap on parsing one file. Parsing is CPU-bound and a crafted
# PDF/DOCX could spin forever; we run it off the event loop and time it out.
try:
    PARSE_TIMEOUT = float(os.getenv("PARSE_TIMEOUT_SECONDS", "15"))
    if PARSE_TIMEOUT <= 0:
        PARSE_TIMEOUT = 15.0
except ValueError:
    PARSE_TIMEOUT = 15.0


def _safe_filename(name: str | None) -> str:
    """A filesystem/header-safe download stem.

    The resume name comes from user uploads / model output and flows into a
    Content-Disposition header, so quotes and CRLF must never survive (response
    header injection). Keep only a conservative charset; fall back to 'resume'.
    """
    base = (name or "").strip().replace(" ", "_")
    base = re.sub(r"[^A-Za-z0-9._-]", "", base).strip("._-")
    return (base or "resume")[:80]


async def _read_capped(upload: UploadFile, limit: int) -> bytes:
    """Read an upload in chunks, aborting as soon as it exceeds `limit`.

    The previous code read the whole file into memory and only then checked the
    size, so the cap didn't actually bound memory. This stops at the limit.
    """
    buf = bytearray()
    while True:
        chunk = await upload.read(CHUNK_SIZE)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > limit:
            raise HTTPException(
                400, f"'{upload.filename}' is too large (max {limit // (1024 * 1024)} MB)."
            )
    return bytes(buf)

SAMPLES = [
    {"id": "entry", "label": "Entry-level — Jordan Lee", "file": "entry_jordan_lee.txt"},
    {"id": "mid", "label": "Mid-career — Priya Nair", "file": "mid_priya_nair.txt"},
    {"id": "senior", "label": "Senior — Marcus Bell", "file": "senior_marcus_bell.txt"},
]


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return FRONTEND.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "auth_disabled": auth.auth_disabled(), "oauth_configured": auth.oauth_configured()}


@app.get("/api/me")
def me(request: Request) -> dict:
    """Who am I, and would a run use demo mode?"""
    cc = agents.using_claude_code()
    user = auth.current_user(request)
    if not user:
        return {"authenticated": False, "oauth_configured": auth.oauth_configured(),
                "provider": "claude-code" if cc else "api"}
    # demo = no claude-code AND no server-level key in .env
    server_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {
        "authenticated": True,
        "email": user["email"],
        "name": user["name"],
        "picture": user.get("picture", ""),
        "provider": "claude-code" if cc else "api",
        "demo": (not cc) and (not server_key),
    }


@app.get("/api/samples")
def list_samples() -> dict:
    return {"samples": [{"id": s["id"], "label": s["label"]} for s in SAMPLES]}


@app.get("/api/samples/{sample_id}")
def get_sample(sample_id: str) -> dict:
    s = next((x for x in SAMPLES if x["id"] == sample_id), None)
    if not s:
        raise HTTPException(404, "Unknown sample.")
    return {
        "id": s["id"],
        "label": s["label"],
        "filename": s["file"],
        "resume_text": (SAMPLES_DIR / s["file"]).read_text(encoding="utf-8"),
        "job_description": (SAMPLES_DIR / "sample_job.txt").read_text(encoding="utf-8"),
    }


@app.post("/api/tailor")
async def tailor(
    request: Request,
    job_description: str = Form(...),
    tone: str = Form("professional"),
    selected_personas: list[str] = Form(default=[]),
    files: list[UploadFile] = File(...),
):
    user = auth.require_user(request)
    if not job_description.strip():
        raise HTTPException(400, "Please paste a target job description.")
    if not files:
        raise HTTPException(400, "Please upload at least one resume.")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"Upload at most {MAX_FILES} resumes.")

    chunks = []
    total = 0
    for f in files:
        data = await _read_capped(f, MAX_BYTES)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(
                400, f"Uploads are too large in total (max {MAX_TOTAL_BYTES // (1024 * 1024)} MB)."
            )
        try:
            # Off the event loop + timed out: a hostile file can't hang or
            # block the server. to_thread can't be cancelled, but wait_for
            # frees the request and the orphaned thread dies with the parse.
            text = await asyncio.wait_for(
                asyncio.to_thread(parsing.extract_text, f.filename, data),
                timeout=PARSE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("Parsing %r exceeded %ss timeout", f.filename, PARSE_TIMEOUT)
            raise HTTPException(
                400,
                f"'{f.filename}' took too long to read and may be malformed. "
                "Try re-exporting it or uploading a TXT version.",
            )
        except ValueError as e:
            raise HTTPException(400, str(e))
        chunks.append(f"--- {f.filename} ---\n{text}")
    resume_text = "\n\n".join(chunks)

    cc = agents.using_claude_code()
    # Server-level key only — no per-user keys. None is fine for claude-code mode.
    server_key = os.getenv("ANTHROPIC_API_KEY") or None
    is_demo = (not cc) and (not server_key)
    try:
        if is_demo:
            panel = demo.demo_panel(resume_text, job_description)
            resume = demo.demo_synthesize(resume_text, job_description, tone)
        else:
            panel = agents.run_panel(resume_text, job_description, api_key=server_key,
                                   user_email=user["email"],
                                   selected_keys=selected_personas or None)
            resume = agents.synthesize(resume_text, job_description, panel, tone, api_key=server_key)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"Generation failed: {e}.")

    job_id = uuid.uuid4().hex[:12]
    db.save_result(job_id, user["email"], resume)

    return JSONResponse(
        {
            "job_id": job_id,
            "demo": is_demo,
            "overall_score": agents.overall_score(panel),
            "panel": panel,
            "resume": resume,
            "change_summary": resume.get("change_summary", []),
        }
    )


@app.get("/api/download/{job_id}")
def download(request: Request, job_id: str, format: str = "pdf"):
    user = auth.require_user(request)
    item = db.get_result(job_id)
    if not item or item.get("owner") != user["email"]:
        raise HTTPException(404, "Result not found. Generate again.")
    resume = item["resume"]
    name = _safe_filename(resume.get("name"))
    if format == "docx":
        return Response(
            content=export.build_docx(resume),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{name}_tailored.docx"'},
        )
    if format == "pdf":
        return Response(
            content=export.build_pdf(resume),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}_tailored.pdf"'},
        )
    raise HTTPException(400, "format must be 'pdf' or 'docx'.")


@app.get("/api/personas")
def list_personas(request: Request) -> dict:
    user = auth.require_user(request)
    ps = personas.get_personas(user["email"])
    return {"personas": [
        {"key": p.key, "name": p.name, "brief": p.brief,
         "is_preset": p.is_preset, "default_enabled": p.default_enabled}
        for p in ps
    ]}


@app.post("/api/personas")
def create_persona(request: Request, body: dict = Body(...)) -> dict:
    user = auth.require_user(request)
    name = (body.get("name") or "").strip()
    brief = (body.get("brief") or "").strip()
    if not name or not brief:
        raise HTTPException(400, "name and brief are required.")
    if len(name) > 80:
        raise HTTPException(400, "name must be 80 characters or fewer.")
    if len(brief) > 2000:
        raise HTTPException(400, "brief must be 2000 characters or fewer.")
    # Derive a key from the name; ensure it doesn't collide with a preset.
    import re as _re
    key = _re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40]
    if not key:
        raise HTTPException(400, "Could not derive a valid key from the name.")
    existing = {p.key for p in personas.get_personas(user["email"])}
    if key in existing:
        key = key + "_custom"
    db.upsert_persona(user["email"], key, name, brief)
    return {"key": key, "name": name, "brief": brief, "is_preset": False}


@app.put("/api/personas/{key}")
def update_persona(request: Request, key: str, body: dict = Body(...)) -> dict:
    user = auth.require_user(request)
    name = (body.get("name") or "").strip()
    brief = (body.get("brief") or "").strip()
    if not name or not brief:
        raise HTTPException(400, "name and brief are required.")
    if len(name) > 80:
        raise HTTPException(400, "name must be 80 characters or fewer.")
    if len(brief) > 2000:
        raise HTTPException(400, "brief must be 2000 characters or fewer.")
    # Allowed for both presets (override) and custom personas.
    all_keys = {p.key for p in personas.get_personas(user["email"])}
    if key not in all_keys:
        raise HTTPException(404, "Persona not found.")
    db.upsert_persona(user["email"], key, name, brief)
    return {"key": key, "name": name, "brief": brief,
            "is_preset": key in personas.preset_keys()}


@app.delete("/api/personas/{key}")
def delete_persona(request: Request, key: str) -> dict:
    user = auth.require_user(request)
    if key in personas.preset_keys():
        raise HTTPException(400, "Preset reviewers cannot be deleted.")
    removed = db.delete_persona(user["email"], key)
    if not removed:
        raise HTTPException(404, "Persona not found.")
    return {"ok": True}


def run():
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run()
