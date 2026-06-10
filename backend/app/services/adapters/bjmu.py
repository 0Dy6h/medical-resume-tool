"""北京大学医学部(bjmu)官网招聘适配器。

抓取 rsc.bjmu.edu.cn/rczp/js/ 列表页的招聘公告。
公告来自北大医学部下属各附属医院和研究所。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.services.attachments import (
    attachment_status,
    build_jobs_from_xlsx_attachment,
    extract_attachment_links,
)
from app.services.classifier import normalize_text
from app.services.crawler import ParsedJob, parse_job_from_text


def extract_article_links(html: str, base_url: str) -> list[dict[str, str]]:
    """从列表页提取公告链接。"""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if not (10 < len(text) < 80):
            continue
        if not any(kw in text for kw in ["招聘", "公告", "博士后", "岗位", "引进"]):
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        results.append({"title": text, "url": href})
    return results


def extract_jobs_from_article(
    html: str,
    source_url: str,
    institution: dict[str, Any],
    *,
    attachment_bytes_by_url: dict[str, bytes] | None = None,
    attachment_errors_by_url: dict[str, str] | None = None,
) -> list[ParsedJob]:
    """从公告页提取岗位信息。"""
    soup = BeautifulSoup(html, "html.parser")
    # bjmu 页面结构：找正文 div
    content = (
        soup.find("div", class_="gp-article")
        or soup.find("div", class_="TRS_Editor")
        or soup.find("div", class_="pageArticle")
    )
    if not content:
        for div in soup.find_all("div"):
            cls = " ".join(div.get("class", []))
            if "content" in cls and len(div.get_text(strip=True)) > 200:
                content = div
                break
    if not content:
        content = soup.find("body")
    if not content:
        return []

    text = content.get_text("\n")
    text_clean = normalize_text(text)
    if len(text_clean) < 50:
        return []

    # 提取标题
    title_tag = soup.find("title")
    title = normalize_text(title_tag.get_text()[:60]) if title_tag else ""
    if not title:
        lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 5]
        title = lines[0][:60] if lines else "北大医学部招聘"

    # 尝试提取招聘条件
    cond_match = re.search(
        r"[一二三四五六七八九十]、\s*(?:招聘条件|任职条件|基本条件|岗位要求)([\s\S]*?)(?=[一二三四五六七八九十]、|$)",
        text,
    )
    body = normalize_text(cond_match.group(1)) if cond_match else text_clean[:2000]

    attachments = extract_attachment_links(html, source_url)
    notice = parse_job_from_text(
        title=title,
        body=body,
        source_url=source_url,
        institution_type=institution["institution_type"],
        region=institution["region"],
        parser_name="bjmu-notice-v1",
        department=None,
    )
    notice.extraction_evidence["attachments"] = [
        _status_for_attachment(item, attachment_bytes_by_url, attachment_errors_by_url) for item in attachments
    ]
    attachment_statuses = notice.extraction_evidence["attachments"]

    jobs = [notice]
    for index, attachment in enumerate(attachments):
        if attachment["extension"] not in {".xlsx", ".xls"}:
            continue
        content = (attachment_bytes_by_url or {}).get(attachment["url"])
        if not content:
            continue
        try:
            jobs.extend(
                build_jobs_from_xlsx_attachment(
                    content=content,
                    attachment=attachment,
                    announcement_url=source_url,
                    institution=institution,
                    parser_name="bjmu-xlsx-v1",
                )
            )
        except Exception as exc:
            attachment_statuses[index] = attachment_status(attachment, "failed", str(exc))
    return jobs


async def crawl_bjmu(institution: dict[str, Any]) -> list[ParsedJob]:
    """抓取北大医学部招聘列表并解析公告。"""
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
                attachments = extract_attachment_links(art_resp.text, article["url"])
                attachment_bytes_by_url: dict[str, bytes] = {}
                attachment_errors_by_url: dict[str, str] = {}
                for attachment in attachments:
                    if attachment["extension"] not in {".xlsx", ".xls"}:
                        continue
                    try:
                        file_resp = await client.get(attachment["url"])
                        file_resp.raise_for_status()
                        attachment_bytes_by_url[attachment["url"]] = file_resp.content
                    except httpx.HTTPError as exc:
                        attachment_errors_by_url[attachment["url"]] = str(exc)
                parsed = extract_jobs_from_article(
                    art_resp.text,
                    article["url"],
                    institution,
                    attachment_bytes_by_url=attachment_bytes_by_url,
                    attachment_errors_by_url=attachment_errors_by_url,
                )
                jobs.extend(parsed)
            except httpx.HTTPError:
                continue
    return jobs


def _status_for_attachment(
    attachment: dict[str, str],
    attachment_bytes_by_url: dict[str, bytes] | None,
    attachment_errors_by_url: dict[str, str] | None,
) -> dict[str, str]:
    if attachment["url"] in (attachment_bytes_by_url or {}):
        return attachment_status(attachment, "parsed")
    if attachment["url"] in (attachment_errors_by_url or {}):
        return attachment_status(attachment, "failed", (attachment_errors_by_url or {})[attachment["url"]])
    return attachment_status(attachment, "discovered")
