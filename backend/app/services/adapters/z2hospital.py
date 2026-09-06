"""浙江大学医学院附属第二医院(浙大二院)官网招聘适配器。

抓取 www.z2hospital.com/channels/611.html 列表页，逐条获取招聘启事详情。
每条启事对应一个岗位（单岗位公告模式）。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.config import config
from app.services.adapters.image_table_ocr import ocr_condition_tables
from app.services.classifier import normalize_text
from app.services.crawler import ParsedJob, parse_job_from_text
from app.services.http_client import build_crawl_client


_LISTING_SELECTOR = "div.main li"

# 文章页 meta 行（作者：/审核：/来源：/发布时间：2026-07-27/阅读次数：…），
# 位于标题与正文之间，混入正文会污染 requirements 与匹配输入。
_META_LINE = re.compile(
    r"^(?:作者|审核|编辑|来源|发布时间|发布日期|阅读次数|点击数|字号|打印|分享)\s*[:：]"
)


def extract_article_links(html: str, base_url: str) -> list[dict[str, str]]:
    """从列表页提取公告链接和日期。"""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("div", class_="main")
    if not main:
        return []
    results = []
    for li in main.find_all("li"):
        a = li.find("a", href=True)
        if not a:
            continue
        text = a.get_text(strip=True)
        if len(text) < 6:
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        date_span = li.find("span")
        date = date_span.get_text(strip=True) if date_span else None
        results.append({"title": text, "url": href, "date": date})
    return results


def extract_job_from_article(
    html: str,
    source_url: str,
    institution: dict[str, Any],
    *,
    extra_body: str = "",
) -> ParsedJob | None:
    """从单条招聘启事页面提取岗位信息。

    extra_body：图片条件表 OCR 文本（image_table_ocr 产物），并入正文尾部
    走同一条解析管线；纯图片公告（正文行数不足）靠它才能进入解析。
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("div", class_="main")
    if not main:
        return None
    text = main.get_text("\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    has_extra = bool(extra_body.strip())
    if len(lines) < 5 and not has_extra:
        return None

    # 提取标题：通常在 "关于招聘..." 或 "招聘..." 行
    title = ""
    for line in lines:
        if ("招聘" in line or "岗位" in line) and 6 < len(line) < 60:
            title = line
            break
    if not title:
        title = lines[0] if lines else "浙大二院招聘"

    # 提取发布日期
    posted_at = None
    for line in lines:
        m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", line)
        if m:
            posted_at = m.group(1).replace("年", "-").replace("月", "-").replace("日", "")
            break

    # 正文：标题后到"报名方式"或末尾
    body_lines = []
    started = False
    for line in lines:
        if line == title:
            started = True
            continue
        if started:
            if _META_LINE.match(line):
                continue
            if any(kw in line for kw in ["报名方式", "简历投递", "联系电话", "联系方式"]):
                break
            body_lines.append(line)
    body = "\n".join(body_lines) if body_lines else "\n".join(lines)
    if has_extra:
        body = f"{body}\n{extra_body.strip()}"

    return parse_job_from_text(
        title=normalize_text(title),
        body=normalize_text(body),
        source_url=source_url,
        institution_type=institution["institution_type"],
        region=institution["region"],
        parser_name="z2hospital-article-v1",
        department=None,
    )


async def crawl_z2hospital(institution: dict[str, Any]) -> list[ParsedJob]:
    """抓取浙大二院招聘列表并逐条解析。"""
    listing_url = institution["listing_url"]
    async with build_crawl_client() as client:
        resp = await client.get(listing_url)
        resp.raise_for_status()
        articles = extract_article_links(resp.text, listing_url)

        jobs: list[ParsedJob] = []
        # 限制每次最多抓取 10 篇，避免过多请求
        for article in articles[:10]:
            try:
                art_resp = await client.get(article["url"])
                art_resp.raise_for_status()
                job = extract_job_from_article(art_resp.text, article["url"], institution)
                # 图片条件表兜底：正文碎片化（解析失败或条件为空）时 OCR 公告内图片重解析。
                # OCR 全程诚实降级（依赖缺失/识别为空 → 空文本），失败不打断抓取。
                if (job is None or not job.requirements.strip()) and config.image_table_ocr_enabled:
                    ocr_text = await ocr_condition_tables(client, art_resp.text, article["url"])
                    if ocr_text:
                        job = extract_job_from_article(
                            art_resp.text, article["url"], institution, extra_body=ocr_text
                        )
                if job:
                    jobs.append(job)
            except httpx.HTTPError:
                continue
    return jobs
