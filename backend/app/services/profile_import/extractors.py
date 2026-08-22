"""Rule-based fact extraction from profile import blocks."""
from __future__ import annotations

import re
from typing import Any

from app.services.profile_import.facts import DocumentBlock, ExtractedFact
from app.services.profile_import.legacy import (
    _AWARD_LEVEL,
    _DEGREE,
    _LANGUAGE_LEVEL,
    _LANGUAGE_NAME,
    _ORG_SUFFIXES,
    _PROJECT_NAME_HINTS,
    _ROLE_SUFFIXES,
    _SCHOOL_SUFFIXES,
    SECTION_ALIASES,
    _build_award,
    _build_certificate,
    _build_education,
    _build_experience,
    _build_language,
    _build_project,
    _build_publication,
    _build_teaching,
    _tokens,
)
from app.services.profile_import.normalization import normalize_time_range
from app.services.profile_import.scoring import score


COLLECTIONS = {
    "education",
    "experiences",
    "projects",
    "publications",
    "certificates",
    "skills",
    "teaching",
    "awards",
    "languages",
}

PRIMARY_PRIORITY: tuple[str, ...] = (
    "experiences",
    "education",
    "projects",
    "publications",
    "teaching",
    "awards",
    "certificates",
    "languages",
)

SKILL_TERMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SPSS", re.compile(r"SPSS", re.I)),
    ("R语言", re.compile(r"R语言|\bR\b")),
    ("Python", re.compile(r"Python", re.I)),
    ("SAS", re.compile(r"SAS", re.I)),
    ("数据清洗", re.compile(r"数据清洗")),
    ("数据管理", re.compile(r"数据管理")),
    ("统计分析", re.compile(r"统计分析|统计")),
    ("临床研究", re.compile(r"临床研究")),
    ("GCP", re.compile(r"GCP", re.I)),
    ("PCR", re.compile(r"PCR", re.I)),
    ("随访", re.compile(r"随访")),
    ("伦理", re.compile(r"伦理")),
)

_CERTIFICATE_HINT = re.compile(r"执业医师|护士资格证|护士资格|GCP证书|GCP|规范化培训|计算机二级|证书")
_PROJECT_HINT = re.compile(r"项目|课题|队列|平台|基金")
_PUBLICATION_HINT = re.compile(r"论文|发表|期刊|doi|DOI|《[^》]+》")
_TEACHING_HINT = re.compile(r"教学|授课|带教|助教|课程")
_CLAUSE_SPLIT = re.compile(r"[，,；;、]\s*")
_SKILL_PREFIX = re.compile(r"^(熟悉|掌握|了解|使用|运用)\s*", re.I)

