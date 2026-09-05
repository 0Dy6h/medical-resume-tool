from __future__ import annotations

import io
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from fpdf import FPDF
from fpdf.enums import XPos, YPos

logger = logging.getLogger(__name__)

# ─── Font candidates ──────────────────────────────────────────────────

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

CJK_BOLD_FONT_CANDIDATES = [
    Path(value)
    for value in (
        os.getenv("PDF_FONT_BOLD_PATH"),
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    )
    if value
]

# ─── Shared layout model (Task A) ────────────────────────────────────


@dataclass
class Entry:
    head: str | None
    role: str | None
    period: str | None
    details: list[str]
    raw: str


@dataclass
class SectionBlock:
    title: str
    section_id: str
    entries: list[Entry]


@dataclass
class Header:
    name: str
    contact_lines: list[str]
    summary_lines: list[str]


@dataclass
class ResumeDoc:
    header: Header
    blocks: list[SectionBlock]


# ─── Entry parsing (lossless contract) ────────────────────────────────

_DATE_RANGE_RE = re.compile(r"^\d{4}([-./]\d{1,2})?(-\d{4}([-./]\d{1,2})?)?$")
_CONTACT_LABELS = ("电话：", "邮箱：", "所在地：", "求职意向：")


def _is_date_range(s: str) -> bool:
    return bool(_DATE_RANGE_RE.match(s.strip()))


def _is_contact_line(text: str) -> bool:
    return " ｜ " in text or any(text.startswith(label) for label in _CONTACT_LABELS)


def _strip_all(s: str) -> str:
    s = re.sub(r"\s+", "", s)
    for ch in ("/", "：", "；", "·", "—", "–"):
        s = s.replace(ch, "")
    return s


def _parse_entry(text: str) -> Entry:
    """Parse a resume item line into structured Entry.

    Format: ``head1 / head2 / ... / period：detail1；detail2``
    - head segments joined with ``" / "``
    - last segment matching a date regex is the period
    - details after the first ``：``, split by ``；``
    - no head or no colon → prose fallback or details-only
    """
    raw = text
    text = text.strip()
    if not text:
        return Entry(head="", role=None, period=None, details=[], raw=raw)

    colon_idx = text.find("：")

    if colon_idx == -1:
        head_part = text
        if " / " in head_part:
            segments = [s.strip() for s in head_part.split(" / ")]
            period = None
            if segments and _is_date_range(segments[-1]):
                period = segments.pop()
            head = segments[0] if segments else None
            role = " · ".join(segments[1:]) if len(segments) > 1 else None
            return Entry(head=head, role=role, period=period, details=[], raw=raw)
        if "；" in head_part:
            details = [d.strip() for d in head_part.split("；") if d.strip()]
            return Entry(head=None, role=None, period=None, details=details, raw=raw)
        return Entry(head=head_part, role=None, period=None, details=[], raw=raw)

    head_part = text[:colon_idx].strip()
    detail_part = text[colon_idx + 1:].strip()
    details = (
        [d.strip() for d in detail_part.split("；") if d.strip()]
        if detail_part
        else []
    )

    if not head_part:
        return Entry(head=None, role=None, period=None, details=details, raw=raw)

    segments = [s.strip() for s in head_part.split(" / ")]
    period = None
    if segments and _is_date_range(segments[-1]):
        period = segments.pop()

    head = segments[0] if segments else None
    role = " · ".join(segments[1:]) if len(segments) > 1 else None
    return Entry(head=head, role=role, period=period, details=details, raw=raw)


def assert_lossless(raw: str, entry: Entry) -> None:
    """Assert that all entry fragments reproduce the raw text when concatenated.

    Separators and whitespace are stripped from both sides before comparison.
    """
    fragments: list[str] = []
    if entry.head:
        fragments.append(entry.head)
    if entry.role:
        fragments.append(entry.role)
    if entry.period:
        fragments.append(entry.period)
    fragments.extend(entry.details)
    rendered = _strip_all("".join(fragments))
    original = _strip_all(raw)
    if rendered != original:
        raise AssertionError(
            f"Lossless violation: rendered={rendered!r} != original={original!r}"
        )


def _format_period(period: str) -> str:
    """Beautify a date period for display (separator replacement only)."""
    parts = period.replace("/", "-").replace(".", "-").split("-")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]} – {parts[2]}.{parts[3]}"
    if len(parts) == 2:
        if len(parts[1]) <= 2:
            return f"{parts[0]}.{parts[1]}"
        return f"{parts[0]} – {parts[1]}"
    return period


