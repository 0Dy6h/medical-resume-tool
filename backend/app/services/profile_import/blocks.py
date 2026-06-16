"""Line-to-block construction for profile fact extraction."""
from __future__ import annotations

import re

from app.services.classifier import normalize_text
from app.services.profile_import.facts import DocumentBlock, DocumentLine
from app.services.profile_import.legacy import SECTION_ALIASES
from app.services.profile_import.normalization import (
    merge_bullets_with_parent,
    normalize_heading,
    normalize_time_range,
)


_ALIAS_TO_COLLECTION = {
    alias: collection for collection, aliases in SECTION_ALIASES.items() for alias in aliases
}
_YEAR_START = re.compile(r"^(?:19|20)\d{2}(?:[年./-]\d{1,2})?")
_PROJECT_HINT = re.compile(r"项目|课题|队列|平台|基金")
_CERTIFICATE_HINT = re.compile(r"证书|执业医师|护士资格|GCP|规范化培训|计算机二级")
_LANGUAGE_HINT = re.compile(r"英语|日语|法语|德语|俄语|韩语|西班牙语|CET-?[46]|四级|六级|雅思|托福|N[1-5]", re.I)
_SKILL_LINE_HINT = re.compile(r"^(熟悉|掌握|了解|专业技能|技能)|技能[:：]", re.I)
_PUBLICATION_HINT = re.compile(r"论文|期刊|发表|doi", re.I)
_AWARD_HINT = re.compile(r"获奖|奖学金|荣誉|优秀|一等奖|二等奖|三等奖")
_TEACHING_HINT = re.compile(r"教学|授课|带教|助教|课程")


def build_blocks(lines: list[str]) -> list[DocumentBlock]:
    """Build semantic blocks from normalized text lines.

    Headings provide section hints for later blocks, but they do not gate
    recognition. Date-led lines and strong standalone fact lines begin blocks;
    bullet children are merged into their parent item.
    """
    blocks: list[DocumentBlock] = []
    current_lines: list[DocumentLine] = []
    current_hint: str | None = None

    def flush() -> None:
        nonlocal current_lines
        if not current_lines:
            return
        text = "\n".join(line.text for line in current_lines if line.text)
        if text:
            blocks.append(
                DocumentBlock(
                    text=text,
                    lines=current_lines,
                    kind=_block_kind(current_lines),
                    section_hint=current_hint,
                )
            )
        current_lines = []

    for group_index, group in enumerate(merge_bullets_with_parent(lines)):
        cleaned_group = [normalize_text(item) for item in group if normalize_text(item)]
        if not cleaned_group:
            continue

        if len(cleaned_group) == 1:
            section = _heading_collection(cleaned_group[0])
            if section:
                flush()
                current_hint = section
                continue

        head = cleaned_group[0]
        if current_lines and _starts_new_block(head, current_lines, current_hint):
            flush()
        current_lines.extend(
            DocumentLine(text=text, line_index=group_index, source_kind="text")
            for text in cleaned_group
        )

    flush()
    return blocks


def _heading_collection(text: str) -> str | None:
    heading = normalize_heading(text)
    if not heading:
        return None
    return _ALIAS_TO_COLLECTION.get(heading)


def _starts_new_block(text: str, current_lines: list[DocumentLine], section_hint: str | None) -> bool:
    if _is_year_start(text):
        return True
    if section_hint in {"skills", "publications", "certificates", "languages", "awards", "teaching"}:
        return True
    if _looks_like_standalone_fact(text):
        return True
    return False


def _is_year_start(text: str) -> bool:
    if _YEAR_START.match(text):
        return True
    start, end, _ = normalize_time_range(text)
    return bool(start and end and text.startswith(start[:4]))


def _looks_like_standalone_fact(text: str) -> bool:
    if _PROJECT_HINT.search(text):
        return True
    if _CERTIFICATE_HINT.search(text) or _LANGUAGE_HINT.search(text):
        return True
    if _SKILL_LINE_HINT.search(text):
        return True
    if _PUBLICATION_HINT.search(text):
        return True
    if _AWARD_HINT.search(text):
        return True
    if _TEACHING_HINT.search(text):
        return True
    return False


def _block_kind(lines: list[DocumentLine]) -> str:
    if len(lines) > 1:
        return "item"
    text = lines[0].text
    if _is_year_start(text):
        return "item"
    if _looks_like_standalone_fact(text):
        return "item"
    return "free_text"
