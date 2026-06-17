"""
Generate TailorCV_Install_Guide.pdf
Run: python scripts/generate_install_guide.py
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Preformatted, Image as RLImage
)
import os as _os
LOGO_PATH = _os.path.join(_os.path.dirname(__file__), "..", "app", "static", "logo_icon_flat.png")
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Brand colour ──────────────────────────────────────────────────────────────
BRAND = colors.HexColor("#1a4d7a")
BRAND_LIGHT = colors.HexColor("#e8f0f7")
CODE_BG = colors.HexColor("#f4f4f4")
GRAY = colors.HexColor("#555555")
BLACK = colors.black
WHITE = colors.white

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "docs", "TailorCV_Install_Guide.pdf")

# ── Page template (header + footer) ───────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    w, h = letter
    # Footer line
    canvas.setStrokeColor(BRAND)
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, 0.6 * inch, w - 0.75 * inch, 0.6 * inch)
    # Footer text
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(0.75 * inch, 0.42 * inch,
                      "github.com/trendtubedev-lab/resume-builder")
    canvas.drawRightString(w - 0.75 * inch, 0.42 * inch, f"Page {doc.page}")
    canvas.restoreState()


def on_first_page(canvas, doc):
    # Cover page — no header/footer rule, just the footer URL
    canvas.saveState()
    w, h = letter
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawCentredString(w / 2, 0.42 * inch,
                             "github.com/trendtubedev-lab/resume-builder")
    canvas.restoreState()


# ── Styles ────────────────────────────────────────────────────────────────────
def build_styles():
    base = getSampleStyleSheet()

    def add(name, parent="Normal", **kw):
        base.add(ParagraphStyle(name=name, parent=base[parent], **kw))

    add("CoverTitle", parent="Title",
        fontSize=30, textColor=WHITE, alignment=TA_CENTER,
        spaceAfter=8, leading=36)
    add("CoverSubtitle", fontSize=14, textColor=colors.HexColor("#cce0f5"),
        alignment=TA_CENTER, spaceAfter=6)
    add("CoverURL", fontSize=11, textColor=colors.HexColor("#a0c4e8"),
        alignment=TA_CENTER, spaceAfter=4)
    add("CoverVersion", fontSize=10, textColor=colors.HexColor("#8ab4d4"),
        alignment=TA_CENTER)

    add("SectionHeading", fontSize=14, textColor=WHITE,
        fontName="Helvetica-Bold", spaceAfter=10, spaceBefore=4,
        leftIndent=0, leading=18)
    add("SubHeading", fontSize=12, textColor=BRAND,
        fontName="Helvetica-Bold", spaceAfter=6, spaceBefore=10)
    add("Body", fontSize=10, textColor=BLACK,
        spaceAfter=6, leading=15)
    add("BulletBody", parent="Body", leftIndent=18, spaceAfter=4,
        bulletIndent=6)
    add("CodeStyle", fontName="Courier", fontSize=9,
        textColor=colors.HexColor("#1a1a1a"),
        leftIndent=0, spaceAfter=0, leading=13)
    add("SmallGray", fontSize=8, textColor=GRAY, spaceAfter=4)
    add("TableHeader", fontName="Helvetica-Bold", fontSize=9,
        textColor=WHITE, alignment=TA_LEFT)
    add("TableCell", fontSize=9, textColor=BLACK, leading=13)
    add("FAQQuestion", fontName="Helvetica-Bold", fontSize=10,
        textColor=BRAND, spaceAfter=2, spaceBefore=8)
    add("FAQAnswer", fontSize=10, textColor=BLACK, spaceAfter=4,
        leftIndent=10, leading=14)
    add("StepNum", fontName="Helvetica-Bold", fontSize=11,
        textColor=BRAND, spaceAfter=2, spaceBefore=10)

    return base


def section_banner(styles, text):
    """Blue banner row containing a section title."""
    tbl = Table([[Paragraph(text, styles["SectionHeading"])]], colWidths=[6.5 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return tbl


def code_block(styles, *lines):
    """Light-gray code block."""
    text = "\n".join(lines)
    inner = Preformatted(text, styles["CodeStyle"])
    tbl = Table([[inner]], colWidths=[6.5 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
    ]))
    return tbl


def cover_block():
    """Full-width blue cover page block."""
    w, h = letter
    from reportlab.platypus import Flowable

    class CoverBg(Flowable):
        def __init__(self, width, height):
            Flowable.__init__(self)
            self.width = width
            self.height = height

        def draw(self):
            self.canv.setFillColor(BRAND)
            self.canv.rect(-0.75 * inch, -self.height + 1.5 * inch,
                           self.width + 1.5 * inch, self.height,
                           fill=1, stroke=0)

    return CoverBg(w, h * 0.45)


def build_story(styles):
    story = []
    B = styles["Body"]
    SH = styles["SubHeading"]

    # ── COVER ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.4 * inch))

    # Logo centered above the blue banner
    if _os.path.exists(LOGO_PATH):
        logo = RLImage(LOGO_PATH, width=1.1 * inch, height=1.1 * inch)
        logo_tbl = Table([[logo]], colWidths=[6.5 * inch])
        logo_tbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(logo_tbl)
        story.append(Spacer(1, 0.15 * inch))

    # Blue banner behind cover text — achieved via a Table with background
    cover_data = [
        [Paragraph("TailorCV", styles["CoverTitle"])],
        [Paragraph("Installation &amp; Setup Guide", styles["CoverTitle"])],
        [Spacer(1, 6)],
        [Paragraph("Tailor your resume to any job in minutes using AI",
                   styles["CoverSubtitle"])],
        [Spacer(1, 4)],
        [Paragraph("github.com/trendtubedev-lab/resume-builder",
                   styles["CoverURL"])],
        [Spacer(1, 4)],
        [Paragraph("Last updated June 2026", styles["CoverVersion"])],
        [Spacer(1, 20)],
    ]
    cover_tbl = Table(cover_data, colWidths=[6.5 * inch])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(cover_tbl)
    story.append(PageBreak())

    # ── SECTION 1: What is TailorCV? ──────────────────────────────────────────
    story.append(section_banner(styles, "Section 1 — What is TailorCV?"))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "TailorCV is a local web app that uses a panel of four independent AI "
        "reviewers — a recruiter, an ATS/keyword specialist, a hiring manager, "
        "and an editor — to critique your resume against a specific job description "
        "and rewrite it into a single, polished tailored version.",
        B))
    story.append(Paragraph(
        "The finished resume can be downloaded as a PDF or Word document. "
        "Everything runs on your own computer: your resume is processed in memory "
        "and never saved to disk or sent to any third party beyond the AI model "
        "you have chosen.",
        B))
    story.append(Paragraph(
        "TailorCV supports two modes: using your existing Claude Pro or Max "
        "subscription (recommended — no per-use cost), or using an Anthropic API "
        "key (a few cents per run).",
        B))
    story.append(Spacer(1, 12))

    # ── SECTION 2: What You'll Need ───────────────────────────────────────────
    story.append(section_banner(styles, "Section 2 — What You'll Need"))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Choose one of the two options below. Option A is recommended — it uses "
        "your existing Claude subscription with no additional per-use cost.", B))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Option A — Use your Claude Pro/Max plan (recommended)",
                            SH))
    bullets_a = [
        "Claude Pro or Max subscription — claude.ai",
        "Node.js 18 or later — nodejs.org (download the LTS installer)",
        "Python 3.10 or later — python.org",
    ]
    for b in bullets_a:
        story.append(Paragraph(f"&bull; &nbsp; {b}", styles["BulletBody"]))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Option B — Use an Anthropic API key", SH))
    bullets_b = [
        "Anthropic API key — console.anthropic.com",
        "Python 3.10 or later — python.org",
    ]
    for b in bullets_b:
        story.append(Paragraph(f"&bull; &nbsp; {b}", styles["BulletBody"]))

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "On Windows, when installing Python make sure to tick "
        "<b>\"Add Python to PATH\"</b> during the installer.", B))
    story.append(Spacer(1, 12))

    # ── SECTION 3: Download & Install ─────────────────────────────────────────
    story.append(section_banner(styles, "Section 3 — Download &amp; Install"))
    story.append(Spacer(1, 8))

    # Step 1
    story.append(Paragraph("Step 1: Download from GitHub", styles["StepNum"]))
    story.append(Paragraph(
        "Go to the repository and click <b>Code → Download ZIP</b>, then unzip "
        "it anywhere on your computer. Or, if you have git:", B))
    story.append(code_block(styles,
        "git clone https://github.com/trendtubedev-lab/resume-builder.git",
        "cd resume-builder"))
    story.append(Spacer(1, 10))

    # Step 2
    story.append(Paragraph("Step 2: Install Claude Code  (Option A only)", styles["StepNum"]))
    story.append(Paragraph(
        "Open a terminal (Windows: PowerShell; Mac: Terminal) and run:", B))
    story.append(code_block(styles,
        "npm install -g @anthropic-ai/claude-code"))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Verify it installed:", B))
    story.append(code_block(styles, "claude --version"))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "You should see a version number. Then sign in with your subscription:", B))
    story.append(code_block(styles, "claude"))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "A browser window opens. Choose <b>Subscription</b> (your Pro/Max account) "
        "— not an API key. Once signed in, type <b>/exit</b> or press Ctrl+C. "
        "You only do this once.", B))
    story.append(Spacer(1, 10))

    # Step 3
    story.append(Paragraph("Step 3: Configure", styles["StepNum"]))
    story.append(Paragraph("Copy the example config file:", B))
    story.append(code_block(styles,
        "Mac/Linux:  cp .env.example .env",
        "Windows:    Copy-Item .env.example .env"))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Open <b>.env</b> in any text editor (Notepad works on Windows). "
        "Set the values for your chosen option:", B))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>For Option A (Claude plan):</b>", B))
    story.append(code_block(styles,
        "PROVIDER=claude-code",
        "AUTH_DISABLED=1",
        "SESSION_SECRET=any-long-random-string-you-make-up"))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>For Option B (API key):</b>", B))
    story.append(code_block(styles,
        "ANTHROPIC_API_KEY=sk-ant-your-key-here",
        "AUTH_DISABLED=1",
        "SESSION_SECRET=any-long-random-string-you-make-up"))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "For <b>SESSION_SECRET</b>, just type any long random string — it only "
        "needs to exist. Example: <font name='Courier' size='9'>mysecretvalue12345xyz</font>", B))
    story.append(Spacer(1, 10))

    # Step 4
    story.append(Paragraph("Step 4: Start TailorCV", styles["StepNum"]))
    story.append(Paragraph(
        "Double-click the startup script for your operating system:", B))
    story.append(code_block(styles,
        "Windows:  double-click  start.bat",
        "Mac:      double-click  start.command"))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "The first run takes about one minute to set up a Python environment "
        "and install dependencies. Subsequent starts are fast. When ready, "
        "open your browser and go to:", B))
    story.append(code_block(styles, "http://localhost:8000"))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "You should see a <b>green banner</b> at the top of the page "
        "(\"Running on your Claude plan\" for Option A, or the reviewer panel "
        "ready for Option B). A yellow banner means demo mode — see Section 5 FAQ.", B))
    story.append(Spacer(1, 12))

    # ── SECTION 4: Using TailorCV ─────────────────────────────────────────────
    story.append(section_banner(styles, "Section 4 — Using TailorCV"))
    story.append(Spacer(1, 8))

    steps = [
        ("1.", "Upload your resume — PDF, DOCX, or TXT. Up to 3 files at once "
               "(useful for uploading multiple versions)."),
        ("2.", "Paste the target job description into the text box."),
        ("3.", "Choose a tone: Professional, Impactful, Concise, or Executive."),
        ("4.", "Click <b>Tailor my resume</b>."),
        ("5.", "Wait roughly 30–60 seconds while four AI reviewers analyze your "
               "resume independently."),
        ("6.", "Review the panel feedback — each reviewer shows a score and "
               "specific suggestions — plus the synthesized tailored resume."),
        ("7.", "Download the result as PDF or Word using the buttons at the bottom."),
    ]
    for num, text in steps:
        row = Table([[Paragraph(f"<b>{num}</b>", styles["SubHeading"]),
                      Paragraph(text, B)]],
                    colWidths=[0.35 * inch, 6.15 * inch])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(row)

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>Tip:</b> Click <b>&#9881; Manage reviewers</b> at the top of the "
        "app to edit any reviewer's focus, add your own, or reset the presets "
        "to defaults.", B))
    story.append(Spacer(1, 12))

    # ── SECTION 5: FAQ ────────────────────────────────────────────────────────
    story.append(section_banner(styles, "Section 5 — Frequently Asked Questions"))
    story.append(Spacer(1, 8))

    faqs = [
        ("Is my resume stored anywhere?",
         "No. Your resume is processed in memory and never saved to disk or "
         "sent to any third party beyond the AI model you have chosen."),
        ("What file types can I upload?",
         "PDF, DOCX, and TXT files. Up to 3 files at once — useful for "
         "uploading different resume versions in the same run."),
        ("Can I customize the AI reviewers?",
         "Yes. Click \"Manage reviewers\" at the top of the app to edit any "
         "reviewer's focus, add your own custom reviewer, or reset the "
         "presets to defaults."),
        ("What does the match score mean?",
         "It is the panel's estimate of how well your original resume matches "
         "the job — before tailoring. Use it as a baseline, not a final grade."),
        ("Will it make things up about me?",
         "No. TailorCV only rephrases, reorders, and emphasizes what is "
         "already in your resume. It will never invent employers, titles, "
         "dates, or skills you do not have."),
        ("What is demo mode?",
         "If you have not set up a Claude plan or API key, the app runs a "
         "lightweight offline preview. The interface works but the results "
         "are not AI-generated. Look for the yellow banner at the top."),
        ("How much does it cost per run?",
         "Option A (Claude plan): covered by your existing subscription. "
         "Option B (API key): roughly a few cents per run using Claude Sonnet "
         "(5 model calls per tailoring run)."),
        ("Something went wrong — what do I do?",
         "Check the troubleshooting table in Section 6 below."),
    ]
    for q, a in faqs:
        story.append(Paragraph(q, styles["FAQQuestion"]))
        story.append(Paragraph(a, styles["FAQAnswer"]))

    story.append(Spacer(1, 12))

    # ── SECTION 6: Troubleshooting ────────────────────────────────────────────
    story.append(section_banner(styles, "Section 6 — Troubleshooting"))
    story.append(Spacer(1, 8))

    headers = ["Problem", "Fix"]
    rows = [
        ["App won't start — \"claude not found\"",
         "Re-run Step 2 (install Claude Code). Open a new terminal after installing and try again."],
        ["\"Are you signed in? Run claude once to log in.\"",
         "Run claude in terminal, sign in with your Claude subscription (choose Subscription, not API key)."],
        ["Yellow demo banner instead of green",
         "Check .env has PROVIDER=claude-code (Option A) or a valid ANTHROPIC_API_KEY (Option B). Restart the app."],
        ["\"Timed out\" during tailoring",
         "Re-run — usually a one-off. If persistent, add CLAUDE_CODE_TIMEOUT=300 to .env."],
        ["start.command won't open on Mac",
         "Right-click the file, choose Open, then confirm in the dialog. Mac security blocks unsigned scripts by default."],
        ["Port 8000 already in use",
         "Another app is using that port. Add PORT=8001 to .env and open http://localhost:8001 instead."],
    ]

    tbl_data = [[Paragraph(h, styles["TableHeader"]) for h in headers]]
    for row in rows:
        tbl_data.append([Paragraph(cell, styles["TableCell"]) for cell in row])

    t = Table(tbl_data, colWidths=[2.6 * inch, 3.9 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # ── SECTION 7: Stopping & Restarting ─────────────────────────────────────
    story.append(section_banner(styles, "Section 7 — Stopping &amp; Restarting"))
    story.append(Spacer(1, 8))
    stop_rows = [
        ["Stop the app", "Press Ctrl+C in the terminal window, or simply close it."],
        ["Restart", "Double-click start.bat (Windows) or start.command (Mac) again."],
        ["Windows quick restart", "Double-click restart.bat — kills any running instance and relaunches."],
    ]
    for label, desc in stop_rows:
        row = Table([[Paragraph(f"<b>{label}:</b>", B),
                      Paragraph(desc, B)]],
                    colWidths=[1.8 * inch, 4.7 * inch])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(row)

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Questions or issues? Open an issue at "
        "github.com/trendtubedev-lab/resume-builder",
        styles["SmallGray"]))

    return story


def main():
    out = os.path.abspath(OUTPUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    styles = build_styles()

    doc = SimpleDocTemplate(
        out,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.9 * inch,
        title="TailorCV Installation & Setup Guide",
        author="TailorCV",
        subject="Installation guide for TailorCV resume-tailoring app",
    )

    story = build_story(styles)

    doc.build(story,
              onFirstPage=on_first_page,
              onLaterPages=on_page)

    print(f"PDF written to: {out}")


if __name__ == "__main__":
    main()
