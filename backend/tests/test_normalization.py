"""测试文本归一化功能。"""
import pytest

from app.services.profile_import.normalization import (
    merge_bullets_with_parent,
    normalize_heading,
    normalize_time_range,
    strip_bullet,
)


def test_normalize_time_range_standard_format():
    start, end, remaining = normalize_time_range("2021.09-2024.06 复旦大学 临床医学")
    assert start == "2021.09"
    assert end == "2024.06"
    assert "复旦大学" in remaining
    assert "临床医学" in remaining


def test_normalize_time_range_with_present():
    start, end, remaining = normalize_time_range("2023.01-至今 上海某三甲医院")
    assert start == "2023.01"
    assert end == "至今"
    assert "上海某三甲医院" in remaining


def test_normalize_time_range_year_only():
    start, end, remaining = normalize_time_range("2021-2024 某项目")
    assert start == "2021"
    assert end == "2024"
    assert "某项目" in remaining


def test_normalize_time_range_chinese_format():
    start, end, remaining = normalize_time_range("2021年9月至2024年6月 复旦大学")
    assert start == "2021.9"
    assert end == "2024.6"


def test_normalize_time_range_no_match():
    start, end, remaining = normalize_time_range("复旦大学 临床医学")
    assert start == ""
    assert end == ""
    assert remaining == "复旦大学 临床医学"


def test_normalize_heading_with_chinese_number():
    assert normalize_heading("一、教育经历") == "教育经历"
    assert normalize_heading("二. 工作经历") == "工作经历"


def test_normalize_heading_with_arabic_number():
    assert normalize_heading("1. 教育经历") == "教育经历"
    assert normalize_heading("2）工作经历") == "工作经历"


def test_normalize_heading_with_brackets():
    assert normalize_heading("【教育经历】") == "教育经历"


def test_normalize_heading_markdown():
    assert normalize_heading("# 教育经历") == "教育经历"
    assert normalize_heading("## 工作经历") == "工作经历"


def test_normalize_heading_plain():
    assert normalize_heading("教育经历") == "教育经历"
    assert normalize_heading("教育背景") == "教育背景"


def test_normalize_heading_rejects_long_text():
    assert normalize_heading("这是一段很长的文本，不应该被识别为标题") is None


def test_normalize_heading_rejects_empty():
    assert normalize_heading("") is None
    assert normalize_heading("   ") is None


def test_strip_bullet_removes_markers():
    assert strip_bullet("- 参与伦理材料整理") == "参与伦理材料整理"
    assert strip_bullet("• 维护随访数据库") == "维护随访数据库"
    assert strip_bullet("1. 使用 SPSS") == "使用 SPSS"


def test_merge_bullets_with_parent():
    lines = [
        "2023.01-2024.06 上海某三甲医院 科研助理",
        "- 参与伦理材料整理",
        "- 维护随访数据库",
        "",
        "另一个项目",
        "• 项目内容",
    ]
    blocks = merge_bullets_with_parent(lines)
    assert len(blocks) == 2
    assert blocks[0][0] == "2023.01-2024.06 上海某三甲医院 科研助理"
    assert blocks[0][1] == "参与伦理材料整理"
    assert blocks[0][2] == "维护随访数据库"
    assert blocks[1][0] == "另一个项目"
    assert blocks[1][1] == "项目内容"


def test_merge_bullets_handles_no_bullets():
    lines = ["第一行", "第二行", "", "第三行"]
    blocks = merge_bullets_with_parent(lines)
    assert len(blocks) == 3
    assert blocks[0] == ["第一行"]
    assert blocks[1] == ["第二行"]
    assert blocks[2] == ["第三行"]
