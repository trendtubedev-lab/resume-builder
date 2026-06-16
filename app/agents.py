"""Multi-agent review panel + tailored-resume synthesis via the Claude API.

Flow:
  1. Several reviewer personas independently critique the candidate's resume(s)
     against the target job description.
  2. A synthesizer agent rewrites the resume into a single tailored version,
     incorporating the panel's feedback, and returns structured JSON.

Each reviewer runs in its own thread so the panel completes in parallel.
"""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache

import anthropic
import httpx

log = logging.getLogger("tailorcv")

REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", "claude-sonnet-4-6")
SYNTH_MODEL = os.getenv("SYNTH_MODEL", "claude-sonnet-4-6")

# Low temperature for consistent, calibrated output.
REVIEWER_TEMPERATURE = 0.2
SYNTH_TEMPERATURE = 0.3

REVIEWER_SYSTEM = (
    "You are part of a blind resume review panel. You review independently and do "
    "not see other reviewers' opinions. Be concrete and honest, not flattering. "
    "Reference actual lines from the resume and actual requirements from the job. "
    "Never invent facts about the candidate. Output strict JSON only — no prose, "
    "no markdown fences."
)

SYNTH_SYSTEM = (
    "You are an expert resume writer. You tailor a candidate's real resume to a "
    "specific job. Truthfulness is absolute: you may rephrase, reorder, emphasize, "
    "and tighten, but you must NEVER invent employers, titles, dates, degrees, "
    "certifications, metrics, or skills the candidate does not actually have. "
    "Output strict JSON only — no prose, no markdown fences."
)


@dataclass
class Persona:
    key: str
    name: str
    brief: str


# The review panel. Each persona reviews independently with NO shared context,
# mirroring the "review-panel" approach: distinct lenses, no groupthink.
PERSONAS = [
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


def _truthy(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def _http_client() -> httpx.Client | None:
    """Build a proxy-aware HTTP client from env, or None to use the SDK default.

    The Anthropic SDK already honors standard proxy env vars (HTTPS_PROXY, etc.)
    out of the box, so we only build a custom client when extra config is set:

      ANTHROPIC_PROXY           explicit proxy URL (overrides env autodetection)
      ANTHROPIC_CA_BUNDLE       path to a corporate root CA (for TLS-inspecting proxies)
      ANTHROPIC_SKIP_TLS_VERIFY=1  disable TLS verification (INSECURE — last resort)

    Returns None when none of these are set, so default deployments are unaffected.
    """
    proxy = os.getenv("ANTHROPIC_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    ca_bundle = os.getenv("ANTHROPIC_CA_BUNDLE")
    skip_verify = _truthy("ANTHROPIC_SKIP_TLS_VERIFY")

    if not (os.getenv("ANTHROPIC_PROXY") or ca_bundle or skip_verify):
        return None  # nothing special — let the SDK manage its own client

    if skip_verify:
        verify: bool | str = False
        log.warning(
            "TLS verification is DISABLED (ANTHROPIC_SKIP_TLS_VERIFY). "
            "Only use this behind a trusted corporate proxy."
        )
    elif ca_bundle:
        verify = ca_bundle
    else:
        verify = True

    kwargs: dict = {"timeout": 120.0, "trust_env": True, "verify": verify}
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.Client(**kwargs)


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "No Anthropic API key. Add your key in the app, or set ANTHROPIC_API_KEY."
        )
    hc = _http_client()
    if hc is not None:
        return anthropic.Anthropic(api_key=key, http_client=hc)
    return anthropic.Anthropic(api_key=key)


def _review_one(client, persona: Persona, resume_text: str, job: str) -> dict:
    prompt = f"""Your lens: {persona.name}. {persona.brief}

Review the candidate's resume(s) below against the TARGET JOB through that lens only.
Be specific: cite concrete lines from the resume and concrete requirements from the
posting. Do not be generically positive — name real problems.

Score calibration for "match_score" (0-100):
- 80-100: clearly qualified, most requirements evidenced.
- 60-79: plausible fit with notable gaps.
- 40-59: partial fit; key requirements missing or unproven.
- below 40: weak fit for this specific role.

=== TARGET JOB DESCRIPTION ===
{job}

=== CANDIDATE RESUME(S) ===
{resume_text}

Output a JSON object of exactly this shape (no other text):
{{
  "match_score": <integer 0-100>,
  "strengths": [<up to 4 short strings, each tied to this job>],
  "gaps": [<up to 5 short strings: missing skills, keywords, or evidence>],
  "suggestions": [<up to 6 short, actionable rewrite suggestions>]
}}"""
    msg = client.messages.create(
        model=REVIEWER_MODEL,
        max_tokens=2000,
        temperature=REVIEWER_TEMPERATURE,
        system=REVIEWER_SYSTEM,
        messages=[
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "{"},  # prefill forces clean JSON
        ],
    )
    data = _parse_json("{" + _text(msg))
    data["persona"] = persona.name
    data["key"] = persona.key
    return data


def run_panel(resume_text: str, job: str, api_key: str | None = None) -> list[dict]:
    """Run all reviewer personas in parallel. Returns a list of critiques."""
    client = _client(api_key)
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(PERSONAS)) as ex:
        futures = {
            ex.submit(_review_one, client, p, resume_text, job): p for p in PERSONAS
        }
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:  # one reviewer failing shouldn't kill the panel
                results.append(
                    {
                        "persona": p.name,
                        "key": p.key,
                        "match_score": None,
                        "strengths": [],
                        "gaps": [f"(reviewer error: {e})"],
                        "suggestions": [],
                    }
                )
    # Keep a stable persona order.
    order = {p.key: i for i, p in enumerate(PERSONAS)}
    results.sort(key=lambda r: order.get(r.get("key"), 99))
    return results