# ─── B1: Bold decision + B3: PDF text normalization ─────────────────

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U00002600-\U000026FF"  # misc symbols (including 🏥 U+1F3E5)
    "\U00002700-\U000027BF"  # dingbats
    "]", flags=re.UNICODE)


def _should_bold_main_line(entry: Entry, section_id: str) -> bool:
    """B1: entry main line is bold unless target section or long no-period prose."""
    main_text = entry.head or ""
    if entry.role:
        main_text = f"{main_text} · {entry.role}" if main_text else entry.role
    return not (
        section_id == "target"
        or (not entry.period and len(main_text) > 24)
    )


def _normalize_pdf_text(text: str) -> str:
    """B3: remove invisible characters and normalize whitespace for PDF rendering.

    Only processes invisible/whitespace characters — visible text is unchanged.
    """
    text = text.replace("\u200B", "").replace("\uFEFF", "").replace("\u00AD", "")
    text = text.replace("\t", " ")
    text = text.replace("\u00A0", " ").replace("\u3000", " ")
    if _EMOJI_RE.search(text):
        logger.warning(
            "Text contains emoji characters that may be missing from the PDF font: %s",
            text[:60],
        )
    return text


# ─── Resume doc builder ───────────────────────────────────────────────


def _build_header(identity: dict[str, Any] | None, draft: dict[str, Any]) -> Header:
    if not identity:
        return Header(name=draft.get("title", ""), contact_lines=[], summary_lines=[])

    items = identity.get("items", [])
    texts = [str(item.get("text", "")).strip() for item in items if str(item.get("text", "")).strip()]
    if not texts:
        return Header(name=draft.get("title", ""), contact_lines=[], summary_lines=[])

    name = texts[0]
    contact_lines: list[str] = []
    summary_lines: list[str] = []
    for text in texts[1:]:
        if _is_contact_line(text):
            contact_lines.append(text)
        else:
            summary_lines.append(text)

    return Header(
        name=name or draft.get("title", ""),
        contact_lines=contact_lines,
        summary_lines=summary_lines,
    )


def _build_resume_doc(draft: dict[str, Any], include_appendix: bool = False) -> ResumeDoc:
    identity, body_sections = _split_identity(draft)
    if include_appendix:
        body_sections = _appendix_body_sections(draft, body_sections)

    header = _build_header(identity, draft)

    blocks: list[SectionBlock] = []
    for section in body_sections:
        section_id = str(section.get("id", ""))
        is_appendix = section_id.startswith("appendix")
        entries: list[Entry] = []
        for item in section.get("items", []):
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            if is_appendix:
                entries.append(Entry(head=None, role=None, period=None, details=[text], raw=text))
            else:
                entry = _parse_entry(text)
                try:
                    assert_lossless(text, entry)
                except AssertionError:
                    logger.warning(
                        "Lossless violation, falling back to raw line: %s", text
                    )
                    entry = Entry(
                        head=None, role=None, period=None,
                        details=[text], raw=text,
                    )
                entries.append(entry)
        blocks.append(SectionBlock(
            title=str(section.get("title", "")),
            section_id=section_id,
            entries=entries,
        ))

    return ResumeDoc(header=header, blocks=blocks)


# ─── Existing helpers (unchanged) ─────────────────────────────────────


def resume_to_plain_text(draft: dict[str, Any]) -> str:
    lines = [draft["title"], ""]
    for section in draft["sections"]:
        lines.append(section["title"])
        for item in section.get("items", []):
            lines.append(f"- {item.get('text', '')}")
        lines.append("")
    return "\n".join(lines)


