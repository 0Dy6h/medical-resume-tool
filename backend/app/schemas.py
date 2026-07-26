from __future__ import annotations

from datetime import date
from typing import Any, Literal, Self

from pydantic import BaseModel, Field


# ── Profile sub-models ───────────────────────────────────────────────


class _HasOptionalId(BaseModel):
    """Mixin for profile items that may carry a client-side ID."""

    id: str | None = None


class BasicInfo(BaseModel):
    """Profile basics: name, contact, intended position, and summary."""

    name: str = ""
    phone: str = ""
    email: str = ""
    location: str = ""
    intended_position: str = ""
    summary: str = ""


class Skill(_HasOptionalId):
    """A named skill with an optional proficiency level."""

    name: str
    level: Literal["beginner", "intermediate", "advanced", "expert"] | None = None


class Experience(_HasOptionalId):
    """Work or internship experience entry."""

    organization: str
    role: str = ""
    start: str = ""
    end: str = ""
    highlights: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class Education(_HasOptionalId):
    """Educational background entry."""

    school: str
    degree: str = ""
    major: str = ""
    start: str = ""
    end: str = ""
    highlights: list[str] = Field(default_factory=list)


class Project(_HasOptionalId):
    """Research or project experience entry."""

    name: str
    role: str = ""
    highlights: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class Publication(_HasOptionalId):
    """Published paper or academic output."""

    title: str
    journal: str = ""
    year: str = ""
    authors: str = ""
    doi: str = ""


class Certificate(_HasOptionalId):
    """Professional certificate or qualification."""

    name: str
    issuer: str = ""
    year: str = ""


class Language(_HasOptionalId):
    """Language proficiency entry."""

    name: str
    level: str = ""


class Teaching(_HasOptionalId):
    """Teaching or instructional experience entry."""

    course: str
    role: str = ""
    institution: str = ""
    year: str = ""


class Award(_HasOptionalId):
    """Honor or award entry."""

    name: str
    issuer: str = ""
    year: str = ""
    level: str = ""


class Profile(BaseModel):
    """Complete typed profile aggregating all curriculum vitae sections.

    This is the canonical internal representation.  Use ``from_legacy_dict()``
    to migrate old dict-format profiles (e.g. from SQLite).
    """

    basics: BasicInfo = Field(default_factory=BasicInfo)
    education: list[Education] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    teaching: list[Teaching] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)

    @classmethod
    def from_legacy_dict(cls, data: dict[str, Any]) -> Profile:
        """Migrate an old dict-format profile to the typed Profile model.

        Handles the legacy ``basic`` key (renamed to ``basics``) and strips
        repository-level metadata like ``updated_at``.
        """
        data = dict(data)
        # Legacy key migration
        if "basic" in data and "basics" not in data:
            data["basics"] = data.pop("basic")
        elif "basic" in data:
            data.pop("basic")
        data.setdefault("basics", {})
        # Strip repository metadata
        data.pop("updated_at", None)
        return cls.model_validate(data)

    @property
    def is_empty(self) -> bool:
        """Return True when no collections have any entries."""
        collections = [
            self.education,
            self.experiences,
            self.projects,
            self.publications,
            self.certificates,
            self.skills,
            self.teaching,
            self.awards,
            self.languages,
        ]
        return not any(collections)


# ── Auth schemas ─────────────────────────────────────────────────────


class RegisterPayload(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class AuthOut(BaseModel):
    token: str
    username: str


# ── Institution / crawl schemas ──────────────────────────────────────


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
    user_status: dict[str, Any] | None = None


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
    """API payload for saving a profile.

    Accepts the legacy dict format as well as typed sub-model objects via
    the ``from_legacy_dict`` migration helper on ``Profile``.  The endpoint
    converts this payload into a ``Profile`` internally.
    """

    basics: BasicInfo = Field(default_factory=BasicInfo)
    education: list[Education] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    teaching: list[Teaching] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)

    def to_profile(self) -> Profile:
        """Convert this payload into a fully typed ``Profile``."""
        return Profile.model_validate(self.model_dump())

    @classmethod
    def from_old_dict_body(cls, body: dict[str, Any]) -> ProfilePayload:
        """Parse an arbitrary dict body (typed or legacy) into a ProfilePayload.

        This keeps backward compatibility with the old ``dict[str, Any]``
        values so the frontend does not need to change.
        """
        return cls(**body)


class ReviewItem(BaseModel):
    collection: str
    item: dict[str, Any]
    source_text: str
    confidence: float
    warnings: list[str] = Field(default_factory=list)


class UnassignedBlock(BaseModel):
    text: str
    reason: str


class ImportMeta(BaseModel):
    source_type: str
    extractor_name: str
    text_quality: float
    warnings: list[str] = Field(default_factory=list)


class ProfileImportOut(BaseModel):
    education: list[dict[str, Any]] = Field(default_factory=list)
    experiences: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    publications: list[dict[str, Any]] = Field(default_factory=list)
    certificates: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[dict[str, Any]] = Field(default_factory=list)
    teaching: list[dict[str, Any]] = Field(default_factory=list)
    awards: list[dict[str, Any]] = Field(default_factory=list)
    languages: list[dict[str, Any]] = Field(default_factory=list)
    review_items: list[ReviewItem] = Field(default_factory=list)
    unassigned_blocks: list[UnassignedBlock] = Field(default_factory=list)
    import_meta: ImportMeta | None = None
    warnings: list[str] = Field(default_factory=list)


class ResumeDraftCreate(BaseModel):
    job_id: int


class ResumeDraftUpdate(BaseModel):
    sections: list[dict[str, Any]]


class JobStatusPayload(BaseModel):
    status: Literal["saved", "evaluating", "preparing", "applied", "archived"] = "saved"
    note: str | None = Field(default=None, max_length=1000)
    deadline: date | None = None


class JobStatusOut(BaseModel):
    job_id: int
    status: str
    note: str | None = None
    deadline: str | None = None
    created_at: str
    updated_at: str


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
ExportMode = Literal["application", "diagnostic"]


# ── JD Structuring (P0-3) ────────────────────────────────────────────────

class JDRequirement(BaseModel):
    """Structured job requirement extracted by LLM."""
    category: str = ""
    requirement: str = ""
    must_have: bool = True


class StructuredJDOut(BaseModel):
    """LLM-structured job description output."""
    job_title: str = ""
    requirements: list[JDRequirement] = Field(default_factory=list)
    summary: str = ""
