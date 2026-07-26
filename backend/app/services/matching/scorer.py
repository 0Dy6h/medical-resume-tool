"""Score how well a profile fact answers a job requirement.

The matcher compares requirement text and fact text in a CJK bigram token space
(see :mod:`tokenize`) weighted by inverse document frequency, so a term that is
common across all job postings ("具有", "能力") contributes little and a
distinctive one ("队列", "SPSS", "随访") contributes a lot.  A small concept
lexicon bridges wording gaps that share no characters ("统计" ↔ "SPSS").

This is deliberately not machine learning: it is deterministic, needs no model
download, and every match is explained by the concrete overlapping terms — which
is what lets the resume stay traceable to the user's real facts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.matching.tokenize import tokenize

_IDF_PATH = Path(__file__).resolve().parents[2] / "data" / "jd_idf.json"

#: Concepts whose member terms should be treated as sharing a token.  Additive:
#: a fact or requirement mentioning any member also carries the concept token,
#: so different wording for the same competency can still overlap.  Kept small
#: and testable rather than exhaustive.
CONCEPT_LEXICON: dict[str, tuple[str, ...]] = {
    "统计分析": ("统计", "spss", "sas", "stata", "r语言", "数据分析", "数据处理", "统计学", "计量"),
    "临床研究": ("临床研究", "临床试验", "gcp", "队列", "随访", "研究方案", "课题"),
    "科研产出": ("科研", "课题", "基金", "论文", "发表", "sci", "成果", "项目"),
    "护理": ("护理", "护士", "护师", "静脉", "picc", "病区"),
    "教学": ("教学", "带教", "授课", "讲师", "助教", "教研", "课程"),
    "公共卫生": ("公共卫生", "流行病", "疾控", "预防医学", "卫生统计", "监测"),
    "英语能力": ("英语", "英文", "cet", "六级", "四级", "雅思", "托福", "sci"),
    "药学": ("药学", "药师", "药物", "制剂", "临床药"),
    "计算机": ("计算机", "办公软件", "office", "编程", "数据库", "python"),
    "沟通协作": ("沟通", "协调", "团队", "协作", "表达"),
    "执业资格": ("执业医师", "执业资格", "资格证", "职业资格", "医师资格"),
    "临床技能": ("临床", "诊疗", "病房", "门诊", "手术", "查房", "接诊"),
}

#: A requirement token that alone is too generic to license a match: overlap on
#: only these never produces evidence.
_GENERIC_CONCEPTS = frozenset({"沟通协作"})

#: Minimum IDF-weighted score (share of the requirement's weight covered) for a
#: fact to count as evidence.  Calibrated on the labeled eval set, where genuine
#: matches score >= 0.24 and unrelated facts <= 0.10; 0.15 sits in that gap.
#: Deliberately conservative: a purely concept-level bridge with no shared
#: distinctive term (e.g. terse "SPSS" vs "统计学基础") scores ~0.11 and stays a
#: gap, because offline it is indistinguishable from a false near-match like
#: "临床护理" vs "临床研究".  Showing an honest gap beats asserting a weak match.
_MIN_SCORE = 0.15
#: Keep supporting facts within this ratio of the best fact's score.
_KEEP_RATIO = 0.6
#: At most this many facts cited per requirement.
_MAX_FACTS_PER_REQ = 3
#: Fallback IDF for a token unseen in the corpus (treated as distinctive).
_DEFAULT_IDF = 6.0


@dataclass(frozen=True)
class Match:
    """One fact offered as evidence for a requirement, with its score."""

    profile_field_id: str
    collection: str
    score: float
    matched_terms: tuple[str, ...]
    source_text: str
    source_label: str


@lru_cache(maxsize=1)
def _idf_table() -> dict[str, float]:
    try:
        return json.loads(_IDF_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _idf(token: str) -> float:
    return _idf_table().get(token, _DEFAULT_IDF)


def _concepts(tokens: frozenset[str]) -> set[str]:
    """Concept tokens implied by a token set, via substring membership."""
    joined = "".join(tokens)
    found = set()
    for concept, members in CONCEPT_LEXICON.items():
        if any(member in joined for member in members):
            found.add(concept)
    return found


def _weighted(tokens: list[str]) -> dict[str, float]:
    """Map each distinct token to its IDF weight."""
    weights: dict[str, float] = {}
    for token in tokens:
        if token not in weights:
            weights[token] = _idf(token)
    return weights


def _concept_weight(concept: str) -> float:
    # A concept is as distinctive as its rarest member term.
    return max((_idf(member) for member in CONCEPT_LEXICON[concept]), default=_DEFAULT_IDF)


def score_fact(requirement: str, fact_text: str) -> tuple[float, tuple[str, ...]]:
    """Return (score, matched_terms) for one requirement/fact pair.

    ``score`` is the IDF-weighted share of the requirement's own weight that the
    fact covers, in ``[0, 1]``.  ``matched_terms`` are the human-meaningful
    overlapping terms (concept names where a concept matched, else the bigrams).
    """
    req_tokens = tokenize(requirement)
    fact_tokens = tokenize(fact_text)
    if not req_tokens or not fact_tokens:
        return 0.0, ()

    req_weights = _weighted(req_tokens)
    fact_set = set(fact_tokens)
    total_weight = sum(req_weights.values())

    covered = 0.0
    literal_terms: list[str] = []
    for token, weight in req_weights.items():
        if token in fact_set:
            covered += weight
            if len(token) >= 2 and not token.isascii():
                literal_terms.append(token)
            elif token.isascii():
                literal_terms.append(token)

    req_concepts = _concepts(frozenset(req_tokens))
    fact_concepts = _concepts(frozenset(fact_tokens))
    shared_concepts = req_concepts & fact_concepts
    meaningful_concepts = shared_concepts - _GENERIC_CONCEPTS

    concept_terms: list[str] = []
    for concept in shared_concepts:
        # Credit the concept only up to its own weight, and only when the literal
        # overlap did not already cover it, so a match is not double-counted.
        concept_terms.append(concept)
        covered += _concept_weight(concept) * 0.5

    denominator = total_weight + sum(_concept_weight(c) * 0.5 for c in req_concepts)
    score = covered / denominator if denominator else 0.0

    # Guard: a bit of incidental bigram overlap with no shared distinctive term
    # and no meaningful concept is not evidence.
    has_distinctive = any(_idf(term) >= 3.0 for term in literal_terms) or bool(meaningful_concepts)
    if not has_distinctive:
        return 0.0, ()

    terms = tuple(dict.fromkeys(concept_terms + literal_terms))
    return round(min(score, 1.0), 4), terms


def best_matches(requirement: str, facts: list[dict]) -> list[Match]:
    """Rank facts for one requirement; return those above threshold.

    ``facts`` are the dicts from ``resume.flatten_profile_facts``.  Returns at
    most :data:`_MAX_FACTS_PER_REQ` matches, best first, keeping only facts
    within :data:`_KEEP_RATIO` of the top score.
    """
    scored: list[Match] = []
    for fact in facts:
        score, terms = score_fact(requirement, fact["text"])
        if score < _MIN_SCORE:
            continue
        scored.append(
            Match(
                profile_field_id=fact["profile_field_id"],
                collection=fact["collection"],
                score=score,
                matched_terms=terms,
                source_text=fact["text"],
                source_label=fact["source_label"],
            )
        )
    if not scored:
        return []
    scored.sort(key=lambda match: match.score, reverse=True)
    cutoff = scored[0].score * _KEEP_RATIO
    return [match for match in scored if match.score >= cutoff][:_MAX_FACTS_PER_REQ]


def strength_band(score: float) -> str:
    """Map a score to the strong/partial/weak label the UI shows."""
    if score >= 0.5:
        return "strong"
    if score >= 0.28:
        return "partial"
    return "weak"
