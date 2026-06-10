from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class InstitutionOut(BaseModel):
    id: int
    name: str
    institution_type: str
    region: str
    official_url: str
    listing_url: str
    crawl_strategy: str
    enabled: bool
    last_crawled_at: str | None = None
    last_status: str | None = None
    last_error: str | None = None


class CrawlRunCreate(BaseModel):
    institution_ids: list[int] | None = None


class CrawlRunOut(BaseModel):
    id: int
    status: str
    started_at: str
    completed_at: str | None = None
    institution_ids: list[int]
    success_count: int
    failure_count: int
    error_summary: list[dict[str, Any]]
    errors: list[dict[str, Any]]


class RawSnapshot(BaseModel):
    source_url: str
    source_text_hash: str
    fetched_at: str
    raw_text: str


class JobOut(BaseModel):
    id: int
    institution_id: int
    institution_name: str
    institution_type: str
    region: str
    title: str
    department: str | None = None
    location: str | None = None
    education: str | None = None
    profession: str | None = None
    job_category: str
    responsibilities: str | None = None
    requirements: str | None = None
    posted_at: str | None = None
    deadline: str | None = None
    source_url: str
    source_text_hash: str
    tags: list[str]
    fetched_at: str
    parser_name: str
    confidence: float


class JobListOut(BaseModel):
    total: int
    items: list[JobOut]
    limit: int = 100
    offset: int = 0


class JobDetailOut(JobOut):
    raw_snapshot: RawSnapshot
    extraction_evidence: dict[str, Any]


class AnalyticsSummary(BaseModel):
    totals: dict[str, int]
    job_categories: list[dict[str, Any]]
    education_levels: list[dict[str, Any]]
    institution_types: list[dict[str, Any]]
    regions: list[dict[str, Any]]
    common_capabilities: list[dict[str, Any]]
    institution_focus: list[dict[str, Any]]
    parser_quality: list[dict[str, Any]]


class ProfilePayload(BaseModel):
    basic: dict[str, Any] = Field(default_factory=dict)
    education: list[dict[str, Any]] = Field(default_factory=list)
    experiences: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    publications: list[dict[str, Any]] = Field(default_factory=list)
    certificates: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[dict[str, Any]] = Field(default_factory=list)
    teaching: list[dict[str, Any]] = Field(default_factory=list)
    awards: list[dict[str, Any]] = Field(default_factory=list)
    languages: list[dict[str, Any]] = Field(default_factory=list)


class ResumeDraftCreate(BaseModel):
    job_id: int


class ResumeDraftUpdate(BaseModel):
    sections: list[dict[str, Any]]


class ResumeDraftOut(BaseModel):
    id: int
    job_id: int
    profile_id: str
    title: str
    sections: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    created_at: str
    updated_at: str


class ReportCreate(BaseModel):
    title: str = "医疗岗位市场分析报告"
    filters: dict[str, Any] = Field(default_factory=dict)


class ReportOut(BaseModel):
    id: int
    title: str
    markdown: str
    html: str
    filters: dict[str, Any]
    created_at: str


ExportFormat = Literal["docx", "pdf"]
