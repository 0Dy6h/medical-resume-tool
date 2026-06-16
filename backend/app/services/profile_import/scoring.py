"""Confidence scoring for extracted profile facts."""
from __future__ import annotations

from typing import Any

from app.services.profile_import.facts import ExtractedFact


def score(fact: ExtractedFact, signals: dict[str, Any]) -> float:
    """Return a bounded confidence score for a fact and its evidence signals."""
    value = 0.4
    if signals.get("section_hint"):
        value += 0.15
    if signals.get("time_range"):
        value += 0.10
    if signals.get("core_entity"):
        value += 0.15
    if signals.get("role_or_degree"):
        value += 0.10
    if signals.get("highlight"):
        value += 0.05
    if signals.get("strong_match"):
        value += 0.15
    if signals.get("many_missing_fields") or len(fact.source_text.strip()) < 4:
        value -= 0.10
    return round(max(0.0, min(1.0, value)), 2)
