from __future__ import annotations

from collections import defaultdict
from typing import Any

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


def flatten_profile_facts(profile: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    for collection in PROFILE_COLLECTIONS:
        for index, item in enumerate(profile.get(collection, []) or []):
            field_id = item.get("id") or f"{collection}-{index + 1}"
            text_parts = []
            for value in item.values():
                if isinstance(value, list):
                    text_parts.extend(str(v) for v in value)
                elif isinstance(value, dict):
                    text_parts.extend(str(v) for v in value.values())
                elif value is not None:
                    text_parts.append(str(value))
            facts.append({"profile_field_id": field_id, "collection": collection, "text": normalize_text(" ".join(text_parts)), "raw": item})
    return facts


def _tokens(text: str) -> set[str]:
    normalized = normalize_text(text).lower()
    tokens = set()
    for piece in normalized.replace("、", " ").replace("，", " ").replace(",", " ").split():
        if len(piece) >= 2:
            tokens.add(piece)
    for keyword in ["临床研究", "数据分析", "SPSS", "Python", "护理", "科研", "教学", "随访", "伦理", "质控", "英语", "检验", "药学", "公共卫生"]:
        if keyword.lower() in normalized:
            tokens.add(keyword.lower())
    return tokens


def match_profile_to_job(profile: dict[str, Any], job: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
                    }
                )
                used_pairs.add(pair)
        else:
            gaps.append({"requirement": requirement, "message": f"未在你的履历中找到对应证据：{requirement}"})
    return evidence, gaps


def build_resume_sections(profile: dict[str, Any], job: dict[str, Any], evidence: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_by_collection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        evidence_by_collection[item["collection"]].append(item)

    sections: list[dict[str, Any]] = [
        {
            "id": "target",
            "title": "求职目标",
            "items": [{"text": f"应聘 {job['institution_name']} - {job['title']}，突出与岗位要求直接相关的真实经历。"}],
        },
    ]
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
        for index, raw_item in enumerate(profile.get(collection, []) or []):
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


def generate_resume_draft(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    evidence, gaps = match_profile_to_job(profile, job)
    sections = build_resume_sections(profile, job, evidence, gaps)
    title = f"{job['title']} 定制简历"
    return {"title": title, "sections": sections, "evidence": evidence, "gaps": gaps}
