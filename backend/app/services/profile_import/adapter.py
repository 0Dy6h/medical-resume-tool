"""适配器：将旧解析器输出转换为新合同格式。"""
from __future__ import annotations

from typing import Any

from app.services.profile_import.facts import ProfileImportContract


def legacy_to_contract(parsed: dict[str, Any], extraction_warnings: list[str]) -> ProfileImportContract:
    """将旧 parse_profile_from_lines 输出转成新合同格式。"""
    contract = ProfileImportContract(
        education=parsed.get("education", []),
        experiences=parsed.get("experiences", []),
        projects=parsed.get("projects", []),
        publications=parsed.get("publications", []),
        certificates=parsed.get("certificates", []),
        skills=parsed.get("skills", []),
        teaching=parsed.get("teaching", []),
        awards=parsed.get("awards", []),
        languages=parsed.get("languages", []),
        warnings=[*extraction_warnings, *parsed.get("warnings", [])],
        import_meta={
            "source_type": "legacy",
            "extractor_name": "rule-based-v1",
            "text_quality": 0.8,
            "warnings": [],
        },
    )
    return contract
