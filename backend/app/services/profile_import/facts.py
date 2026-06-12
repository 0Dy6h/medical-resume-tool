"""履历事实数据结构与导入合同。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentLine:
    """文档中的一行，保留来源位置。"""
    text: str
    page: int | None = None
    block_index: int | None = None
    line_index: int | None = None
    source_kind: str = "text"  # paragraph/table/pdf_block/ocr


@dataclass
class DocumentBlock:
    """文档中的一个语义块。"""
    text: str
    lines: list[DocumentLine]
    kind: str  # heading/item/bullet/table_row/free_text
    section_hint: str | None = None


@dataclass
class ExtractedFact:
    """识别出的一个履历事实。"""
    collection: str  # education/experiences/projects/publications/certificates/skills/teaching/awards/languages
    fields: dict[str, Any]
    source_text: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ProfileImportContract:
    """导入预览合同：已识别 + 待确认 + 未归类。"""
    education: list[dict[str, Any]] = field(default_factory=list)
    experiences: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    publications: list[dict[str, Any]] = field(default_factory=list)
    certificates: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)
    teaching: list[dict[str, Any]] = field(default_factory=list)
    awards: list[dict[str, Any]] = field(default_factory=list)
    languages: list[dict[str, Any]] = field(default_factory=list)
    review_items: list[dict[str, Any]] = field(default_factory=list)
    unassigned_blocks: list[dict[str, str]] = field(default_factory=list)
    import_meta: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转成 API 响应字典。"""
        return {
            "education": self.education,
            "experiences": self.experiences,
            "projects": self.projects,
            "publications": self.publications,
            "certificates": self.certificates,
            "skills": self.skills,
            "teaching": self.teaching,
            "awards": self.awards,
            "languages": self.languages,
            "review_items": self.review_items,
            "unassigned_blocks": self.unassigned_blocks,
            "import_meta": self.import_meta,
            "warnings": self.warnings,
        }
