from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
from fpdf import FPDF
from fpdf.enums import XPos, YPos

CJK_FONT_CANDIDATES = [
    Path(value)
    for value in (
        os.getenv("PDF_FONT_PATH"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyh.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    )
    if value
]


def resume_to_plain_text(draft: dict[str, Any]) -> str:
    lines = [draft["title"], ""]
    for section in draft["sections"]:
        lines.append(section["title"])
        for item in section.get("items", []):
            lines.append(f"- {item.get('text', '')}")
        lines.append("")
    return "\n".join(lines)


def _split_identity(draft: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Separate the identity header (name + contact) from the body sections."""
    sections = draft.get("sections", [])
    identity = next((section for section in sections if section.get("id") == "identity"), None)
    body = [section for section in sections if section.get("id") != "identity"]
    return identity, body


def _identity_lines(identity: dict[str, Any]) -> tuple[str, list[str]]:
    """Return (name, contact_lines) from an identity section's items."""
    texts = [str(item.get("text", "")).strip() for item in (identity.get("items") or [])]
    texts = [text for text in texts if text]
    if not texts:
        return "", []
    return texts[0], texts[1:]


def _apply_cjk_default_font(document: Document) -> None:
    """Best-effort: hint a CJK font so Chinese renders cleanly. Word substitutes a
    CJK font regardless, so failure here is non-fatal."""
    try:
        normal = document.styles["Normal"]
        normal.font.name = "Microsoft YaHei"
        rpr = normal.element.get_or_add_rPr()
        rfonts = rpr.get_or_add_rFonts()
        rfonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    except Exception:
        pass


def export_docx(draft: dict[str, Any]) -> bytes:
    """Render the resume draft as a real Word document via python-docx.

    The applicant's name + contact line lead the document (resume header), then
    each section renders as a heading with bulleted items.
    """
    document = Document()
    _apply_cjk_default_font(document)
    identity, body_sections = _split_identity(draft)

    if identity:
        name, contact_lines = _identity_lines(identity)
        header = document.add_paragraph()
        header.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = header.add_run(name or draft.get("title", ""))
        run.bold = True
        run.font.size = Pt(20)
        for line in contact_lines:
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.add_run(line)
    else:
        document.add_heading(draft["title"], level=0)

    for section in body_sections:
        document.add_heading(section.get("title", ""), level=1)
        for item in section.get("items", []):
            text = str(item.get("text", "")).strip()
            if text:
                document.add_paragraph(text, style="List Bullet")

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def export_pdf(draft: dict[str, Any]) -> bytes:
    """Export resume draft to PDF with CJK support using fpdf2."""
    pdf = FPDF()
    pdf.add_page()

    font_path = _find_cjk_font()
    if font_path is None:
        searched = ", ".join(str(path) for path in CJK_FONT_CANDIDATES)
        raise RuntimeError(
            "No CJK-capable PDF font found. Install fonts-noto-cjk or set PDF_FONT_PATH "
            f"to a Unicode font file. Searched: {searched}"
        )
    pdf.add_font("cjk", style="", fname=str(font_path))
    pdf.set_font("cjk", size=12)

    identity, body_sections = _split_identity(draft)

    # Header: applicant name + contact, or the draft title as a fallback.
    if identity:
        name, contact_lines = _identity_lines(identity)
        pdf.set_font_size(18)
        pdf.multi_cell(pdf.epw, 10, name or draft.get("title", ""), align="C")
        pdf.set_font_size(10)
        for line in contact_lines:
            pdf.multi_cell(pdf.epw, 6, line, align="C")
        pdf.ln(4)
    else:
        pdf.set_font_size(16)
        pdf.multi_cell(pdf.epw, 10, draft["title"], align="C")
        pdf.ln(5)

    for section in body_sections:
        pdf.set_font_size(14)
        pdf.cell(0, 8, section["title"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font_size(11)
        pdf.ln(2)

        for item in section.get("items", []):
            text = item.get("text", "")
            if text:
                pdf.multi_cell(0, 6, f"• {text}")
                pdf.ln(1)

        pdf.ln(3)

    return bytes(pdf.output())


def _find_cjk_font() -> Path | None:
    for font_path in CJK_FONT_CANDIDATES:
        if font_path.exists():
            return font_path
    return None
