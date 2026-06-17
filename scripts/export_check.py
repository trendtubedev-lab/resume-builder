"""Offline validation for the PDF/DOCX exporters.

Exercises app.export.build_docx / build_pdf with a representative resume dict and
asserts each returns a non-empty file with the correct magic header. Needs NO
Anthropic API key — it tests only the rendering path users actually receive, so
a broken exporter is caught before shipping.

Usage:
    python scripts/export_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import export  # noqa: E402

# Representative structured resume covering every section the exporters render.
SAMPLE_RESUME = {
    "name": "Priya Nair",
    "contact": {
        "email": "priya@example.com",
        "phone": "555-0100",
        "location": "Austin, TX",
        "links": ["linkedin.com/in/priyanair"],
    },
    "summary": "Backend engineer with 6 years building payment systems.",
    "skills": ["Python", "PostgreSQL", "AWS", "Kafka"],
    "experience": [
        {
            "title": "Senior Engineer",
            "company": "PayCo",
            "location": "Austin, TX",
            "dates": "2021–2024",
            "bullets": ["Cut latency 40%", "Led migration to Kafka"],
        }
    ],
    "education": [
        {
            "degree": "B.S. Computer Science",
            "school": "UT Austin",
            "dates": "2014–2018",
            "details": "Graduated with honors",
        }
    ],
    "additional": [
        {"heading": "Certifications", "items": ["AWS Solutions Architect"]}
    ],
}

# (builder, expected leading magic bytes, label)
CASES = [
    (export.build_docx, b"PK\x03\x04", "docx"),  # docx == zip container
    (export.build_pdf, b"%PDF", "pdf"),
]

MIN_BYTES = 500  # a real one-page resume is far larger; catches empty/stub output


def check() -> bool:
    ok = True
    for builder, magic, label in CASES:
        try:
            data = builder(SAMPLE_RESUME)
        except Exception as e:
            print(f"[FAIL] {label}: builder raised {e!r}")
            ok = False
            continue
        if not data or len(data) < MIN_BYTES:
            print(f"[FAIL] {label}: output too small ({len(data) if data else 0} bytes)")
            ok = False
        elif not data.startswith(magic):
            print(f"[FAIL] {label}: bad header {data[:8]!r} (expected {magic!r})")
            ok = False
        else:
            print(f"[OK] {label}: {len(data):,} bytes, valid header")
    return ok


def main():
    print("Export self-test (offline, no API key needed)")
    ok = check()
    print("ALL EXPORTS OK" if ok else "EXPORT CHECK FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