def synthesize(resume_text: str, job: str, panel: list[dict], tone: str = "professional",
               api_key: str | None = None) -> dict:
    """Rewrite the resume into a tailored version using the panel's feedback."""
    client = _client(api_key)
    panel_json = json.dumps(panel, indent=2)
    prompt = f"""Rewrite the candidate's resume into a SINGLE tailored version optimized
for the target job, acting on the review panel's feedback. Tone: {tone}.

Hard rules (truthfulness comes before everything else):
- Use ONLY facts present in the original resume(s). Do NOT invent employers,
  titles, dates, degrees, certifications, or metrics.
- Do NOT add a skill unless the resume already shows it. You may surface and
  reorder real skills to match the job; you may not fabricate new ones.
- Keep every employer, title, and date exactly as in the original.
- Numbers: keep real metrics; never invent figures. If impact is real but
  unquantified, describe it qualitatively.

Tailoring guidance:
- Lead the summary toward the target role and what the candidate genuinely offers it.
- Reorder skills and bullets so the most job-relevant come first.
- Rewrite bullets to start with a strong action verb and show outcome/impact.
- Mirror the posting's exact terminology where the candidate truly matches it.
- Keep bullets tight (ideally one line). Cut filler and clichés.

=== TARGET JOB DESCRIPTION ===
{job}

=== ORIGINAL RESUME(S) ===
{resume_text}

=== REVIEW PANEL FEEDBACK (act on the consensus, use judgment) ===
{panel_json}

Output a JSON object of exactly this shape (no other text):
{{
  "name": "",
  "contact": {{"email": "", "phone": "", "location": "", "links": []}},
  "summary": "",
  "skills": [],
  "experience": [
    {{"title": "", "company": "", "location": "", "dates": "", "bullets": []}}
  ],
  "education": [
    {{"degree": "", "school": "", "location": "", "dates": "", "details": ""}}
  ],
  "additional": [
    {{"heading": "", "items": []}}
  ],
  "change_summary": [<3-6 short strings describing the key tailoring changes you made>]
}}"""
    msg = client.messages.create(
        model=SYNTH_MODEL,
        max_tokens=8000,
        temperature=SYNTH_TEMPERATURE,
        system=SYNTH_SYSTEM,
        messages=[
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "{"},  # prefill forces clean JSON
        ],
    )
    return _parse_json("{" + _text(msg))


def overall_score(panel: list[dict]) -> int | None:
    scores = [r.get("match_score") for r in panel if isinstance(r.get("match_score"), int)]
    if not scores:
        return None
    return round(sum(scores) / len(scores))


# --- helpers ---------------------------------------------------------------

def _text(msg) -> str:
    return "".join(block.text for block in msg.content if block.type == "text")


def _parse_json(s: str) -> dict:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1:
            return json.loads(s[start : end + 1])
        raise
