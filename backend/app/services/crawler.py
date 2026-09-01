from __future__ import annotations

import asyncio
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.services.classifier import (
    confidence_for,
    extract_requirements,
    extract_tags,
    infer_education,
    infer_job_category,
    infer_profession,
    normalize_text,
)
from app.services.http_client import OutboundBlockedError


FIXTURE_JOBS: dict[int, list[dict[str, str]]] = {
    1: [
        {
            "title": "护理部临床护士",
            "department": "护理部",
            "body": "岗位职责：承担病区护理、患者沟通、护理文书和质量改进。任职要求：护理学本科及以上，具备护士资格证，责任心强，沟通协作能力好，有三甲医院实习经历优先。",
        },
        {
            "title": "临床研究中心科研助理",
            "department": "临床研究中心",
            "body": "岗位职责：协助队列随访、伦理材料整理、数据库维护和统计分析。任职要求：临床医学、公共卫生或基础医学硕士，熟悉 SPSS 或 R 语言，具备临床研究和数据质控能力，英语阅读能力良好。",
        },
        {
            "title": "检验科医学检验技师",
            "department": "检验科",
            "body": "岗位职责：完成临床检验、仪器维护、报告审核和室内质控。任职要求：医学检验本科及以上，具备检验技师资格，熟悉实验室质量管理和沟通协作。",
        },
    ],
    2: [
        {
            "title": "内科住院医师",
            "department": "内科",
            "body": "岗位职责：承担住院患者诊疗、病历书写、门急诊轮转和教学病例讨论。任职要求：临床医学硕士及以上，完成住院医师规范化培训，具备执业医师资格，英语和科研训练良好。",
        },
        {
            "title": "药学部临床药师",
            "department": "药学部",
            "body": "岗位职责：参与用药审核、药学门诊、处方点评和临床药学研究。任职要求：药学或临床药学硕士，熟悉药物治疗管理，具备沟通能力和数据分析能力。",
        },
    ],
    3: [
        {
            "title": "流行病与卫生统计学教师",
            "department": "流行病学教研室",
            "body": "岗位职责：承担本科和研究生课程教学、科研课题申报、学生指导和公共卫生研究。任职要求：公共卫生或流行病与卫生统计博士，发表高水平论文，具备教学能力、R 或 Python 数据分析能力。",
        },
        {
            "title": "公共卫生项目专员",
            "department": "社会医学与卫生事业管理系",
            "body": "岗位职责：负责项目协调、现场调查、数据清洗、报告撰写和政策沟通。任职要求：公共卫生硕士，熟悉问卷调查和卫生统计，执行力强。",
        },
    ],
    4: [
        {
            "title": "基础医学博士后",
            "department": "免疫学重点实验室",
            "body": "岗位职责：围绕免疫调控开展课题研究、论文写作、基金申请和研究生协助指导。任职要求：基础医学、生物学或药学博士，具备英文论文写作能力和独立科研能力。",
        }
    ],
    5: [
        {
            "title": "医院运营管理专员",
            "department": "运营管理部",
            "body": "岗位职责：参与医院绩效分析、流程优化、数据报表和跨部门协作。任职要求：卫生管理、公共卫生或医学相关本科及以上，熟悉 Excel 和数据分析，沟通能力强。",
        }
    ],
    6: [
        {
            "title": "医学影像科医师",
            "department": "医学影像科",
            "body": "岗位职责：承担影像诊断、报告审核、疑难病例讨论和科研教学。任职要求：医学影像或临床医学硕士，具备执业医师资格，完成规培者优先。",
        }
    ],
}


