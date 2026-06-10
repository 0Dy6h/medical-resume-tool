"""南京医科大学(njmu)官网招聘适配器。

抓取 rsc.njmu.edu.cn/10978/list.htm 列表页的招聘公告。
公告正文含整体招聘要求（条件、流程），具体岗位表为 PDF 附件。
适配器提取公告文本作为整体记录，并标注需人工查阅附件获取具体岗位。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.services.attachments import attachment_status, extract_attachment_links
from app.services.classifier import normalize_text
from app.services.crawler import ParsedJob, parse_job_from_text


def extract_article_links(html: str, base_url: str) -> list[dict[str, str]]:
    """从列表页提取公告链接。"""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    # njmu 使用 col_news 类的 div 包含文章列表
    news_div = soup.find("div", class_="col_news")
    container = news_div or soup
    for a in container.find_all("a", href=True):
        text = a.get_text(strip=True)
        if not (10 < len(text) < 80):
            continue
        if not any(kw in text for kw in ["招聘", "公告", "博士后"]):
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        results.append({"title": text, "url": href})
    return results


def extract_jobs_from_article(html: str, source_url: str, institution: dict[str, Any]) -> list[ParsedJob]:
    """从公告页提取岗位信息。"""
    soup = BeautifulSoup(html, "html.parser")
    # njmu 使用 wp_articlecontent 或 article 类
    content = (
        soup.find("div", class_="wp_articlecontent")
        or soup.find("div", class_="article")
        or soup.find("article")
    )
    if not content:
        for div in soup.find_all("div"):
            cls = " ".join(div.get("class", []))
            if "article" in cls or "content" in cls:
                content = div
                break
    if not content:
        return []

    text = content.get_text("\n")
    text_clean = normalize_text(text)

    # 提取标题
    title_tag = soup.find("title")
    title = normalize_text(title_tag.get_text()) if title_tag else ""
    if not title:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        title = lines[0][:60] if lines else "南京医科大学招聘"

    # 提取报考条件
    cond_match = re.search(
        r"[一二三四五六七八九十]、\s*(?:报考条件|招聘条件|基本条件)([\s\S]*?)(?=[一二三四五六七八九十]、|$)", text
    )
    conditions = normalize_text(cond_match.group(1)) if cond_match else ""

    body = f"报考条件：{conditions}" if conditions else text_clean[:2000]

    job = parse_job_from_text(
        title=title,
        body=body,
        source_url=source_url,
        institution_type=institution["institution_type"],
        region=institution["region"],
        parser_name="njmu-notice-v1",
        department=None,
    )
    job.extraction_evidence["attachments"] = [
        attachment_status(item, "discovered") for item in extract_attachment_links(html, source_url)
    ]
    return [job]


async def crawl_njmu(institution: dict[str, Any]) -> list[ParsedJob]:
    """抓取南京医科大学招聘列表并解析公告。"""
    listing_url = institution["listing_url"]
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "MedicalJobMVP/0.1"},
    ) as client:
        resp = await client.get(listing_url)
        resp.raise_for_status()
        articles = extract_article_links(resp.text, listing_url)

        jobs: list[ParsedJob] = []
        for article in articles[:8]:
            try:
                art_resp = await client.get(article["url"])
                art_resp.raise_for_status()
                parsed = extract_jobs_from_article(art_resp.text, article["url"], institution)
                jobs.extend(parsed)
            except httpx.HTTPError:
                continue
    return jobs
