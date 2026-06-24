"""Render every template/format combo to output/samples/ for visual review.

Offline, no API key. Uses the same representative resume dict as export_check.
Run: python scripts/render_samples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import export  # noqa: E402
from scripts.export_check import SAMPLE_RESUME  # noqa: E402

OUT = ROOT / "output" / "samples"
OUT.mkdir(parents=True, exist_ok=True)

TEMPLATES = ["classic", "banner", "minimal"]

for t in TEMPLATES:
    pdf = export.build_pdf(SAMPLE_RESUME, template=t)
    (OUT / f"{t}.pdf").write_bytes(pdf)
    docx = export.build_docx(SAMPLE_RESUME, template=t)
    (OUT / f"{t}.docx").write_bytes(docx)
    print(f"[OK] {t}: pdf {len(pdf):,}B  docx {len(docx):,}B")

print(f"\nWrote {len(TEMPLATES)*2} files to {OUT}")
