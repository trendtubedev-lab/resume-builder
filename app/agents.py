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
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache

import anthropic
import httpx

log = logging.getLogger("tailorcv")

DEFAULT_MODEL = "claude-sonnet-4-6"

# Read lazily (not at import) so .env is honored regardless of load ordering.
def reviewer_model() -> str:
    return os.getenv("REVIEWER_MODEL", DEFAULT_MODEL)


def synth_model() -> str:
    return os.getenv("SYNTH_MODEL", DEFAULT_MODEL)

# Where completions are routed:
#   "api"         — Anthropic API, using a per-user or server ANTHROPIC_API_KEY (hosted default).
#   "claude-code" — the user's LOCAL Claude Code CLI, on their own Pro/Max plan (no API key).
# See QUICKSTART_FRIENDS.md for the local setup.
# PROVIDER and the timeout are read lazily (using_claude_code() / _cc_timeout())
# so they honor .env no matter when it is loaded relative to this import.
DEFAULT_CC_TIMEOUT = 180

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


# Personas are loaded dynamically from personas.py (presets + per-user custom).
# Import lazily to avoid circular imports at module load time.
def _load_personas(user_email: str) -> list[Persona]:
    from app.personas import get_personas
    return [Persona(p.key, p.name, p.brief) for p in get_personas(user_email)]


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


@lru_cache(maxsize=8)
def _client(api_key: str | None = None) -> anthropic.Anthropic:
    # Cached by key so a single tailoring run (4 reviewers + 1 synth) reuses one
    # client instead of constructing five. lru_cache does not cache the raises below.
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "No Anthropic API key. Add your key in the app, or set ANTHROPIC_API_KEY."
        )
    hc = _http_client()
    if hc is not None:
        return anthropic.Anthropic(api_key=key, http_client=hc)
    return anthropic.Anthropic(api_key=key)


# --- provider layer --------------------------------------------------------
# Both reviewer and synthesizer go through complete(): it returns the model's
# raw response text (a JSON object as a string) for _parse_json to handle.

def using_claude_code() -> bool:
    return os.getenv("PROVIDER", "api").strip().lower() in {"claude-code", "claude_code", "cc"}


def _cc_timeout() -> int:
    """CLAUDE_CODE_TIMEOUT as an int, tolerant of a bad value (no boot crash)."""
    raw = os.getenv("CLAUDE_CODE_TIMEOUT", str(DEFAULT_CC_TIMEOUT))
    try:
        return int(raw)
    except ValueError:
        log.warning("CLAUDE_CODE_TIMEOUT=%r is not an integer; using %ds.", raw, DEFAULT_CC_TIMEOUT)
        return DEFAULT_CC_TIMEOUT


@lru_cache(maxsize=1)
def _claude_exe() -> str | None:
    """Resolve the `claude` CLI, handling the Windows .cmd shim via PATHEXT."""
    return shutil.which("claude")


def preflight() -> None:
    """Validate the selected provider at startup. Raises with a friendly message."""
    if using_claude_code():
        if _claude_exe() is None:
            raise RuntimeError(
                "PROVIDER=claude-code but the `claude` command was not found. "
                "Install Claude Code and sign in, then restart. "
                "See QUICKSTART_FRIENDS.md."
            )
        log.info("Provider: claude-code (local Claude Code CLI, user's own plan).")
    else:
        log.info("Provider: api (Anthropic API key).")


def complete(system: str, user: str, model: str, max_tokens: int,
             temperature: float, api_key: str | None) -> str:
    """Return the model's raw text response (expected to be a JSON object)."""
    if using_claude_code():
        return _claude_code_complete(system, user, model)
    return _api_complete(system, user, model, max_tokens, temperature, api_key)


def _api_complete(system: str, user: str, model: str, max_tokens: int,
                  temperature: float, api_key: str | None) -> str:
    client = _client(api_key)
    # No assistant-message prefill: newer models (e.g. claude-sonnet-4-6) reject
    # it ("does not support assistant message prefill"). The prompts already ask
    # for JSON-only and _parse_json() strips fences / extracts the outer object.
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[
            {"role": "user", "content": user},
        ],
    )
    return _text(msg)


