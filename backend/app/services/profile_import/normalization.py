"""文本归一化：标题识别、时间解析、bullet 处理。"""
from __future__ import annotations

import re
from typing import Any

from app.services.classifier import normalize_text

# 标题识别模式
_HEADING_PATTERNS = [
    re.compile(r"^[一二三四五六七八九十]+[、\.]?\s*(.+)$"),  # 一、教育经历
    re.compile(r"^\d{1,2}[、.\.\)）]\s*(.+)$"),              # 1. 教育经历
    re.compile(r"^【(.+?)】$"),                              # 【教育经历】
    re.compile(r"^#+\s*(.+)$"),                             # # 教育经历 (Markdown)
]

_TIME_PATTERNS = [
    re.compile(r"(\d{4})\s*[-–—~～至到]+\s*(至今|现在|(\d{4}))(?![年月])"),  # 年份格式，排除后面有年月
    re.compile(r"(\d{4})[年./\-](\d{1,2})[月]?\s*[-–—~～至到]+\s*(至今|现在|(\d{4})[年./\-](\d{1,2})[月]?)"),
]


def normalize_time_range(text: str) -> tuple[str, str, str]:
    """提取并归一化时间范围。返回 (start, end, remaining_text)。"""
    for idx, pattern in enumerate(_TIME_PATTERNS):
        match = pattern.search(text)
        if not match:
            continue

        groups = match.groups()

        # 第一个模式：只有年份
        if idx == 0:
            start_year = groups[0]
            end_text = groups[1]

            if end_text in ("至今", "现在"):
                start = start_year
                end = "至今"
            elif len(groups) >= 3 and groups[2]:
                start = start_year
                end = groups[2]
            else:
                start = start_year
                end = end_text

        # 第二个模式：有月份
        elif idx == 1 and len(groups) >= 3:
            start_year, start_month = groups[0], groups[1]
            end_text = groups[2]

            if end_text in ("至今", "现在"):
                start = f"{start_year}.{start_month}"
                end = "至今"
            elif len(groups) >= 5 and groups[3]:
                end_year, end_month = groups[3], groups[4] if groups[4] else ""
                start = f"{start_year}.{start_month}"
                end = f"{end_year}.{end_month}" if end_month else end_year
            else:
                start = f"{start_year}.{start_month}"
                end = end_text
        else:
            continue

        remaining = normalize_text(text[:match.start()] + " " + text[match.end():])
        return start, end, remaining

    return "", "", text


def normalize_heading(line: str) -> str | None:
    """识别并规范化标题，返回标题文本（去除装饰）。"""
    line = line.strip()
    if not line or len(line) > 20:
        return None

    # 直接匹配
    for pattern in _HEADING_PATTERNS:
        match = pattern.match(line)
        if match:
            return normalize_text(match.group(1))

    # 去除常见装饰后检查
    cleaned = re.sub(r"^[\s\d一二三四五六七八九十、.．()（）\[\]【】*#:：\-—]+|[\s:：、.．*#\-—]+$", "", line)
    if 2 <= len(cleaned) <= 12:
        return cleaned

    return None


def strip_bullet(line: str) -> str:
    """去除行首的 bullet 标记。"""
    return re.sub(r"^[•·●◦▪‣*\-–—]+\s*|^\d{1,2}[.、)）]\s*", "", line).strip()


def merge_bullets_with_parent(lines: list[str]) -> list[list[str]]:
    """将连续的 bullet 行与其父条目合并成块。

    示例：
        2023.01-2024.06 上海某三甲医院 科研助理
        - 参与伦理材料整理
        - 维护随访数据库

    返回：[[parent, bullet1, bullet2], ...]
    """
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        text = normalize_text(line)
        if not text:
            if current_block:
                blocks.append(current_block)
                current_block = []
            continue

        # 判断是否为 bullet
        is_bullet = bool(re.match(r"^[•·●◦▪‣*\-–—]", text))

        if is_bullet and current_block:
            current_block.append(strip_bullet(text))
        else:
            if current_block:
                blocks.append(current_block)
            current_block = [text]

    if current_block:
        blocks.append(current_block)

    return blocks
