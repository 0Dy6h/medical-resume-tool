"""Requirement segmentation quality, measured against the committed fixtures."""

import glob
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.services.classifier import normalize_text
from app.services.matching.segment import segment_requirements

_FIXTURES = Path(__file__).parent.parent / "fixtures"

#: Terms that mark a clause as application procedure or employer self-promotion.
#: None of these may appear in any extracted requirement.  (落户/户口 are
#: deliberately excluded — they occur inside genuine eligibility requirements
#: such as "符合...就业落户相关政策要求".)
_BOILERPLATE_MARKERS = (
    "报名", "截止", "邮箱", "笔试", "面试", "公示", "拟录用",
    "医院拥有", "现有床位", "占地", "成立于", "http", "上传照片",
    "资格审查", "资格初审", "工资待遇",
)


def _fixture_text(path: str) -> str:
    html = Path(path).read_text(encoding="utf-8", errors="ignore")
    return normalize_text(BeautifulSoup(html, "html.parser").get_text("\n", strip=True))


def _all_article_fixtures():
    return sorted(glob.glob(str(_FIXTURES / "*" / "article*.html")))


def test_numbered_list_that_lost_its_line_breaks_is_split():
    text = "岗位要求：1、硕士及以上学历；2、熟悉SPSS等统计软件；3、有队列研究经验者优先。"
    reqs = segment_requirements(text).requirements
    assert len(reqs) >= 3
    assert any("硕士" in r for r in reqs)
    assert any("SPSS" in r for r in reqs)
    assert any("队列" in r for r in reqs)


def test_a_bare_requirement_line_is_kept():
    assert segment_requirements("持有执业医师证").requirements == ["持有执业医师证"]
    assert segment_requirements("2、具有临床试验项目管理经验").requirements == ["具有临床试验项目管理经验"]


def test_no_extracted_requirement_is_boilerplate():
    """Across every fixture, no clause we call a requirement is procedure/blurb."""
    offenders = []
    for path in _all_article_fixtures():
        for req in segment_requirements(_fixture_text(path)).requirements:
            for marker in _BOILERPLATE_MARKERS:
                if marker in req:
                    offenders.append((Path(path).parent.name, marker, req[:40]))
    assert not offenders, offenders


def test_section_headings_are_not_returned_as_requirements():
    for path in _all_article_fixtures():
        reqs = segment_requirements(_fixture_text(path)).requirements
        assert "基本条件" not in reqs
        assert "岗位条件" not in reqs
        assert "招聘方式及待遇" not in reqs


def test_name_table_fixture_yields_no_fabricated_requirements():
    """hrbmu's article is a 拟录用人员公示 name table — it has no requirements.

    The old extractor fabricated '岗位提到：护理' etc. here; the segmenter must
    return nothing and say so.
    """
    result = segment_requirements(_fixture_text(str(_FIXTURES / "hrbmu" / "article.html")))
    assert result.requirements == []
    assert result.warnings


def test_real_requirement_clauses_are_recovered():
    """z2hospital's 招聘启事 states its conditions inline; recover them."""
    result = segment_requirements(_fixture_text(str(_FIXTURES / "z2hospital" / "article_24348.html")))
    joined = " ".join(result.requirements)
    assert "执业医师" in joined
    assert "临床医学" in joined


def test_body_condition_requirement_is_not_dropped_as_a_heading():
    text = "一、报考条件 （一）具有中华人民共和国国籍。 （三）适应岗位要求的身体条件。"
    reqs = segment_requirements(text).requirements
    assert any("身体条件" in r for r in reqs)


@pytest.mark.parametrize("path", _all_article_fixtures())
def test_boilerplate_rate_is_low_per_fixture(path):
    reqs = segment_requirements(_fixture_text(path)).requirements
    if not reqs:
        return
    bad = sum(1 for r in reqs if any(m in r for m in _BOILERPLATE_MARKERS))
    assert bad / len(reqs) <= 0.10, (Path(path).parent.name, bad, len(reqs))


def test_empty_text_reports_a_warning_not_a_crash():
    result = segment_requirements("")
    assert result.requirements == []
    assert result.warnings


def test_image_table_heading_fragment_is_not_a_requirement():
    """图片表格型公告（浙大二院）：条件表是 PNG，正文只剩标题碎片。

    "一、 岗位及条件 二、报名方式" 必须不产出「岗位及条件 二」这类垃圾条款
    （2026-09 真实抓取中曾作为 unmet 要求出现在列表与详情里）。
    """
    text = normalize_text(
        "浙大二院 柯桥院区财务科因工作需要，现面向社会招聘劳务派遣工作人员。"
        " 一、 岗位及条件 二 、报名方式 简历投递："
    )
    reqs = segment_requirements(text).requirements
    assert all("岗位及条件" not in r for r in reqs), reqs


def test_benefits_clauses_are_classified():
    """待遇/薪酬类条款不是履历可举证的要求（2026-09 试用：#97/#346 混入硬性要求）。"""
    from app.services.matching.segment import is_benefits_clause

    assert is_benefits_clause("岗位待遇 根据浙江大学医学院附属第二医院相关规定执行，具体待遇面议")
    assert is_benefits_clause("引进待遇 根据引进人才的类别，高层次人才享受相应的工资和福利待遇")
    assert is_benefits_clause("思政特岗教授 享受相应专业技术职务的工资和福利待遇，同时享受人才津贴")
    assert is_benefits_clause("薪酬福利按国家和学校有关规定执行")


def test_benefits_classification_keeps_real_requirements():
    from app.services.matching.segment import is_benefits_clause

    # 学历标记优先：带学历的条款必须留给学位门
    assert not is_benefits_clause("硕士及以上学历，享受相应待遇")
    # 含需求提示词的条款不得因尾部提待遇而被误杀
    assert not is_benefits_clause("具有三年以上临床护理工作经验者优先，待遇从优")
    assert not is_benefits_clause("具有执业医师资格证书")
    assert not is_benefits_clause("熟悉临床试验流程及 GCP 法规")
