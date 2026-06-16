from pathlib import Path

from app.services.profile_import.blocks import build_blocks
from app.services.profile_import.pipeline import build_profile_contract


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "profile_import"


def _fixture_lines(name: str) -> list[str]:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8").splitlines()


def test_build_blocks_preserves_section_hints_and_merges_child_lines():
    blocks = build_blocks(
        [
            "教育经历",
            "2021.09-2024.06 复旦大学 临床医学 硕士",
            "",
            "工作经历",
            "2023.01-2024.06 上海某三甲医院 科研助理",
            "- 参与伦理材料整理",
            "- 维护随访数据库",
            "慢病队列随访项目 项目成员",
        ]
    )

    assert len(blocks) == 3
    assert blocks[0].section_hint == "education"
    assert blocks[0].text == "2021.09-2024.06 复旦大学 临床医学 硕士"

    assert blocks[1].section_hint == "experiences"
    assert blocks[1].text.splitlines() == [
        "2023.01-2024.06 上海某三甲医院 科研助理",
        "参与伦理材料整理",
        "维护随访数据库",
    ]

    assert blocks[2].section_hint == "experiences"
    assert blocks[2].text == "慢病队列随访项目 项目成员"


def test_unsectioned_resume_builds_structured_profile_contract():
    contract = build_profile_contract(_fixture_lines("plain_unsectioned_resume.txt"), [])

    assert len(contract.education) == 1
    education = contract.education[0]
    assert education["school"] == "复旦大学"
    assert education["degree"] == "硕士"
    assert education["major"] == "临床医学"
    assert education["start"] == "2021.09"
    assert education["end"] == "2024.06"

    assert len(contract.experiences) == 1
    experience = contract.experiences[0]
    assert experience["organization"] == "上海某三甲医院"
    assert experience["role"] == "科研助理"
    assert experience["start"] == "2023.01"
    assert experience["end"] == "2024.06"
    assert len(experience["highlights"]) == 3
    assert {"伦理", "随访", "SPSS"} <= set(experience["skills"])

    assert len(contract.projects) == 1
    project = contract.projects[0]
    assert project["name"] == "慢病队列随访项目"
    assert project["role"] == "项目成员"
    assert project["highlights"]

    assert len(contract.certificates) == 1
    assert contract.certificates[0]["name"] == "GCP证书"

    assert len(contract.languages) == 1
    assert contract.languages[0]["name"] == "英语"
    assert contract.languages[0]["level"] == "六级"

    skill_names = {item["name"] for item in contract.skills}
    assert {"Python", "R语言", "SPSS", "数据清洗", "伦理", "随访"} <= skill_names
    assert len(skill_names) >= 6

    assert contract.review_items == []
    assert contract.unassigned_blocks == []
    assert contract.import_meta == {
        "source_type": "lines",
        "extractor_name": "fact-extractor-v1",
        "text_quality": 1.0,
        "warnings": [],
    }
