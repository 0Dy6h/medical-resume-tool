from __future__ import annotations

from datetime import date
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, ValidationError, field_validator


# ── Profile sub-models ───────────────────────────────────────────────


SKILL_LEVELS = ("beginner", "intermediate", "advanced", "expert")

# Legacy/free-text proficiency wording seen in profiles saved before the typed
# schema landed.  Anything unrecognised degrades to None rather than 500-ing.
_LEVEL_ALIASES = {
    "入门": "beginner",
    "了解": "beginner",
    "初级": "beginner",
    "一般": "intermediate",
    "中级": "intermediate",
    "掌握": "intermediate",
    "熟悉": "intermediate",
    "熟练": "advanced",
    "高级": "advanced",
    "精通": "expert",
    "专家": "expert",
}


class _HasOptionalId(BaseModel):
    """Mixin for profile items that may carry a client-side ID.

    Every concrete item keeps all of its fields optional on purpose: the editor
    creates a blank row first and the user fills it in progressively, so a
    partially-typed row must round-trip instead of failing validation.  The
    real invariant — *a persisted item is not entirely blank* — is enforced
    once, at the payload boundary, by ``_drop_blank_items()``.
    """

    id: str | None = None

    @property
    def is_blank(self) -> bool:
        """True when the item carries no content beyond its client-side id."""
        for name, value in self.model_dump(exclude={"id"}).items():
            del name
            if isinstance(value, list):
                if any(str(entry).strip() for entry in value):
                    return False
            elif value is not None and str(value).strip():
                return False
        return True


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

    name: str = ""
    level: Literal["beginner", "intermediate", "advanced", "expert"] | None = None

    @field_validator("level", mode="before")
    @classmethod
    def _coerce_level(cls, value: Any) -> Any:
        """Map legacy free-text levels ("熟练") onto the enum; drop unknowns.

        Pre-P0-1 profiles stored whatever the user typed here.  Rejecting those
        rows would make the owning account's profile permanently unreadable, so
        an unrecognised level degrades to None instead.
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.lower() in SKILL_LEVELS:
            return text.lower()
        return _LEVEL_ALIASES.get(text)


class Experience(_HasOptionalId):
    """Work or internship experience entry."""

    organization: str = ""
    role: str = ""
    start: str = ""
    end: str = ""
    highlights: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class Education(_HasOptionalId):
    """Educational background entry."""

    school: str = ""
    degree: str = ""
    major: str = ""
    start: str = ""
    end: str = ""
    highlights: list[str] = Field(default_factory=list)


class Project(_HasOptionalId):
    """Research or project experience entry."""

    name: str = ""
    role: str = ""
    highlights: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class Publication(_HasOptionalId):
    """Published paper or academic output."""

    title: str = ""
    journal: str = ""
    year: str = ""
    authors: str = ""
    doi: str = ""

    @field_validator("authors", mode="before")
    @classmethod
    def _join_authors(cls, value: Any) -> Any:
        """Accept the editor's multi-line author input as a single string.

        The frontend renders 作者 as a textarea, which yields a list of lines.
        """
        if isinstance(value, (list, tuple)):
            return "、".join(str(entry).strip() for entry in value if str(entry).strip())
        return value


class Certificate(_HasOptionalId):
    """Professional certificate or qualification."""

    name: str = ""
    issuer: str = ""
    year: str = ""


class Language(_HasOptionalId):
    """Language proficiency entry."""

    name: str = ""
    level: str = ""


class Teaching(_HasOptionalId):
    """Teaching or instructional experience entry."""

    course: str = ""
    role: str = ""
    institution: str = ""
    year: str = ""


class Award(_HasOptionalId):
    """Honor or award entry."""

    name: str = ""
    issuer: str = ""
    year: str = ""
    level: str = ""


#: Canonical order of the profile's item collections.  Single source of truth —
#: ``resume.PROFILE_COLLECTIONS`` re-exports this.
PROFILE_COLLECTION_NAMES = (
    "education",
    "experiences",
    "projects",
    "publications",
    "certificates",
    "skills",
    "teaching",
    "awards",
    "languages",
)


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
    mode: Literal["fresh_grad", "experienced"] = "experienced"

    @classmethod
    def from_legacy_dict(cls, data: dict[str, Any]) -> Profile:
        """Migrate an old dict-format profile to the typed Profile model.

        Handles the legacy ``basic`` key (renamed to ``basics``) and strips
        repository-level metadata like ``updated_at``.

        Never raises on stored data.  Profiles written before the typed schema
        landed may hold values this model cannot represent; losing one malformed
        entry is recoverable, but a ``ValidationError`` here would make the
        owning account's profile — and every export that reads it — permanently
        unreadable.  Unparsable entries are therefore skipped individually.
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
        try:
            return cls.model_validate(data)
        except ValidationError:
            return cls._salvage(data)

    @classmethod
    def _salvage(cls, data: dict[str, Any]) -> Profile:
        """Rebuild a Profile from legacy data, dropping only what cannot parse."""
        salvaged: dict[str, Any] = {}
        try:
            salvaged["basics"] = BasicInfo.model_validate(data.get("basics") or {})
        except ValidationError:
            salvaged["basics"] = BasicInfo()
        for name in PROFILE_COLLECTION_NAMES:
            field = cls.model_fields[name]
            item_model = field.annotation.__args__[0]  # list[Item] -> Item
            kept = []
            for entry in data.get(name) or []:
                try:
                    kept.append(item_model.model_validate(entry))
                except ValidationError:
                    continue
            salvaged[name] = kept
        # Pass through scalar fields with defaults (e.g. mode)
        for name in ("mode",):
            if name in data and data[name] is not None:
                salvaged[name] = data[name]
        return cls(**salvaged)

    @property
    def is_empty(self) -> bool:
        """Return True when no collection holds an item with any content."""
        return not any(
            item for name in PROFILE_COLLECTION_NAMES
            for item in getattr(self, name)
            if not item.is_blank
        )


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
    consecutive_failures: int = 0
    blocked_reason: str | None = None


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
    trigger: str = "manual"


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
    data_trust: str = "real"
    user_status: dict[str, Any] | None = None
    match: dict[str, Any] | None = None


