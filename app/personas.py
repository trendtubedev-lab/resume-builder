"""Persona management: merge hardcoded presets with per-user custom personas.

Presets are the source of truth for keys/names/briefs out of the box.
A user can override a preset's name/brief (stored in custom_personas with
is_override implied by the key matching a preset key), or add new ones.

Future paywall enforcement:
  - Free tier:  show first 3 presets, no custom allowed
  - Paid tier:  all presets + up to 2 custom
  Apply those limits in get_personas() / add guards in the API routes.
"""
from __future__ import annotations

from dataclasses import dataclass

from app import db

# ---------------------------------------------------------------------------
# Preset definitions — these ship with the product for every user.
# ---------------------------------------------------------------------------

@dataclass
class Persona:
    key: str
    name: str
    brief: str
    is_preset: bool = True


PRESET_PERSONAS: list[Persona] = [
    Persona(
        "recruiter",
        "Technical Recruiter",
        "You screen hundreds of resumes a week. You care about clarity, relevance "
        "to the role, signal-to-noise, and whether you'd pass this candidate to the "
        "hiring manager in the first 10 seconds.",
    ),
    Persona(
        "ats",
        "ATS / Keyword Specialist",
        "You optimize resumes to pass Applicant Tracking Systems. You compare the "
        "resume against the job description for missing hard keywords, skills, "
        "titles, and phrasing that the ATS and recruiters search for.",
    ),
    Persona(
        "hiring_manager",
        "Hiring Manager",
        "You will manage this person. You care about demonstrated impact, "
        "quantified results, scope/seniority fit, and evidence they can do THIS job. "
        "You are skeptical of fluff and unsupported claims.",
    ),
    Persona(
        "editor",
        "Professional Resume Editor",
        "You care about writing quality: strong action verbs, concise bullets, "
        "consistency, formatting, and removing clichés and weak language.",
    ),
]

_PRESET_KEYS = {p.key for p in PRESET_PERSONAS}


def get_personas(user_email: str) -> list[Persona]:
    """Return the merged persona list for a user.

    Order: presets first (in preset order, with any user overrides applied),
    then the user's custom personas sorted by sort_order.
    """
    overrides: dict[str, dict] = {
        r["key"]: r for r in db.list_custom_personas(user_email)
    }

    merged: list[Persona] = []
    for p in PRESET_PERSONAS:
        if p.key in overrides:
            ov = overrides[p.key]
            merged.append(Persona(p.key, ov["name"], ov["brief"], is_preset=True))
        else:
            merged.append(p)

    for r in db.list_custom_personas(user_email):
        if r["key"] not in _PRESET_KEYS:
            merged.append(Persona(r["key"], r["name"], r["brief"], is_preset=False))

    return merged


def preset_keys() -> set[str]:
    return _PRESET_KEYS