def _claude_code_complete(system: str, user: str, model: str) -> str:
    """Run one completion through the local Claude Code CLI on the user's plan.

    Notes:
    - max_tokens / temperature are not exposed by `claude -p`, so they don't
      apply here; the model's defaults are used.
    - The prompt is piped via stdin (not argv) to avoid OS command-line length
      limits on large resumes/job descriptions.
    - We run in a neutral temp cwd so the project's own CLAUDE.md is not
      injected into the prompt context.
    """
    exe = _claude_exe()
    if exe is None:
        raise RuntimeError(
            "`claude` command not found. Install Claude Code and sign in "
            "(see QUICKSTART_FRIENDS.md)."
        )
    prompt = (
        f"{system}\n\n{user}\n\n"
        "Respond with ONLY the JSON object — no markdown fences, no preamble."
    )
    timeout = _cc_timeout()
    try:
        proc = subprocess.run(
            # --tools "" disables ALL tools: the resume/job text is untrusted, so the
            # model must only emit text and can never be induced (prompt injection) to
            # run a tool on the host. Prompt is piped via stdin, never as an argv.
            [exe, "-p", "--output-format", "json", "--model", model, "--tools", ""],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            cwd=tempfile.gettempdir(),
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Claude Code timed out after {timeout}s.") from e
    if proc.returncode != 0:
        # Log the detail server-side; don't leak local paths/stderr to the client.
        log.error("claude exited %s: %s", proc.returncode,
                  (proc.stderr or proc.stdout or "").strip()[-1000:])
        raise RuntimeError(
            "Claude Code call failed. Are you signed in? Run `claude` once to log in "
            "(see QUICKSTART_FRIENDS.md)."
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError("Could not parse Claude Code output as JSON.") from e
    if payload.get("is_error") or payload.get("subtype") != "success":
        raise RuntimeError(
            f"Claude Code returned an error: {payload.get('result') or payload.get('subtype')}"
        )
    return str(payload.get("result", ""))


def _review_one(persona: Persona, resume_text: str, job: str, api_key: str | None) -> dict:
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
    raw = complete(REVIEWER_SYSTEM, prompt, reviewer_model(), 2000,
                   REVIEWER_TEMPERATURE, api_key)
    data = _parse_json(raw)
    data["persona"] = persona.name
    data["key"] = persona.key
    return data


def run_panel(resume_text: str, job: str, api_key: str | None = None,
              user_email: str = "local@localhost") -> list[dict]:
    """Run all reviewer personas in parallel. Returns a list of critiques."""
    panel_personas = _load_personas(user_email)
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(panel_personas)) as ex:
        futures = {
            ex.submit(_review_one, p, resume_text, job, api_key): p for p in panel_personas
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
    order = {p.key: i for i, p in enumerate(panel_personas)}
    results.sort(key=lambda r: order.get(r.get("key"), 99))
    return results


def synthesize(resume_text: str, job: str, panel: list[dict], tone: str = "professional",
               api_key: str | None = None) -> dict:
    """Rewrite the resume into a tailored version using the panel's feedback."""
    panel_json = json.dumps(panel, indent=2)
    prompt = f"""Rewrite the candidate's resume into a SINGLE tailored version optimized
for the target job, acting on the review panel's feedback. Tone: {tone}.

Hard rules (truthfulness comes before everything else):
- Use ONLY facts present in the original resume(s). Do NOT invent employers,
  titles, dates, degrees, certifications, or metrics.
- Do NOT add a skill unless the resume already shows it. You may surface and
  reorder real skills to match the job; you may not fabricate new ones.
- Keep every employer, title, and date exactly as in the original. The `company`
  field must be the verbatim company name — do NOT append descriptors, labels,
  or domain annotations (e.g. "(e-commerce retailer)") to it.
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
    raw = complete(SYNTH_SYSTEM, prompt, synth_model(), 8000, SYNTH_TEMPERATURE, api_key)
    return _parse_json(raw)


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
