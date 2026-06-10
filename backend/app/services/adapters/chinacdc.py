"""中国疾病预防控制中心(chinacdc)官网招聘适配器。

抓取 www.chinacdc.cn/rcjs/rczp/ 列表页，逐条获取招聘公告。
支持两种公告：
  - 部门级启事：单岗位，正文含岗位职责和条件（可直接解析）
  - 年度公开招聘公告：多岗位，具体岗位在 xlsx 附件中（仅提取公告元信息）
"""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from app.services.adapters.adapter_base import extract_links_by_keyword, fetch_articles
from app.services.attachments import attachment_status, extract_attachment_links
from app.services.classifier import normalize_text
from app.services.crawler import ParsedJob, parse_job_from_text


def extract_article_links(html: str, base_url: str) -> list[dict[str, str]]:
    """从列表页提取公告链接和日期。"""
    return extract_links_by_keyword(html, base_url, keywords=["招聘", "公告", "引进"])


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
    from app.services.adapters.adapter_base import parse_notice_with_xlsx_attachments

    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", class_="content")
    if not content:
        return []
    text = content.get_text("\n")
    text_clean = normalize_text(text)

    # 判断是否为部门级启事（含"岗位职责"章节）
    if "岗位职责" not in text_clean and "工作内容" not in text_clean:
        # 年度公开招聘公告，岗位在附件中
        def parse_annual_notice(html: str, url: str, inst: dict[str, Any]) -> ParsedJob:
            soup = BeautifulSoup(html, "html.parser")
            content = soup.find("div", class_="content")
            text_clean = normalize_text(content.get_text("\n")) if content else ""
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True)[:60] if title_tag else "中疾控招聘公告"
            return parse_job_from_text(
                title=normalize_text(title),
                body=text_clean[:2000],
                source_url=url,
                institution_type=inst["institution_type"],
                region=inst["region"],
                parser_name="chinacdc-notice-v1",
                department=None,
            )

        return parse_notice_with_xlsx_attachments(
            html,
            source_url,
            institution,
            parser_name="chinacdc",
            notice_parser=parse_annual_notice,
            attachment_bytes_by_url=attachment_bytes_by_url,
            attachment_errors_by_url=attachment_errors_by_url,
        )

    # 部门级启事解析
    job_title_match = re.search(r"[一二三四五六七八九十]、\s*招聘岗位\s*\n(.+?)(?:\n|$)", text)
    job_title = job_title_match.group(1).strip() if job_title_match else ""
    if not job_title:
        first_line = text.strip().split("\n")[0]
        job_title = first_line[:40] if first_line else "中疾控招聘岗位"

    resp_match = re.search(
        r"[一二三四五六七八九十]、\s*岗位职责([\s\S]*?)(?=[一二三四五六七八九十]、|$)", text
    )
    responsibilities = normalize_text(resp_match.group(1)) if resp_match else ""

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
    evidence = dict(job.extraction_evidence)
    evidence["attachments"] = [
        attachment_status(item, "discovered") for item in extract_attachment_links(html, source_url)
    ]
    from dataclasses import replace
    return [replace(job, extraction_evidence=evidence)]


async def crawl_chinacdc(institution: dict[str, Any]) -> list[ParsedJob]:
    """抓取中疾控招聘列表并逐条解析。"""
    return await fetch_articles(
        institution,
        extract_links=extract_article_links,
        parse_article=extract_jobs_from_article,
        limit=10,
        fetch_attachments=True,
    )
