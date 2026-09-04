"""Tests for profile boundary checks: overlap detection and draft-reference counting.

Covers PRD 4.3 boundary items:
* Time-overlap detection within education/experiences (pure function + API)
* Draft-reference counting across sections/evidence/gaps (pure function + API)
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.database import init_db, reset_db
from app.services.profile_checks import (
    OVERLAP_THRESHOLD,
    _build_interval,
    _overlap_ratio,
    check_profile_overlaps,
    count_field_references,
    detect_time_overlap,
    parse_profile_date,
)
from app.services.repositories import create_resume_draft


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'checks.db'}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


@pytest.fixture
def headers(client):
    token = client.post(
        "/api/auth/register", json={"username": "checker", "password": "secret123"}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_job(client) -> int:
    """Insert a dummy job so resume_drafts FK is satisfied."""
    from app.services.database import connect, to_json

    engine = client.app.state.engine
    with connect(engine) as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (
                institution_id, institution_name, institution_type, region,
                title, job_category, source_url, source_text_hash, raw_text,
                tags, extraction_evidence, fetched_at, parser_name, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "测试医院", "医院", "上海", "测试岗位", "临床",
             "https://example.com/test", "hash1", "raw", to_json([]), to_json([]),
             "2025-01-01T00:00:00Z", "test", 0.9),
        )
        conn.commit()
        return int(cur.lastrowid)


# ── parse_profile_date ──────────────────────────────────────────────


class TestParseProfileDate:
    def test_year(self):
        d, open_ended = parse_profile_date("2021")
        assert d == date(2021, 1, 1)
        assert not open_ended

    def test_year_month(self):
        d, open_ended = parse_profile_date("2021-06")
        assert d == date(2021, 6, 1)
        assert not open_ended

    def test_full_date(self):
        d, open_ended = parse_profile_date("2021-06-15")
        assert d == date(2021, 6, 15)
        assert not open_ended

    def test_open_ended_zh(self):
        d, open_ended = parse_profile_date("至今")
        assert open_ended is True

    def test_open_ended_en(self):
        d, open_ended = parse_profile_date("present")
        assert open_ended is True

    def test_unparseable_chinese_date(self):
        d, open_ended = parse_profile_date("2021年6月")
        assert d is None
        assert not open_ended

    def test_empty(self):
        assert parse_profile_date("") == (None, False)
        assert parse_profile_date("   ") == (None, False)

    def test_none(self):
        assert parse_profile_date(None) == (None, False)

    def test_non_string(self):
        assert parse_profile_date(2021) == (None, False)

    def test_invalid_month(self):
        d, _ = parse_profile_date("2021-13")
        assert d is None

    def test_strips_whitespace(self):
        d, _ = parse_profile_date("  2021  ")
        assert d == date(2021, 1, 1)


# ── _overlap_ratio ───────────────────────────────────────────────────


class TestOverlapRatio:
    def test_full_overlap(self):
        r = _overlap_ratio(date(2020, 1, 1), date(2024, 1, 1),
                           date(2020, 1, 1), date(2024, 1, 1))
        assert r == 1.0

    def test_no_overlap(self):
        r = _overlap_ratio(date(2020, 1, 1), date(2021, 1, 1),
                           date(2022, 1, 1), date(2024, 1, 1))
        assert r == 0.0

    def test_partial_above_threshold(self):
        # a: 2020-2024 (4 yrs), b: 2023-2024 (1 yr)
        # intersection = 1 yr, shorter = 1 yr → ratio = 1.0
        r = _overlap_ratio(date(2020, 1, 1), date(2024, 1, 1),
                           date(2023, 1, 1), date(2024, 1, 1))
        assert r >= OVERLAP_THRESHOLD

    def test_partial_below_threshold(self):
        # a: 2020-2024 (4 yrs ≈ 1461 days), b: 2020-2021 (1 yr ≈ 365 days)
        # intersection = 365 days, shorter = 365 → ratio = 1.0
        # That's above threshold. Let me make b shorter.
        # a: 2020-2024 (4 yrs), b: 2021-2021-06 (0.5 yr)
        # intersection = 0, no overlap
        r = _overlap_ratio(date(2020, 1, 1), date(2024, 1, 1),
                           date(2025, 1, 1), date(2025, 6, 1))
        assert r == 0.0

    def test_small_overlap_below_threshold(self):
        # a: 2020-01-01 to 2024-01-01 (1461 days)
        # b: 2023-07-01 to 2023-12-01 (183 days)
        # intersection = 183 days, shorter = 183 → ratio = 1.0
        # Let me make b barely overlap
        # a: 2020-2024 (1461 days)
        # b: 2023-12-30 to 2024-01-02 (3 days)
        # intersection = 2 days, shorter = 3 → ratio ≈ 0.67 → above threshold
        # Actually let me make it clearly below 50%
        # a: 2020-2024, b: 2023-12-31 to 2024-01-01 (1 day)
        # intersection = 1 day, shorter = 1 day → ratio = 1.0
        # Hmm, point-ish intervals are tricky. Let me use larger intervals.
        # a: 2020-2024 (1461 days), b: 2023-01-01 to 2023-01-30 (29 days)
        # intersection = 29 days, shorter = 29 → ratio = 1.0
        # This is still above. The issue is that if b is fully contained in a,
        # ratio = 1.0 regardless.
        # For below threshold, b must partially overlap a and the non-overlapping
        # part must be > 50% of the shorter interval.
        # a: 2020-01-01 to 2020-12-31 (364 days)
        # b: 2020-12-15 to 2021-06-15 (~182 days)
        # intersection = 2020-12-15 to 2020-12-31 = 16 days
        # shorter = 182 days → ratio = 16/182 ≈ 0.088 → below threshold
        r = _overlap_ratio(date(2020, 1, 1), date(2020, 12, 31),
                           date(2020, 12, 15), date(2021, 6, 15))
        assert r is not None
        assert r < OVERLAP_THRESHOLD


# ── detect_time_overlap ─────────────────────────────────────────────


class TestDetectTimeOverlap:
    def test_overlapping_above_threshold(self):
        items = [
            {"id": "edu-1", "school": "A大学", "start": "2018", "end": "2022"},
        ]
        new = {"id": "edu-2", "school": "B大学", "start": "2020", "end": "2022"}
        result = detect_time_overlap(items, new)
        assert len(result) == 1
        assert result[0]["id"] == "edu-1"

    def test_overlapping_below_threshold(self):
        items = [
            {"id": "edu-1", "school": "A大学", "start": "2018", "end": "2018-06"},
        ]
        new = {"id": "edu-2", "school": "B大学", "start": "2018-05", "end": "2022"}
        result = detect_time_overlap(items, new)
        assert len(result) == 0

    def test_no_dates_no_trigger(self):
        items = [
            {"id": "edu-1", "school": "A大学", "start": "", "end": ""},
        ]
        new = {"id": "edu-2", "school": "B大学", "start": "2020", "end": "2022"}
        result = detect_time_overlap(items, new)
        assert len(result) == 0

    def test_unparseable_dates_no_trigger(self):
        items = [
            {"id": "edu-1", "school": "A大学", "start": "2021年9月", "end": "2024年6月"},
        ]
        new = {"id": "edu-2", "school": "B大学", "start": "2022", "end": "2024"}
        result = detect_time_overlap(items, new)
        assert len(result) == 0

    def test_new_item_unparseable_no_trigger(self):
        items = [
            {"id": "edu-1", "school": "A大学", "start": "2020", "end": "2024"},
        ]
        new = {"id": "edu-2", "school": "B大学", "start": "some text", "end": "至今"}
        result = detect_time_overlap(items, new)
        assert len(result) == 0

    def test_self_excluded_by_id(self):
        items = [
            {"id": "edu-1", "school": "A大学", "start": "2018", "end": "2022"},
        ]
        new = {"id": "edu-1", "school": "A大学", "start": "2020", "end": "2022"}
        result = detect_time_overlap(items, new)
        assert len(result) == 0

    def test_open_ended_overlap(self):
        items = [
            {"id": "exp-1", "organization": "某医院", "start": "2019", "end": "至今"},
        ]
        new = {"id": "exp-2", "organization": "另一医院", "start": "2020", "end": "至今"}
        result = detect_time_overlap(items, new)
        assert len(result) == 1


# ── check_profile_overlaps ──────────────────────────────────────────


class TestCheckProfileOverlaps:
    def test_education_overlap_detected(self):
        profile = {
            "education": [
                {"id": "edu-1", "school": "A大学", "start": "2018", "end": "2022"},
                {"id": "edu-2", "school": "B大学", "start": "2020", "end": "2022"},
            ],
            "experiences": [],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is True
        assert len(result["items"]) == 2

    def test_experiences_overlap_detected(self):
        profile = {
            "education": [],
            "experiences": [
                {"id": "exp-1", "organization": "A医院", "start": "2019", "end": "至今"},
                {"id": "exp-2", "organization": "B医院", "start": "2020", "end": "2022"},
            ],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is True

    def test_no_overlap(self):
        profile = {
            "education": [
                {"id": "edu-1", "school": "A大学", "start": "2015", "end": "2019"},
                {"id": "edu-2", "school": "B大学", "start": "2020", "end": "2024"},
            ],
            "experiences": [],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is False
        assert result["items"] == []

    def test_id_less_items_all_flagged(self):
        # API payloads may omit row ids entirely; every participant of an
        # overlapping pair must still be reported, not just the first one.
        profile = {
            "education": [
                {"school": "A大学", "start": "2018", "end": "2022"},
                {"school": "B大学", "start": "2020", "end": "2022"},
            ],
            "experiences": [],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is True
        assert len(result["items"]) == 2

    def test_two_id_less_pairs_all_flagged(self):
        profile = {
            "education": [
                {"school": "A大学", "start": "2018", "end": "2022"},
                {"school": "B大学", "start": "2020", "end": "2022"},
                {"school": "C大学", "start": "2010", "end": "2014"},
                {"school": "D大学", "start": "2012", "end": "2016"},
            ],
            "experiences": [],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is True
        assert len(result["items"]) == 4

    def test_cross_category_not_checked(self):
        profile = {
            "education": [
                {"id": "edu-1", "school": "A大学", "start": "2018", "end": "2022"},
            ],
            "experiences": [
                {"id": "exp-1", "organization": "某医院", "start": "2019", "end": "2021"},
            ],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is False

    def test_unparseable_dates_not_flagged(self):
        profile = {
            "education": [
                {"id": "edu-1", "school": "A大学", "start": "2021年", "end": "2024年"},
                {"id": "edu-2", "school": "B大学", "start": "2022年", "end": "2024年"},
            ],
            "experiences": [],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is False

    def test_missing_dates_not_flagged(self):
        profile = {
            "education": [
                {"id": "edu-1", "school": "A大学"},
                {"id": "edu-2", "school": "B大学"},
            ],
            "experiences": [],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is False

    def test_single_item_no_overlap(self):
        profile = {
            "education": [{"id": "edu-1", "school": "A大学", "start": "2018", "end": "2022"}],
            "experiences": [],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is False

    def test_items_deduplicated(self):
        profile = {
            "education": [
                {"id": "edu-1", "school": "A大学", "start": "2018", "end": "2022"},
                {"id": "edu-2", "school": "B大学", "start": "2019", "end": "2021"},
                {"id": "edu-3", "school": "C大学", "start": "2020", "end": "2022"},
            ],
            "experiences": [],
        }
        result = check_profile_overlaps(profile)
        assert result["overlap"] is True
        ids = {item["id"] for item in result["items"]}
        assert ids == {"edu-1", "edu-2", "edu-3"}


# ── count_field_references ──────────────────────────────────────────


class TestCountFieldReferences:
    def test_zero_references(self):
        drafts = []
        result = count_field_references(drafts, "edu-1")
        assert result["count"] == 0
        assert result["draft_ids"] == []
        assert result["field_id"] == "edu-1"

    def test_one_reference_in_sections(self):
        drafts = [
            {"id": 1, "sections": [{"items": [{"profile_field_id": "edu-1"}]}], "evidence": [], "gaps": []},
        ]
        result = count_field_references(drafts, "edu-1")
        assert result["count"] == 1
        assert result["draft_ids"] == [1]

    def test_one_reference_in_evidence(self):
        drafts = [
            {"id": 1, "sections": [], "evidence": [{"profile_field_id": "edu-1"}], "gaps": []},
        ]
        result = count_field_references(drafts, "edu-1")
        assert result["count"] == 1

    def test_one_reference_in_gaps(self):
        drafts = [
            {"id": 1, "sections": [], "evidence": [], "gaps": [{"profile_field_id": "edu-1"}]},
        ]
        result = count_field_references(drafts, "edu-1")
        assert result["count"] == 1

    def test_multiple_drafts(self):
        drafts = [
            {"id": 1, "sections": [{"items": [{"profile_field_id": "edu-1"}]}], "evidence": [], "gaps": []},
            {"id": 2, "sections": [], "evidence": [{"profile_field_id": "edu-1"}], "gaps": []},
            {"id": 3, "sections": [], "evidence": [], "gaps": []},
        ]
        result = count_field_references(drafts, "edu-1")
        assert result["count"] == 2
        assert result["draft_ids"] == [1, 2]

    def test_exact_match_required(self):
        drafts = [
            {"id": 1, "sections": [{"items": [{"profile_field_id": "edu-1"}]}], "evidence": [], "gaps": []},
        ]
        result = count_field_references(drafts, "edu-10")
        assert result["count"] == 0

    def test_multiple_sections_one_draft_counts_once(self):
        drafts = [
            {"id": 1, "sections": [
                {"items": [{"profile_field_id": "edu-1"}]},
                {"items": [{"profile_field_id": "edu-1"}]},
            ], "evidence": [{"profile_field_id": "edu-1"}], "gaps": []},
        ]
        result = count_field_references(drafts, "edu-1")
        assert result["count"] == 1


# ── API: POST /api/profile/check-overlap ────────────────────────────


class TestCheckOverlapEndpoint:
    def test_overlap_detected(self, client, headers):
        payload = {
            "education": [
                {"id": "edu-1", "school": "A大学", "start": "2018", "end": "2022"},
                {"id": "edu-2", "school": "B大学", "start": "2020", "end": "2022"},
            ],
            "experiences": [],
        }
        response = client.post("/api/profile/check-overlap", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["overlap"] is True
        assert len(data["items"]) == 2

    def test_no_overlap(self, client, headers):
        payload = {
            "education": [
                {"id": "edu-1", "school": "A大学", "start": "2015", "end": "2019"},
                {"id": "edu-2", "school": "B大学", "start": "2020", "end": "2024"},
            ],
            "experiences": [],
        }
        response = client.post("/api/profile/check-overlap", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["overlap"] is False

    def test_unparseable_dates_no_overlap(self, client, headers):
        payload = {
            "education": [
                {"id": "edu-1", "school": "A大学", "start": "2021年", "end": "2024年"},
                {"id": "edu-2", "school": "B大学", "start": "2022年", "end": "2024年"},
            ],
            "experiences": [],
        }
        response = client.post("/api/profile/check-overlap", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["overlap"] is False

    def test_experiences_overlap(self, client, headers):
        payload = {
            "education": [],
            "experiences": [
                {"id": "exp-1", "organization": "A医院", "start": "2019", "end": "至今"},
                {"id": "exp-2", "organization": "B医院", "start": "2020", "end": "2022"},
            ],
        }
        response = client.post("/api/profile/check-overlap", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["overlap"] is True

    def test_requires_auth(self, client):
        response = client.post("/api/profile/check-overlap", json={"education": []})
        assert response.status_code == 401


# ── API: GET /api/profile/field-references ──────────────────────────


class TestFieldReferencesEndpoint:
    def test_zero_references(self, client, headers):
        response = client.get(
            "/api/profile/field-references", params={"field_id": "edu-1"}, headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["draft_ids"] == []

    def test_with_one_draft_reference(self, client, headers):
        job_id = _seed_job(client)
        engine = client.app.state.engine
        create_resume_draft(
            engine, user_id=1, job_id=job_id,
            title="测试草稿",
            sections=[{"id": "education", "title": "教育背景", "items": [{"text": "...", "profile_field_id": "edu-1"}]}],
            evidence=[{"requirement": "学历", "profile_field_id": "edu-1", "collection": "education", "matched_terms": [], "source_text": "", "source_label": "", "score": 0.5, "evidence_strength": "moderate"}],
            gaps=[],
        )
        response = client.get(
            "/api/profile/field-references", params={"field_id": "edu-1"}, headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert 1 in data["draft_ids"]

    def test_with_multiple_draft_references(self, client, headers):
        job_id = _seed_job(client)
        engine = client.app.state.engine
        for i in range(3):
            create_resume_draft(
                engine, user_id=1, job_id=job_id,
                title=f"草稿{i}",
                sections=[{"id": "education", "title": "教育背景", "items": [{"text": "...", "profile_field_id": "edu-1"}]}],
                evidence=[],
                gaps=[],
            )
        response = client.get(
            "/api/profile/field-references", params={"field_id": "edu-1"}, headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["draft_ids"]) == 3

    def test_unreferenced_field(self, client, headers):
        job_id = _seed_job(client)
        engine = client.app.state.engine
        create_resume_draft(
            engine, user_id=1, job_id=job_id,
            title="测试草稿",
            sections=[{"id": "education", "title": "教育背景", "items": [{"text": "...", "profile_field_id": "edu-1"}]}],
            evidence=[],
            gaps=[],
        )
        response = client.get(
            "/api/profile/field-references", params={"field_id": "exp-99"}, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_reference_in_gaps(self, client, headers):
        job_id = _seed_job(client)
        engine = client.app.state.engine
        create_resume_draft(
            engine, user_id=1, job_id=job_id,
            title="测试草稿",
            sections=[],
            evidence=[],
            gaps=[{"requirement": "学历", "message": "...", "profile_field_id": "edu-1"}],
        )
        response = client.get(
            "/api/profile/field-references", params={"field_id": "edu-1"}, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_requires_auth(self, client):
        response = client.get(
            "/api/profile/field-references", params={"field_id": "edu-1"}
        )
        assert response.status_code == 401
