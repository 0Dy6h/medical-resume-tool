"""Matching-quality eval: labeled (requirement -> expected fact) cases.

This is the guardrail the whole matcher exists to satisfy. Two profiles, one of
them (profile_b) never consulted while tuning, each with positive cases (a
requirement the profile answers, and the fact ids that answer it) and negative
cases (a requirement the profile does NOT answer, which must stay a gap).

The hard bars, expressed as assertions:
  - top-1 source accuracy >= 0.90 across both profiles
  - held-out profile (profile_b) top-1 >= 0.85
  - zero wrong-source attributions (never cite a fact not in the gold set)
  - zero false positives on negatives (a gap requirement must produce no evidence)
  - an off-domain control fact is never cited for any requirement
"""

import json
from pathlib import Path

import pytest

from app.schemas import Profile
from app.services.resume import flatten_profile_facts
from app.services.matching.scorer import best_matches

_FIXTURES = Path(__file__).parent / "fixtures" / "matching"


def _load(name: str):
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


PROFILES = _load("profiles.json")
CASES = _load("cases.json")


def _facts(profile_key: str):
    return flatten_profile_facts(Profile.from_legacy_dict(PROFILES[profile_key]))


def _evaluate(profile_key: str):
    facts = _facts(profile_key)
    positives = 0
    top1_hits = 0
    wrong_source = 0
    false_positives = 0
    for case in CASES[profile_key]:
        matches = best_matches(case["requirement"], facts)
        matched_ids = [match.profile_field_id for match in matches]
        expect = case["expect"]
        if expect is None:
            if matched_ids:
                false_positives += 1
            continue
        positives += 1
        expected = set(expect)
        if matched_ids and matched_ids[0] in expected:
            top1_hits += 1
        # Any cited fact outside the gold set is a wrong-source attribution.
        if any(field_id not in expected for field_id in matched_ids):
            wrong_source += 1
    return {
        "positives": positives,
        "top1_hits": top1_hits,
        "wrong_source": wrong_source,
        "false_positives": false_positives,
    }


def test_no_false_positives_on_negative_cases():
    """A requirement the profile does not meet must remain a gap, both profiles."""
    for profile_key in PROFILES:
        result = _evaluate(profile_key)
        assert result["false_positives"] == 0, f"{profile_key}: {result}"


def test_no_wrong_source_attributions():
    """Evidence must never cite a fact outside the labeled gold set."""
    for profile_key in PROFILES:
        result = _evaluate(profile_key)
        assert result["wrong_source"] == 0, f"{profile_key}: {result}"


def test_overall_top1_source_accuracy_meets_bar():
    total_pos = 0
    total_hits = 0
    for profile_key in PROFILES:
        result = _evaluate(profile_key)
        total_pos += result["positives"]
        total_hits += result["top1_hits"]
    accuracy = total_hits / total_pos
    assert accuracy >= 0.90, f"top-1 accuracy {accuracy:.2f} ({total_hits}/{total_pos})"


def test_held_out_profile_top1_accuracy_meets_bar():
    """profile_b was not used while tuning the scorer."""
    result = _evaluate("profile_b")
    accuracy = result["top1_hits"] / result["positives"]
    assert accuracy >= 0.85, f"held-out top-1 {accuracy:.2f} ({result})"


def test_off_domain_fact_is_never_cited():
    """A fact with no relation to any requirement must never surface as evidence."""
    control = {
        "profile_field_id": "ctrl-1",
        "collection": "skills",
        "text": "业余油画创作与陶艺",
        "source_label": "技能能力：油画",
    }
    for profile_key in PROFILES:
        facts = _facts(profile_key) + [control]
        for case in CASES[profile_key]:
            matches = best_matches(case["requirement"], facts)
            assert all(m.profile_field_id != "ctrl-1" for m in matches), case["requirement"]


def test_every_cited_fact_is_traceable_to_a_real_profile_item():
    """100% traceability: an evidence id must resolve to an actual fact."""
    for profile_key in PROFILES:
        facts = _facts(profile_key)
        valid_ids = {fact["profile_field_id"] for fact in facts}
        for case in CASES[profile_key]:
            for match in best_matches(case["requirement"], facts):
                assert match.profile_field_id in valid_ids


@pytest.mark.parametrize("profile_key", list(PROFILES))
def test_beats_the_old_keyword_overlap_baseline(profile_key):
    """Sanity: the new matcher answers most positive cases (the old one answered ~half)."""
    result = _evaluate(profile_key)
    assert result["top1_hits"] >= result["positives"] * 0.8, result
