"""Tests for the nfyy (南方医院) announcement adapter."""
from pathlib import Path

import pytest

from app.services.adapters.nfyy import extract_jobs_from_announcement

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "nfyy" / "a_121553.html"
INSTITUTION = {
    "id": 21,
    "name": "南方医科大学南方医院",
    "institution_type": "医院",
    "region": "广东",
}
SOURCE_URL = "https://www.nfyy.com/job/gkzp/a_121553.html"


@pytest.fixture
def jobs():
    html = FIXTURE_PATH.read_text(encoding="utf-8", errors="ignore")
    return extract_jobs_from_announcement(html, SOURCE_URL, INSTITUTION)


def test_extracts_correct_number_of_jobs(jobs):
    assert len(jobs) == 11


def test_job_titles_are_meaningful(jobs):
    titles = [j.title for j in jobs]
    assert "各专科医师岗位" in titles
    assert "护理岗位" in titles
    assert "博士后岗位" in titles


def test_education_levels_inferred(jobs):
    edu_map = {j.title: j.education for j in jobs}
    assert edu_map["各专科医师岗位"] in ("博士", "硕士")
    assert edu_map["护理岗位"] in ("本科", "硕士")
    assert edu_map["博士后岗位"] == "博士"


def test_categories_assigned(jobs):
    cat_map = {j.title: j.job_category for j in jobs}
    assert cat_map["医技岗位"] == "医技"
    assert cat_map["药剂岗位"] == "药学"
    assert cat_map["护理岗位"] == "护理"


def test_parser_name_and_source_url(jobs):
    for j in jobs:
        assert j.parser_name == "nfyy-announcement-v1"
        assert j.source_url.startswith(SOURCE_URL)
        assert j.source_text_hash


def test_confidence_within_range(jobs):
    for j in jobs:
        assert 0.5 <= j.confidence <= 1.0


def test_tags_include_institution_metadata(jobs):
    for j in jobs:
        assert "医院" in j.tags or "广东" in j.tags
