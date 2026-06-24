"""Multi-agent review panel + tailored-resume synthesis via the local Claude CLI.

Flow:
  1. Several reviewer personas independently critique the candidate's resume(s)
     against the target job description.
  2. A synthesizer agent rewrites the resume into a single tailored version,
     incorporating the panel's feedback, and returns structured JSON.

Each reviewer runs in its own thread so the panel completes in parallel.
Calls route through the local `claude` CLI on the user's own Pro/Max plan —
no Anthropic API key required.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache

log = logging.getLogger("tailorcv")

DEFAULT_MODEL = "claude-sonnet-4-6"

# Max concurrent `claude` subprocesses (a large persona set could otherwise
# spawn one process each and trip plan rate limits / starve the machine).
MAX_PANEL_WORKERS = 6
# How many times to (re)try a single model call before giving up. Covers
# transient CLI hiccups and the occasional unparseable JSON response.
COMPLETION_ATTEMPTS = 2

# Read lazily (not at import) so .env is honored regardless of load ordering.
def reviewer_model() -> str:
    return os.getenv("REVIEWER_MODEL", DEFAULT_MODEL)


def synth_model() -> str:
    return os.getenv("SYNTH_MODEL", DEFAULT_MODEL)


# Seconds to wait on a single claude CLI call before timing out.
DEFAULT_CC_TIMEOUT = 180

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
    """Validate at startup that the `claude` CLI is available. Raises with a friendly message."""
    if _claude_exe() is None:
        raise RuntimeError(
            "The `claude` command was not found. "
            "Install Claude Code and sign in, then restart. "
            "See QUICKSTART_FRIENDS.md."
        )
    log.info("Provider: claude-code (local Claude Code CLI, user's own plan).")


def complete(system: str, user: str, model: str) -> str:
    """Return the model's raw text response (expected to be a JSON object)."""
    return _claude_code_complete(system, user, model)


def _cache_key(system: str, user: str, model: str) -> str:
    """Stable hash of the full request. Identical resume+JD+persona => same key."""
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(system.encode("utf-8"))
    h.update(b"\x00")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


def _complete_json(system: str, user: str, model: str) -> dict:
    """Cache-and-retry wrapper that returns parsed JSON.

    - Dedup: an identical (model, system, user) call is served from the SQLite
      completion cache, skipping the model round-trip entirely. Because the
      whole resume + job description live in `user`, re-running the same inputs
      (or a barely-changed one) is free and instant.
    - Retry: transient CLI failures or an unparseable response are retried up
      to COMPLETION_ATTEMPTS times. Only successfully-parsed results are cached.
    """
    from app import db  # local import avoids a circular import at module load

    key = _cache_key(system, user, model)
    cached = db.get_cached_completion(key)
    if cached is not None:
        try:
            return _parse_json(cached)
        except Exception:
            pass  # corrupt cache entry — fall through and regenerate

    last_err: Exception | None = None
    for attempt in range(1, COMPLETION_ATTEMPTS + 1):
        try:
            raw = complete(system, user, model)
            data = _parse_json(raw)
            db.save_cached_completion(key, raw)
            return data
        except Exception as e:
            last_err = e
            log.warning("Completion attempt %d/%d failed: %s",
                        attempt, COMPLETION_ATTEMPTS, e)
    raise RuntimeError(f"Model call failed after {COMPLETION_ATTEMPTS} attempts: {last_err}")


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


def _review_one(persona: Persona, resume_text: str, job: str) -> dict:
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
    data = _complete_json(REVIEWER_SYSTEM, prompt, reviewer_model())
    data["persona"] = persona.name
    data["key"] = persona.key
    return data


def run_panel(resume_text: str, job: str,
              user_email: str = "local@localhost",
              selected_keys: list[str] | None = None) -> list[dict]:
    """Run reviewer personas in parallel. Returns a list of critiques.

    selected_keys: if provided, only run personas whose key is in the list.
    If None or empty, falls back to the default-enabled presets.
    """
    panel_personas = _load_personas(user_email)
    if selected_keys:
        key_set = set(selected_keys)
        panel_personas = [p for p in panel_personas if p.key in key_set]
    if not panel_personas:
        # Nothing selected or nothing matched — fall back to default-enabled.
        from app.personas import PRESET_PERSONAS
        default_keys = {p.key for p in PRESET_PERSONAS if p.default_enabled}
        panel_personas = [p for p in _load_personas(user_email) if p.key in default_keys]
    results: list[dict] = []
    workers = max(1, min(len(panel_personas), MAX_PANEL_WORKERS))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(_review_one, p, resume_text, job): p for p in panel_personas
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


def synthesize(resume_text: str, job: str, panel: list[dict], tone: str = "professional") -> dict:
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
    return _complete_json(SYNTH_SYSTEM, prompt, synth_model())


def overall_score(panel: list[dict]) -> int | None:
    scores = [r.get("match_score") for r in panel if isinstance(r.get("match_score"), int)]
    if not scores:
        return None
    return round(sum(scores) / len(scores))


# --- helpers ---------------------------------------------------------------

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
