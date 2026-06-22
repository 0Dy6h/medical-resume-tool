"""Tests for jd_structurer — LLM-powered JD requirement extraction."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.services.jd_structurer import (
    STRUCTURER_API_KEY,
    STRUCTURER_BASE_URL,
    StructuredJD,
    structure_jd,
    structure_jd_from_job,
)


class TestStructureJd:
    """Tests for the main structure_jd() function."""

    def test_empty_input_returns_empty(self):
        """structure_jd with no meaningful text should return empty result."""
        result = structure_jd(title="", requirements="", responsibilities="", description="")
        assert isinstance(result, StructuredJD)
        assert result.requirements == []
        assert result.job_title == ""

    def test_minimal_input_returns_empty(self):
        """structure_jd with very short input (< 20 chars) should skip LLM call."""
        result = structure_jd(
            title="医生", requirements="临床", responsibilities="", description=""
        )
        assert isinstance(result, StructuredJD)
        assert result.requirements == []

    def test_with_mocked_llm_response(self):
        """structure_jd with sufficient input calls the LLM and parses the response."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"job_title":"心内科医师","requirements":[{"category":"学历要求","requirement":"硕士及以上","must_have":true},{"category":"临床技能","requirement":"三年以上心内科经验","must_have":true}],"summary":"核心要求"}'
                    }
                }
            ]
        }

        with patch("app.services.jd_structurer.httpx.post", return_value=mock_response):
            # Temporarily set a fake API key so the call goes through
            with patch.dict(
                os.environ,
                {"STRUCTURER_API_KEY": "test-key"},
                clear=False,
            ):
                # Need to reload the module's cached env var
                import app.services.jd_structurer as mod
                old_key = mod.STRUCTURER_API_KEY
                mod.STRUCTURER_API_KEY = "test-key"
                try:
                    result = structure_jd(
                        title="心内科医师",
                        department="心内科",
                        requirements="硕士及以上学历，具有三年以上三甲医院心内科临床工作经验",
                        responsibilities="负责心内科门诊及病房工作",
                    )
                finally:
                    mod.STRUCTURER_API_KEY = old_key

        assert isinstance(result, StructuredJD)
        assert result.job_title == "心内科医师"
        assert len(result.requirements) == 2
        assert result.requirements[0].category == "学历要求"
        assert result.requirements[0].must_have is True
        assert result.summary == "核心要求"

    def test_api_failure_falls_back_gracefully(self):
        """When the LLM API fails, structure_jd returns empty result instead of crashing."""
        import httpx

        with patch(
            "app.services.jd_structurer.httpx.post",
            side_effect=httpx.HTTPError("Connection timeout"),
        ):
            with patch.dict(os.environ, {"STRUCTURER_API_KEY": "test-key"}, clear=False):
                import app.services.jd_structurer as mod
                old_key = mod.STRUCTURER_API_KEY
                mod.STRUCTURER_API_KEY = "test-key"
                try:
                    result = structure_jd(
                        title="医师",
                        requirements="具有执业医师资格证，三年以上临床经验",
                    )
                finally:
                    mod.STRUCTURER_API_KEY = old_key

        # Should NOT raise — falls back to empty
        assert isinstance(result, StructuredJD)
        assert result.requirements == []

    def test_invalid_json_response_falls_back(self):
        """When LLM returns invalid JSON, structure_jd falls back gracefully."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not valid json {{{"}}]
        }

        with patch("app.services.jd_structurer.httpx.post", return_value=mock_response):
            with patch.dict(os.environ, {"STRUCTURER_API_KEY": "test-key"}, clear=False):
                import app.services.jd_structurer as mod
                old_key = mod.STRUCTURER_API_KEY
                mod.STRUCTURER_API_KEY = "test-key"
                try:
                    result = structure_jd(
                        title="医师",
                        requirements="具有执业医师资格证，熟悉GCP规范",
                    )
                finally:
                    mod.STRUCTURER_API_KEY = old_key

        assert isinstance(result, StructuredJD)
        assert result.requirements == []

    def test_with_realistic_chinese_medical_jd(self):
        """Full integration-style test with realistic Chinese medical JD text."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"job_title":"临床研究协调员(CRC)",'
                            '"requirements":['
                            '{"category":"学历要求","requirement":"医学、药学或护理学本科及以上学历","must_have":true},'
                            '{"category":"证书资质","requirement":"具有GCP证书","must_have":true},'
                            '{"category":"临床技能","requirement":"熟悉临床试验流程，具有一年以上CRC或CRA经验","must_have":true},'
                            '{"category":"语言能力","requirement":"CET-6或同等英语水平","must_have":false},'
                            '{"category":"计算机技能","requirement":"熟练使用EDC系统和Office办公软件","must_have":false}'
                            '],'
                            '"summary":"CRC岗位，要求医学背景+GCP证书+临床试验经验"}'
                        )
                    }
                }
            ]
        }

        with patch("app.services.jd_structurer.httpx.post", return_value=mock_response):
            with patch.dict(os.environ, {"STRUCTURER_API_KEY": "test-key"}, clear=False):
                import app.services.jd_structurer as mod
                old_key = mod.STRUCTURER_API_KEY
                mod.STRUCTURER_API_KEY = "test-key"
                try:
                    result = structure_jd(
                        title="临床研究协调员",
                        department="药物临床试验机构",
                        requirements=(
                            "1. 医学、药学或护理学本科及以上学历；"
                            "2. 具有GCP证书；"
                            "3. 熟悉临床试验流程，一年以上CRC或CRA经验优先；"
                            "4. 良好的英语读写能力"
                        ),
                        responsibilities="协助研究者完成临床试验的启动、执行和关闭",
                    )
                finally:
                    mod.STRUCTURER_API_KEY = old_key

        assert len(result.requirements) == 5
        # Check must_have vs nice-to-have
        must_haves = [r for r in result.requirements if r.must_have]
        nice_to_haves = [r for r in result.requirements if not r.must_have]
        assert len(must_haves) == 3  # education, GCP, clinical experience
        assert len(nice_to_haves) == 2  # English, computer


class TestStructureJdFromJob:
    """Tests for the convenience wrapper structure_jd_from_job()."""

    def test_basic_job_dict(self):
        """structure_jd_from_job extracts relevant fields from a dict job record."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": '{"job_title":"护士","requirements":[],"summary":""}'}}
            ]
        }

        job = {
            "title": "护士",
            "department": "护理部",
            "requirements": "大专及以上学历，具有护士执业证书",
            "responsibilities": "负责病区护理工作",
            "raw_text": "招聘护士一名，要求...",
        }

        with patch("app.services.jd_structurer.httpx.post", return_value=mock_response):
            with patch.dict(os.environ, {"STRUCTURER_API_KEY": "test-key"}, clear=False):
                import app.services.jd_structurer as mod
                old_key = mod.STRUCTURER_API_KEY
                mod.STRUCTURER_API_KEY = "test-key"
                try:
                    result = structure_jd_from_job(job)
                finally:
                    mod.STRUCTURER_API_KEY = old_key

        assert result.job_title == "护士"

    def test_job_with_missing_fields(self):
        """structure_jd_from_job handles missing fields gracefully."""
        result = structure_jd_from_job({"title": ""})
        assert isinstance(result, StructuredJD)
        assert result.requirements == []
