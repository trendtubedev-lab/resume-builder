"""Google OAuth sign-in.

Auth uses Authlib's OIDC integration against Google. Logged-in user info lives
in a signed session cookie (Starlette SessionMiddleware).

Set AUTH_DISABLED=1 to bypass Google entirely for local development — every
request is treated as a single local user.

AI calls use PROVIDER=claude-code (user's own Claude plan) or a server-level
ANTHROPIC_API_KEY in .env for hosted mode. No per-user key storage.
"""
from __future__ import annotations

import os

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter()

_oauth: OAuth | None = None


def auth_disabled() -> bool:
    return os.getenv("AUTH_DISABLED", "").lower() in {"1", "true", "yes", "on"}


def oauth_configured() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))


def get_oauth() -> OAuth:
    global _oauth
    if _oauth is None:
        _oauth = OAuth()
        _oauth.register(
            name="google",
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            client_kwargs={"scope": "openid email profile"},
        )
    return _oauth


def current_user(request: Request) -> dict | None:
    """Return the logged-in user dict, or a synthetic one if auth is disabled."""
    if auth_disabled():
        return {"email": "local@localhost", "name": "Local User", "picture": ""}
    return request.session.get("user")


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Please sign in.")
    return user


@router.get("/auth/login")
async def login(request: Request):
    if auth_disabled():
        return RedirectResponse("/")
    if not oauth_configured():
        raise HTTPException(
            503,
            "Google sign-in is not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET (or AUTH_DISABLED=1 for local use).",
        )
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI") or str(request.url_for("auth_callback"))
    return await get_oauth().google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    try:
        token = await get_oauth().google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(400, f"Sign-in failed: {e}")
    info = token.get("userinfo") or {}
    if not info.get("email"):
        raise HTTPException(400, "Could not read your Google profile.")
    request.session["user"] = {
        "email": info.get("email"),
        "name": info.get("name") or info.get("email"),
        "picture": info.get("picture", ""),
    }
    return RedirectResponse("/")


@router.get("/auth/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse("/")