@dataclass(frozen=True)
class ParsedJob:
    title: str
    department: str | None
    location: str | None
    education: str
    profession: str
    job_category: str
    responsibilities: str
    requirements: str
    posted_at: str | None
    deadline: str | None
    source_url: str
    source_text_hash: str
    raw_text: str
    tags: list[str]
    extraction_evidence: dict[str, Any]
    fetched_at: str
    parser_name: str
    confidence: float


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_job_from_text(
    *,
    title: str,
    body: str,
    source_url: str,
    institution_type: str,
    region: str,
    parser_name: str,
    department: str | None = None,
) -> ParsedJob:
    raw_text = normalize_text(f"{title}\n{body}")
    education = infer_education(raw_text)
    profession = infer_profession(raw_text)
    job_category = infer_job_category(title, raw_text)
    tags = extract_tags(title, raw_text, institution_type, region)
    requirements_list = extract_requirements(raw_text)
    responsibilities = body.split("任职要求")[0].replace("岗位职责：", "").strip()
    requirements = "；".join(requirements_list) if requirements_list else body
    return ParsedJob(
        title=normalize_text(title),
        department=department,
        location=region,
        education=education,
        profession=profession,
        job_category=job_category,
        responsibilities=normalize_text(responsibilities),
        requirements=normalize_text(requirements),
        posted_at=None,
        deadline=None,
        source_url=source_url,
        source_text_hash=hash_text(raw_text),
        raw_text=raw_text,
        tags=tags,
        extraction_evidence={
            "title": {"value": title, "source": "标题文本"},
            "requirements": [{"value": item, "source": "岗位原文"} for item in requirements_list],
            "tags": [{"value": item, "source": "规则关键词"} for item in tags],
        },
        fetched_at=utc_now(),
        parser_name=parser_name,
        confidence=confidence_for(raw_text, title),
    )


