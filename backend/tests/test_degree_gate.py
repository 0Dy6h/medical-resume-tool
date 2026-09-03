"""Degree gate: ordinal degree-level matching that similarity scoring can't do."""

import pytest

from app.services.matching.gates import (
    evaluate_degree_gate,
    hard_degree_floor,
    highest_profile_degree,
    is_degree_requirement,
    required_degree_level,
)


@pytest.mark.parametrize(
    "requirement,expected",
    [
        ("具有硕士（含）以上学历，本科为全日制本科", 3),
        ("硕士研究生及以上学历", 3),
        ("本科及以上学历", 2),
        ("具有博士研究生学历", 4),
        ("大专及以上学历", 1),
        ("护理学专业本科及以上学历", 2),
    ],
)
def test_required_level_prefers_the_or_above_floor(requirement, expected):
    assert required_degree_level(requirement) == expected


def test_non_degree_requirement_is_not_a_gate():
    assert not is_degree_requirement("具备良好的沟通协调能力")
    assert evaluate_degree_gate("具备良好的沟通协调能力", [{"id": "e", "degree": "本科"}]) is None


def test_highest_degree_reads_the_degree_field():
    edu = [{"id": "e1", "degree": "本科"}, {"id": "e2", "degree": "硕士"}]
    assert highest_profile_degree(edu) == (3, "e2")


def test_highest_degree_falls_back_to_major_text():
    """"临床医学博士" in the major still counts as a doctorate."""
    edu = [{"id": "e1", "degree": "", "major": "临床医学博士"}]
    assert highest_profile_degree(edu) == (4, "e1")


def test_met_when_candidate_meets_the_floor():
    gate = evaluate_degree_gate("具有硕士（含）以上学历", [{"id": "e", "degree": "硕士"}])
    assert gate.outcome == "met"
    assert gate.profile_field_id == "e"


def test_higher_degree_still_meets_a_lower_floor():
    gate = evaluate_degree_gate("大专及以上学历", [{"id": "e", "degree": "本科"}])
    assert gate.outcome == "met"


def test_not_met_when_candidate_is_below_the_floor():
    """The exact case fuzzy scoring cannot reject: 本科 vs a 硕士 requirement
    whose text also mentions 本科."""
    gate = evaluate_degree_gate("具有硕士（含）以上学历，本科为全日制本科", [{"id": "e", "degree": "本科"}])
    assert gate.outcome == "not_met"
    assert "硕士" in gate.message
    assert "本科" in gate.message


def test_unknown_when_profile_has_no_education():
    gate = evaluate_degree_gate("具有硕士以上学历", [])
    assert gate.outcome == "unknown"
    assert gate.profile_field_id is None


def test_gate_result_surfaces_in_resume_matching():
    """A not-met degree requirement becomes a blocking gap, not silent output."""
    from app.schemas import Profile
    from app.services.resume import match_profile_to_job

    profile = Profile.from_legacy_dict({"education": [{"id": "ed1", "school": "某大学", "degree": "本科", "major": "护理学"}]})
    job = {"institution_name": "某院", "title": "研究员", "raw_text": "招聘条件：1、具有博士研究生学历；2、身体健康。"}
    evidence, gaps = match_profile_to_job(profile, job)
    blocking = [gap for gap in gaps if gap.get("blocking")]
    assert blocking, gaps
    assert any("博士" in gap["message"] for gap in blocking)


def test_met_degree_requirement_becomes_traceable_evidence():
    from app.schemas import Profile
    from app.services.resume import match_profile_to_job

    profile = Profile.from_legacy_dict({"education": [{"id": "ed1", "school": "某大学", "degree": "硕士", "major": "流行病学"}]})
    job = {"institution_name": "某院", "title": "助理", "raw_text": "招聘条件：1、具有硕士及以上学历；2、身体健康。"}
    evidence, _gaps = match_profile_to_job(profile, job)
    degree_evidence = [item for item in evidence if item.get("gate") == "degree"]
    assert degree_evidence
    assert degree_evidence[0]["profile_field_id"] == "ed1"


# ── 复合条款中的硬学历底线（博士后岗"……博士，具备……能力"类）───────────


POSTDOC_CLAUSE = "基础医学、生物学或药学博士，具备英文论文写作能力和独立科研能力"


def test_compound_clause_with_hard_floor_blocks_below_floor():
    """条款超长且无"以上/学历"标记时 is_degree_requirement 为 False，但其中的
    博士仍是硬性底线：低于该底线的档案必须收到阻断性 gap，而不是普通缺口。"""
    gate = evaluate_degree_gate(POSTDOC_CLAUSE, [{"id": "e", "degree": "硕士"}])
    assert gate is not None
    assert gate.outcome == "not_met"

    from app.schemas import Profile
    from app.services.resume import match_profile_to_job, summarize_match

    profile = Profile.from_legacy_dict({"education": [{"id": "ed1", "school": "某大学", "degree": "硕士", "major": "公共卫生"}]})
    job = {"institution_name": "某所", "title": "基础医学博士后", "raw_text": f"任职要求：{POSTDOC_CLAUSE}。"}
    _evidence, gaps = match_profile_to_job(profile, job)
    summary = summarize_match(_evidence, gaps)
    assert summary["blocking_gap"] is True


def test_compound_clause_met_floor_stays_with_fuzzy_matching():
    """达到复合条款底线时门槛返回 None：其余方面（论文、能力）仍由模糊匹配
    产生证据，门槛不得抢走整条条款。"""
    gate = evaluate_degree_gate(POSTDOC_CLAUSE, [{"id": "e", "degree": "博士"}])
    assert gate is None


def test_priority_and_institutional_mentions_are_not_floors():
    """「博士优先」是择优不是门槛；「博士点」是机构平台不是学历要求。"""
    edu = [{"id": "e", "degree": "本科"}]
    assert evaluate_degree_gate("具有博士学位者优先，发表过SCI论文", edu) is None
    assert evaluate_degree_gate("参与博士点建设申报工作", edu) is None
    assert hard_degree_floor("博士优先") is None
    assert hard_degree_floor(POSTDOC_CLAUSE) == 4


def test_compound_floor_without_education_stays_unjudged():
    """复合条款 + 档案无学历信息：不阻断（不确定的事交给用户确认）。"""
    assert evaluate_degree_gate(POSTDOC_CLAUSE, []) is None
