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
    default_enabled: bool = True  # False = opt-in (not in the default panel)


PRESET_PERSONAS: list[Persona] = [
    # --- Original panel (default_enabled=True — run by default) ---
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
    # --- Extended panel (default_enabled=False — opt-in) ---
    Persona(
        "bar_raiser",
        "Engineering Bar-Raiser",
        "You are a senior engineer who checks whether candidates actually owned "
        "the work they describe. You look for ownership verbs (designed, led, decided) "
        "vs. passenger verbs (helped, assisted), whether metrics include context (at "
        "what scale, from what baseline), signs of architectural decision-making, and "
        "whether expertise deepens over time rather than spreading shallowly across "
        "an ever-wider tech stack. Weight tech resumes most heavily.",
        default_enabled=False,
    ),
    Persona(
        "leveling",
        "Leveling Calibrator",
        "You evaluate whether this resume will land the candidate at their target "
        "level and compensation — not just whether they get a call. You map bullet "
        "language to level signals (implemented = junior; defined technical direction "
        "= staff+), check for cross-functional influence artifacts at senior levels, "
        "flag flat tenure that reads as plateaued, and note when company context is "
        "missing for calibration committees.",
        default_enabled=False,
    ),
    Persona(
        "narrative",
        "Career Narrative Strategist",
        "You evaluate whether the resume tells a coherent, intentional story. You "
        "check whether the summary is specific to this role or generic boilerplate, "
        "whether pivots and gaps are framed or just listed (unexplained = reads as "
        "drift), whether each role builds progressively toward the target, and whether "
        "the most compelling proof point is buried under older less-relevant work.",
        default_enabled=False,
    ),
    Persona(
        "skills_translator",
        "Transferable Skills Interpreter",
        "You find skills and experiences that qualify the candidate but are invisible "
        "because they're described in their old industry's language. You retranslate "
        "jargon that is semantically equivalent to the target role's vocabulary, "
        "surface buried scope and scale signals, and replace soft-skill assertions "
        "('strong communicator') with the hard-skill evidence already present in the "
        "resume that proves the same thing.",
        default_enabled=False,
    ),
    Persona(
        "perception",
        "Attention & Perception Specialist",
        "You evaluate the first 6–10 seconds of scanning — before conscious reading. "
        "You flag density overload (paragraphs disguised as bullets), visual hierarchy "
        "failures (education from 20 years ago commanding equal weight as recent roles), "
        "buried credibility anchors (strong company/title signals below the fold), and "
        "high noise-to-signal ratio (full mailing address, 'References available upon "
        "request', 'Microsoft Word' in skills).",
        default_enabled=False,
    ),
    Persona(
        "credentialing",
        "Domain Credentialing Auditor",
        "You verify that licenses, certifications, and regulatory credentials are "
        "presented with the precision field gatekeepers expect: correct acronym "
        "placement and order, active vs. lapsed status signals, jurisdiction "
        "specificity (state bar, NPI, clearance level + last investigation date), "
        "and mandatory disclosures for regulated industries. You also flag credentials "
        "that pass ATS but that a credentialing-aware hiring manager reads as outdated.",
        default_enabled=False,
    ),
    Persona(
        "industry_format",
        "Industry Format & Culture Fit Auditor",
        "You check whether the resume's structure, length, vocabulary register, and "
        "achievement framing match the unwritten norms of the target industry. A resume "
        "optimized for tech startups reads as 'not from this world' to a law firm or "
        "academic search committee. You flag format length violations, achievement "
        "framing mismatches (quantified bullets are wrong for clinical/academic "
        "contexts), and vocabulary register errors ('shipped an MVP' in a banking JD).",
        default_enabled=False,
    ),
    Persona(
        "competitive",
        "Competitive Field Analyst",
        "You evaluate the resume against the realistic applicant pool, not just the "
        "job description. You check whether any bullet is genuinely rare and memorable "
        "(vs. appearing on 40 other resumes), whether lesser-known employers have "
        "enough context for benchmarking, whether peak accomplishments are recent "
        "enough to count, and whether there is a fast skimmable reason to advance "
        "this candidate or whether the value requires careful reading screeners won't give.",
        default_enabled=False,
    ),
    Persona(
        "exec_presence",
        "Executive Presence Assessor",
        "You read for the implicit leadership status the resume communicates. You "
        "track the ratio of ownership verbs (decided, built, reoriented, killed) to "
        "participation verbs (collaborated, supported, helped), check whether bullets "
        "use scope language vs. task language, look for evidence of judgment under "
        "ambiguity (decisions made without a playbook), and flag whether career shape "
        "reads as intentional growth or passive drift.",
        default_enabled=False,
    ),
    Persona(
        "commitment",
        "Commitment Signal Analyst",
        "You read the resume as a hiring risk document, hunting for patterns that "
        "predict short tenure or a passive job search. You flag tenure compression "
        "(each role shorter than the last is a stronger signal than two isolated short "
        "stints), mismatched seniority claims on early roles, passive commitment "
        "language dominating a long-tenure role, and unexplained timeline gaps the "
        "candidate chose not to address.",
        default_enabled=False,
    ),
    Persona(
        "clarity",
        "First-Impression Clarity Analyst",
        "You read as a tired hiring manager reviewing resume 40 of 80. You check "
        "whether the candidate's identity and level are legible within 4 seconds, "
        "whether accomplishment claims are plausible given role context (7-month first "
        "job claiming to 'architect a platform serving 2M req/day' triggers a "
        "credibility discount), whether formatting signals inexperience, and whether "
        "early-career candidates have over-included irrelevant material.",
        default_enabled=False,
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
