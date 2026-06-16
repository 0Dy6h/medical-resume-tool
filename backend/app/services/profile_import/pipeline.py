"""Profile import assembly pipeline for line-based fact extraction."""
from __future__ import annotations

from typing import Any

from app.services.profile_import.blocks import build_blocks
from app.services.profile_import.extractors import COLLECTIONS, extract_facts
from app.services.profile_import.facts import ExtractedFact, ProfileImportContract


AUTO_THRESHOLD = 0.75
REVIEW_THRESHOLD = 0.45


def build_profile_contract(lines: list[str], extraction_warnings: list[str]) -> ProfileImportContract:
    """Build the API import-preview contract from extracted text lines."""
    blocks = build_blocks(lines)
    facts = extract_facts(blocks)
    contract = ProfileImportContract(warnings=list(extraction_warnings))
    assigned_source_texts: set[str] = set()

    for fact in facts:
        if fact.confidence >= AUTO_THRESHOLD:
            _append_fact(contract, fact)
            assigned_source_texts.add(fact.source_text)
        elif fact.confidence >= REVIEW_THRESHOLD:
            contract.review_items.append(_review_item(fact))
            assigned_source_texts.add(fact.source_text)

    for block in blocks:
        if block.text not in assigned_source_texts:
            contract.unassigned_blocks.append({"text": block.text, "reason": "未命中可导入事实"})

    _dedupe_contract(contract)
    contract.import_meta = {
        "source_type": "lines",
        "extractor_name": "fact-extractor-v1",
        "text_quality": _text_quality(len(blocks), len(assigned_source_texts)),
        "warnings": list(extraction_warnings),
    }
    return contract


def _append_fact(contract: ProfileImportContract, fact: ExtractedFact) -> None:
    if fact.collection not in COLLECTIONS:
        return
    collection = getattr(contract, fact.collection)
    collection.append(fact.fields)


def _review_item(fact: ExtractedFact) -> dict[str, Any]:
    return {
        "collection": fact.collection,
        "item": fact.fields,
        "source_text": fact.source_text,
        "confidence": fact.confidence,
        "warnings": fact.warnings,
    }


def _dedupe_contract(contract: ProfileImportContract) -> None:
    contract.skills = _dedupe_by_fields(contract.skills, ("name",))
    contract.languages = _dedupe_by_fields(contract.languages, ("name", "level"))
    contract.certificates = _dedupe_by_fields(contract.certificates, ("name", "year"))
    contract.education = _dedupe_by_fields(contract.education, ("school", "degree", "major", "start", "end"))
    contract.experiences = _dedupe_by_fields(contract.experiences, ("organization", "role", "start", "end"))
    contract.projects = _dedupe_by_fields(contract.projects, ("name", "role"))


def _dedupe_by_fields(items: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(field, "") for field in fields)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _text_quality(block_count: int, assigned_count: int) -> float:
    if block_count == 0:
        return 0.0
    return round(assigned_count / block_count, 2)
