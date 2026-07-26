import pytest

from app.schemas import Profile
from app.services.resume import (
    _format_profile_item,
    _identity_section,
    flatten_profile_facts,
    generate_resume_draft,
    match_profile_to_job,
)


def profile_of(**data) -> Profile:
    """Build a typed Profile from the loose dict shape used in these tests."""
    return Profile.from_legacy_dict(data)


def test_identity_section_built_from_filled_basics():
    profile = profile_of(
        basics={
            "name": "林晓",
            "phone": "13800000000",
            "email": "lin@example.com",
            "intended_position": "临床研究助理",
        }
    )
    section = _identity_section(profile)
    assert section is not None
    assert section["id"] == "identity"
    assert section["items"][0]["text"] == "林晓"
    contact = section["items"][1]["text"]
    assert "13800000000" in contact
    assert "lin@example.com" in contact
    assert "临床研究助理" in contact


def test_identity_section_absent_without_basics():
    assert _identity_section(profile_of(basics={})) is None
    assert _identity_section(profile_of()) is None


def test_generate_resume_draft_leads_with_identity_when_basics_present():
    profile = profile_of(basics={"name": "林晓"}, skills=[{"id": "s1", "name": "SPSS"}])
    job = {"institution_name": "某医院", "title": "数据岗", "raw_text": "要求：熟悉统计分析。"}
    draft = generate_resume_draft(profile, job)
    assert draft["sections"][0]["id"] == "identity"


def test_generate_resume_draft_keeps_target_first_without_basics():
    profile = profile_of(skills=[{"id": "s1", "name": "SPSS"}])
    job = {"institution_name": "某医院", "title": "数据岗", "raw_text": "要求：熟悉统计分析。"}
    draft = generate_resume_draft(profile, job)
    assert draft["sections"][0]["id"] == "target"


def test_semantic_match_bridges_spss_skill_to_a_statistics_requirement():
    """A JD asking for 统计/数据处理 should match a real SPSS/统计分析 skill.

    This is the semantic bridge the concept lexicon exists for: the requirement
    and the fact share no wording beyond 数据, yet both map to the 统计分析
    concept.  The skill is written as an applicant actually would (naming the
    tool and what it was used for), which is what makes it a confident match
    rather than a terse keyword.
    """
    profile = profile_of(skills=[{"id": "s1", "name": "熟练使用 SPSS、SAS 进行统计分析与数据处理"}])
    job = {
        "institution_name": "某医院",
        "title": "研究助理",
        "raw_text": "岗位要求：具备统计学基础与数据处理能力。",
    }
    evidence, _gaps = match_profile_to_job(profile, job)
    assert evidence
    assert evidence[0]["profile_field_id"] == "s1"
    assert "统计分析" in evidence[0]["matched_terms"]


def test_a_terse_off_wording_skill_stays_a_gap_not_a_false_match():
    """Conservative by design: a bare skill that only bridges by concept — and is
    lexically the same shape as a false near-match — is reported as a gap."""
    profile = profile_of(experiences=[{"id": "ex1", "organization": "省人民医院临床研究中心", "role": "研究助理"}])
    job = {"institution_name": "某医院", "title": "护理岗", "raw_text": "岗位要求：具有三年以上临床护理工作经验。"}
    evidence, gaps = match_profile_to_job(profile, job)
    # 临床研究 ≠ 临床护理 — must not be asserted as evidence.
    assert not any(item["profile_field_id"] == "ex1" for item in evidence)
    assert gaps


# ── the exported document must not lose the user's real facts ────────


def full_profile() -> Profile:
    return profile_of(
        basics={"name": "林晓"},
        education=[{"id": "ed1", "school": "某医科大学", "degree": "硕士", "major": "流行病与卫生统计学", "start": "2018", "end": "2021"}],
        experiences=[{"id": "ex1", "organization": "省人民医院", "role": "研究助理", "highlights": ["负责糖尿病队列基线调查与随访"]}],
        publications=[{"id": "pub1", "title": "胃癌预后模型研究", "journal": "中华肿瘤杂志", "year": "2025"}],
        certificates=[{"id": "c1", "name": "执业医师资格证", "year": "2023"}],
        teaching=[{"id": "t1", "course": "医学统计学", "role": "助教", "institution": "某医科大学", "year": "2022"}],
        skills=[{"id": "s1", "name": "熟练使用 SPSS 进行数据分析"}],
    )


