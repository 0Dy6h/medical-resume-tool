from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from openpyxl import load_workbook

from app.services.classifier import normalize_text
from app.services.crawler import ParsedJob, parse_job_from_text


SUPPORTED_ATTACHMENT_EXTENSIONS = {".xlsx", ".xls", ".pdf"}


@dataclass(frozen=True)
class XlsxRow:
    sheet_name: str
    row_index: int
    headers: list[str]
    values: dict[str, str]
    raw_text: str


def extract_attachment_links(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    attachments: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        absolute_url = urljoin(base_url, href)
        extension = _extension_from_url(absolute_url)
        if extension not in SUPPORTED_ATTACHMENT_EXTENSIONS:
            continue
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        name = normalize_text(anchor.get_text(" ")) or absolute_url.rsplit("/", 1)[-1]
        attachments.append({"name": name, "url": absolute_url, "extension": extension})
    return attachments


def parse_xlsx_table(content: bytes) -> list[XlsxRow]:
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    rows: list[XlsxRow] = []
    for sheet in workbook.worksheets:
        table = list(sheet.iter_rows(values_only=True))
        if len(table) < 2:
            continue
        header_index, headers = _find_header_row(table)
        if not headers:
            continue
        for offset, row in enumerate(table[header_index + 1 :], start=header_index + 2):
            values = _row_values(headers, row)
            if not values:
                continue
            raw_text = "；".join(f"{key}：{value}" for key, value in values.items())
            rows.append(
                XlsxRow(
                    sheet_name=str(sheet.title),
                    row_index=offset,
                    headers=headers,
                    values=values,
                    raw_text=raw_text,
                )
            )
    workbook.close()
    return rows


def build_jobs_from_xlsx_attachment(
    *,
    content: bytes,
    attachment: dict[str, str],
    announcement_url: str,
    institution: dict[str, Any],
    parser_name: str,
    parser_warning: str | None = None,
) -> list[ParsedJob]:
    jobs: list[ParsedJob] = []
    for row in parse_xlsx_table(content):
        title = _pick(row.values, ["岗位名称", "招聘岗位", "岗位", "职位名称", "职位"])
        unit = _pick(row.values, ["招聘单位", "单位", "用人部门", "部门", "科室"])
        profession = _pick(row.values, ["专业", "所学专业", "专业要求"])
        education = _pick(row.values, ["学历", "学历要求", "学位", "学历学位"])
        if not title:
            title = _fallback_title(row.values, attachment["name"])
        body_parts = []
        if unit:
            body_parts.append(f"招聘单位：{unit}")
        if profession:
            body_parts.append(f"专业要求：{profession}")
        if education:
            body_parts.append(f"学历要求：{education}")
        body_parts.append(row.raw_text)
        job = parse_job_from_text(
            title=title,
            body="。".join(body_parts),
            source_url=f"{attachment['url']}#{row.sheet_name}-{row.row_index}",
            institution_type=institution["institution_type"],
            region=institution["region"],
            parser_name=parser_name,
            department=unit,
        )
        evidence = dict(job.extraction_evidence)
        evidence.update(
            {
                "announcement_url": announcement_url,
                "attachment_url": attachment["url"],
                "attachment_name": attachment["name"],
                "sheet_name": row.sheet_name,
                "row_index": row.row_index,
                "headers": row.headers,
            }
        )
        if parser_warning:
            evidence["parser_warning"] = parser_warning
        jobs.append(_replace_evidence(job, evidence))
    return jobs


def attachment_status(attachment: dict[str, str], status: str, error: str | None = None) -> dict[str, str]:
    payload = {
        "name": attachment["name"],
        "url": attachment["url"],
        "extension": attachment["extension"],
        "status": status,
    }
    if error:
        payload["error"] = error
    return payload


def _extension_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for extension in SUPPORTED_ATTACHMENT_EXTENSIONS:
        if path.endswith(extension):
            return extension
    return ""


def _find_header_row(table: list[tuple[Any, ...]]) -> tuple[int, list[str]]:
    for index, row in enumerate(table[:10]):
        headers = [_cell_text(value) for value in row]
        headers = [value for value in headers if value]
        if len(headers) >= 2 and any(_is_job_header(value) for value in headers):
            return index, headers
    first = [_cell_text(value) for value in table[0]]
    first = [value for value in first if value]
    return (0, first) if len(first) >= 2 else (0, [])


def _row_values(headers: list[str], row: tuple[Any, ...]) -> dict[str, str]:
    values: dict[str, str] = {}
    for header, value in zip(headers, row):
        text = _cell_text(value)
        if text:
            values[header] = text
    return values


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return normalize_text(str(value))


def _is_job_header(value: str) -> bool:
    return any(keyword in value for keyword in ["岗位", "职位", "专业", "学历", "招聘单位", "科室"])


def _pick(values: dict[str, str], candidates: list[str]) -> str:
    for candidate in candidates:
        for key, value in values.items():
            if candidate in key and value:
                return value
    return ""


def _fallback_title(values: dict[str, str], attachment_name: str) -> str:
    for key, value in values.items():
        if any(keyword in key for keyword in ["岗位", "职位", "专业"]):
            return value
    first_value = next(iter(values.values()), "")
    return first_value or attachment_name.replace(".xlsx", "").replace(".xls", "")


def _replace_evidence(job: ParsedJob, evidence: dict[str, Any]) -> ParsedJob:
    return ParsedJob(
        title=job.title,
        department=job.department,
        location=job.location,
        education=job.education,
        profession=job.profession,
        job_category=job.job_category,
        responsibilities=job.responsibilities,
        requirements=job.requirements,
        posted_at=job.posted_at,
        deadline=job.deadline,
        source_url=job.source_url,
        source_text_hash=job.source_text_hash,
        raw_text=job.raw_text,
        tags=job.tags,
        extraction_evidence=evidence,
        fetched_at=job.fetched_at,
        parser_name=job.parser_name,
        confidence=job.confidence,
    )
