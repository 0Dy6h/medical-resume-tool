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


def test_multi_entity_block_routes_to_single_primary():
    lines = [
        "2020.09-2023.06 北京某三甲医院 主治医师",
        "- 负责国家自然科学基金面上项目，发表SCI论文3篇",
    ]
    contract = build_profile_contract(lines, [])
    # Single-primary invariant: only one collection gets the block (no fan-out).
    # With _is_experience mutual exclusion, experience is eliminated when project
    # signals are present; publication wins on confidence among remaining candidates.
    primary_collections = sum(
        1 for name in ("education", "experiences", "projects", "publications", "teaching", "awards", "certificates", "languages")
        if getattr(contract, name)
    )
    assert primary_collections == 1
    assert len(contract.publications) == 1
    assert contract.experiences == []


def test_basics_extraction_fills_phone_email_and_name():
    lines = [
        "张三",
        "电话：13800138000",
        "邮箱：zhangsan@example.com",
        "2020.09-2023.06 北京某三甲医院 主治医师",
    ]
    contract = build_profile_contract(lines, [])

    assert contract.basics["name"] == "张三"
    assert contract.basics["phone"] == "13800138000"
    assert contract.basics["email"] == "zhangsan@example.com"
    assert contract.unassigned_blocks == []


def test_basics_extraction_leaves_name_empty_without_signal():
    lines = [
        "2020.09-2023.06 北京某三甲医院 主治医师",
        "熟悉 Python、SPSS",
    ]
    contract = build_profile_contract(lines, [])

    assert "name" not in contract.basics


def test_basics_name_prefers_label_over_title_line():
    """「姓名 王大力」是强信号，不得让排在前面的标题行「个人简历」抢先冒充姓名。"""
    lines = [
        "个人简历",
        "姓名 王大力",
        "学校 北京大学 专业 临床医学 学历 本科 2015-09 至 2019-06",
    ]
    contract = build_profile_contract(lines, [])

    assert contract.basics["name"] == "王大力"


def test_basics_name_skips_resume_title_line_for_positional_fallback():
    """标题行被排除后，位置启发式才能落到真正的姓名行。"""
    contract = build_profile_contract(["个人简历", "张三"], [])

    assert contract.basics["name"] == "张三"


def test_basics_name_accepts_label_without_colon():
    contract = build_profile_contract(["姓名 李四明"], [])

    assert contract.basics["name"] == "李四明"


def test_basics_name_not_confused_by_label_without_separator():
    """「姓名」后无分隔符直接连正文时不得截成姓名。"""
    contract = build_profile_contract(["姓名与身份证不符的情况说明"], [])

    assert "name" not in contract.basics


def test_project_block_not_misrouted_to_experience():
    lines = ["2021.01-2023.12 北京某三甲医院 科研项目 负责人"]
    contract = build_profile_contract(lines, [])
    assert len(contract.projects) == 1
    assert contract.experiences == []
