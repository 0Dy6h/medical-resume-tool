from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from app.schemas import PROFILE_COLLECTION_NAMES, Profile
from app.services.classifier import normalize_text
from app.services.matching.gates import DegreeGateResult, evaluate_degree_gate
from app.services.matching.scorer import best_matches, strength_band
from app.services.matching.segment import is_benefits_clause, is_eligibility_clause, segment_requirements
from app.services.repositories import get_profile

if TYPE_CHECKING:
    from app.services.database import DatabaseEngine

#: Re-exported for callers that already import it from here.
PROFILE_COLLECTIONS = list(PROFILE_COLLECTION_NAMES)

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


#: Fields excluded from a fact's searchable text.  ``id`` is an internal handle
#: and ``doi``/``level`` are identifiers rather than描述性 content — including
#: them lets an internal token be reported to the user as matched "evidence".
FACT_TEXT_EXCLUDED_FIELDS = frozenset({"id", "doi", "level"})


#: A short, always-true descriptor of what each collection's items *are*, added
#: to a fact's searchable text so a requirement can match on the item's nature.
#: A publication's stored fields are just its title and journal, so without this
#: a requirement phrased "发表论文" cannot match a real paper.  This is metadata
#: about the item's type, not invented content.
COLLECTION_FACT_KEYWORDS = {
    "publications": "发表论文 学术论文 科研成果",
    "certificates": "证书 资格",
    "education": "学历 学位 专业",
    "teaching": "教学 授课",
    "awards": "获奖 荣誉",
    "languages": "语言能力",
}


def _fact_text(item: dict[str, Any], collection: str) -> str:
    """Build the searchable text for one profile item.

    Only descriptive fields contribute.  A bare year is dropped too: it carries
    no competency signal and collides across unrelated entries.  A collection
    descriptor is appended so the item can be matched on its type.
    """
    parts: list[str] = []
    for key, value in item.items():
        if key in FACT_TEXT_EXCLUDED_FIELDS:
            continue
        if isinstance(value, list):
            parts.extend(str(entry) for entry in value)
        elif isinstance(value, dict):
            parts.extend(str(entry) for entry in value.values())
        elif value is not None:
            text = str(value)
            if text.strip().isdigit():
                continue
            parts.append(text)
    keyword = COLLECTION_FACT_KEYWORDS.get(collection)
    if keyword:
        parts.append(keyword)
    return normalize_text(" ".join(parts))