class JobListOut(BaseModel):
    total: int
    items: list[JobOut]
    limit: int = 100
    offset: int = 0


class JobSnapshotOut(BaseModel):
    """岗位历史版本快照（A4 溯源：公告改版后的旧正文）。"""
    source_text_hash: str
    raw_text: str
    parser_name: str
    fetched_at: str
    captured_at: str


class JobDetailOut(JobOut):
    raw_snapshot: RawSnapshot
    extraction_evidence: dict[str, Any]
    match_analysis: list[dict[str, Any]] | None = None
    history: list[JobSnapshotOut] = []


class AnalyticsSummary(BaseModel):
    totals: dict[str, int]
    job_categories: list[dict[str, Any]]
    education_levels: list[dict[str, Any]]
    institution_types: list[dict[str, Any]]
    regions: list[dict[str, Any]]
    common_capabilities: list[dict[str, Any]]
    institution_focus: list[dict[str, Any]]
    parser_quality: list[dict[str, Any]]
    trust_breakdown: list[dict[str, Any]] = []
    generated_at: str | None = None


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
    mode: Literal["fresh_grad", "experienced"] = "experienced"

    def to_profile(self) -> Profile:
        """Convert this payload into a fully typed ``Profile``.

        Rows the user added in the editor but never filled in are dropped here
        rather than rejected, so an untouched blank row cannot block a save that
        is otherwise valid.
        """
        data = self.model_dump()
        for name in PROFILE_COLLECTION_NAMES:
            items = getattr(self, name)
            data[name] = [item.model_dump() for item in items if not item.is_blank]
        return Profile.model_validate(data)

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
    basics: dict[str, str] = Field(default_factory=dict)
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


_VALID_DECISIONS = ("adopt", "edit", "remove")


