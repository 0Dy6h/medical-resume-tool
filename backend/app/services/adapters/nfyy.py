"""南方医院(nfyy)官网招聘公告适配器。

抓取 www.nfyy.com/job/gkzp/ 下的静态招聘公告页并拆分为结构化岗位。
公告格式为编号式(一)…(二)…，每段含岗位名和应聘条件。
"""
from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.services.classifier import normalize_text
from app.services.crawler import ParsedJob, hash_text, parse_job_from_text, utc_now

# 编号标题模式：（一）...、（二）... 或 1. ... 2. ...
_SECTION_PATTERN = re.compile(
    r"(?:（[一二三四五六七八九十]+）|[（(]\d+[)）]|\d+[.、])\s*(.+?)(?=\n|$)"
)

# 更精确：中文编号开头的岗位大类
_CATEGORY_SPLIT = re.compile(
    r"(?=（[一二三四五六七八九十]{1,3}）)"
)


def extract_jobs_from_announcement(html: str, source_url: str, institution: dict[str, Any]) -> list[ParsedJob]:
    """从公告 HTML 抽取结构化岗位列表。"""
    soup = BeautifulSoup(html, "html.parser")
    main_div = soup.find("div", class_="main")
    if not main_div:
        return []
    text = main_div.get_text("\n")
    return parse_announcement_text(text, source_url, institution)


def parse_announcement_text(text: str, source_url: str, institution: dict[str, Any]) -> list[ParsedJob]:
    """将公告纯文本按编号拆分为岗位记录。"""
    # 找到"招聘岗位"章节起始
    start_match = re.search(r"[二三四五六七八九十]、\s*招聘岗位", text)
    if not start_match:
        # fallback: 从头开始找编号段
        start_pos = 0
    else:
        start_pos = start_match.end()

    # 找到下一个大章节(三、福利待遇 / 四、联系方式)作为结束
    end_match = re.search(r"[二三四五六七八九十]、\s*(?:福利待遇|联系方式|报名|应聘方式|其他)", text[start_pos:])
    end_pos = start_pos + end_match.start() if end_match else len(text)

    job_section = text[start_pos:end_pos]

    # 按中文编号拆分
    segments = _CATEGORY_SPLIT.split(job_section)
    segments = [s.strip() for s in segments if s.strip() and "（" in s[:5]]

    jobs: list[ParsedJob] = []
    for idx, seg in enumerate(segments, start=1):
        # 提取标题行
        title_match = re.match(r"（[一二三四五六七八九十]+）\s*(.+?)(?:\n|$)", seg)
        if not title_match:
            continue
        title = normalize_text(title_match.group(1))
        body = normalize_text(seg[title_match.end():])
        if not body or len(body) < 10:
            body = normalize_text(seg)

        jobs.append(
            parse_job_from_text(
                title=title,
                body=body,
                source_url=f"{source_url}#job-{idx}",
                institution_type=institution["institution_type"],
                region=institution["region"],
                parser_name="nfyy-announcement-v1",
                department=None,
            )
        )
    return jobs


async def crawl_nfyy(institution: dict[str, Any]) -> list[ParsedJob]:
    """抓取南方医院官网招聘公告页并抽取岗位。"""
    listing_url = institution["listing_url"]
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "MedicalJobMVP/0.1"},
    ) as client:
        resp = await client.get(listing_url)
        resp.raise_for_status()
    return extract_jobs_from_announcement(resp.text, listing_url, institution)
