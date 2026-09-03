"""U5 自动抓取闭环：每日定时抓取、单飞互斥、触发标记、抓取后订阅扫描。"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.crawler import release_crawl_slot, try_acquire_crawl_slot
from app.services.database import connect, create_engine, init_db
from app.services.repositories import list_crawl_runs
from app.services.scheduler import DailyScheduler

FIXED_TIME = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db_path}")
    from app.services.database import reset_db

    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


def register_user(client: TestClient, username: str) -> dict:
    resp = client.post("/api/auth/register", json={"username": username, "password": "secret123"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def wait_for_run(client: TestClient, run_id: int, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get(f"/api/crawl-runs/{run_id}").json()
        if payload["status"] in {"completed", "partial", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"crawl run {run_id} did not finish within {timeout}s")


def _backdate_subscription(engine, subscription_id: int, days: float) -> None:
    from datetime import timedelta

    backdated = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect(engine) as conn:
        conn.execute(
            "UPDATE subscriptions SET last_pushed_at = ? WHERE id = ?",
            (backdated, subscription_id),
        )
        conn.commit()


# ── 触发标记与列表 ──────────────────────────────────────────────────


def test_manual_run_records_manual_trigger(tmp_path):
    client = make_client(tmp_path)
    user = register_user(client, "manual_user")
    headers = {"Authorization": f"Bearer {user['token']}"}

    run_resp = client.post("/api/crawl-runs", json={"institution_ids": [1]}, headers=headers)
    assert run_resp.status_code == 201, run_resp.text
    run = wait_for_run(client, run_resp.json()["id"])
    assert run["trigger"] == "manual"


def test_crawl_runs_list_latest_first(tmp_path):
    client = make_client(tmp_path)
    user = register_user(client, "list_user")
    headers = {"Authorization": f"Bearer {user['token']}"}

    first = client.post("/api/crawl-runs", json={"institution_ids": [1]}, headers=headers)
    first_id = first.json()["id"]
    wait_for_run(client, first_id)
    second = client.post("/api/crawl-runs", json={"institution_ids": [2]}, headers=headers)
    assert second.status_code == 201, second.text
    wait_for_run(client, second.json()["id"])

    listed = client.get("/api/crawl-runs", headers=headers).json()
    assert len(listed) >= 2
    assert listed[0]["id"] > listed[-1]["id"]
    assert all(item["trigger"] == "manual" for item in listed)


# ── 单飞互斥 ────────────────────────────────────────────────────────


def test_manual_crawl_conflicts_while_slot_busy(tmp_path):
    client = make_client(tmp_path)
    user = register_user(client, "busy_user")
    headers = {"Authorization": f"Bearer {user['token']}"}

    assert try_acquire_crawl_slot()
    try:
        resp = client.post("/api/crawl-runs", json={"institution_ids": [1]}, headers=headers)
        assert resp.status_code == 409
        assert "进行中" in resp.json()["detail"]
    finally:
        release_crawl_slot()

    # 释放后可正常启动
    resp = client.post("/api/crawl-runs", json={"institution_ids": [1]}, headers=headers)
    assert resp.status_code == 201, resp.text
    wait_for_run(client, resp.json()["id"])


def test_crawl_requires_auth(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/api/crawl-runs", json={"institution_ids": [1]})
    assert resp.status_code == 401


# ── 每日自动循环 ────────────────────────────────────────────────────


def test_auto_cycle_creates_auto_run_then_scans_subscriptions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auto.db'}")
    init_db(engine)

    from app.services.auth import hash_password
    from app.services.repositories import create_subscription, create_user

    password_hash, password_salt = hash_password("secret123")
    user = create_user(engine, "auto_user", password_hash, password_salt)
    # 关键词命中机构 1 的 fixture 岗位（护理），抓取后应产生新的可推送岗位
    sub = create_subscription(engine, user["id"], "护理订阅", "护理", [1])
    _backdate_subscription(engine, sub["id"], days=2)

    scheduler = DailyScheduler(
        engine,
        hour=9,
        minute=0,
        enabled=False,
        clock=lambda: FIXED_TIME,
        auto_crawl=True,
        crawl_delay=0,
    )
    result = scheduler.run_cycle_once()

    assert result["crawl"] is not None
    # fixture 机构离线必有产出；真实适配器在离线环境会失败（partial），符合 U4「有产出或明确失败」
    assert result["crawl"]["success_count"] >= 1
    assert result["scan"]["pushed"] >= 1

    auto_runs = [item for item in list_crawl_runs(engine) if item["trigger"] == "auto"]
    assert len(auto_runs) == 1
    assert auto_runs[0]["success_count"] >= 1

    with connect(engine) as conn:
        pushed_at = conn.execute(
            "SELECT last_pushed_at FROM subscriptions WHERE id = ?", (sub["id"],)
        ).fetchone()["last_pushed_at"]
    assert pushed_at > _backdate_iso(days=2)


def _backdate_iso(days: float) -> str:
    """相对注入时钟取历史时间点：真实墙时已越过 FIXED_TIME，按 now 回溯会让断言变成时间炸弹。"""
    from datetime import timedelta

    return (FIXED_TIME - timedelta(days=days)).isoformat()


def test_auto_cycle_skips_crawl_when_slot_busy(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'busy.db'}")
    init_db(engine)

    scheduler = DailyScheduler(
        engine,
        hour=9,
        minute=0,
        enabled=False,
        clock=lambda: FIXED_TIME,
        auto_crawl=True,
        crawl_delay=0,
    )

    assert try_acquire_crawl_slot()
    try:
        result = scheduler.run_cycle_once()
    finally:
        release_crawl_slot()

    assert result["crawl"] is None
    assert result["scan"] is not None  # 扫描不受单飞阻塞

    from app.services.repositories import list_crawl_runs

    assert list_crawl_runs(engine) == []  # 未创建任何跑批记录


def test_auto_cycle_disabled_crawl_still_scans(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'nodb.db'}")
    init_db(engine)

    scheduler = DailyScheduler(
        engine,
        hour=9,
        minute=0,
        enabled=False,
        clock=lambda: FIXED_TIME,
        auto_crawl=False,
    )
    result = scheduler.run_cycle_once()
    assert result["crawl"] is None
    assert result["scan"] is not None


# ── 既有库迁移 ──────────────────────────────────────────────────────


def test_init_db_migrates_crawl_runs_trigger_column(tmp_path):
    """旧库 crawl_runs 缺 trigger 列时，init_db 补列且历史记录视为 manual。"""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE crawl_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            institution_ids TEXT NOT NULL,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            error_summary TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    conn.execute(
        "INSERT INTO crawl_runs (status, started_at, institution_ids) VALUES ('completed', '2026-08-01T00:00:00+00:00', '[1]')"
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)

    with connect(engine) as migrated:
        cols = {row["name"] for row in migrated.execute("PRAGMA table_info(crawl_runs)").fetchall()}
        assert "trigger" in cols
        row = migrated.execute("SELECT trigger FROM crawl_runs").fetchone()
        assert row["trigger"] == "manual"


# ── 启动补跑（P0-3）：进程错过时钟点时按 24h 内有无 auto 抓取决定是否补跑 ──


def _insert_auto_run(engine, started_iso: str) -> None:
    with connect(engine) as conn:
        conn.execute(
            """
            INSERT INTO crawl_runs (status, started_at, completed_at, institution_ids,
                                    success_count, failure_count, error_summary, trigger)
            VALUES ('completed', ?, ?, '[1]', 1, 0, '[]', 'auto')
            """,
            (started_iso, started_iso),
        )
        conn.commit()


def test_startup_catch_up_runs_when_no_recent_auto_run(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catchup_fresh.db'}")
    init_db(engine)
    scheduler = DailyScheduler(
        engine, hour=9, minute=0, enabled=False,
        clock=lambda: FIXED_TIME, auto_crawl=True, crawl_delay=0,
    )
    result = scheduler.maybe_catch_up()
    assert result is not None and result["crawl"] is not None
    auto_runs = [r for r in list_crawl_runs(engine) if r["trigger"] == "auto"]
    assert len(auto_runs) == 1


def test_startup_catch_up_skips_when_auto_run_within_24h(tmp_path):
    """昨天 09:00 已自动抓取过 → 今天 09:00 重启不重跑（避免重复抓取）。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'catchup_recent.db'}")
    init_db(engine)
    _insert_auto_run(engine, "2026-08-31T09:00:00+00:00")  # FIXED_TIME 前 24h 整
    scheduler = DailyScheduler(
        engine, hour=9, minute=0, enabled=False,
        clock=lambda: FIXED_TIME, auto_crawl=True, crawl_delay=0,
    )
    assert scheduler.maybe_catch_up() is None
    assert len([r for r in list_crawl_runs(engine) if r["trigger"] == "auto"]) == 1


def test_startup_catch_up_runs_when_last_auto_run_older_than_24h(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catchup_stale.db'}")
    init_db(engine)
    _insert_auto_run(engine, "2026-08-30T08:00:00+00:00")  # 距 FIXED_TIME 超 24h
    scheduler = DailyScheduler(
        engine, hour=9, minute=0, enabled=False,
        clock=lambda: FIXED_TIME, auto_crawl=True, crawl_delay=0,
    )
    result = scheduler.maybe_catch_up()
    assert result is not None
    assert len([r for r in list_crawl_runs(engine) if r["trigger"] == "auto"]) == 2


def test_startup_catch_up_disabled_with_auto_crawl_off(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catchup_off.db'}")
    init_db(engine)
    scheduler = DailyScheduler(
        engine, hour=9, minute=0, enabled=False,
        clock=lambda: FIXED_TIME, auto_crawl=False,
    )
    assert scheduler.maybe_catch_up() is None
    assert list_crawl_runs(engine) == []
