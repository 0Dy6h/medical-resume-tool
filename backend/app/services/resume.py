from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.schemas import (
    BasicInfo,
    Certificate,
    Education,
    Experience,
    Language,
    Profile,
    Project,
    Publication,
    Skill,
    Teaching,
    Award,
)
from app.services.classifier import extract_requirements, normalize_text

PROFILE_COLLECTIONS = [
    "education",
    "experiences",
    "projects",
    "publications",
    "certificates",
    "skills",
    "teaching",
    "awards",
    "languages",
]

COLLECTION_TITLES = {
    "education": "教育经历",
    "experiences": "工作/实习经历",
    "projects": "科研/项目经历",
    "publications": "发表论文",
    "certificates": "证书资质",
    "skills": "技能能力",
    "teaching": "教学经历",
    "awards": "获奖荣誉",
    "languages": "语言能力",
}


def _profile_collection_items(profile: Profile, collection: str) -> list[dict[str, Any]]:
    """Return a collection's items as plain dicts for downstream processing."""
    items = getattr(profile, collection)
    return [item.model_dump() if hasattr(item, "model_dump") else item for item in items]


def flatten_profile_facts(profile: Profile) -> list[dict[str, Any]]:
    facts = []
    for collection in PROFILE_COLLECTIONS:
        for index, item in enumerate(_profile_collection_items(profile, collection)):
            field_id = item.get("id") or f"{collection}-{index + 1}"
            text_parts = []
            for value in item.values():
                if isinstance(value, list):
                    text_parts.extend(str(v) for v in value)
                elif isinstance(value, dict):
                    text_parts.extend(str(v) for v in value.values())
                elif value is not None:
                    text_parts.append(str(value))
            facts.append(
                {
                    "profile_field_id": field_id,
                    "collection": collection,
                    "text": normalize_text(" ".join(text_parts)),
                    "raw": item,
                    "source_label": _source_label(collection, item, index),
                }
            )
    return facts


def _source_label(collection: str, item: dict[str, Any], index: int) -> str:
    title = COLLECTION_TITLES.get(collection, collection)
    for key in ["organization", "school", "name", "title", "course", "role"]:
        value = item.get(key)
        if value:
            return f"{title}：{value}"
    return f"{title} #{index + 1}"


# 医疗领域同义/近义词归并：requirement 与 fact 用不同措辞表达同一能力时也能命中。
# 仅做加法（命中任一变体则补一个规范 token），不删除原有 token，避免回归。
SYNONYM_GROUPS = {
    "数据统计": ["统计", "spss", "sas", "stata", "r语言", "数据分析", "数据处理", "统计分析"],
    "临床研究": ["临床研究", "临床试验", "gcp", "队列", "随访"],
    "科研产出": ["科研", "课题", "基金", "论文", "发表", "sci"],
    "护理": ["护理", "护士", "护师"],
    "教学": ["教学", "带教", "授课", "讲师", "助教"],
    "公共卫生": ["公共卫生", "流行病", "疾控", "预防医学"],
    "英语能力": ["英语", "英文", "cet", "六级", "四级", "雅思", "托福"],
    "药学": ["药学", "药师", "药物", "制剂"],
}


def _tokens(text: str) -> set[str]:
    normalized = normalize_text(text).lower()
    tokens = set()
    for piece in normalized.replace("、", " ").replace("，", " ").replace(",", " ").split():
        if len(piece) >= 2:
            tokens.add(piece)
    for keyword in ["临床研究", "数据分析", "SPSS", "Python", "护理", "科研", "教学", "随访", "伦理", "质控", "英语", "检验", "药学", "公共卫生"]:
        if keyword.lower() in normalized:
            tokens.add(keyword.lower())
    for canonical, variants in SYNONYM_GROUPS.items():
        if any(variant in normalized for variant in variants):
            tokens.add(canonical)
    return tokens