async def crawl_institution(institution: dict[str, Any]) -> list[ParsedJob]:
    from app.config import config
    retries = config.crawl_retries
    base_delay = config.crawl_retry_base_seconds
    last_error = None
    for attempt in range(retries + 1):
        try:
            return await _crawl_institution_once(institution)
        except (httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt >= retries:
                raise
            await asyncio.sleep(base_delay * (2**attempt))
    if last_error:
        raise last_error
    raise AssertionError("unreachable")


async def _crawl_institution_once(institution: dict[str, Any]) -> list[ParsedJob]:
    if institution["listing_url"].startswith("fixture://"):
        return crawl_fixture(institution)
    strategy = institution.get("crawl_strategy", "generic")
    adapter = _resolve_adapter(strategy)
    if adapter:
        return await adapter(institution)
    return await crawl_generic(institution)


def _resolve_adapter(strategy: str):
    """Lazy adapter lookup — keeps imports one-way (adapter -> crawler)."""
    if strategy == "nfyy":
        from app.services.adapters.nfyy import crawl_nfyy
        return crawl_nfyy
    if strategy == "z2hospital":
        from app.services.adapters.z2hospital import crawl_z2hospital
        return crawl_z2hospital
    if strategy == "chinacdc":
        from app.services.adapters.chinacdc import crawl_chinacdc
        return crawl_chinacdc
    if strategy == "njmu":
        from app.services.adapters.njmu import crawl_njmu
        return crawl_njmu
    if strategy == "hrbmu":
        from app.services.adapters.hrbmu import crawl_hrbmu
        return crawl_hrbmu
    if strategy == "bjmu":
        from app.services.adapters.bjmu import crawl_bjmu
        return crawl_bjmu
    return None


def crawl_fixture(institution: dict[str, Any]) -> list[ParsedJob]:
    jobs = FIXTURE_JOBS.get(institution["id"], [])
    parsed = []
    for idx, item in enumerate(jobs, start=1):
        parsed.append(
            parse_job_from_text(
                title=item["title"],
                body=item["body"],
                source_url=f"fixture://institution/{institution['id']}/job/{idx}",
                institution_type=institution["institution_type"],
                region=institution["region"],
                parser_name="fixture-v1",
                department=item.get("department"),
            )
        )
    return parsed


async def crawl_generic(institution: dict[str, Any]) -> list[ParsedJob]:
    from app.services.http_client import build_crawl_client

    url = institution["listing_url"]
    async with build_crawl_client() as client:
        response = await client.get(url)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    candidates = []
    for anchor in soup.find_all("a", href=True):
        text = normalize_text(anchor.get_text(" "))
        if 4 <= len(text) <= 80 and any(word in text for word in ["招聘", "岗位", "人才", "医师", "护士", "科研", "博士后"]):
            href = anchor["href"]
            source_url = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
            candidates.append((text, source_url))
    if not candidates:
        page_text = normalize_text(soup.get_text(" "))
        title = soup.title.get_text(" ") if soup.title else f"{institution['name']}招聘信息"
        return [
            parse_job_from_text(
                title=title[:60],
                body=page_text[:2000],
                source_url=url,
                institution_type=institution["institution_type"],
                region=institution["region"],
                parser_name="generic-page-v1",
            )
        ]
    parsed = []
    for index, (title, source_url) in enumerate(candidates[:30], start=1):
        body = f"{title}。来源页面：{escape(url)}。该记录由通用列表解析器抽取，需人工复核岗位详情。"
        parsed.append(
            parse_job_from_text(
                title=re.sub(r"^\d+[.、]\s*", "", title),
                body=body,
                source_url=source_url or f"{url}#job-{index}",
                institution_type=institution["institution_type"],
                region=institution["region"],
                parser_name="generic-list-v1",
            )
        )
    return parsed


def execute_crawl_run(
    engine: Any,
    run_id: int,
    institutions: list[dict[str, Any]],
    delay: float,
) -> dict[str, Any]:
    """Crawl the given institutions for a created run, updating progress incrementally.

    Runs the async per-institution crawl synchronously (suitable for a background
    thread). Persists success/failure counts after each institution so polling
    clients can observe live progress, then finalizes the run.
    """
    from app.services.repositories import (
        complete_crawl_run,
        mark_institution,
        update_crawl_progress,
        upsert_job,
    )

    async def _run() -> dict[str, Any]:
        success_count = 0
        failure_count = 0
        errors: list[dict[str, Any]] = []
        for index, institution in enumerate(institutions):
            try:
                parsed_jobs = await crawl_institution(institution)
            except OutboundBlockedError as exc:
                failure_count += 1
                errors.append(
                    {
                        "institution_id": institution["id"],
                        "institution": institution["name"],
                        "error": str(exc),
                        "error_type": "outbound_blocked",
                    }
                )
                mark_institution(engine, institution["id"], "failed", str(exc))
                update_crawl_progress(
                    engine,
                    run_id,
                    success_count=success_count,
                    failure_count=failure_count,
                    errors=errors,
                )
                if delay and index < len(institutions) - 1:
                    await asyncio.sleep(delay)
                continue
            except Exception as exc:  # pragma: no cover - exact network failures vary.
                failure_count += 1
                errors.append(
                    {
                        "institution_id": institution["id"],
                        "institution": institution["name"],
                        "error": str(exc),
                        "error_type": "network",
                    }
                )
                mark_institution(engine, institution["id"], "failed", str(exc))
                update_crawl_progress(
                    engine,
                    run_id,
                    success_count=success_count,
                    failure_count=failure_count,
                    errors=errors,
                )
                if delay and index < len(institutions) - 1:
                    await asyncio.sleep(delay)
                continue

            if not parsed_jobs:
                # A2：零产出视为失败——页面抓取成功但一条岗位都没解析出来，
                # 大概率是站点结构变化导致适配器失明，绝不能静默标记成功。
                reason = (
                    "解析零产出：页面抓取成功但未解析出任何岗位，"
                    "疑似站点结构变化，需人工复核适配器"
                )
                failure_count += 1
                errors.append(
                    {
                        "institution_id": institution["id"],
                        "institution": institution["name"],
                        "error": reason,
                        "error_type": "zero_output",
                    }
                )
                mark_institution(engine, institution["id"], "failed", reason)
            else:
                for parsed in parsed_jobs:
                    upsert_job(engine, institution, parsed)
                    success_count += 1
                mark_institution(engine, institution["id"], "success")
            update_crawl_progress(
                engine,
                run_id,
                success_count=success_count,
                failure_count=failure_count,
                errors=errors,
            )
            if delay and index < len(institutions) - 1:
                await asyncio.sleep(delay)
        return complete_crawl_run(
            engine,
            run_id,
            success_count=success_count,
            failure_count=failure_count,
            errors=errors,
        )

    return asyncio.run(_run())
