# 结构化按格式提取，预留给未来升级，当前线上管线走 lines+blocks。
"""增强的文档提取：DOCX、PDF、Markdown、文本。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document

from app.services.classifier import normalize_text
from app.services.profile_import.facts import DocumentBlock, DocumentLine


@dataclass
class ExtractedDocument:
    """提取后的文档结构。"""
    blocks: list[DocumentBlock] = field(default_factory=list)
    lines: list[DocumentLine] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    text_quality: float = 0.8


def extract_docx_document(content: bytes) -> ExtractedDocument:
    """增强的 DOCX 提取：段落、表格、标题样式。"""
    try:
        document = Document(BytesIO(content))
    except Exception as exc:
        raise ValueError("无法读取该 docx 文件，请确认文件未损坏") from exc

    lines: list[DocumentLine] = []
    blocks: list[DocumentBlock] = []
    line_index = 0

    for paragraph in document.paragraphs:
        text = normalize_text(paragraph.text)
        if not text:
            continue

        # 检查是否为标题样式
        is_heading = paragraph.style.name.startswith("Heading")
        kind = "heading" if is_heading else "paragraph"

        doc_line = DocumentLine(text=text, line_index=line_index, source_kind="paragraph")
        lines.append(doc_line)
        blocks.append(DocumentBlock(text=text, lines=[doc_line], kind=kind))
        line_index += 1

    # 表格处理
    for table in document.tables:
        for row in table.rows:
            cells = [normalize_text(cell.text) for cell in row.cells]
            unique = [cell for cell in dict.fromkeys(cells) if cell]
            if unique:
                text = "；".join(unique)
                doc_line = DocumentLine(text=text, line_index=line_index, source_kind="table")
                lines.append(doc_line)
                blocks.append(DocumentBlock(text=text, lines=[doc_line], kind="table_row"))
                line_index += 1

    return ExtractedDocument(blocks=blocks, lines=lines, text_quality=0.9)


def extract_markdown_document(content: bytes) -> ExtractedDocument:
    """Markdown 提取：识别标题、列表、表格。"""
    text = content.decode("utf-8-sig", errors="replace")
    lines_raw = text.splitlines()

    lines: list[DocumentLine] = []
    blocks: list[DocumentBlock] = []

    for line_index, raw in enumerate(lines_raw):
        text = normalize_text(raw)
        if not text:
            continue

        # Markdown 标题
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", raw.strip())
        if heading_match:
            heading_text = normalize_text(heading_match.group(2))
            doc_line = DocumentLine(text=heading_text, line_index=line_index, source_kind="markdown")
            lines.append(doc_line)
            blocks.append(DocumentBlock(text=heading_text, lines=[doc_line], kind="heading"))
            continue

        # Markdown bullet
        if re.match(r"^[\s]*[-*+]\s+", raw):
            cleaned = re.sub(r"^[\s]*[-*+]\s+", "", raw).strip()
            doc_line = DocumentLine(text=cleaned, line_index=line_index, source_kind="markdown")
            lines.append(doc_line)
            blocks.append(DocumentBlock(text=cleaned, lines=[doc_line], kind="bullet"))
            continue

        # 普通文本
        doc_line = DocumentLine(text=text, line_index=line_index, source_kind="markdown")
        lines.append(doc_line)
        blocks.append(DocumentBlock(text=text, lines=[doc_line], kind="paragraph"))

    return ExtractedDocument(blocks=blocks, lines=lines, text_quality=0.85)


def extract_pdf_document(content: bytes) -> ExtractedDocument:
    """增强的 PDF 提取：使用 blocks 而非纯文本，支持简单的多栏检测。"""
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("PDF 导入需要安装 PyMuPDF") from exc

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise ValueError("无法读取该 PDF 文件，请确认文件未损坏") from exc

    lines: list[DocumentLine] = []
    blocks: list[DocumentBlock] = []
    warnings: list[str] = []
    line_index = 0

    try:
        page_count = min(document.page_count, 20)
        for page_num in range(page_count):
            page = document.load_page(page_num)
            page_blocks = page.get_text("blocks")

            # 按 y 坐标排序
            sorted_blocks = sorted(page_blocks, key=lambda b: (b[1], b[0]))

            for block in sorted_blocks:
                text = normalize_text(block[4])
                if not text or len(text) < 2:
                    continue

                doc_line = DocumentLine(text=text, page=page_num, line_index=line_index, source_kind="pdf_block")
                lines.append(doc_line)
                blocks.append(DocumentBlock(text=text, lines=[doc_line], kind="pdf_block"))
                line_index += 1

        quality = 0.8 if lines else 0.0
        if not lines:
            warnings.append("PDF 中未提取到文本，可能是扫描件")

    finally:
        document.close()

    return ExtractedDocument(blocks=blocks, lines=lines, warnings=warnings, text_quality=quality)
