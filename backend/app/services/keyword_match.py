"""订阅关键词匹配语义（B2 关键词边界）。

- 中文等非 ASCII 关键词：按子串匹配（中文无词边界概念）。
- 纯 ASCII（英文/数字）关键词：按词边界匹配，大小写不敏感——
  「ICU」不得命中「RICU」/「讨论DICUSSion」这类嵌在更长英文词里的片段，
  但命中「ICU 护士」「icu护理」。
"""
from __future__ import annotations

import re

_ASCII_WORD = re.compile(r"[A-Za-z0-9]+")


def keyword_matches(text: str, keyword: str) -> bool:
    """按关键词类型返回是否命中。空关键词永远不命中。"""
    kw = keyword.strip()
    if not kw:
        return False
    if kw.isascii():
        pattern = r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])"
        return re.search(pattern, text, re.IGNORECASE) is not None
    return kw in text


def refine_keyword_hits(rows: list[dict], keyword: str) -> list[dict]:
    """对 SQL LIKE 的粗筛结果做边界精筛（仅在 keyword 为纯 ASCII 时可能缩小集合）。"""
    kw = keyword.strip()
    if not kw or not kw.isascii():
        return rows
    return [row for row in rows if keyword_matches(_searchable_text(row), kw)]


def _searchable_text(row: dict) -> str:
    return " ".join(
        part
        for part in (row.get("title"), row.get("institution_name"), row.get("raw_text"))
        if part
    )
