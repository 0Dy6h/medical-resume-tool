"""履历资料导入：文档提取 + 事实识别 + 来源追踪。"""
from __future__ import annotations

from app.services.profile_import.adapter import legacy_to_contract
from app.services.profile_import.facts import (
    ExtractedFact,
    ProfileImportContract,
)
from app.services.profile_import.legacy import (
    _ocr_image_bytes,
    extract_docx_text,
    extract_profile_text,
    parse_profile_from_lines,
    ProfileImportError,
    ProfileTextExtraction,
)
from app.services.profile_import.pipeline import build_profile_contract

__all__ = [
    "ExtractedFact",
    "ProfileImportContract",
    "_ocr_image_bytes",
    "extract_docx_text",
    "extract_profile_text",
    "parse_profile_from_lines",
    "legacy_to_contract",
    "build_profile_contract",
    "ProfileImportError",
    "ProfileTextExtraction",
]
