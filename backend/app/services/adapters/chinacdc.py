"""中国疾病预防控制中心(chinacdc)官网招聘适配器。

抓取 www.chinacdc.cn/rcjs/rczp/ 列表页，逐条获取招聘公告。
支持两种公告：
  - 部门级启事：单岗位，正文含岗位职责和条件（可直接解析）
  - 年度公开招聘公告：多岗位，具体岗位在 xlsx 附件中（仅提取公告元信息）
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
    """从列表页提取公告链接和日期。"""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if not (10 < len(text) < 80):
            continue
        if not any(kw in text for kw in ["招聘", "公告", "引进"]):
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        # 提取行内日期 (2025-03-25 格式常附在文本末尾)
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        date = date_match.group(1) if date_match else None
        title = re.sub(r"\d{4}-\d{2}-\d{2}$", "", text).strip()
        results.append({"title": title, "url": href, "date": date})
    return results


def extract_jobs_from_article(
    html: str,
    source_url: str,
    institution: dict[str, Any],
    *,
    attachment_bytes_by_url: dict[str, bytes] | None = None,
    attachment_errors_by_url: dict[str, str] | None = None,
) -> list[ParsedJob]:
    """从公告页提取岗位信息。

    部门级启事通常含一个岗位，格式：
      一、招聘岗位 → 二、岗位职责 → 三、招聘条件 → 四、招聘方式及待遇
    """
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", class_="content")
    if not content:
        return []
    text = content.get_text("\n")
    text_clean = normalize_text(text)
    attachments = extract_attachment_links(html, source_url)

    # 判断是否为部门级启事（含"岗位职责"章节）
    if "岗位职责" not in text_clean and "工作内容" not in text_clean:
        # 年度公开招聘公告，岗位在附件中，只提取公告标题作为记录
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True)[:60] if title_tag else "中疾控招聘公告"
        notice = parse_job_from_text(
            title=normalize_text(title),
            body=text_clean[:2000],
            source_url=source_url,
            institution_type=institution["institution_type"],
            region=institution["region"],
            parser_name="chinacdc-notice-v1",
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
            content_bytes = (attachment_bytes_by_url or {}).get(attachment["url"])
            if not content_bytes:
                continue
            try:
                jobs.extend(
                    build_jobs_from_xlsx_attachment(
                        content=content_bytes,
                        attachment=attachment,
                        announcement_url=source_url,
                        institution=institution,
                        parser_name="chinacdc-xlsx-v1",
                    )
                )
            except Exception as exc:
                attachment_statuses[index] = attachment_status(attachment, "failed", str(exc))
        return jobs

    # 部门级启事解析
    # 提取岗位名称
    job_title_match = re.search(r"[一二三四五六七八九十]、\s*招聘岗位\s*\n(.+?)(?:\n|$)", text)
    job_title = job_title_match.group(1).strip() if job_title_match else ""
    if not job_title:
        # 尝试从开头提取
        first_line = text.strip().split("\n")[0]
        job_title = first_line[:40] if first_line else "中疾控招聘岗位"

    # 提取岗位职责
    resp_match = re.search(
        r"[一二三四五六七八九十]、\s*岗位职责([\s\S]*?)(?=[一二三四五六七八九十]、|$)", text
    )
    responsibilities = normalize_text(resp_match.group(1)) if resp_match else ""

    # 提取招聘条件
    req_match = re.search(
        r"[一二三四五六七八九十]、\s*招聘条件([\s\S]*?)(?=[一二三四五六七八九十]、|$)", text
    )
    requirements = normalize_text(req_match.group(1)) if req_match else ""

    body = f"岗位职责：{responsibilities}\n任职要求：{requirements}" if responsibilities else text_clean[:2000]

    job = parse_job_from_text(
        title=normalize_text(job_title),
        body=body,
        source_url=source_url,
        institution_type=institution["institution_type"],
        region=institution["region"],
        parser_name="chinacdc-dept-v1",
        department=None,
    )
    job.extraction_evidence["attachments"] = [
        _status_for_attachment(item, attachment_bytes_by_url, attachment_errors_by_url) for item in attachments
    ]
    return [job]


async def crawl_chinacdc(institution: dict[str, Any]) -> list[ParsedJob]:
    """抓取中疾控招聘列表并逐条解析。"""
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
        for article in articles[:10]:
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
