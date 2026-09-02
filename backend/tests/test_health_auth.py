"""B1 数据健康视图 + D2 认证密钥持久化。"""
from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.database import connect, init_db, reset_db


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


def _fail_times(client: TestClient, institution_id: int, times: int, error: str = "ERR") -> None:
    from app.services.repositories import mark_institution

    engine = client.app.state.engine
    for _ in range(times):
        mark_institution(engine, institution_id, "failed", error)


# ── B1 连续失败计数与 review 状态 ───────────────────────────────────


def test_single_failure_stays_failed_not_review(tmp_path):
    client = make_client(tmp_path)
    _fail_times(client, 1, 1)
    items = {i["id"]: i for i in client.get("/api/institutions").json()}
    assert items[1]["last_status"] == "failed"
    assert items[1]["consecutive_failures"] == 1


def test_consecutive_failures_reach_review_threshold(tmp_path):
    client = make_client(tmp_path)
    _fail_times(client, 1, 2, "解析零产出")
    items = {i["id"]: i for i in client.get("/api/institutions").json()}
    assert items[1]["last_status"] == "review"
    assert items[1]["consecutive_failures"] == 2


def test_success_resets_failure_counter(tmp_path):
    client = make_client(tmp_path)
    _fail_times(client, 1, 3)
    from app.services.repositories import mark_institution

    mark_institution(client.app.state.engine, 1, "success")
    items = {i["id"]: i for i in client.get("/api/institutions").json()}
    assert items[1]["last_status"] == "success"
    assert items[1]["consecutive_failures"] == 0


def test_health_endpoint_lists_unhealthy_only(tmp_path):
    client = make_client(tmp_path)
    headers = register(client, "health_user")
    _fail_times(client, 1, 2)
    _fail_times(client, 2, 1)

    payload = client.get("/api/institutions/health", headers=headers).json()
    assert payload["threshold"] == 2
    ids = {item["id"] for item in payload["institutions"]}
    assert ids == {1}
    assert payload["review_count"] == 1


def test_health_requires_auth(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/institutions/health").status_code == 401


def test_legacy_db_gets_consecutive_failures_column(tmp_path):
    """旧库缺 consecutive_failures 列时 init_db 自动补齐且默认 0。"""
    import sqlite3

    from app.services.database import create_engine

    db_path = tmp_path / "legacy-inst.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE institutions (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            institution_type TEXT NOT NULL,
            region TEXT NOT NULL,
            official_url TEXT NOT NULL,
            listing_url TEXT NOT NULL,
            crawl_strategy TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_crawled_at TEXT,
            last_status TEXT DEFAULT 'never',
            last_error TEXT
        );
        INSERT INTO institutions (id, name, institution_type, region, official_url, listing_url, crawl_strategy, enabled)
        VALUES (1, '甲', '医院', '广州', 'https://a.test', 'fixture://institution/1', 'fixture', 1);
        """
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)
    with connect(engine) as c:
        row = c.execute(
            "SELECT consecutive_failures FROM institutions WHERE id = 1"
        ).fetchone()
    assert row["consecutive_failures"] == 0


# ── B1 一键重跑 ─────────────────────────────────────────────────────


def test_recrawl_institution_success_and_guards(tmp_path):
    client = make_client(tmp_path)
    headers = register(client, "recrawl_user")

    # 未适配机构拒绝
    resp = client.post("/api/institutions/8/recrawl", headers=headers)
    assert resp.status_code == 400

    # 正常重跑 fixture 机构
    resp = client.post("/api/institutions/1/recrawl", headers=headers)
    assert resp.status_code == 201, resp.text
    run = resp.json()
    deadline = time.time() + 30
    while time.time() < deadline:
        done = client.get(f"/api/crawl-runs/{run['id']}").json()
        if done["status"] in ("completed", "partial", "failed"):
            break
        time.sleep(0.02)
    assert done["status"] == "completed"
    assert done["success_count"] >= 1

    # 需要登录
    anon = client.post("/api/institutions/1/recrawl")
    assert anon.status_code == 401


# ── D2 密钥持久化 ───────────────────────────────────────────────────


def test_auth_secret_persists_across_reload(tmp_path, monkeypatch):
    """未设置 AUTH_SECRET 时密钥落盘，重载后复用同一密钥。"""
    data_dir = tmp_path / "authdata"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.delenv("AUTH_SECRET", raising=False)

    import importlib

    from app.services import auth

    importlib.reload(auth)
    first = auth.SECRET
    assert (data_dir / ".auth_secret").exists()
    assert first == (data_dir / ".auth_secret").read_text().strip()

    importlib.reload(auth)
    assert auth.SECRET == first

    # 环境变量优先
    monkeypatch.setenv("AUTH_SECRET", "env-fixed-secret")
    importlib.reload(auth)
    assert auth.SECRET == "env-fixed-secret"
    importlib.reload(auth)  # 还原为文件态，避免污染其他测试


def test_token_survives_secret_reload(tmp_path, monkeypatch):
    """同一持久化密钥下，重启（重载模块）前后 token 均可验证。"""
    data_dir = tmp_path / "authdata2"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.delenv("AUTH_SECRET", raising=False)

    import importlib

    from app.services import auth

    importlib.reload(auth)
    token = auth.make_token(42, "alice")
    assert auth.verify_token(token) is not None

    importlib.reload(auth)  # 模拟重启
    payload = auth.verify_token(token)
    assert payload is not None
    assert payload["uid"] == 42
