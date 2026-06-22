"""
Structured JD requirement extraction via LLM.

Takes raw job description text and uses an LLM (OpenAI-compatible API)
to extract structured, categorized requirements. Replaces the rule-based
keyword approach in classifier.py with semantic understanding.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import BaseModel, Field


# ── Configuration ──────────────────────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


STRUCTURER_API_KEY = _env("STRUCTURER_API_KEY", _env("OPENAI_API_KEY", _env("DOGAPI_API_KEY")))
STRUCTURER_BASE_URL = _env("STRUCTURER_BASE_URL", _env("OPENAI_BASE_URL", "https://api.openai.com/v1"))
STRUCTURER_MODEL = _env("STRUCTURER_MODEL", "gpt-4o-mini")
STRUCTURER_TIMEOUT = int(_env("STRUCTURER_TIMEOUT", "30"))


# ── Output models ──────────────────────────────────────────────────────────

class JDRequirement(BaseModel):
    """A single structured requirement extracted from a job description."""
    category: str = Field(
        description="Category: 临床技能/科研能力/教学经验/学历要求/证书资质/"
                    "语言能力/计算机技能/管理经验/其他"
    )
    requirement: str = Field(
        description="The actual requirement, rephrased as a clear competency statement"
    )
    must_have: bool = Field(
        description="True if this is a mandatory requirement, False if preferred/nice-to-have"
    )


class StructuredJD(BaseModel):
    """Structured extraction of a job description's requirements."""
    job_title: str = ""
    requirements: list[JDRequirement] = Field(default_factory=list)
    summary: str = ""


# ── LLM prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一位医疗招聘需求分析专家。请从以下岗位描述中提取结构化的能力要求。

规则：
1. 每条要求归入以下类别之一：临床技能、科研能力、教学经验、学历要求、证书资质、语言能力、计算机技能、管理经验、其他
2. 每条要求改写为清晰的能力陈述（例如"具有独立设计临床试验方案的经验"）
3. 标记每条要求是"必须"还是"加分项"
4. 只提取岗位描述中明确提到的要求，不推测、不补充
5. 用 JSON 格式输出，不要输出任何 JSON 之外的内容

输出格式：
{
  "job_title": "岗位名称",
  "requirements": [
    {"category": "学历要求", "requirement": "具有硕士研究生及以上学历", "must_have": true},
    {"category": "临床技能", "requirement": "具有三年以上三甲医院内科临床工作经验", "must_have": true}
  ],
  "summary": "一句话概述这个岗位的核心要求"
}"""

USER_PROMPT_TEMPLATE = """请分析以下岗位描述：

岗位名称：{title}
部门：{department}
要求：{requirements}
职责：{responsibilities}
描述：{description}"""


# ── API call ───────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str) -> dict[str, Any]:
    """Call OpenAI-compatible chat completion API."""
    if not STRUCTURER_API_KEY:
        raise RuntimeError(
            "STRUCTURER_API_KEY not set. Set it via environment variable "
            "(STRUCTURER_API_KEY, OPENAI_API_KEY, or DOGAPI_API_KEY)."
        )

    payload = {
        "model": STRUCTURER_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }

    response = httpx.post(
        f"{STRUCTURER_BASE_URL.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {STRUCTURER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=STRUCTURER_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


# ── Public API ─────────────────────────────────────────────────────────────

def structure_jd(
    title: str = "",
    department: str = "",
    requirements: str = "",
    responsibilities: str = "",
    description: str = "",
) -> StructuredJD:
    """
    Extract structured requirements from a job description.

    Args:
        title: Job title
        department: Department name
        requirements: Raw requirements text from the JD
        responsibilities: Raw responsibilities text
        description: Additional description or combined text

    Returns:
        StructuredJD with categorized requirements

    Raises:
        RuntimeError: If LLM API key is not configured
        httpx.HTTPError: If API call fails
    """
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=title or "未提供",
        department=department or "未提供",
        requirements=requirements or "未提供",
        responsibilities=responsibilities or "未提供",
        description=description or "",
    )

    # If there's essentially no content, return empty
    combined = f"{requirements} {responsibilities} {description}".strip()
    if len(combined) < 20:
        return StructuredJD(job_title=title)

    try:
        result = _call_llm(SYSTEM_PROMPT, user_prompt)
        return StructuredJD(**result)
    except Exception:
        # Fall back to empty — don't crash the pipeline
        return StructuredJD(job_title=title)


def structure_jd_from_job(job: dict[str, Any]) -> StructuredJD:
    """
    Convenience wrapper for the current dict-based job format.
    Will be replaced when P0-1 (typed schemas) is complete.
    """
    return structure_jd(
        title=str(job.get("title", "")),
        department=str(job.get("department", "")),
        requirements=str(job.get("requirements", "")),
        responsibilities=str(job.get("responsibilities", "")),
        description=str(job.get("raw_text", "")),
    )
