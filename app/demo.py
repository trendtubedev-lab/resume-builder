"""Demo mode: produce realistic-looking output with NO Claude API call.

Used when ANTHROPIC_API_KEY is missing or DEMO_MODE is set. It heuristically
parses a resume (tuned for the bundled samples, degrades gracefully on anything
else), invents a plausible review panel, and lightly "tailors" the resume by
surfacing skills that appear in the job description. Clearly labelled as demo in
the UI so no one mistakes it for the real AI panel.
"""
from __future__ import annotations

import re

SECTION_WORDS = {
    "summary": "summary",
    "objective": "summary",
    "profile": "summary",
    "skills": "skills",
    "technical skills": "skills",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment": "experience",
    "education": "education",
    "projects": "projects",
    "certifications": "certifications",
    "certification": "certifications",
    "awards": "awards",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s().]{7,}\d)")
LINK_RE = re.compile(r"(linkedin\.com/\S+|github\.com/\S+|https?://\S+)", re.I)


def parse_resume_text(text: str) -> dict:
    # Drop file-separator headers the backend adds for multi-file uploads,
    # e.g. "--- resume.pdf ---", so they aren't mistaken for the name.
    lines = [
        l.rstrip()
        for l in text.splitlines()
        if not re.match(r"^\s*-{2,}\s*.+\s*-{2,}\s*$", l)
    ]
    nonempty = [l for l in lines if l.strip()]
    name = nonempty[0].strip() if nonempty else "Candidate"

    # Contact line is usually within the first few lines.
    head = "\n".join(nonempty[:4])
    email = (EMAIL_RE.search(head) or EMAIL_RE.search(text))
    email = email.group(0) if email else ""
    links = LINK_RE.findall(head)
    # Phone: avoid catching dates; look in the header block.
    phone = ""
    m = PHONE_RE.search(head)
    if m:
        phone = m.group(0).strip()
    # Location: a "City, ST" pattern in the header.
    loc = ""
    lm = re.search(r"([A-Z][A-Za-z.\s]+,\s*[A-Z]{2})\b", head)
    if lm:
        loc = lm.group(1).strip()

    # Split into sections by heading lines.
    sections: dict[str, list[str]] = {}
    current = None
    for l in lines[1:]:
        key = _heading_key(l)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(l)

    summary = " ".join(x.strip() for x in sections.get("summary", []) if x.strip())

    skills = []
    for l in sections.get("skills", []):
        for part in re.split(r"[,•|]", l):
            p = part.strip()
            if p:
                skills.append(p)

    experience = _parse_experience(sections.get("experience", []))
    education = _parse_education(sections.get("education", []))

    additional = []
    for sec in ("projects", "certifications", "awards"):
        items = _bullets(sections.get(sec, []))
        if items:
            additional.append({"heading": sec.capitalize(), "items": items})

    return {
        "name": name,
        "contact": {"email": email, "phone": phone, "location": loc, "links": list(links)},
        "summary": summary,
        "skills": skills,
        "experience": experience,
        "education": education,
        "additional": additional,
    }


def _heading_key(line: str):
    s = line.strip().lower().rstrip(":")
    if not s or len(s) > 30:
        return None
    return SECTION_WORDS.get(s)


def _bullets(rows):
    out = []
    for r in rows:
        t = r.strip().lstrip("-•* ").strip()
        if t:
            out.append(t)
    return out


def _parse_experience(rows):
    jobs = []
    cur = None
    for r in rows:
        s = r.strip()
        if not s:
            continue
        is_bullet = bool(re.match(r"^[-•*]", s))
        if is_bullet and cur:
            cur["bullets"].append(s.lstrip("-•* ").strip())
        else:
            # New role header line, e.g. "Title — Company | Location | Dates"
            if cur:
                jobs.append(cur)
            cur = {"title": "", "company": "", "location": "", "dates": "", "bullets": []}
            # Split off the meta (pipe-separated) part.
            head, *meta = s.split("|")
            tc = re.split(r"\s+[—–-]\s+", head.strip(), maxsplit=1)
            cur["title"] = tc[0].strip()
            if len(tc) > 1:
                cur["company"] = tc[1].strip()
            if meta:
                cur["location"] = meta[0].strip()
            if len(meta) > 1:
                cur["dates"] = meta[1].strip()
    if cur:
        jobs.append(cur)
    return jobs


