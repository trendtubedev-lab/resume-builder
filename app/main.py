"""TailorCV — local web app that tailors resumes to a job using a Claude review panel.

Run locally:  python -m app.main   (or: uvicorn app.main:app --reload)
Deploy:       it's a standard ASGI app — see README for Render/Fly/Docker.

Auth: Google sign-in (Authlib). Each user supplies their own Anthropic API key.
Set AUTH_DISABLED=1 to bypass Google for local development.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Body
from fastapi.responses import HTMLResponse, Response, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from . import agents, auth, demo, export, parsing

load_dotenv()

app = FastAPI(title="TailorCV")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-insecure-change-me"),
    same_site="lax",
    https_only=os.getenv("HTTPS_ONLY", "").lower() in {"1", "true", "yes", "on"},
)
app.include_router(auth.router)

# In-memory store of generated resumes, keyed by job id.
# For a hosted multi-user service, swap this for Redis or a DB (see README).
_STORE: dict[str, dict] = {}

FRONTEND = Path(__file__).parent / "static" / "index.html"
SAMPLES_DIR = Path(__file__).parent / "samples"
MAX_FILES = 3
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file

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
    """Who am I, do I have a key, and would a run use demo mode?"""
    user = auth.current_user(request)
    if not user:
        return {"authenticated": False, "oauth_configured": auth.oauth_configured()}
    has_key = bool(auth.user_api_key(user["email"]))
    return {
        "authenticated": True,
        "email": user["email"],
        "name": user["name"],
        "picture": user.get("picture", ""),
        "has_key": has_key,
        "demo": not has_key,
    }


@app.post("/api/key")
def set_key(request: Request, api_key: str = Body(..., embed=True)) -> dict:
    user = auth.require_user(request)
    key = (api_key or "").strip()
    if not key:
        auth.USER_KEYS.pop(user["email"], None)
        return {"has_key": bool(auth.user_api_key(user["email"]))}
    if not key.startswith("sk-ant-"):
        raise HTTPException(400, "That doesn't look like an Anthropic key (should start with 'sk-ant-').")
    auth.USER_KEYS[user["email"]] = key
    return {"has_key": True}


@app.delete("/api/key")
def clear_key(request: Request) -> dict:
    user = auth.require_user(request)
    auth.USER_KEYS.pop(user["email"], None)
    return {"has_key": bool(auth.user_api_key(user["email"]))}


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
    for f in files:
        data = await f.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(400, f"'{f.filename}' is too large (max 5 MB).")
        try:
            text = parsing.extract_text(f.filename, data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        chunks.append(f"--- {f.filename} ---\n{text}")
    resume_text = "\n\n".join(chunks)

    key = auth.user_api_key(user["email"])
    is_demo = not key
    try:
        if is_demo:
            panel = demo.demo_panel(resume_text, job_description)
            resume = demo.demo_synthesize(resume_text, job_description, tone)
        else:
            panel = agents.run_panel(resume_text, job_description, api_key=key)
            resume = agents.synthesize(resume_text, job_description, panel, tone, api_key=key)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"Generation failed: {e}.")

    job_id = uuid.uuid4().hex[:12]
    _STORE[job_id] = {"resume": resume, "owner": user["email"]}

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
    item = _STORE.get(job_id)
    if not item or item.get("owner") != user["email"]:
        raise HTTPException(404, "Result expired or not found. Generate again.")
    resume = item["resume"]
    name = (resume.get("name") or "resume").replace(" ", "_")
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


def run():
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run()