def match_profile_to_job(profile: Profile, job: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match profile facts against job requirements and return (evidence, gaps)."""
    facts = flatten_profile_facts(profile)
    requirements = extract_requirements(job.get("raw_text") or f"{job.get('requirements', '')} {job.get('responsibilities', '')}")
    evidence = []
    gaps = []
    used_pairs = set()
    for requirement in requirements:
        req_tokens = _tokens(requirement)
        matches = []
        for fact in facts:
            fact_tokens = _tokens(fact["text"])
            overlap = req_tokens & fact_tokens
            if overlap:
                matches.append((len(overlap), fact, sorted(overlap)))
        if matches:
            matches.sort(key=lambda item: item[0], reverse=True)
            _, fact, overlap = matches[0]
            pair = (requirement, fact["profile_field_id"])
            if pair not in used_pairs:
                evidence.append(
                    {
                        "requirement": requirement,
                        "profile_field_id": fact["profile_field_id"],
                        "collection": fact["collection"],
                        "matched_terms": overlap,
                        "source_text": fact["text"],
                        "source_label": fact["source_label"],
                        "evidence_strength": _evidence_strength(len(overlap), len(req_tokens)),
                    }
                )
                used_pairs.add(pair)
        else:
            gaps.append({"requirement": requirement, "message": f"未在你的履历中找到对应证据：{requirement}"})
    return evidence, gaps


def _evidence_strength(overlap_count: int, requirement_token_count: int) -> str:
    if overlap_count >= 3 or (requirement_token_count and overlap_count / requirement_token_count >= 0.5):
        return "strong"
    if overlap_count >= 2:
        return "partial"
    return "weak"


CONTACT_FIELDS = [
    ("phone", "电话"),
    ("email", "邮箱"),
    ("location", "所在地"),
    ("intended_position", "求职意向"),
]


def _identity_section(profile: Profile) -> dict[str, Any] | None:
    """Build a resume header from user-provided personal facts.

    Only includes fields the user actually filled in — same truth constraint as
    the rest of the generator. Returns None when no identity info exists so older
    profiles fall back to the previous (title-only) layout.
    """
    basics = profile.basics
    name = basics.name.strip()
    contact_bits = []
    for key, label in CONTACT_FIELDS:
        value = str(getattr(basics, key, "") or "").strip()
        if value:
            contact_bits.append(f"{label}：{value}")
    if not name and not contact_bits:
        return None
    items: list[dict[str, Any]] = [{"text": name or "（未填写姓名）"}]
    if contact_bits:
        items.append({"text": " ｜ ".join(contact_bits)})
    summary = basics.summary.strip()
    if summary:
        items.append({"text": summary})
    return {"id": "identity", "title": "个人信息", "items": items}


def build_resume_sections(
    profile: Profile, job: dict[str, Any], evidence: list[dict[str, Any]], gaps: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build resume sections from matched evidence and profile collections."""
    evidence_by_collection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        evidence_by_collection[item["collection"]].append(item)

    sections: list[dict[str, Any]] = []
    identity = _identity_section(profile)
    if identity:
        sections.append(identity)
    sections.append(
        {
            "id": "target",
            "title": "求职目标",
            "items": [{"text": f"应聘 {job['institution_name']} - {job['title']}，突出与岗位要求直接相关的真实经历。"}],
        }
    )
    for collection, title in [
        ("education", "教育背景"),
        ("experiences", "工作/实习经历"),
        ("projects", "科研/项目经历"),
        ("publications", "论文成果"),
        ("certificates", "证书资质"),
        ("skills", "技能能力"),
        ("teaching", "教学经历"),
        ("awards", "获奖经历"),
        ("languages", "语言能力"),
    ]:
        items = []
        matched_ids = {item["profile_field_id"] for item in evidence_by_collection.get(collection, [])}
        for index, raw_item in enumerate(_profile_collection_items(profile, collection)):
            field_id = raw_item.get("id") or f"{collection}-{index + 1}"
            if evidence and field_id not in matched_ids and collection not in {"education", "skills", "languages"}:
                continue
            text = _format_profile_item(raw_item)
            if text:
                items.append({"text": text, "profile_field_id": field_id, "evidence_level": "matched" if field_id in matched_ids else "supporting"})
        if items:
            sections.append({"id": collection, "title": title, "items": items})
    if gaps:
        sections.append(
            {
                "id": "gaps",
                "title": "投递前需补充确认",
                "items": [{"text": gap["message"]} for gap in gaps[:5]],
            }
        )
    return sections


def _format_profile_item(item: dict[str, Any]) -> str:
    preferred = [
        "school",
        "degree",
        "major",
        "organization",
        "role",
        "name",
        "issuer",
        "year",
        "level",
    ]
    head = " / ".join(str(item[key]) for key in preferred if item.get(key))
    highlights = item.get("highlights") or item.get("skills") or []
    if isinstance(highlights, list) and highlights:
        return f"{head}：{'；'.join(str(value) for value in highlights)}" if head else "；".join(str(value) for value in highlights)
    return head or normalize_text(" ".join(str(value) for value in item.values() if not isinstance(value, (list, dict))))


def generate_resume_draft(profile: Profile, job: dict[str, Any]) -> dict[str, Any]:
    """Generate a tailored resume draft from a typed Profile and a job dict."""
    evidence, gaps = match_profile_to_job(profile, job)
    sections = build_resume_sections(profile, job, evidence, gaps)
    title = f"{job['title']} 定制简历"
    return {"title": title, "sections": sections, "evidence": evidence, "gaps": gaps}
