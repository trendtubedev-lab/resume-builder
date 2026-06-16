"""Render a structured tailored resume into .docx and .pdf files."""
from __future__ import annotations

import io


def _g(d: dict, key: str, default=""):
    v = d.get(key, default)
    return v if v is not None else default


def build_docx(resume: dict) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    # Header: name + contact
    name = _g(resume, "name") or "Your Name"
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h.add_run(name)
    run.bold = True
    run.font.size = Pt(20)

    contact = _g(resume, "contact", {}) or {}
    bits = [contact.get("email"), contact.get("phone"), contact.get("location")]
    bits += list(contact.get("links") or [])
    bits = [b for b in bits if b]
    if bits:
        c = doc.add_paragraph(" | ".join(bits))
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.runs[0].font.size = Pt(9.5)

    def section(title: str):
        p = doc.add_paragraph()
        r = p.add_run(title.upper())
        r.bold = True
        r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(0x1A, 0x4D, 0x7A)
        pbdr = doc.add_paragraph()
        pbdr.paragraph_format.space_before = Pt(0)
        pbdr.paragraph_format.space_after = Pt(2)
        return p

    if _g(resume, "summary"):
        section("Summary")
        doc.add_paragraph(resume["summary"])

    skills = _g(resume, "skills", []) or []
    if skills:
        section("Skills")
        doc.add_paragraph(" • ".join(str(s) for s in skills))

    exp = _g(resume, "experience", []) or []
    if exp:
        section("Experience")
        for job in exp:
            p = doc.add_paragraph()
            title = _g(job, "title")
            company = _g(job, "company")
            line = title
            if company:
                line = f"{title} — {company}" if title else company
            r = p.add_run(line)
            r.bold = True
            meta = " | ".join(x for x in [_g(job, "location"), _g(job, "dates")] if x)
            if meta:
                p.add_run(f"\t{meta}").italic = True
            for b in _g(job, "bullets", []) or []:
                doc.add_paragraph(str(b), style="List Bullet")

    edu = _g(resume, "education", []) or []
    if edu:
        section("Education")
        for e in edu:
            p = doc.add_paragraph()
            deg = _g(e, "degree")
            school = _g(e, "school")
            line = " — ".join(x for x in [deg, school] if x)
            p.add_run(line).bold = True
            meta = " | ".join(x for x in [_g(e, "location"), _g(e, "dates")] if x)
            if meta:
                p.add_run(f"\t{meta}").italic = True
            if _g(e, "details"):
                doc.add_paragraph(str(e["details"]))

    for block in _g(resume, "additional", []) or []:
        heading = _g(block, "heading")
        items = _g(block, "items", []) or []
        if heading and items:
            section(heading)
            for it in items:
                doc.add_paragraph(str(it), style="List Bullet")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_pdf(resume: dict) -> bytes:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        HRFlowable,
        ListFlowable,
        ListItem,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )
    ss = getSampleStyleSheet()
    accent = HexColor("#1A4D7A")
    name_style = ParagraphStyle("name", parent=ss["Title"], fontSize=22, alignment=TA_CENTER, spaceAfter=2)
    contact_style = ParagraphStyle("contact", parent=ss["Normal"], fontSize=9, alignment=TA_CENTER, textColor=HexColor("#444444"))
    sec_style = ParagraphStyle("sec", parent=ss["Heading2"], fontSize=12, textColor=accent, spaceBefore=10, spaceAfter=2)
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=10.5, leading=14)
    role = ParagraphStyle("role", parent=body, fontSize=11, spaceBefore=4)
    meta = ParagraphStyle("meta", parent=body, fontSize=9, textColor=HexColor("#555555"))

    flow = []

    def esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    flow.append(Paragraph(esc(_g(resume, "name") or "Your Name"), name_style))
    contact = _g(resume, "contact", {}) or {}
    bits = [contact.get("email"), contact.get("phone"), contact.get("location")]
    bits += list(contact.get("links") or [])
    bits = [esc(b) for b in bits if b]
    if bits:
        flow.append(Paragraph(" &nbsp;|&nbsp; ".join(bits), contact_style))

    def section(title):
        flow.append(Paragraph(esc(title).upper(), sec_style))
        flow.append(HRFlowable(width="100%", thickness=0.6, color=accent, spaceAfter=4))

    def bullets(items):
        lis = [ListItem(Paragraph(esc(b), body), leftIndent=10) for b in items if b]
        if lis:
            flow.append(ListFlowable(lis, bulletType="bullet", start="•", leftIndent=12))

    if _g(resume, "summary"):
        section("Summary")
        flow.append(Paragraph(esc(resume["summary"]), body))

    skills = _g(resume, "skills", []) or []
    if skills:
        section("Skills")
        flow.append(Paragraph(" &nbsp;•&nbsp; ".join(esc(s) for s in skills), body))

    exp = _g(resume, "experience", []) or []
    if exp:
        section("Experience")
        for job in exp:
            title = _g(job, "title")
            company = _g(job, "company")
            line = " — ".join(x for x in [title, company] if x)
            m = " | ".join(x for x in [_g(job, "location"), _g(job, "dates")] if x)
            flow.append(Paragraph(f"<b>{esc(line)}</b>" + (f"  <font size=9 color='#555555'>{esc(m)}</font>" if m else ""), role))
            bullets(_g(job, "bullets", []) or [])

    edu = _g(resume, "education", []) or []
    if edu:
        section("Education")
        for e in edu:
            line = " — ".join(x for x in [_g(e, "degree"), _g(e, "school")] if x)
            m = " | ".join(x for x in [_g(e, "location"), _g(e, "dates")] if x)
            flow.append(Paragraph(f"<b>{esc(line)}</b>" + (f"  <font size=9 color='#555555'>{esc(m)}</font>" if m else ""), role))
            if _g(e, "details"):
                flow.append(Paragraph(esc(e["details"]), body))

    for block in _g(resume, "additional", []) or []:
        heading = _g(block, "heading")
        items = _g(block, "items", []) or []
        if heading and items:
            section(heading)
            bullets(items)

    doc.build(flow)
    return buf.getvalue()
