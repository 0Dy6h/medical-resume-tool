"""P0-1 资格条款不进入匹配缺口：国籍/年龄/身体条件类条款与履历可比要求分离。"""
from __future__ import annotations

from app.schemas import Profile
from app.services.matching.segment import is_eligibility_clause, segment_requirements
from app.services.resume import match_profile_to_job, summarize_match


def _profile() -> Profile:
    return Profile.from_legacy_dict(
        {
            "basics": {"name": "测试", "phone": "13800000000"},
            "education": [
                {"school": "某医科大学", "degree": "硕士", "major": "公共卫生", "start": "2021-09", "end": "2024-06"}
            ],
            "experiences": [
                {"organization": "某疾控中心", "role": "实习生", "start": "2023-03", "end": "2023-09",
                 "highlights": ["参与传染病监测数据分析"]}
            ],
        }
    )


# ── is_eligibility_clause 谓词 ──────────────────────────────────────


def test_nationality_and_law_clauses_are_eligibility():
    assert is_eligibility_clause("具有中华人民共和国国籍，遵守中华人民共和国宪法和法律")
    assert is_eligibility_clause("年龄不超过38周岁（1988年1月1日之后出生）")
    assert is_eligibility_clause("适应岗位要求的身体条件")
    assert is_eligibility_clause("遵纪守法，品行端正")
    assert is_eligibility_clause("无违法违纪记录")


def test_degree_clauses_are_never_eligibility():
    """学历条款必须留给算术门槛判定，哪怕混有年龄等资格语义。"""
    assert not is_eligibility_clause("硕士研究生及以上学历，并具有相应学位")
    assert not is_eligibility_clause("硕士及以上学历，年龄不超过35周岁")
    assert not is_eligibility_clause("本科及以上学历")


def test_skill_requirements_are_not_eligibility():
    assert not is_eligibility_clause("熟悉流行病学统计分析方法，熟练使用SPSS")
    assert not is_eligibility_clause("具有临床试验项目管理经验")


# ── 匹配层过滤 ──────────────────────────────────────────────────────


def _job(raw_text: str) -> dict:
    return {"id": 1, "title": "测试岗位", "institution_name": "测试机构", "raw_text": raw_text}


def test_eligibility_clauses_do_not_become_gaps():
    raw = (
        "一、报考条件 （一）具有中华人民共和国国籍，遵守中华人民共和国宪法和法律；"
        "（二）年龄不超过38周岁；"
        "（三）适应岗位要求的身体条件；"
        "（四）硕士研究生及以上学历，并具有相应学位；"
        "（五）熟悉SPSS等统计分析软件。"
    )
    requirements = segment_requirements(raw).requirements
    assert requirements, "分词仍应提取出条款（过滤只发生在匹配层）"

    evidence, gaps = match_profile_to_job(_profile(), _job(raw))
    gap_requirements = " ".join(g["requirement"] for g in gaps)
    assert "国籍" not in gap_requirements
    assert "周岁" not in gap_requirements
    assert "身体条件" not in gap_requirements
    # 履历可比要求照常工作
    assert any("SPSS" in g["requirement"] for g in gaps) or any(
        "SPSS" in (e.get("requirement") or "") for e in evidence
    )
    assert any(e.get("gate") == "degree" for e in evidence), "学历门槛应照常出证据"


def test_summary_counts_exclude_eligibility_only_jobs():
    """纯资格条款的公告：不再产生缺口，匹配度显示为 0/0 而不是全红。"""
    raw = "一、报考条件 （一）具有中华人民共和国国籍；（二）遵纪守法，品行端正；（三）适应岗位要求的身体条件。"
    evidence, gaps = match_profile_to_job(_profile(), _job(raw))
    assert gaps == []
    summary = summarize_match(evidence, gaps)
    assert summary["total"] == 0
    assert not summary["blocking_gap"]


def test_total_mismatch_not_triggered_by_eligibility_only_announcement():
    from app.services.resume import is_total_mismatch

    raw = "一、报考条件 （一）具有中华人民共和国国籍；（二）年龄不超过40周岁。"
    evidence, gaps = match_profile_to_job(_profile(), _job(raw))
    assert not is_total_mismatch(evidence, gaps), "纯资格公告不应 422 阻断生成"
