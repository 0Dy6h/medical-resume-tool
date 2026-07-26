"""Arithmetic gate for degree/学历 requirements.

A degree requirement expresses an ordinal floor ("硕士研究生及以上学历"), which
similarity scoring cannot evaluate: the fuzzy matcher gives a 本科 profile and a
硕士 profile the same score against a 硕士 requirement whenever the requirement
text also mentions 本科.  Degree level is therefore decided by comparing ordinals,
not by overlap.

The gate returns one of three outcomes so the caller can be honest with the user:
``met`` (evidence, traceable to the education entry), ``not_met`` (a hard gap —
the applicant is categorically ineligible), or ``unknown`` (the profile has no
degree to compare, so the requirement is surfaced for the user to confirm).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Degree names mapped to an ordinal level.  研究生 without qualification means
#: 硕士研究生 in these announcements, so it maps to the 硕士 level.
_DEGREE_LEVELS: dict[str, int] = {
    "大专": 1, "专科": 1, "高职": 1,
    "本科": 2, "学士": 2,
    "硕士": 3, "研究生": 3, "碩士": 3,
    "博士": 4, "博士研究生": 4,
}

#: Longest names first so "博士研究生" wins over "研究生", "本科" over bare matches.
_DEGREE_PATTERN = re.compile("|".join(sorted(_DEGREE_LEVELS, key=len, reverse=True)))

#: Marks a clause as being *primarily* about degree attainment: it names an
#: attainment noun (学历/学位) or attaches an "以上" floor to a degree.  A clause
#: that only mentions a degree in passing ("…统计博士，发表论文，具备教学能力")
#: is compound and must go to fuzzy matching so its other facets can match too.
_DEGREE_FLOOR_MARKER = re.compile(r"学历|学位|(?:大专|专科|高职|本科|学士|硕士|研究生|博士)(?:研究生)?\s*(?:（?\s*含\s*）?)?\s*(?:及|或)?\s*以上")

#: A compound clause this long is not a pure degree requirement even with a
#: marker; fuzzy matching handles its several facets better than the gate.
_MAX_GATE_LEN = 30

#: "…及以上" / "…以上" / "…（含）以上" — the degree it follows is the floor.
_OR_ABOVE = re.compile(r"(大专|专科|高职|本科|学士|硕士|研究生|博士)(?:研究生)?\s*(?:（?\s*含\s*）?)?\s*(?:及|或)?\s*以上")

_LEVEL_NAMES = {1: "大专", 2: "本科", 3: "硕士", 4: "博士"}


@dataclass(frozen=True)
class DegreeGateResult:
    """Outcome of evaluating a degree requirement against a profile."""

    outcome: str  # "met" | "not_met" | "unknown"
    required_level: int
    profile_level: int | None
    profile_field_id: str | None
    message: str


def is_degree_requirement(requirement: str) -> bool:
    """True when a requirement is primarily about degree attainment.

    Requires both a degree name and an explicit floor marker (学历/学位 or an
    "以上" qualifier), and excludes long compound clauses, so a requirement that
    merely mentions a degree alongside other competencies is left to fuzzy
    matching.
    """
    if len(requirement) > _MAX_GATE_LEN:
        return False
    return bool(_DEGREE_PATTERN.search(requirement)) and bool(_DEGREE_FLOOR_MARKER.search(requirement))


def required_degree_level(requirement: str) -> int | None:
    """The minimum degree level a requirement demands, or None.

    Prefers the degree attached to an "以上" qualifier ("硕士及以上" -> 硕士).
    Absent that, uses the lowest degree named, since "本科、硕士" as alternatives
    means 本科 is the floor.
    """
    floors = [_DEGREE_LEVELS[name.replace("研究生", "研究生")] if name in _DEGREE_LEVELS else _DEGREE_LEVELS.get(name)
              for name in _OR_ABOVE.findall(requirement)]
    floors = [level for level in floors if level]
    if floors:
        return min(floors)
    mentioned = [_DEGREE_LEVELS[match] for match in _DEGREE_PATTERN.findall(requirement)]
    return min(mentioned) if mentioned else None


def highest_profile_degree(education: list[dict]) -> tuple[int, str] | None:
    """The applicant's highest degree as (level, field_id), or None.

    Reads each education entry's ``degree`` first, then falls back to any degree
    word in the entry so "临床医学博士" is still recognised.
    """
    best: tuple[int, str] | None = None
    for index, entry in enumerate(education):
        field_id = entry.get("id") or f"education-{index + 1}"
        haystack = f"{entry.get('degree', '')} {entry.get('major', '')} {entry.get('school', '')}"
        found = _DEGREE_PATTERN.findall(haystack)
        if not found:
            continue
        level = max(_DEGREE_LEVELS[name] for name in found)
        if best is None or level > best[0]:
            best = (level, field_id)
    return best


def evaluate_degree_gate(requirement: str, education: list[dict]) -> DegreeGateResult | None:
    """Evaluate a degree requirement against the profile's education.

    Returns None when the requirement is not a degree requirement (so the caller
    falls back to fuzzy matching).
    """
    required = required_degree_level(requirement)
    if required is None or not is_degree_requirement(requirement):
        return None

    highest = highest_profile_degree(education)
    required_name = _LEVEL_NAMES.get(required, "相应")
    if highest is None:
        return DegreeGateResult(
            outcome="unknown",
            required_level=required,
            profile_level=None,
            profile_field_id=None,
            message=f"岗位要求{required_name}及以上学历，请确认你的学历是否满足",
        )

    profile_level, field_id = highest
    profile_name = _LEVEL_NAMES.get(profile_level, "现有")
    if profile_level >= required:
        return DegreeGateResult(
            outcome="met",
            required_level=required,
            profile_level=profile_level,
            profile_field_id=field_id,
            message=f"学历满足要求（要求{required_name}及以上，你为{profile_name}）",
        )
    return DegreeGateResult(
        outcome="not_met",
        required_level=required,
        profile_level=profile_level,
        profile_field_id=field_id,
        message=f"学历不满足：岗位要求{required_name}及以上，你的最高学历为{profile_name}",
    )
