"""北京大学医学部(bjmu)官网招聘适配器。

抓取 rsc.bjmu.edu.cn/rczp/js/ 列表页的招聘公告。
公告来自北大医学部下属各附属医院和研究所。
"""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from app.services.adapters.adapter_base import extract_links_by_keyword, fetch_articles
from app.services.classifier import normalize_text
from app.services.crawler import ParsedJob, parse_job_from_text


def extract_article_links(html: str, base_url: str) -> list[dict[str, str]]:
    """从列表页提取公告链接。"""
    return extract_links_by_keyword(html, base_url, keywords=["招聘", "公告", "博士后", "岗位", "引进"])


def extract_jobs_from_article(
    html: str,
    source_url: str,
    institution: dict[str, Any],
    *,
    attachment_bytes_by_url: dict[str, bytes] | None = None,
    attachment_errors_by_url: dict[str, str] | None = None,
) -> list[ParsedJob]:
    """从公告页提取岗位信息。"""
    from app.services.adapters.adapter_base import parse_notice_with_xlsx_attachments

    def parse_notice(html: str, url: str, inst: dict[str, Any]) -> ParsedJob:
        soup = BeautifulSoup(html, "html.parser")
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
            raise ValueError("No content found")

        text = content.get_text("\n")
        text_clean = normalize_text(text)
        if len(text_clean) < 50:
            raise ValueError("Content too short")

        title_tag = soup.find("title")
        title = normalize_text(title_tag.get_text()[:60]) if title_tag else ""
        if not title:
            lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 5]
            title = lines[0][:60] if lines else "北大医学部招聘"

        cond_match = re.search(
            r"[一二三四五六七八九十]、\s*(?:招聘条件|任职条件|基本条件|岗位要求)([\s\S]*?)(?=[一二三四五六七八九十]、|$)",
            text,
        )
        body = normalize_text(cond_match.group(1)) if cond_match else text_clean[:2000]

        return parse_job_from_text(
            title=title,
            body=body,
            source_url=url,
            institution_type=inst["institution_type"],
            region=inst["region"],
            parser_name="bjmu-notice-v1",
            department=None,
        )

    return parse_notice_with_xlsx_attachments(
        html,
        source_url,
        institution,
        parser_name="bjmu",
        notice_parser=parse_notice,
        attachment_bytes_by_url=attachment_bytes_by_url,
        attachment_errors_by_url=attachment_errors_by_url,
    )


async def crawl_bjmu(institution: dict[str, Any]) -> list[ParsedJob]:
    """抓取北大医学部招聘列表并解析公告。"""
    return await fetch_articles(
        institution,
        extract_links=extract_article_links,
        parse_article=extract_jobs_from_article,
        limit=8,
        fetch_attachments=True,
    )
