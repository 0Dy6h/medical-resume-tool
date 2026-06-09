"""哈尔滨医科大学(hrbmu)官网招聘适配器。

抓取 hr.hrbmu.edu.cn 列表页的招聘公告。
招聘简章含整体条件，具体岗位需求在附件中。
另有"拟聘公示"含 HTML 表格（已录取人员），可提取岗位信息作为历史参考。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

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
        if not any(kw in text for kw in ["招聘", "公告", "博士后", "岗位"]):
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        results.append({"title": text, "url": href})
    return results


def extract_jobs_from_table_article(html: str, source_url: str, institution: dict[str, Any]) -> list[ParsedJob]:
    """从含表格的公示页提取岗位信息（作为市场参考）。"""
    soup = BeautifulSoup(html, "html.parser")
    content = None
    for div in soup.find_all("div"):
        cls = " ".join(div.get("class", []))
        if "content" in cls or "article" in cls or "mt10" in cls:
            content = div
            break
    if not content:
        return []

    tables = content.find_all("table")
    if not tables:
        # 无表格则按普通公告处理
        text = normalize_text(content.get_text("\n"))
        title_tag = soup.find("title")
        title = normalize_text(title_tag.get_text()[:60]) if title_tag else "哈医大招聘公告"
        return [
            parse_job_from_text(
                title=title,
                body=text[:2000],
                source_url=source_url,
                institution_type=institution["institution_type"],
                region=institution["region"],
                parser_name="hrbmu-notice-v1",
                department=None,
            )
        ]

    # 解析表格：提取岗位和科室信息做汇总
    table = tables[0]
    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    # 解析表头
    header_cells = [td.get_text(strip=True) for td in rows[0].find_all(["td", "th"])]
    dept_col = next((i for i, h in enumerate(header_cells) if "科室" in h or "部门" in h), None)
    pos_col = next((i for i, h in enumerate(header_cells) if "岗位" in h), None)
    unit_col = next((i for i, h in enumerate(header_cells) if "单位" in h), None)

    # 聚合岗位类型
    positions: dict[str, set[str]] = {}  # 岗位 -> {科室集合}
    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if len(cells) <= max(filter(None, [dept_col, pos_col, unit_col]), default=0):
            continue
        pos = cells[pos_col] if pos_col is not None and pos_col < len(cells) else ""
        dept = cells[dept_col] if dept_col is not None and dept_col < len(cells) else ""
        if pos:
            positions.setdefault(pos, set()).add(dept)

    jobs: list[ParsedJob] = []
    for pos_name, depts in positions.items():
        dept_list = "、".join(sorted(depts)[:5])
        body = f"岗位：{pos_name}。涉及科室：{dept_list}。来源为拟聘公示表，反映实际录用岗位分布。"
        jobs.append(
            parse_job_from_text(
                title=f"哈尔滨医科大学{pos_name}岗位",
                body=body,
                source_url=source_url,
                institution_type=institution["institution_type"],
                region=institution["region"],
                parser_name="hrbmu-table-v1",
                department=None,
            )
        )
    return jobs


async def crawl_hrbmu(institution: dict[str, Any]) -> list[ParsedJob]:
    """抓取哈医大招聘列表并解析。"""
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
        for article in articles[:6]:
            try:
                art_resp = await client.get(article["url"])
                art_resp.raise_for_status()
                parsed = extract_jobs_from_table_article(
                    art_resp.text, article["url"], institution
                )
                jobs.extend(parsed)
            except httpx.HTTPError:
                continue
    return jobs
