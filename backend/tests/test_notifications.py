"""U7 订阅触达：扫描写站内通知、通知已读、关键词边界（词边界/空词）。"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.database import connect, create_engine, init_db, reset_db
from app.services.keyword_match import keyword_matches

FIXED_TIME = datetime(2026, 9, 2, 9, 0, 0, tzinfo=timezone.utc)


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db_path}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


def register(client: TestClient, username: str) -> dict[str, str]:
    resp = client.post("/api/auth/register", json={"username": username, "password": "secret123"})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _backdate_subscription(engine, subscription_id: int, days: float) -> None:
    backdated = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect(engine) as conn:
        conn.execute(
            "UPDATE subscriptions SET last_pushed_at = ? WHERE id = ?",
            (backdated, subscription_id),
        )
        conn.commit()


def _wait_runs(client: TestClient, run_id: int) -> dict:
    deadline = time.time() + 30
    while time.time() < deadline:
        payload = client.get(f"/api/crawl-runs/{run_id}").json()
        if payload["status"] in {"completed", "partial", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("crawl run did not finish")


# ── 扫描产生站内通知 ────────────────────────────────────────────────


def _crawl_fixture_once(client: TestClient, headers: dict[str, str]) -> None:
    """灌入 fixture 岗位（fresh fetched_at），供后续扫描命中。"""
    run = client.post("/api/crawl-runs", json={"institution_ids": [1]}, headers=headers)
    assert run.status_code == 201, run.text
    _wait_runs(client, run.json()["id"])


def test_scan_creates_notification_with_summary(tmp_path):
    client = make_client(tmp_path)
    headers = register(client, "notify_user")
    engine = client.app.state.engine
    _crawl_fixture_once(client, headers)

    created = client.post(
        "/api/subscriptions",
        json={"name": "护理订阅", "keyword": "护理", "institution_ids": [1]},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    _backdate_subscription(engine, created.json()["id"], days=2)

    scan = client.post("/api/subscriptions/scan", headers=headers).json()
    assert scan["pushed"] >= 1
    assert scan["notified"] >= 1

    items = client.get("/api/notifications", headers=headers).json()
    assert len(items) >= 1
    first = items[0]
    assert first["keyword"] == "护理"
    assert first["subscription_name"] == "护理订阅"
    assert first["job_count"] >= 1
    assert first["summary"]  # 有可读摘要
    assert first["read"] is False

    unread = client.get("/api/notifications/unread-count", headers=headers).json()
    assert unread["count"] == len([i for i in items if not i["read"]])


def test_scan_without_new_jobs_creates_no_notification(tmp_path):
    client = make_client(tmp_path)
    headers = register(client, "quiet_user")
    engine = client.app.state.engine

    created = client.post(
        "/api/subscriptions",
        json={"name": "无命中订阅", "keyword": "放射物理师", "institution_ids": [1]},
        headers=headers,
    )
    assert created.status_code == 201
    _backdate_subscription(engine, created.json()["id"], days=2)

    scan = client.post("/api/subscriptions/scan", headers=headers).json()
    assert scan["pushed"] == 0
    assert scan["notified"] == 0
    assert client.get("/api/notifications", headers=headers).json() == []


def test_crawl_run_triggers_notification(tmp_path):
    """自动/手动抓取后的订阅扫描也写通知（全链路）。"""
    client = make_client(tmp_path)
    headers = register(client, "chain_user")
    engine = client.app.state.engine

    created = client.post(
        "/api/subscriptions",
        json={"name": "医订阅", "keyword": "医", "institution_ids": [1]},
        headers=headers,
    )
    _backdate_subscription(engine, created.json()["id"], days=2)

    run = client.post(
        "/api/crawl-runs", json={"institution_ids": [1]}, headers=headers
    )
    assert run.status_code == 201
    _wait_runs(client, run.json()["id"])

    # 爬取钩子在 run 状态写入 completed 之后才执行订阅扫描（main._crawl_then_scan
    # 的 finally 段），_wait_runs 返回可能落在「completed 已写、扫描未跑」的窗口，
    # 轮询宽限避免竞态假红（2026-09-05 夜班实测概率性失败）。
    deadline = time.time() + 5
    items = client.get("/api/notifications", headers=headers).json()
    while len(items) < 1 and time.time() < deadline:
        time.sleep(0.05)
        items = client.get("/api/notifications", headers=headers).json()
    assert len(items) >= 1
    assert items[0]["job_count"] >= 1


# ── 已读语义 ────────────────────────────────────────────────────────


def test_mark_read_and_read_all(tmp_path):
    client = make_client(tmp_path)
    headers = register(client, "read_user")
    engine = client.app.state.engine
    _crawl_fixture_once(client, headers)

    created = client.post(
        "/api/subscriptions",
        json={"name": "护理订阅", "keyword": "护理", "institution_ids": [1]},
        headers=headers,
    )
    sub_id = created.json()["id"]
    # 产生两条通知（两次回拨 + 两次扫描）
    for _ in range(2):
        _backdate_subscription(engine, sub_id, days=2)
        client.post("/api/subscriptions/scan", headers=headers)

    items = client.get("/api/notifications", headers=headers).json()
    assert len(items) == 2

    marked = client.post(f"/api/notifications/{items[0]['id']}/read", headers=headers)
    assert marked.status_code == 200
    assert marked.json()["read"] is True

    unread = client.get("/api/notifications/unread-count", headers=headers).json()
    assert unread["count"] == 1

    all_marked = client.post("/api/notifications/read-all", headers=headers).json()
    assert all_marked["marked"] == 1
    unread = client.get("/api/notifications/unread-count", headers=headers).json()
    assert unread["count"] == 0

    # 重复 read-all 不再计数量
    again = client.post("/api/notifications/read-all", headers=headers).json()
    assert again["marked"] == 0


def test_notifications_require_auth_and_isolated_per_user(tmp_path):
    client = make_client(tmp_path)
    headers_a = register(client, "user_a")
    headers_b = register(client, "user_b")
    engine = client.app.state.engine
    _crawl_fixture_once(client, headers_a)

    created = client.post(
        "/api/subscriptions",
        json={"name": "A的订阅", "keyword": "护理", "institution_ids": [1]},
        headers=headers_a,
    )
    _backdate_subscription(engine, created.json()["id"], days=2)
    client.post("/api/subscriptions/scan", headers=headers_a)

    assert client.get("/api/notifications").status_code == 401
    # B 看不到 A 的通知
    assert client.get("/api/notifications", headers=headers_b).json() == []
    # A 的通知 B 也无法标记已读（404，不泄露存在性）
    items = client.get("/api/notifications", headers=headers_a).json()
    resp = client.post(f"/api/notifications/{items[0]['id']}/read", headers=headers_b)
    assert resp.status_code == 404


# ── 关键词边界 ──────────────────────────────────────────────────────


def test_keyword_matches_word_boundary_for_ascii():
    assert keyword_matches("ICU 护士招聘", "ICU")
    assert keyword_matches("招聘icu专科护士", "ICU")  # 大小写不敏感
    assert not keyword_matches("RICU 专科护士", "ICU")  # 嵌在更长英文词里不命中
    assert not keyword_matches("讨论DICUsion会纪要", "ICU")
    assert keyword_matches("BW-500 型检验设备操作员", "500")


def test_keyword_matches_substring_for_cjk():
    assert keyword_matches("护理部临床护士招聘", "护理")
    assert keyword_matches("内科主治医师", "内科")
    assert not keyword_matches("儿科护士长", "内科")


def test_keyword_empty_never_matches():
    assert not keyword_matches("护理部临床护士", "")
    assert not keyword_matches("护理部临床护士", "   ")


def test_subscription_keyword_blank_rejected(tmp_path):
    client = make_client(tmp_path)
    headers = register(client, "blank_user")
    resp = client.post(
        "/api/subscriptions",
        json={"name": "空词订阅", "keyword": "   ", "institution_ids": [1]},
        headers=headers,
    )
    assert resp.status_code == 422
