"""Live validation harness for TailorCV's AI panel.

Runs the real Claude API against the three bundled sample resumes, prints each
reviewer's scores and the synthesized result, and runs a basic FABRICATION CHECK
(every employer, school, and 4-digit year in the output must appear in the
original resume). Use this after adding your Anthropic key to confirm output
quality before shipping or charging.

Usage:
    # key from .env or environment
    python scripts/live_test.py
    # or just one sample
    python scripts/live_test.py mid
"""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app import agents  # noqa: E402

SAMPLES = {
    "entry": "entry_jordan_lee.txt",
    "mid": "mid_priya_nair.txt",
    "senior": "senior_marcus_bell.txt",
}
SAMPLES_DIR = ROOT / "app" / "samples"


def fabrication_check(original: str, resume: dict) -> list[str]:
    """Flag employers/schools/years in the output that aren't in the original."""
    orig = original.lower()
    problems = []

    def seen(value: str) -> bool:
        v = (value or "").strip().lower()
        return not v or v in orig

    for job in resume.get("experience", []) or []:
        if not seen(job.get("company", "")):
            problems.append(f"Company not in original: {job.get('company')!r}")
        if not seen(job.get("title", "")):
            # Titles can be lightly rephrased; only flag if no word overlaps.
            words = [w for w in re.findall(r"\w+", (job.get("title") or "").lower()) if len(w) > 3]
            if words and not any(w in orig for w in words):
                problems.append(f"Title looks invented: {job.get('title')!r}")
    for e in resume.get("education", []) or []:
        if not seen(e.get("school", "")):
            problems.append(f"School not in original: {e.get('school')!r}")

    # Any 4-digit year in output should exist in the original.
    out_years = set(re.findall(r"\b(19|20)\d{2}\b", _flatten(resume)))
    in_years = set(re.findall(r"\b(19|20)\d{2}\b", original))
    # (re.findall with a group returns the group; recompute fully)
    out_years = set(re.findall(r"\b(?:19|20)\d{2}\b", _flatten(resume)))
    in_years = set(re.findall(r"\b(?:19|20)\d{2}\b", original))
    for y in out_years - in_years:
        problems.append(f"Year not in original: {y}")
    return problems


def _flatten(obj) -> str:
    if isinstance(obj, dict):
        return " ".join(_flatten(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_flatten(v) for v in obj)
    return str(obj)


def run(sample_id: str):
    text = (SAMPLES_DIR / SAMPLES[sample_id]).read_text(encoding="utf-8")
    job = (SAMPLES_DIR / "sample_job.txt").read_text(encoding="utf-8")
    print(f"\n{'='*60}\nSAMPLE: {sample_id}\n{'='*60}")

    panel = agents.run_panel(text, job)
    print(f"Overall match score (pre-tailoring): {agents.overall_score(panel)}")
    for r in panel:
        print(f"  • {r['persona']}: {r.get('match_score')}  "
              f"(gaps: {len(r.get('gaps', []))}, suggestions: {len(r.get('suggestions', []))})")

    resume = agents.synthesize(text, job, panel)
    print(f"\nTailored name: {resume.get('name')}")
    print(f"Summary: {resume.get('summary', '')[:200]}")
    print(f"Skills (top 8): {resume.get('skills', [])[:8]}")
    print(f"Experience entries: {len(resume.get('experience', []))}")
    print("Change summary:")
    for c in resume.get("change_summary", []):
        print(f"  - {c}")

    problems = fabrication_check(text, resume)
    if problems:
        print("\n⚠️  FABRICATION CHECK FAILED:")
        for p in problems:
            print(f"   {p}")
    else:
        print("\n✅ Fabrication check passed (no invented employers/schools/years).")
    return not problems


def main():
    # Exporters are validated first — they need no API key and are the part
    # users actually receive, so a broken renderer should fail fast.
    from scripts.export_check import check as export_check
    print("Export self-test (offline):")
    if not export_check():
        print("\n❌ Export check failed — fix exporters before the API panel.")
        sys.exit(2)

    # Show which provider will handle the calls BEFORE any fire, so it is never
    # a surprise whether a run costs API money.
    if agents.using_claude_code():
        print("\nProvider: claude-code — calls run on your local Claude Code plan "
              "(NO API tokens billed).")
    else:
        print("\nProvider: api — calls bill against ANTHROPIC_API_KEY (costs money). "
              "Set PROVIDER=claude-code in .env to use your own plan instead.")
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("No ANTHROPIC_API_KEY found. Add it to .env or export it, then re-run.")
            sys.exit(1)
    ids = sys.argv[1:] or list(SAMPLES)
    ok = True
    for sid in ids:
        if sid not in SAMPLES:
            print(f"Unknown sample '{sid}'. Choose from: {', '.join(SAMPLES)}")
            continue
        try:
            ok = run(sid) and ok
        except Exception as e:
            ok = False
            print(f"\n❌ {sid} failed: {e}")
    print(f"\n{'='*60}\n{'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED — review above'}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