def flatten_profile_facts(profile: Profile) -> list[dict[str, Any]]:
    facts = []
    for collection in PROFILE_COLLECTIONS:
        for index, item in enumerate(_profile_collection_items(profile, collection)):
            field_id = item.get("id") or f"{collection}-{index + 1}"
            facts.append(
                {
                    "profile_field_id": field_id,
                    "collection": collection,
                    "text": _fact_text(item, collection),
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


def match_profile_to_job(profile: Profile, job: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match profile facts against job requirements and return (evidence, gaps).

    Requirements are segmented from the announcement (:mod:`matching.segment`).
    A degree requirement is evaluated by the arithmetic degree gate
    (:mod:`matching.gates`); every other requirement is scored against each
    profile fact in a CJK bigram token space weighted by corpus IDF
    (:mod:`matching.scorer`).  A requirement with no supporting fact becomes a
    gap.  Every evidence row carries the ``profile_field_id`` it came from, so
    the generated resume stays traceable to the user's real input.
    """
    facts = flatten_profile_facts(profile)
    education = _profile_collection_items(profile, "education")
    raw_text = job.get("raw_text") or f"{job.get('requirements', '')} {job.get('responsibilities', '')}"
    requirements = segment_requirements(raw_text).requirements

    evidence: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for requirement in requirements:
        # Eligibility clauses (nationality, age, political status, health…)
        # state who may apply at all; the profile has no comparable facts, so
        # they would always render as red "不满足" noise.  They stay visible in
        # the job's raw announcement text and are the applicant's to confirm.
        if is_eligibility_clause(requirement):
            continue
        # Compensation/benefits clauses (岗位待遇…面议) are employer promises,
        # not facts the profile can evidence; counting them inflates
        # "满足 X/Y 项" with permanently unmet rows.
        if is_benefits_clause(requirement):
            continue
        gate = evaluate_degree_gate(requirement, education)
        if gate is not None:
            _apply_degree_gate(requirement, gate, evidence, gaps)
            continue
        matches = best_matches(requirement, facts)
        if not matches:
            gaps.append({"requirement": requirement, "message": f"未在你的履历中找到对应证据：{requirement}"})
            continue
        for match in matches:
            evidence.append(
                {
                    "requirement": requirement,
                    "profile_field_id": match.profile_field_id,
                    "collection": match.collection,
                    "matched_terms": list(match.matched_terms),
                    "source_text": match.source_text,
                    "source_label": match.source_label,
                    "score": match.score,
                    "evidence_strength": strength_band(match.score),
                }
            )
    return evidence, gaps


def _apply_degree_gate(
    requirement: str,
    gate: DegreeGateResult,
    evidence: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> None:
    """Record a degree gate's outcome as evidence or a (possibly blocking) gap."""
    if gate.outcome == "met":
        evidence.append(
            {
                "requirement": requirement,
                "profile_field_id": gate.profile_field_id,
                "collection": "education",
                "matched_terms": ["学历"],
                "source_text": gate.message,
                "source_label": "教育经历",
                "score": 1.0,
                "evidence_strength": "strong",
                "gate": "degree",
            }
        )
    else:
        gaps.append(
            {
                "requirement": requirement,
                "message": gate.message,
                # not_met means categorically ineligible — the UI can flag it.
                "blocking": gate.outcome == "not_met",
            }
        )


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
            text = _format_profile_item(collection, raw_item)
            if text:
                items.append(
                    {
                        "text": text,
                        "profile_field_id": field_id,
                        "evidence_level": "matched" if field_id in matched_ids else "supporting",
                    }
                )
        if items:
            # Requirement-matched entries lead the section; nothing is removed.
            # An unmatched entry means "the JD did not ask for this", not "this
            # is untrue", and dropping it would silently delete real experience
            # from a document the user submits.  `evidence_level` carries the
            # distinction for the UI instead.
            items.sort(key=lambda entry: entry["evidence_level"] != "matched")
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


#: Which fields lead each collection's resume line, in reading order.
#: Per-collection because one shared list cannot serve every shape: a flat
#: ordering silently dropped `title` and `course`, so a publication rendered as
#: nothing but its year.
ITEM_HEAD_FIELDS = {
    "education": ("school", "degree", "major"),
    "experiences": ("organization", "role"),
    "projects": ("name", "role"),
    "publications": ("title", "journal", "year"),
    "certificates": ("name", "issuer", "year"),
    "skills": ("name", "level"),
    "teaching": ("course", "role", "institution", "year"),
    "awards": ("name", "issuer", "level", "year"),
    "languages": ("name", "level"),
}

#: Fields never rendered into a resume line (internal or non-prose).
ITEM_TEXT_EXCLUDED_FIELDS = frozenset({"id", "doi"})


def _date_range(item: dict[str, Any]) -> str:
    start = str(item.get("start") or "").strip()
    end = str(item.get("end") or "").strip()
    if start and end:
        return f"{start}-{end}"
    return start or end


def _format_profile_item(collection: str, item: dict[str, Any]) -> str:
    """Render one profile item as a resume line.

    Only reorders and joins the user's own field values — no wording is
    invented, which is what keeps the output traceable to the profile.
    """
    head_fields = ITEM_HEAD_FIELDS.get(collection, ())
    parts = [str(item[key]).strip() for key in head_fields if str(item.get(key) or "").strip()]
    period = _date_range(item)
    if period:
        parts.append(period)
    head = " / ".join(parts)

    details = item.get("highlights") or item.get("skills") or []
    if isinstance(details, list):
        details = [str(value).strip() for value in details if str(value).strip()]
    else:
        details = []
    if details:
        body = "；".join(details)
        return f"{head}：{body}" if head else body
    if head:
        return head
    # Unknown collection or an item whose head fields are all empty: fall back to
    # its remaining prose so nothing the user typed disappears.
    return normalize_text(
        " ".join(
            str(value)
            for key, value in item.items()
            if key not in ITEM_TEXT_EXCLUDED_FIELDS and not isinstance(value, (list, dict)) and value is not None
        )
    )


def is_total_mismatch(
    evidence: list[dict[str, Any]], gaps: list[dict[str, Any]]
) -> bool:
    """Return True when the job has segmentable requirements but none matched.

    ``gaps`` non-empty means the job has structured, evaluable requirements; when
    ``evidence`` is empty at the same time, the profile missed every one of them.
    Both empty (job with no structured requirements) is not a mismatch — the
    matcher simply had nothing to evaluate.
    """
    return bool(gaps) and not evidence


def generate_resume_draft(profile: Profile, job: dict[str, Any]) -> dict[str, Any]:
    """Generate a tailored resume draft from a typed Profile and a job dict."""
    evidence, gaps = match_profile_to_job(profile, job)
    sections = build_resume_sections(profile, job, evidence, gaps)
    title = f"{job['title']} 定制简历"
    return {"title": title, "sections": sections, "evidence": evidence, "gaps": gaps}


def summarize_match(evidence: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse (evidence, gaps) into a per-job match summary.

    Counts *requirements*, not evidence rows: one requirement that matches
    several facts is still a single met requirement.  ``total`` is the number
    of distinct requirements evaluated; ``met`` is how many were satisfied.
    """
    met_reqs = {e.get("requirement") for e in evidence}
    gap_reqs = {g.get("requirement") for g in gaps}
    met = len(met_reqs)
    total = met + len(gap_reqs)
    degree = round(met / total * 100) if total else 0
    blocking = any(bool(g.get("blocking")) for g in gaps)
    return {"met": met, "total": total, "degree_percent": degree, "blocking_gap": blocking}


def analyze_job_match(profile: Profile, job: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-requirement match breakdown for the job detail page (PRD 4.2).

    Groups the (evidence, gaps) from match_profile_to_job by requirement and
    classifies each into one of four states:
      - "met"      : has evidence, no blocking gap
      - "partial"  : has evidence AND a non-blocking gap (related but incomplete)
      - "blocking" : any gap with blocking=True (e.g. degree categorical mismatch)
      - "unmet"    : only gap(s), no evidence found
    Each item: {requirement, status, evidence: [...], advice: str|None}.
    """
    evidence, gaps = match_profile_to_job(profile, job)
    by_req: dict[str, dict] = {}
    for e in evidence:
        r = e.get("requirement")
        by_req.setdefault(r, {"evidence": [], "gaps": []})
        by_req[r]["evidence"].append(e)
    for g in gaps:
        r = g.get("requirement")
        by_req.setdefault(r, {"evidence": [], "gaps": []})
        by_req[r]["gaps"].append(g)
    out = []
    for req, grp in by_req.items():
        ev, gp = grp["evidence"], grp["gaps"]
        if any(bool(g.get("blocking")) for g in gp):
            status = "blocking"
        elif ev and gp:
            status = "partial"
        elif ev:
            status = "met"
        else:
            status = "unmet"
        advice = next((g.get("message") for g in gp), None)
        out.append({
            "requirement": req,
            "status": status,
            "evidence": [{"source": e.get("source_label"), "text": e.get("source_text")} for e in ev],
            "advice": advice,
        })
    return out


def attach_job_matches(
    engine: "DatabaseEngine", jobs: list[dict[str, Any]], user_id: int | None
) -> list[dict[str, Any]]:
    """Attach a ``match`` summary to each job for the given user.

    Returns jobs unchanged-shaped with an added ``match`` key:
    - when ``user_id`` is None or the user has no profile → ``match=None``
    - otherwise → result of ``summarize_match`` over ``match_profile_to_job``
    """
    if not user_id:
        return [{**job, "match": None} for job in jobs]
    profile = get_profile(engine, user_id)
    if profile.is_empty:
        return [{**job, "match": None} for job in jobs]
    out = []
    for job in jobs:
        evidence, gaps = match_profile_to_job(profile, job)
        out.append({**job, "match": summarize_match(evidence, gaps)})
    return out
