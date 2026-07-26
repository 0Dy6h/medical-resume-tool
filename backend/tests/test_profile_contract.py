"""Profile save/load contract: blank rows, legacy rows, and lossy fields.

These cover the boundary between the editor (which creates partial rows), the
typed schema, and profiles written before the typed schema existed.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import Profile, ProfilePayload
from app.services.database import connect
from app.services.repositories import get_profile


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(f"sqlite:///{tmp_path / 'contract.db'}"))


@pytest.fixture
def headers(client):
    token = client.post(
        "/api/auth/register", json={"username": "zoe", "password": "secret123"}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── blank rows ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "collection",
    [
        "education", "experiences", "projects", "publications", "certificates",
        "skills", "teaching", "awards", "languages",
    ],
)
def test_adding_an_untouched_row_does_not_block_the_save(client, headers, collection):
    """The editor's 添加 button creates a row holding only an id."""
    response = client.put("/api/profile", json={collection: [{"id": "new-1"}]}, headers=headers)
    assert response.status_code == 200
    # A row the user never filled in is not persisted.
    assert response.json()[collection] == []


def test_blank_rows_are_dropped_but_filled_rows_are_kept(client, headers):
    payload = {"skills": [{"id": "s1", "name": "SPSS"}, {"id": "s2"}, {"id": "s3", "name": ""}]}
    saved = client.put("/api/profile", json=payload, headers=headers).json()
    assert [item["name"] for item in saved["skills"]] == ["SPSS"]


def test_a_profile_of_only_blank_rows_counts_as_empty():
    payload = ProfilePayload(skills=[{"id": "s1"}], experiences=[{"id": "e1"}])
    assert payload.to_profile().is_empty


def test_partially_filled_row_round_trips(client, headers):
    """A half-typed entry must survive — the user saves as they go."""
    saved = client.put(
        "/api/profile",
        json={"experiences": [{"id": "e1", "organization": "省人民医院"}]},
        headers=headers,
    ).json()
    assert saved["experiences"][0]["organization"] == "省人民医院"
    assert saved["experiences"][0]["role"] == ""


# ── legacy rows ──────────────────────────────────────────────────────


def test_legacy_free_text_skill_level_is_mapped_not_rejected(client, headers):
    """Pre-typed-schema profiles stored whatever the user typed as 熟练度."""
    profile = Profile.from_legacy_dict(
        {"skills": [{"id": "s1", "name": "SPSS", "level": "熟练"}]}
    )
    assert profile.skills[0].level == "advanced"


def test_unknown_skill_level_degrades_to_none():
    profile = Profile.from_legacy_dict({"skills": [{"id": "s1", "name": "R", "level": "还行"}]})
    assert profile.skills[0].level is None


def test_legacy_basic_key_is_migrated_to_basics():
    profile = Profile.from_legacy_dict({"basic": {"name": "林晓"}})
    assert profile.basics.name == "林晓"


def test_legacy_profile_row_does_not_brick_the_endpoint(client, headers):
    """A row the typed schema cannot fully represent must not 500 the account.

    Regression: get_profile() raised an uncaught ValidationError, making
    /api/profile, resume drafts and every export permanently unreadable.
    """
    legacy = {
        "basic": {"name": "旧用户"},
        "skills": [{"id": "s1", "name": "SPSS", "level": "熟练"}],
        "experiences": [{"id": "e1", "organization": "旧医院", "role": "技师"}],
    }
    with connect(client.app.state.engine) as conn:
        conn.execute(
            "INSERT INTO profiles (user_id, data, updated_at) VALUES (1, ?, '2026-01-01T00:00:00+00:00')",
            (json.dumps(legacy, ensure_ascii=False),),
        )
        conn.commit()

    response = client.get("/api/profile", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["basics"]["name"] == "旧用户"
    assert body["skills"][0]["name"] == "SPSS"
    assert body["experiences"][0]["organization"] == "旧医院"


def test_unparsable_entry_is_dropped_without_losing_the_rest(client):
    """One malformed entry costs that entry, not the whole profile."""
    profile = Profile.from_legacy_dict(
        {
            "skills": [
                {"id": "s1", "name": "SPSS"},
                {"id": "s2", "name": {"unexpected": "nested"}},
                {"id": "s3", "name": "R"},
            ]
        }
    )
    assert [skill.name for skill in profile.skills] == ["SPSS", "R"]


def test_legacy_profile_survives_a_load_save_reload_cycle(client, headers):
    with connect(client.app.state.engine) as conn:
        conn.execute(
            "INSERT INTO profiles (user_id, data, updated_at) VALUES (1, ?, '2026-01-01T00:00:00+00:00')",
            (json.dumps({"basic": {"name": "旧用户"}, "skills": [{"id": "s1", "name": "SPSS", "level": "精通"}]}, ensure_ascii=False),),
        )
        conn.commit()
    loaded = client.get("/api/profile", headers=headers).json()
    resaved = client.put("/api/profile", json=loaded, headers=headers)
    assert resaved.status_code == 200
    assert get_profile(client.app.state.engine, 1).skills[0].level == "expert"


# ── field-shape mismatches with the editor ───────────────────────────


def test_multiline_authors_from_the_editor_is_accepted(client, headers):
    """The 作者 field renders as a textarea, so the editor sends a list."""
    saved = client.put(
        "/api/profile",
        json={"publications": [{"id": "p1", "title": "队列研究", "authors": ["张三", "李四"]}]},
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json()["publications"][0]["authors"] == "张三、李四"