def _parse_education(rows):
    edu = []
    for r in rows:
        s = r.strip()
        if not s:
            continue
        if re.match(r"^(gpa|relevant|coursework|honors)", s, re.I) and edu:
            edu[-1]["details"] = (edu[-1].get("details", "") + " " + s).strip()
            continue
        e = {"degree": "", "school": "", "location": "", "dates": "", "details": ""}
        head, *meta = s.split("|")
        ds = re.split(r"\s+[—–-]\s+", head.strip(), maxsplit=1)
        e["degree"] = ds[0].strip()
        if len(ds) > 1:
            e["school"] = ds[1].strip()
        if meta:
            e["location"] = meta[0].strip()
        if len(meta) > 1:
            e["dates"] = meta[1].strip()
        edu.append(e)
    return edu


# --- fake but plausible panel + tailoring --------------------------------

def _job_keywords(job: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z+/.]{1,}", job)
    common = {
        "the", "and", "you", "your", "for", "with", "our", "will", "are", "this",
        "that", "role", "what", "who", "looking", "about", "have", "from", "into",
        "across", "key", "ideally", "bonus", "experience", "strong", "excellent",
    }
    seen, out = set(), []
    for w in words:
        lw = w.lower()
        if len(w) >= 3 and lw not in common and lw not in seen:
            seen.add(lw)
            out.append(w)
    return out


def demo_panel(resume_text: str, job: str) -> list[dict]:
    rl = resume_text.lower()
    kws = _job_keywords(job)
    present = [k for k in kws if k.lower() in rl]
    missing = [k for k in kws if k.lower() not in rl]
    # Heuristic score: how much of the job's vocabulary the resume already covers.
    coverage = int(100 * len(present) / max(1, len(present) + len(missing)))
    base = max(35, min(85, coverage))

    def miss(n):
        picks = [m for m in missing if m[0].isupper()][:n] or missing[:n]
        return picks

    return [
        {
            "persona": "Technical Recruiter", "key": "recruiter", "match_score": base,
            "strengths": ["Relevant role history is easy to scan", "Clear, consistent formatting"],
            "gaps": [f"Job terms not surfaced: {', '.join(miss(3)) or 'minor'}"],
            "suggestions": ["Lead the summary with the target job title",
                            "Move the most relevant role/skills to the top"],
        },
        {
            "persona": "ATS / Keyword Specialist", "key": "ats", "match_score": max(30, base - 8),
            "strengths": ["Standard section headings parse cleanly"],
            "gaps": [f"Missing keywords from the posting: {', '.join(miss(4)) or 'none major'}"],
            "suggestions": ["Mirror exact phrasing from the job description where true",
                            "Add a focused Skills line with the job's hard skills"],
        },
        {
            "persona": "Hiring Manager", "key": "hiring_manager", "match_score": max(30, base - 4),
            "strengths": ["Some quantified impact present"],
            "gaps": ["Not every bullet shows measurable outcome",
                     "Scope/seniority fit could be made more explicit"],
            "suggestions": ["Quantify more bullets (%, $, time saved)",
                            "Tie achievements directly to this role's responsibilities"],
        },
        {
            "persona": "Professional Editor", "key": "editor", "match_score": min(90, base + 6),
            "strengths": ["Action verbs used in most bullets"],
            "gaps": ["A few bullets start weakly or run long"],
            "suggestions": ["Start every bullet with a strong verb",
                            "Trim filler; keep bullets to one line where possible"],
        },
    ]


def demo_synthesize(resume_text: str, job: str, tone: str = "professional") -> dict:
    r = parse_resume_text(resume_text)
    kws = _job_keywords(job)
    rl = " ".join(r.get("skills", [])).lower()

    # Surface skills the candidate has that the job mentions, first.
    present = [k for k in kws if k.lower() in rl]
    if r.get("skills"):
        prioritized = [s for s in r["skills"] if any(s.lower() in k.lower() or k.lower() in s.lower() for k in present)]
        rest = [s for s in r["skills"] if s not in prioritized]
        r["skills"] = prioritized + rest

    # Lightly retune the summary toward the job's first line (its title).
    target_title = (job.strip().splitlines() or [""])[0].split("—")[0].split("-")[0].strip()
    if target_title and r.get("summary"):
        r["summary"] = f"{target_title} candidate. " + r["summary"]

    r["change_summary"] = [
        "[DEMO] Reordered skills to surface job-relevant ones first",
        f"[DEMO] Aligned the summary toward the target role ({target_title or 'the posting'})",
        "[DEMO] Flagged missing keywords for you to weave in",
        "Note: this is a no-API demo. With an API key, the real AI panel rewrites the full resume.",
    ]
    return r
