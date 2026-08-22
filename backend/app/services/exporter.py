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


def _build_appendix_sections(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Build match-analysis appendix sections from evidence and gaps.

    Replaces the gaps paragraph in diagnostic mode with a structured
    ✅已满足 / ⚠️未满足 breakdown that carries evidence and suggestions.
    """
    satisfied_items: list[dict[str, Any]] = []
    for ev in draft.get("evidence", []):
        req = str(ev.get("requirement", "")).strip()
        label = str(ev.get("source_label", "")).strip()
        source = str(ev.get("source_text", "")).strip()
        strength = str(ev.get("evidence_strength", "")).strip()
        parts = [req]
        detail = "：".join(p for p in (label, source) if p)
        if detail:
            parts.append(f"证据：{detail}")
        if strength:
            parts.append(f"强度：{strength}")
        satisfied_items.append({"text": " — ".join(parts)})

    unmet_items: list[dict[str, Any]] = []
    for gap in draft.get("gaps", []):
        req = str(gap.get("requirement", "")).strip()
        msg = str(gap.get("message", "")).strip()
        parts = [req]
        if msg:
            parts.append(f"建议：{msg}")
        if gap.get("blocking"):
            parts.append("（硬性条件不满足）")
        unmet_items.append({"text": " — ".join(parts)})

    sections: list[dict[str, Any]] = [{"id": "appendix", "title": "匹配分析附录", "items": []}]
    if satisfied_items:
        sections.append({"id": "appendix-satisfied", "title": "已满足", "items": satisfied_items})
    if unmet_items:
        sections.append({"id": "appendix-unmet", "title": "未满足", "items": unmet_items})
    return sections


def _appendix_body_sections(draft: dict[str, Any], body_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return body sections with the match-analysis appendix appended."""
    return body_sections + _build_appendix_sections(draft)


def export_docx(draft: dict[str, Any], include_appendix: bool = False) -> bytes:
    """Render the resume draft as a real Word document via python-docx.

    The applicant's name + contact line lead the document (resume header), then
    each section renders as a heading with bulleted items.  When
    *include_appendix* is True a match-analysis appendix (✅已满足/⚠️未满足
    with evidence and suggestions) replaces the plain gaps paragraph.
    """
    document = Document()
    _apply_cjk_default_font(document)
    identity, body_sections = _split_identity(draft)
    if include_appendix:
        body_sections = _appendix_body_sections(draft, body_sections)

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


def export_pdf(draft: dict[str, Any], include_appendix: bool = False) -> bytes:
    """Export resume draft to PDF with CJK support using fpdf2.

    When *include_appendix* is True a match-analysis appendix is appended
    after the body sections, mirroring the DOCX diagnostic output.
    """
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
    if include_appendix:
        body_sections = _appendix_body_sections(draft, body_sections)

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
