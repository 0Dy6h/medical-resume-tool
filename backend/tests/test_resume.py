from app.schemas import Profile
from app.services.resume import (
    _identity_section,
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


def test_synonym_expansion_matches_statistics_requirement_to_spss_fact():
    """统计学/数据处理 的要求应能命中只写了 SPSS/数据分析 的真实事实。"""
    profile = profile_of(skills=[{"id": "s1", "name": "熟练使用 SPSS 进行数据分析"}])
    job = {
        "institution_name": "某医院",
        "title": "研究助理",
        "raw_text": "岗位要求：具备统计学基础与数据处理能力。",
    }
    evidence, _gaps = match_profile_to_job(profile, job)
    assert evidence
    assert any("数据统计" in item["matched_terms"] for item in evidence)
