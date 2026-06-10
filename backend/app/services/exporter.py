from __future__ import annotations

import io
import zipfile
from html import escape
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos


def resume_to_plain_text(draft: dict[str, Any]) -> str:
    lines = [draft["title"], ""]
    for section in draft["sections"]:
        lines.append(section["title"])
        for item in section.get("items", []):
            lines.append(f"- {item.get('text', '')}")
        lines.append("")
    return "\n".join(lines)


def export_docx(draft: dict[str, Any]) -> bytes:
    body = "".join(_paragraph(draft["title"], style="Title"))
    for section in draft["sections"]:
        body += "".join(_paragraph(section["title"], style="Heading1"))
        for item in section.get("items", []):
            body += "".join(_paragraph(item.get("text", ""), style="Normal"))
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _paragraph(text: str, style: str = "Normal") -> list[str]:
    escaped = escape(text)
    style_xml = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style != "Normal" else ""
    return [f"<w:p>{style_xml}<w:r><w:t>{escaped}</w:t></w:r></w:p>"]


def export_pdf(draft: dict[str, Any]) -> bytes:
    """Export resume draft to PDF with CJK support using fpdf2."""
    pdf = FPDF()
    pdf.add_page()

    # Use Microsoft YaHei on Windows, fallback to system fonts
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        pdf.add_font("yahei", style="", fname=str(font_path))
        pdf.set_font("yahei", size=12)
    else:
        # Fallback: try using fpdf2's Unicode support with DejaVu
        pdf.set_font("helvetica", size=12)

    # Title
    pdf.set_font_size(16)
    pdf.cell(0, 10, draft["title"], new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(5)

    # Sections
    for section in draft["sections"]:
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