_PHONE_RE = re.compile(r"1[3-9]\d{9}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_NAME_LABEL_RE = re.compile(r"(?:姓名|名字|称谓)[:：]\s*(\S{2,4})")
_PURE_CJK_RE = re.compile(r"^[\u4e00-\u9fff]{2,4}$")

_SECTION_HEADING_TEXTS: set[str] = set()
for _aliases in SECTION_ALIASES.values():
    _SECTION_HEADING_TEXTS.update(_aliases)

_PRIORITY_INDEX = {collection: i for i, collection in enumerate(PRIMARY_PRIORITY)}


def extract_facts(blocks: list[DocumentBlock]) -> list[ExtractedFact]:
    """Extract profile facts from blocks using collection-specific signals."""
    facts: list[ExtractedFact] = []
    for block in blocks:
        facts.extend(_facts_for_block(block))
    return facts


def extract_skills(text: str) -> list[str]:
    """Extract canonical skill names from free text."""
    skills: list[str] = []
    for name, pattern in SKILL_TERMS:
        if pattern.search(text) and name not in skills:
            skills.append(name)
    return skills


def build_basics(blocks: list[DocumentBlock]) -> tuple[dict[str, str], set[str]]:
    """Extract basic info (name/phone/email) from blocks.

    Returns (basics_dict, consumed_source_texts). Consumed texts should be
    excluded from unassigned_blocks to avoid phone/email/name lines polluting it.
    Never fabricates — fields without a signal are left absent.
    """
    basics: dict[str, str] = {}
    consumed: set[str] = set()

    for index, block in enumerate(blocks):
        text = block.text

        phone_match = _PHONE_RE.search(text)
        if phone_match:
            basics["phone"] = phone_match.group(0)
            consumed.add(text)

        email_match = _EMAIL_RE.search(text)
        if email_match:
            basics["email"] = email_match.group(0)
            consumed.add(text)

        if "name" not in basics:
            for line in block.lines:
                line_text = line.text
                if not line_text:
                    continue
                name_match = _NAME_LABEL_RE.search(line_text)
                if name_match:
                    basics["name"] = name_match.group(1).strip()
                    consumed.add(text)
                    break
                if index < 3 and _is_likely_name(line_text):
                    basics["name"] = line_text.strip()
                    consumed.add(text)
                    break

    return basics, consumed


def _is_likely_name(text: str) -> bool:
    stripped = text.strip()
    if not _PURE_CJK_RE.match(stripped):
        return False
    if stripped in _SECTION_HEADING_TEXTS:
        return False
    for suffix_list in (_ORG_SUFFIXES, _ROLE_SUFFIXES, _SCHOOL_SUFFIXES):
        if any(suffix in stripped for suffix in suffix_list):
            return False
    if _DEGREE.search(stripped):
        return False
    return True


def _facts_for_block(block: DocumentBlock) -> list[ExtractedFact]:
    text = block.text
    lines = [line.text for line in block.lines if line.text]

    candidates: list[ExtractedFact] = []
    if _is_education(text, block):
        candidates.append(_education_fact(block, lines))
    if _is_experience(text, block):
        candidates.append(_experience_fact(block, lines))
    if _is_project(text, block):
        candidates.append(_project_fact(block, lines))
    if _is_publication(text, block):
        candidates.append(_simple_fact("publications", _build_publication(text), block, strong=True))
    if _is_teaching(text, block):
        candidates.append(_simple_fact("teaching", _build_teaching(text), block, strong=True))
    if _is_award(text, block):
        candidates.append(_simple_fact("awards", _build_award(text), block, strong=True))
    if _is_certificate(text, block):
        candidates.append(_certificate_fact(block))
    if _is_language(text, block):
        candidates.append(_language_fact(block))

    primary = _best_primary(candidates)

    facts: list[ExtractedFact] = []
    if primary is not None:
        facts.append(primary)

    skills = extract_skills(text)
    if skills and (block.section_hint == "skills" or _is_skill_line(text) or facts):
        for skill in skills:
            facts.append(_skill_fact(skill, block, strong=block.section_hint == "skills" or _is_skill_line(text) or bool(facts)))

    return facts


def _best_primary(candidates: list[ExtractedFact]) -> ExtractedFact | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    best = candidates[0]
    for candidate in candidates[1:]:
        if candidate.confidence > best.confidence:
            best = candidate
        elif candidate.confidence == best.confidence:
            if _PRIORITY_INDEX.get(candidate.collection, 999) < _PRIORITY_INDEX.get(best.collection, 999):
                best = candidate
    return best


def _is_education(text: str, block: DocumentBlock) -> bool:
    return block.section_hint == "education" or (
        _has_any(text, _SCHOOL_SUFFIXES) and bool(_DEGREE.search(text))
    )


def _is_experience(text: str, block: DocumentBlock) -> bool:
    if block.section_hint == "experiences":
        return True
    return _has_any(text, _ORG_SUFFIXES) and _has_any(text, _ROLE_SUFFIXES)


def _is_project(text: str, block: DocumentBlock) -> bool:
    return block.section_hint == "projects" or bool(_PROJECT_HINT.search(text))


def _is_publication(text: str, block: DocumentBlock) -> bool:
    return block.section_hint == "publications" or bool(_PUBLICATION_HINT.search(text))


def _is_teaching(text: str, block: DocumentBlock) -> bool:
    return block.section_hint == "teaching" or bool(_TEACHING_HINT.search(text))


def _is_award(text: str, block: DocumentBlock) -> bool:
    return block.section_hint == "awards" or bool(_AWARD_LEVEL.search(text) or re.search(r"获奖|奖学金|荣誉", text))


def _is_certificate(text: str, block: DocumentBlock) -> bool:
    return block.section_hint == "certificates" or bool(_CERTIFICATE_HINT.search(text))


def _is_language(text: str, block: DocumentBlock) -> bool:
    return block.section_hint == "languages" or bool(_LANGUAGE_NAME.search(text) and _LANGUAGE_LEVEL.search(text))


def _is_skill_line(text: str) -> bool:
    return bool(re.search(r"熟悉|掌握|技能|使用|运用", text)) and bool(extract_skills(text))


def _education_fact(block: DocumentBlock, lines: list[str]) -> ExtractedFact:
    fields = _build_education(lines)
    fields["highlights"] = _split_highlights(fields.get("highlights", []))
    return _scored_fact(
        "education",
        _trim_empty_lists(fields),
        block,
        core_entity=bool(fields.get("school")),
        role_or_degree=bool(fields.get("degree")),
        highlight=bool(fields.get("highlights")),
    )


def _experience_fact(block: DocumentBlock, lines: list[str]) -> ExtractedFact:
    fields = _build_experience(lines)
    fields["highlights"] = _split_highlights(fields.get("highlights", []))
    skills = extract_skills(block.text)
    if skills:
        fields["skills"] = skills
    return _scored_fact(
        "experiences",
        _trim_empty_lists(fields),
        block,
        core_entity=bool(fields.get("organization")),
        role_or_degree=bool(fields.get("role")),
        highlight=bool(fields.get("highlights")),
        strong_match=bool(fields.get("organization") and fields.get("role")),
    )


def _project_fact(block: DocumentBlock, lines: list[str]) -> ExtractedFact:
    fields = _build_project(lines)
    inline_highlights = _project_inline_highlights(lines[0], fields)
    fields["highlights"] = _split_highlights([*fields.get("highlights", []), *inline_highlights])
    skills = extract_skills(block.text)
    if skills:
        fields["skills"] = skills
    return _scored_fact(
        "projects",
        _trim_empty_lists(fields),
        block,
        core_entity=bool(fields.get("name")),
        role_or_degree=bool(fields.get("role")),
        highlight=bool(fields.get("highlights")),
        strong_match=True,
    )


def _certificate_fact(block: DocumentBlock) -> ExtractedFact:
    fields = _build_certificate(_certificate_source_text(block.text))
    if re.search(r"GCP", block.text, re.I):
        fields["name"] = "GCP证书"
    return _scored_fact(
        "certificates",
        fields,
        block,
        core_entity=bool(fields.get("name")),
        role_or_degree=True,
        strong_match=True,
    )


def _language_fact(block: DocumentBlock) -> ExtractedFact:
    fields = _build_language(block.text)
    return _scored_fact(
        "languages",
        fields,
        block,
        core_entity=bool(fields.get("name")),
        role_or_degree=bool(fields.get("level")),
        strong_match=True,
    )


def _skill_fact(name: str, block: DocumentBlock, *, strong: bool) -> ExtractedFact:
    return _scored_fact(
        "skills",
        {"name": name},
        block,
        core_entity=True,
        role_or_degree=strong,
        strong_match=strong,
    )


def _simple_fact(collection: str, fields: dict[str, Any], block: DocumentBlock, *, strong: bool = False) -> ExtractedFact:
    return _scored_fact(
        collection,
        fields,
        block,
        core_entity=bool(fields),
        role_or_degree=strong,
        strong_match=strong,
    )


def _scored_fact(
    collection: str,
    fields: dict[str, Any],
    block: DocumentBlock,
    *,
    core_entity: bool,
    role_or_degree: bool,
    highlight: bool = False,
    strong_match: bool = False,
) -> ExtractedFact:
    fact = ExtractedFact(
        collection=collection,
        fields=fields,
        source_text=block.text,
        confidence=0.0,
        reasons=_reasons(
            section_hint=block.section_hint == collection,
            time_range=_has_time_range(block.text),
            core_entity=core_entity,
            role_or_degree=role_or_degree,
            highlight=highlight,
            strong_match=strong_match,
        ),
    )
    fact.confidence = score(
        fact,
        {
            "section_hint": block.section_hint == collection,
            "time_range": _has_time_range(block.text),
            "core_entity": core_entity,
            "role_or_degree": role_or_degree,
            "highlight": highlight,
            "strong_match": strong_match,
            "many_missing_fields": _many_missing_fields(collection, fields),
        },
    )
    return fact


def _reasons(**signals: bool) -> list[str]:
    labels = {
        "section_hint": "命中板块提示",
        "time_range": "命中时间范围",
        "core_entity": "命中核心实体",
        "role_or_degree": "命中角色/学历/证书等级",
        "highlight": "包含成果描述",
        "strong_match": "命中强规则",
    }
    return [labels[key] for key, enabled in signals.items() if enabled]


def _has_time_range(text: str) -> bool:
    start, end, _ = normalize_time_range(text)
    return bool(start and end)


def _has_any(text: str, hints: list[str]) -> bool:
    return any(hint in text for hint in hints)


def _split_highlights(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    highlights: list[str] = []
    for item in items:
        for part in _CLAUSE_SPLIT.split(str(item)):
            cleaned = part.strip()
            if cleaned and cleaned not in highlights:
                highlights.append(cleaned)
    return highlights


def _project_inline_highlights(head: str, fields: dict[str, Any]) -> list[str]:
    ignored = {fields.get("name", ""), fields.get("role", "")}
    highlights: list[str] = []
    for token in _tokens(head):
        if token in ignored:
            continue
        if any(token.startswith(prefix) for prefix in ("完成", "输出", "建立", "负责", "参与", "维护")):
            highlights.append(token)
    return highlights


def _certificate_source_text(text: str) -> str:
    if re.search(r"GCP", text, re.I):
        return "GCP证书"
    return text


def _many_missing_fields(collection: str, fields: dict[str, Any]) -> bool:
    required = {
        "education": ("school", "degree"),
        "experiences": ("organization", "role"),
        "projects": ("name",),
        "certificates": ("name",),
        "languages": ("name", "level"),
        "skills": ("name",),
    }
    keys = required.get(collection)
    if not keys:
        return False
    return sum(1 for key in keys if fields.get(key)) < max(1, len(keys) - 1)


def _trim_empty_lists(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value != [] and value != ""}