class ResumeDraftUpdate(BaseModel):
    sections: list[dict[str, Any]]

    @field_validator("sections")
    @classmethod
    def validate_decisions(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """审阅决策只接受 adopt/edit/remove（未决策为缺省）。

        sections 是自由 dict,没有这里的前置校验,任意字符串（如 "maybe"）
        会被原样入库并回显,审阅生命周期与导出守卫都无法解释它。
        """
        for section in v:
            for item in section.get("items") or []:
                decision = item.get("decision")
                if decision is not None and decision not in _VALID_DECISIONS:
                    raise ValueError(
                        f"decision 仅支持 {'/'.join(_VALID_DECISIONS)}，收到 {decision!r}"
                    )
        return v


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
    status: str = "draft"
    created_at: str
    updated_at: str


class ResumeDraftSummaryOut(BaseModel):
    id: int
    job_id: int
    title: str
    status: str = "draft"
    created_at: str
    updated_at: str


_REPORT_FILTER_KEYS = {
    "keyword",
    "institution_id",
    "region",
    "job_category",
    "education",
    "institution_type",
    "tag",
    "trust",
    "fresh_days",
}
_TRUST_FILTER_VALUES = {"real", "placeholder", "fixture", "disabled"}


def _is_int_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        try:
            int(value)
            return True
        except ValueError:
            return False
    return False


class ReportCreate(BaseModel):
    title: str = "医疗岗位市场分析报告"
    filters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Reject free-form filters before they reach build_jobs_where_clause.

        The SQL builder silently ignores unknown keys and would crash on a
        non-numeric ``fresh_days`` (``int()``), so an invalid slice must be
        refused here rather than reported as a full-dataset or 500 report.
        """
        unknown = sorted(set(v) - _REPORT_FILTER_KEYS)
        if unknown:
            raise ValueError(f"不支持的筛选字段：{', '.join(unknown)}")
        trust = v.get("trust")
        if trust is not None and trust not in _TRUST_FILTER_VALUES:
            raise ValueError("trust 仅支持 real/placeholder/fixture/disabled")
        institution_id = v.get("institution_id")
        if institution_id is not None and not _is_int_like(institution_id):
            raise ValueError("institution_id 必须是机构 ID 整数")
        fresh_days = v.get("fresh_days")
        if fresh_days is not None:
            if not _is_int_like(fresh_days):
                raise ValueError("fresh_days 必须是整数天数")
            if int(fresh_days) < 1:
                raise ValueError("fresh_days 必须 ≥ 1（与岗位列表接口口径一致）")
            if int(fresh_days) > 3650:
                raise ValueError("fresh_days 必须 ≤ 3650（10 年上限，防止时间差溢出）")
        return v


class ReportOut(BaseModel):
    id: int
    title: str
    markdown: str
    html: str
    filters: dict[str, Any]
    created_at: str


ExportFormat = Literal["docx", "pdf"]
ExportMode = Literal["application", "diagnostic"]


# ── Subscriptions (PRD 4.1) ──────────────────────────────────────────


class SubscriptionInstitutionStatus(BaseModel):
    """Status of an institution within a subscription."""
    id: int
    name: str
    is_maintenance: bool


class SubscriptionCreate(BaseModel):
    """Payload for creating a subscription."""
    name: str = Field(min_length=2, max_length=30)
    keyword: str = Field(min_length=1, max_length=50)
    institution_ids: list[int] | None = Field(default=None)

    @field_validator("institution_ids")
    @classmethod
    def _check_institution_count(cls, value: list[int] | None) -> list[int] | None:
        if value is not None:
            if len(value) < 1 or len(value) > 12:
                raise ValueError("机构数量必须在 1-12 之间")
        return value

    @field_validator("keyword")
    @classmethod
    def _check_keyword_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("关键词不能为空")
        return value.strip()


class SubscriptionOut(BaseModel):
    """Subscription with push status for the frontend."""
    id: int
    name: str
    keyword: str
    institution_ids: list[int]
    institution_statuses: list[SubscriptionInstitutionStatus]
    new_count: int
    last_checked_at: str
    last_pushed_at: str | None = None
    is_empty_30d: bool
    warning: str | None = None
    created_at: str


class SubscriptionScanOut(BaseModel):
    """Result of a subscription scan."""
    scanned: int
    pushed: int
    notified: int = 0


class NotificationOut(BaseModel):
    """站内通知（B2 订阅触达）：一次订阅扫描产生的新岗位摘要。"""
    id: int
    subscription_id: int
    subscription_name: str
    keyword: str
    job_count: int
    job_ids: list[int]
    summary: str
    created_at: str
    read: bool
