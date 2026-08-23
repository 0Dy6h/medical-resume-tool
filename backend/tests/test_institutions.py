from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.database import create_engine, init_db, reset_db
from app.services.seeds import BLOCKED_REASONS, SEED_INSTITUTIONS


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db_path}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


def test_institutions_list_has_blocked_reason_none_for_enabled(tmp_path):
    """Enabled institutions have blocked_reason = None."""
    client = make_client(tmp_path)
    response = client.get("/api/institutions")
    assert response.status_code == 200
    items = response.json()
    enabled_items = [item for item in items if item["enabled"]]
    assert len(enabled_items) > 0
    for item in enabled_items:
        assert item["blocked_reason"] is None


def test_institutions_disabled_with_comment_matches_blocked_reasons_verbatim(tmp_path):
    """A disabled institution with a seed comment returns the exact reason string."""
    client = make_client(tmp_path)
    response = client.get("/api/institutions")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()}

    # id=8 has comment "SPA 渲染，需 headless browser" — must match exactly
    inst = items[8]
    assert inst["enabled"] is False
    assert inst["blocked_reason"] == "SPA 渲染，需 headless browser"
    assert inst["blocked_reason"] == BLOCKED_REASONS[8]


def test_institutions_disabled_without_comment_uses_default_reason(tmp_path):
    """A disabled institution without a seed comment returns the default reason."""
    client = make_client(tmp_path)
    response = client.get("/api/institutions")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()}

    # id=9 has no comment — should return the default fallback
    inst = items[9]
    assert inst["enabled"] is False
    assert inst["blocked_reason"] == "尚未适配该站点，暂未启用"
    assert inst["blocked_reason"] == BLOCKED_REASONS[9]


def test_blocked_reasons_covers_all_disabled_seeds():
    """BLOCKED_REASONS covers every enabled=False seed id exactly (no missing, no extra)."""
    disabled_ids = {seed["id"] for seed in SEED_INSTITUTIONS if not seed["enabled"]}
    blocked_keys = set(BLOCKED_REASONS.keys())
    assert disabled_ids == blocked_keys, (
        f"disabled seed ids {sorted(disabled_ids)} "
        f"!= BLOCKED_REASONS keys {sorted(blocked_keys)}"
    )


def test_crawl_all_disabled_returns_400(tmp_path):
    """Selecting only disabled institutions returns 400 with exact message."""
    client = make_client(tmp_path)
    # ids 8, 9, 10 are all disabled
    response = client.post("/api/crawl-runs", json={"institution_ids": [8, 9, 10]})
    assert response.status_code == 400
    assert response.json()["detail"] == "所选机构均尚未适配，无法抓取"


def test_crawl_mixed_only_crawls_enabled(tmp_path):
    """Mixing enabled and disabled institutions — only enabled ones are crawled."""
    client = make_client(tmp_path)
    # id=1 is enabled (fixture), id=8 is disabled
    response = client.post("/api/crawl-runs", json={"institution_ids": [1, 8]})
    assert response.status_code == 201
    run_data = response.json()
    # The crawl run should only contain enabled institution ids
    assert run_data["institution_ids"] == [1]
    assert 8 not in run_data["institution_ids"]