def _split_identity(draft: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    sections = draft.get("sections", [])
    identity = next((section for section in sections if section.get("id") == "identity"), None)
    body = [section for section in sections if section.get("id") != "identity"]
    return identity, body


def _identity_lines(identity: dict[str, Any]) -> tuple[str, list[str]]:
    texts = [str(item.get("text", "")).strip() for item in (identity.get("items") or [])]
    texts = [text for text in texts if text]
    if not texts:
        return "", []
    return texts[0], texts[1:]


_SKIP_SECTION_IDS = {
    "identity",
    "target",
    "gaps",
    "appendix",
    "appendix-satisfied",
    "appendix-unmet",
    "appendix-unlinked",
}
_SKIP_SECTION_TITLE = "投递前需补充确认"


def collect_unlinked_items(
    draft: dict[str, Any],
    valid_field_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """收集「未绑定档案证据」的草稿条目。

    ``valid_field_ids`` 是当前档案全部合法证据引用（条目自带 id 或位置 id，
    口径同 ``resume.flatten_profile_facts``）。传入时，引用必须真实存在于
    当前档案才算已关联——伪造/失效的 ``profile_field_id`` 不能伪装成有证据；
    不传（None）保持旧口径：非空即已关联。
    """
    unlinked: list[dict[str, Any]] = []
    for section in draft.get("sections", []):
        if section.get("id") in _SKIP_SECTION_IDS:
            continue
        if str(section.get("title", "")).strip() == _SKIP_SECTION_TITLE:
            continue
        for item in section.get("items", []):
            if item.get("decision") == "remove":
                continue
            ref = str(item.get("profile_field_id") or "").strip()
            if ref and (valid_field_ids is None or ref in valid_field_ids):
                continue
            unlinked.append({"text": item.get("text", "")})
    return unlinked


def _build_appendix_sections(draft: dict[str, Any]) -> list[dict[str, Any]]:
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

    unlinked_items = collect_unlinked_items(draft)
    if unlinked_items:
        sections.append({"id": "appendix-unlinked", "title": "用户手动添加，无档案证据", "items": unlinked_items})

    return sections


def _appendix_body_sections(draft: dict[str, Any], body_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return body_sections + _build_appendix_sections(draft)


# ─── Filename helpers (Task C) ────────────────────────────────────────


def build_export_filename(draft: dict[str, Any], ext: str, mode: str = "application") -> str:
    """Build a human-readable export filename.

    Pattern: ``{姓名}-{岗位}-简历-{YYYYMMDD}.{ext}``  (diagnostic adds ``-诊断版``).
    Falls back to ``resume-{draft_id}.{ext}`` when name or job title is missing.
    """
    name = ""
    for section in draft.get("sections", []):
        if section.get("id") == "identity":
            items = section.get("items", [])
            if items:
                name = str(items[0].get("text", "")).strip()
            break

    title = str(draft.get("title", ""))
    job_title = title.replace(" 定制简历", "").strip() if " 定制简历" in title else ""

    today = datetime.now().strftime("%Y%m%d")

    if name and job_title:
        filename = f"{name}-{job_title}-简历-{today}"
    else:
        filename = f"resume-{draft.get('id', 'unknown')}"

    if mode == "diagnostic":
        filename += "-诊断版"

    return f"{filename}.{ext}"


def content_disposition_header(filename: str) -> str:
    """Build a Content-Disposition header with RFC 5987 ``filename*``."""
    ascii_name = filename.encode("ascii", "replace").decode("ascii")
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


# ─── DOCX rendering (Task B) ──────────────────────────────────────────

_FONT_NAME = "Microsoft YaHei"
_MUTED_COLOR = RGBColor(0x66, 0x71, 0x6D)
_BORDER_COLOR = "AAAAAA"


def _set_style_font(style: Any, font_name: str) -> None:
    """Set ascii / hAnsi / eastAsia on a style's rFonts."""
    style.font.name = font_name
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:ascii"), font_name)
    rfonts.set(qn("w:hAnsi"), font_name)
    rfonts.set(qn("w:eastAsia"), font_name)


def _setup_docx_styles(document: Document) -> None:
    _set_style_font(document.styles["Normal"], _FONT_NAME)
    document.styles["Normal"].font.size = Pt(10)

    for name in ("Heading 1", "Heading 2", "Heading 3", "Heading 4"):
        try:
            style = document.styles[name]
            _set_style_font(style, _FONT_NAME)
            style.font.color.rgb = RGBColor(0, 0, 0)
        except KeyError:
            pass

    for style_name, size in (("ResumeEntry", Pt(10.5)), ("ResumeDetail", Pt(10))):
        try:
            style = document.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
        except ValueError:
            style = document.styles[style_name]
        _set_style_font(style, _FONT_NAME)
        style.font.size = size


def _add_paragraph_bottom_border(paragraph: Any, sz: int = 6, color: str = _BORDER_COLOR) -> None:
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(sz))
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_field(paragraph: Any, field_code: str) -> None:
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {field_code} "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def _add_docx_footer(document: Document) -> None:
    section = document.sections[0]
    footer = section.footer
    footer.is_linked_to_previous = False
    paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run("第 ")
    _add_field(paragraph, "PAGE")
    paragraph.add_run(" 页 / 共 ")
    _add_field(paragraph, "NUMPAGES")
    paragraph.add_run(" 页")


def _render_docx_entry(document: Document, entry: Entry, section_id: str = "") -> None:
    has_main = bool(entry.head or entry.role or entry.period)
    if has_main:
        main = document.add_paragraph(style="ResumeEntry")
        main.paragraph_format.tab_stops.add_tab_stop(Mm(166), WD_TAB_ALIGNMENT.RIGHT)
        main.paragraph_format.space_after = Pt(2)

        should_bold = _should_bold_main_line(entry, section_id)

        if entry.head:
            head_run = main.add_run(entry.head)
            head_run.bold = should_bold

        if entry.role:
            sep = " · " if entry.head else ""
            role_run = main.add_run(f"{sep}{entry.role}")
            role_run.bold = should_bold

        if entry.period:
            main.add_run("\t")
            period_run = main.add_run(_format_period(entry.period))
            period_run.font.size = Pt(9.5)
            period_run.bold = should_bold

    for detail in entry.details:
        d = document.add_paragraph(style="ResumeDetail")
        d.paragraph_format.left_indent = Mm(4)
        d.paragraph_format.first_line_indent = Mm(-4)
        d.paragraph_format.line_spacing = 1.35
        d.paragraph_format.space_after = Pt(2)
        d.add_run(f"– {detail}")


def export_docx(draft: dict[str, Any], include_appendix: bool = False) -> bytes:
    document = Document()
    _setup_docx_styles(document)

    section = document.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(20)
    section.bottom_margin = Mm(20)
    section.left_margin = Mm(22)
    section.right_margin = Mm(22)

    _add_docx_footer(document)

    doc = _build_resume_doc(draft, include_appendix=include_appendix)
    header = doc.header

    name_para = document.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_para.paragraph_format.space_after = Pt(4)
    name_run = name_para.add_run(header.name)
    name_run.bold = True
    name_run.font.size = Pt(20)

    for line in header.contact_lines:
        contact_para = document.add_paragraph()
        contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_run = contact_para.add_run(line)
        contact_run.font.size = Pt(9.5)
        contact_run.font.color.rgb = _MUTED_COLOR

    for idx, line in enumerate(header.summary_lines):
        summary_para = document.add_paragraph()
        summary_para.paragraph_format.line_spacing = 1.4
        if idx == 0:
            summary_para.paragraph_format.space_before = Pt(6)
        summary_run = summary_para.add_run(line)
        summary_run.font.size = Pt(10)

    for block in doc.blocks:
        title_para = document.add_paragraph(style="Heading 1")
        title_para.paragraph_format.space_before = Pt(10)
        title_para.paragraph_format.space_after = Pt(4)
        title_para.paragraph_format.keep_with_next = True
        title_para.paragraph_format.keep_together = True
        _add_paragraph_bottom_border(title_para)
        title_run = title_para.add_run(block.title)
        title_run.bold = True
        title_run.font.size = Pt(12)

        for entry in block.entries:
            _render_docx_entry(document, entry, block.section_id)

    core_props = document.core_properties
    core_props.title = f"{header.name} 简历"
    core_props.author = header.name or draft.get("title", "")

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# ─── PDF rendering (Task B) ──────────────────────────────────────────


class ResumePDF(FPDF):
    def footer(self) -> None:
        if not self.font_family:
            return
        self.set_y(-15)
        self.set_font("cjk", size=8)
        self.cell(0, 10, f"第 {self.page_no()} 页 / 共 {{nb}} 页", align="C")


def _find_cjk_font() -> Path | None:
    for path in CJK_FONT_CANDIDATES:
        if path.exists():
            return path
    return None


def _find_cjk_bold_font() -> Path | None:
    for path in CJK_BOLD_FONT_CANDIDATES:
        if path.exists():
            return path
    return None


def _render_pdf_entry(pdf: FPDF, entry: Entry, section_id: str = "") -> None:
    has_main = bool(entry.head or entry.role or entry.period)

    if has_main:
        should_bold = _should_bold_main_line(entry, section_id)
        main_style = "B" if should_bold else ""
        pdf.set_font("cjk", style=main_style, size=10.5)
        head_text = _normalize_pdf_text(entry.head or "")
        if entry.role:
            role_text = _normalize_pdf_text(entry.role)
            head_text = f"{head_text} · {role_text}" if head_text else role_text

        if entry.period:
            period_text = _format_period(entry.period)
            pdf.set_font("cjk", size=9.5)
            period_w = pdf.get_string_width(period_text)
            pdf.set_font("cjk", style=main_style, size=10.5)
            head_w = pdf.get_string_width(head_text)
            avail = pdf.epw - period_w - 2

            if head_w > avail:
                pdf.multi_cell(pdf.epw, 5.5, head_text, align="L",
                               new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font("cjk", size=9.5)
                pdf.cell(pdf.epw, 5, period_text, align="R",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                pdf.set_font("cjk", style=main_style, size=10.5)
                pdf.cell(head_w, 5.5, head_text, new_x=XPos.RIGHT, new_y=YPos.TOP)
                pdf.set_font("cjk", size=9.5)
                pdf.cell(pdf.epw - head_w, 5.5, period_text, align="R",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.multi_cell(pdf.epw, 5.5, head_text, align="L",
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("cjk", size=10)
    for detail in entry.details:
        detail_text = _normalize_pdf_text(detail)
        bullet = "– "
        bullet_w = pdf.get_string_width(bullet)
        indent = max(bullet_w + 1, 4)

        pdf.set_x(pdf.l_margin)
        pdf.cell(indent, 5.6, bullet, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.multi_cell(pdf.epw - indent, 5.6, detail_text, align="L",
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(2)


def export_pdf(draft: dict[str, Any], include_appendix: bool = False) -> bytes:
    pdf = ResumePDF()
    pdf.set_margins(22, 20)
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()

    font_path = _find_cjk_font()
    if font_path is None:
        searched = ", ".join(str(p) for p in CJK_FONT_CANDIDATES)
        raise RuntimeError(
            "No CJK-capable PDF font found. Install fonts-noto-cjk or set PDF_FONT_PATH "
            f"to a Unicode font file. Searched: {searched}"
        )
    pdf.add_font("cjk", style="", fname=str(font_path))

    bold_path = _find_cjk_bold_font()
    if bold_path:
        pdf.add_font("cjk", style="B", fname=str(bold_path))
    else:
        pdf.add_font("cjk", style="B", fname=str(font_path))
        logger.warning("No bold CJK font found, using regular as fallback")

    pdf.set_font("cjk", size=12)
    pdf.alias_nb_pages()

    doc = _build_resume_doc(draft, include_appendix=include_appendix)
    header = doc.header

    # ── Header (D1 fix: reset cursor with new_x=XPos.LMARGIN) ──
    pdf.set_font("cjk", style="B", size=20)
    pdf.multi_cell(pdf.epw, 8, _normalize_pdf_text(header.name), align="C",
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    pdf.set_font("cjk", size=9.5)
    for line in header.contact_lines:
        pdf.multi_cell(pdf.epw, 5, _normalize_pdf_text(line), align="C",
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if header.summary_lines:
        pdf.ln(3)
        pdf.set_font("cjk", size=10)
        for line in header.summary_lines:
            pdf.multi_cell(pdf.epw, 5.6, _normalize_pdf_text(line), align="L",
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    # ── Sections ──
    for block in doc.blocks:
        # Keep-with-next: estimate title + first entry height
        title_h = 7 + 2 + 2  # cell height + line gap + after
        first_entry_h = 5.5 + 2 + 5.6 + 2  # main + after + detail + after
        needed = title_h + first_entry_h
        if pdf.get_y() + needed > pdf.h - pdf.b_margin:
            pdf.add_page()

        # Section title (D6 fix: bottom border line)
        pdf.set_font("cjk", style="B", size=12)
        pdf.multi_cell(pdf.epw, 7, _normalize_pdf_text(block.title), align="L",
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        line_y = pdf.get_y()
        pdf.line(pdf.l_margin, line_y, pdf.w - pdf.r_margin, line_y)
        pdf.ln(2)

        for entry in block.entries:
            _render_pdf_entry(pdf, entry, block.section_id)

    return bytes(pdf.output())
