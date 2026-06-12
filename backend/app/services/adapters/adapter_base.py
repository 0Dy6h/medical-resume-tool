"""适配器公共流程：列表 → 文章 → 附件 的抓取骨架。

每个站点适配器只需提供两件事：
  - extract_links(html, base_url) -> [{"title", "url", ...}]    如何从列表页找到公告
  - parse_article(html, url, institution, ...) -> [ParsedJob]    如何解析一篇公告

公共的 client 创建、逐篇抓取、xlsx 附件下载、文章级错误处理都集中在这里，
新增站点时不必再抄一遍主循环。
"""
from __future__ import annotations

import logging
from typing import Any, Callable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.services.attachments import extract_attachment_links
from app.services.crawler import ParsedJob

logger = logging.getLogger("app.crawler")

XLSX_EXTENSIONS = {".xlsx", ".xls"}
_HEADERS = {"User-Agent": "MedicalJobMVP/0.1"}

LinkExtractor = Callable[[str, str], list[dict[str, str]]]
ArticleParser = Callable[..., list[ParsedJob]]


def make_client() -> httpx.AsyncClient:
    """所有适配器共用一套 httpx 客户端配置。"""
    from app.config import config
    return httpx.AsyncClient(
        timeout=config.crawl_timeout,
        follow_redirects=True,
        headers=_HEADERS,
        verify=False,  # 允许自签名证书和证书不匹配
    )


def extract_links_by_keyword(
    html: str,
    base_url: str,
    *,
    keywords: list[str],
    min_len: int = 10,
    max_len: int = 80,
    container: str | None = None,
) -> list[dict[str, str]]:
    """从列表页按关键词筛选公告链接（覆盖只差关键词/容器的几家站点）。"""
    soup = BeautifulSoup(html, "html.parser")
    root: Any = soup
    if container:
        root = soup.find("div", class_=container) or soup
    results: list[dict[str, str]] = []
    for anchor in root.find_all("a", href=True):
        text = anchor.get_text(strip=True)
        if not (min_len < len(text) < max_len):
            continue
        if not any(keyword in text for keyword in keywords):
            continue
        href = anchor["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        results.append({"title": text, "url": href})
    return results


async def fetch_articles(
    institution: dict[str, Any],
    *,
    extract_links: LinkExtractor,
    parse_article: ArticleParser,
    limit: int,
    fetch_attachments: bool = False,
) -> list[ParsedJob]:
    """抓取列表页，逐篇取公告并解析。

    列表页请求失败会向上抛出（交由 crawl_institution 的重试逻辑处理）；
    单篇文章失败只记录日志并跳过，不影响其余公告。
    """
    listing_url = institution["listing_url"]
    jobs: list[ParsedJob] = []
    async with make_client() as client:
        resp = await client.get(listing_url)
        resp.raise_for_status()
        articles = extract_links(resp.text, listing_url)

        for article in articles[:limit]:
            try:
                art_resp = await client.get(article["url"])
                art_resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(
                    "article fetch failed institution=%s url=%s error=%s",
                    institution.get("id"),
                    article["url"],
                    exc,
                )
                continue
            if fetch_attachments:
                attachment_bytes_by_url, attachment_errors_by_url = await _download_xlsx_attachments(
                    client, art_resp.text, article["url"], institution
                )
                jobs.extend(
                    parse_article(
                        art_resp.text,
                        article["url"],
                        institution,
                        attachment_bytes_by_url=attachment_bytes_by_url,
                        attachment_errors_by_url=attachment_errors_by_url,
                    )
                )
            else:
                jobs.extend(parse_article(art_resp.text, article["url"], institution))
    return jobs


def parse_notice_with_xlsx_attachments(
    html: str,
    source_url: str,
    institution: dict[str, Any],
    *,
    parser_name: str,
    notice_parser: Callable[[str, str, dict], ParsedJob],
    attachment_bytes_by_url: dict[str, bytes] | None = None,
    attachment_errors_by_url: dict[str, str] | None = None,
) -> list[ParsedJob]:
    """通用的公告+附件解析流程。

    先解析公告正文，然后遍历 xlsx/xls 附件，从中提取岗位行。
    适配器只需提供 notice_parser 函数即可。
    """
    from dataclasses import replace
    from app.services.attachments import (
        attachment_status,
        build_jobs_from_xlsx_attachment,
        extract_attachment_links,
        status_for_attachment,
    )

    attachments = extract_attachment_links(html, source_url)
    notice = notice_parser(html, source_url, institution)
    evidence = dict(notice.extraction_evidence)
    evidence["attachments"] = [
        status_for_attachment(item, attachment_bytes_by_url, attachment_errors_by_url)
        for item in attachments
    ]
    attachment_statuses = evidence["attachments"]
    jobs = [replace(notice, extraction_evidence=evidence)]

    for index, attachment in enumerate(attachments):
        if attachment["extension"] not in XLSX_EXTENSIONS:
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
                    parser_name=f"{parser_name}-xlsx-v1",
                )
            )
        except Exception as exc:
            attachment_statuses[index] = attachment_status(attachment, "failed", str(exc))
    return jobs


async def _download_xlsx_attachments(
    client: httpx.AsyncClient,
    html: str,
    base_url: str,
    institution: dict[str, Any],
) -> tuple[dict[str, bytes], dict[str, str]]:
    """下载公告页里的 xlsx/xls 附件，返回 (成功字节, 失败原因)。"""
    attachment_bytes_by_url: dict[str, bytes] = {}
    attachment_errors_by_url: dict[str, str] = {}
    for attachment in extract_attachment_links(html, base_url):
        if attachment["extension"] not in XLSX_EXTENSIONS:
            continue
        try:
            file_resp = await client.get(attachment["url"])
            file_resp.raise_for_status()
            attachment_bytes_by_url[attachment["url"]] = file_resp.content
        except httpx.HTTPError as exc:
            attachment_errors_by_url[attachment["url"]] = str(exc)
            logger.warning(
                "attachment fetch failed institution=%s url=%s error=%s",
                institution.get("id"),
                attachment["url"],
                exc,
            )
    return attachment_bytes_by_url, attachment_errors_by_url