NO_MATCH_JOB = {"institution_name": "某医院", "title": "研究岗", "raw_text": "岗位要求：本科及以上学历，具备良好沟通能力。"}
ONE_MATCH_JOB = {"institution_name": "某医院", "title": "研究岗", "raw_text": "岗位要求：熟悉SPSS等统计软件，具备数据分析能力。"}


def section_ids(draft: dict) -> list[str]:
    return [section["id"] for section in draft["sections"] if section["id"] != "gaps"]


def test_a_single_match_does_not_delete_the_other_sections():
    """Regression: matching one requirement erased most of the resume.

    `build_resume_sections` dropped every unmatched item as soon as any
    evidence existed, so one incidental keyword hit removed work history,
    publications, certificates and teaching from the exported DOCX/PDF — and
    the application-mode export then strips the gaps section, leaving no trace.
    """
    profile = full_profile()
    unmatched = generate_resume_draft(profile, NO_MATCH_JOB)
    matched = generate_resume_draft(profile, ONE_MATCH_JOB)

    assert matched["evidence"], "expected the SPSS requirement to match"
    assert not unmatched["evidence"]
    assert section_ids(matched) == section_ids(unmatched)
    for collection in ("experiences", "publications", "certificates", "teaching"):
        assert collection in section_ids(matched)


def test_every_profile_item_reaches_the_draft():
    draft = generate_resume_draft(full_profile(), ONE_MATCH_JOB)
    rendered = {
        item["profile_field_id"]
        for section in draft["sections"]
        for item in section["items"]
        if "profile_field_id" in item
    }
    assert {"ed1", "ex1", "pub1", "c1", "t1", "s1"} <= rendered


def test_matched_items_are_ordered_before_supporting_ones():
    draft = generate_resume_draft(full_profile(), ONE_MATCH_JOB)
    skills = next(section for section in draft["sections"] if section["id"] == "skills")
    levels = [item["evidence_level"] for item in skills["items"]]
    assert levels == sorted(levels, key=lambda level: level != "matched")


# ── item rendering keeps the content, not just the year ──────────────


@pytest.mark.parametrize(
    "collection,item,expected",
    [
        ("publications", {"title": "胃癌预后模型研究", "journal": "中华肿瘤杂志", "year": "2025"}, "胃癌预后模型研究 / 中华肿瘤杂志 / 2025"),
        ("teaching", {"course": "医学统计学", "role": "助教", "institution": "某医科大学", "year": "2022"}, "医学统计学 / 助教 / 某医科大学 / 2022"),
        ("certificates", {"name": "执业医师资格证", "year": "2023"}, "执业医师资格证 / 2023"),
        ("education", {"school": "某医科大学", "degree": "硕士", "major": "流行病学", "start": "2018", "end": "2021"}, "某医科大学 / 硕士 / 流行病学 / 2018-2021"),
        ("awards", {"name": "优秀论文奖", "issuer": "省医学会", "level": "省级", "year": "2024"}, "优秀论文奖 / 省医学会 / 省级 / 2024"),
    ],
)
def test_item_rendering_keeps_the_defining_field(collection, item, expected):
    """Regression: a publication rendered as its year alone ('2025')."""
    assert _format_profile_item(collection, item) == expected


def test_experience_highlights_follow_the_header():
    text = _format_profile_item(
        "experiences",
        {"organization": "省人民医院", "role": "研究助理", "highlights": ["负责队列基线调查", "完成课题申报书"]},
    )
    assert text == "省人民医院 / 研究助理：负责队列基线调查；完成课题申报书"


def test_internal_ids_are_never_reported_as_evidence():
    """A truthfulness product must not cite its own field handle as a match."""
    profile = profile_of(skills=[{"id": "skills-1", "name": "沟通"}])
    job = {"institution_name": "某医院", "title": "岗位", "raw_text": "要求 skills-1 具备能力。"}
    evidence, _gaps = match_profile_to_job(profile, job)
    assert evidence == []


def test_doi_and_bare_years_stay_out_of_the_searchable_text():
    profile = profile_of(publications=[{"id": "pub-1", "title": "队列研究", "authors": "张三", "year": "2025", "doi": "10.1/x"}])
    text = flatten_profile_facts(profile)[0]["text"]
    assert "10.1/x" not in text
    assert "pub-1" not in text
    assert "队列研究" in text
