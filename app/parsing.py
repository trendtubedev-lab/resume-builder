"""Resume text extraction from PDF, DOCX, and plain text uploads."""
from __future__ import annotations

import io


def extract_text(filename: str, data: bytes) -> str:
    """Return plain text from an uploaded resume file.

    Supports .pdf, .docx, .txt / .md. Raises ValueError on unsupported types.
    """
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _from_pdf(data)
    if name.endswith(".docx"):
        return _from_docx(data)
    if name.endswith(".txt") or name.endswith(".md") or name.endswith(".text"):
        return data.decode("utf-8", errors="replace")
    # Last resort: try to decode as text.
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(
            f"Unsupported file type for '{filename}'. Use PDF, DOCX, or TXT."
        )


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError(
            "Could not extract text from this PDF (it may be a scanned image). "
            "Try exporting a text-based PDF or upload a DOCX/TXT version."
        )
    return text


def _from_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    # Include table cell text, which often holds resume content.
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text:
                    parts.append(cell.text)
    return "\n".join(parts).strip()
