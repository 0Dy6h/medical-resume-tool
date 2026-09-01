"""U6 溯源与快照：岗位身份键、改版历史归档、镜像公告防吞并/防错挂。"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.crawler import parse_job_from_text
from app.services.database import connect, create_engine, init_db, reset_db
from app.services.repositories import list_job_snapshots, upsert_job

BODY_A = "岗位职责：负责病区护理工作。任职要求：护理学本科及以上，持有护士资格证。"
BODY_B = "岗位职责：负责病区护理与教学带教工作。任职要求：护理学本科及以上，持有护士资格证，有带教经验优先。"


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


def parsed(title: str, body: str, source_url: str, parser: str = "adapter-test"):
    return parse_job_from_text(
        title=title,
        body=body,
        source_url=source_url,
        institution_type="医院",
        region="广州",
        parser_name=parser,
    )


def crawl_and_wait(client: TestClient, institution_ids: list[int]) -> dict:
    headers = register(client, f"crawler-{institution_ids}")
    run = client.post(
        "/api/crawl-runs", json={"institution_ids": institution_ids}, headers=headers
    )
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]
    deadline = time.time() + 30
    while time.time() < deadline:
        payload = client.get(f"/api/crawl-runs/{run_id}").json()
        if payload["status"] in {"completed", "partial", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("crawl run did not finish")


def _job_count(engine, institution_id: int | None = None) -> int:
    with connect(engine) as conn:
        if institution_id is None:
            return conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
        return conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE institution_id = ?", (institution_id,)
        ).fetchone()["c"]


# ── 内容改版：历史正文可查 ──────────────────────────────────────────


def test_content_update_archives_previous_version(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'snap.db'}")
    init_db(engine)
    inst = {"id": 1, "name": "南方医院", "institution_type": "医院", "region": "广州"}

    assert upsert_job(engine, inst, parsed("护理护士", BODY_A, "https://nfyy.example.test/a1")) is True
    # 同一身份（机构+URL）内容改版 → 更新并归档旧版本
    assert upsert_job(engine, inst, parsed("护理护士（含带教）", BODY_B, "https://nfyy.example.test/a1")) is False

    assert _job_count(engine) == 1
    snapshots = list_job_snapshots(engine, 1)
    assert len(snapshots) == 1
    assert "岗位职责：负责病区护理工作" in snapshots[0]["raw_text"]
    assert snapshots[0]["captured_at"]

    # 现行为最新内容
    with connect(engine) as conn:
        row = conn.execute("SELECT raw_text, source_text_hash FROM jobs WHERE id = 1").fetchone()
    assert "岗位职责：负责病区护理与教学带教" in row["raw_text"]

    # 内容再次改版 → 两份历史
    assert upsert_job(engine, inst, parsed("护理护士（含教学）", BODY_A + "有科研经历者优先。", "https://nfyy.example.test/a1")) is False
    assert len(list_job_snapshots(engine, 1)) == 2


def test_unchanged_recrawl_updates_fetched_at_without_snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'same.db'}")
    init_db(engine)
    inst = {"id": 1, "name": "南方医院", "institution_type": "医院", "region": "广州"}

    assert upsert_job(engine, inst, parsed("护理护士", BODY_A, "https://nfyy.example.test/a1")) is True
    assert upsert_job(engine, inst, parsed("护理护士", BODY_A, "https://nfyy.example.test/a1")) is False

    assert _job_count(engine) == 1
    assert list_job_snapshots(engine, 1) == []


# ── 镜像公告：不吞并、不错挂 ────────────────────────────────────────


def test_same_text_different_urls_not_swallowed(tmp_path):
    """两家机构发布相同文本公告（各自 URL）→ 各自成行，互不吞并。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'mirror.db'}")
    init_db(engine)
    inst_a = {"id": 1, "name": "南方医院", "institution_type": "医院", "region": "广州"}
    inst_b = {"id": 2, "name": "浙大二院", "institution_type": "医院", "region": "杭州"}

    assert upsert_job(engine, inst_a, parsed("护理护士", BODY_A, "https://nfyy.example.test/a1")) is True
    assert upsert_job(engine, inst_b, parsed("护理护士", BODY_A, "https://z2hospital.example.org/b1")) is True

    assert _job_count(engine, 1) == 1
    assert _job_count(engine, 2) == 1
    with connect(engine) as conn:
        rows = conn.execute(
            "SELECT institution_id, source_url FROM jobs WHERE source_text_hash = ?",
            (parsed("护理护士", BODY_A, "x").source_text_hash,),
        ).fetchall()
    assert {row["institution_id"] for row in rows} == {1, 2}


def test_same_text_same_institution_different_urls_kept(tmp_path):
    """同一机构两篇相同文本公告（不同 URL）→ 两条记录。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'dup.db'}")
    init_db(engine)
    inst = {"id": 1, "name": "南方医院", "institution_type": "医院", "region": "广州"}

    assert upsert_job(engine, inst, parsed("护理护士", BODY_A, "https://nfyy.example.test/a1")) is True
    assert upsert_job(engine, inst, parsed("护理护士", BODY_A, "https://nfyy.example.test/a2")) is True
    assert _job_count(engine, 1) == 2


def test_same_url_different_institution_not_misattributed(tmp_path):
    """两家机构记录同一公告 URL → 各自成行，先入库一方内容不被覆盖错挂。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'shared.db'}")
    init_db(engine)
    inst_a = {"id": 1, "name": "南方医院", "institution_type": "医院", "region": "广州"}
    inst_b = {"id": 2, "name": "浙大二院", "institution_type": "医院", "region": "杭州"}
    shared_url = "https://shared.example.test/notice/100"

    assert upsert_job(engine, inst_a, parsed("护理护士", BODY_A, shared_url)) is True
    assert upsert_job(engine, inst_b, parsed("护理护士", BODY_B, shared_url)) is True

    with connect(engine) as conn:
        rows = conn.execute(
            "SELECT institution_id, raw_text FROM jobs WHERE source_url = ? ORDER BY institution_id",
            (shared_url,),
        ).fetchall()
    assert len(rows) == 2
    assert rows[0]["institution_id"] == 1
    assert "岗位职责：负责病区护理工作" in rows[0]["raw_text"]  # A 的内容未被 B 覆盖
    assert rows[1]["institution_id"] == 2


# ── 详情接口携带历史 ────────────────────────────────────────────────


def test_job_detail_includes_history(tmp_path):
    client = make_client(tmp_path)
    payload = crawl_and_wait(client, [1])
    assert payload["success_count"] >= 1

    jobs = client.get("/api/jobs", params={"institution_id": 1}).json()["items"]
    job_id = jobs[0]["id"]
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["history"] == []

    # 直接制造一次改版归档
    engine = client.app.state.engine
    previous_text = detail["raw_snapshot"]["raw_text"]
    inst = {"id": 1, "name": jobs[0]["institution_name"], "institution_type": "医院", "region": "广州"}
    upsert_job(
        engine,
        inst,
        parse_job_from_text(
            title=jobs[0]["title"] + "（更新）",
            body=previous_text + "本公告内容已更新，新增体检安排说明。",
            source_url=jobs[0]["source_url"],
            institution_type="医院",
            region="广州",
            parser_name="fixture-v1",
        ),
    )
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert len(detail["history"]) == 1
    assert detail["history"][0]["raw_text"] == previous_text


# ── 旧库身份键迁移 ──────────────────────────────────────────────────


def test_init_db_rebuilds_legacy_jobs_identity_key(tmp_path):
    """旧库（全局 source_url 唯一）init_db 后重建为 (institution_id, source_url)，数据保留。"""
    db_path = tmp_path / "legacy-jobs.db"
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
        VALUES (1, '甲医院', '医院', '广州', 'https://a.test', 'https://a.test/list', 'generic', 1),
               (2, '乙医院', '医院', '杭州', 'https://b.test', 'https://b.test/list', 'generic', 1);
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_id INTEGER NOT NULL REFERENCES institutions(id),
            institution_name TEXT NOT NULL,
            institution_type TEXT NOT NULL,
            region TEXT NOT NULL,
            title TEXT NOT NULL,
            department TEXT,
            location TEXT,
            education TEXT,
            profession TEXT,
            job_category TEXT NOT NULL,
            responsibilities TEXT,
            requirements TEXT,
            posted_at TEXT,
            deadline TEXT,
            source_url TEXT NOT NULL UNIQUE,
            source_text_hash TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            tags TEXT NOT NULL,
            extraction_evidence TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            parser_name TEXT NOT NULL,
            confidence REAL NOT NULL
        );
        INSERT INTO jobs (
            institution_id, institution_name, institution_type, region, title,
            job_category, source_url, source_text_hash, raw_text, tags,
            extraction_evidence, fetched_at, parser_name, confidence
        ) VALUES (
            1, '甲医院', '医院', '广州', '旧岗位',
            '临床', 'https://shared.test/notice/1', 'hash-1', '旧正文', '[]',
            '{}', '2026-08-01T00:00:00+00:00', 'legacy-parser', 0.9
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE resume_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            title TEXT NOT NULL,
            sections TEXT NOT NULL,
            evidence TEXT NOT NULL,
            gaps TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)

    with connect(engine) as migrated:
        # 唯一约束现在是 (institution_id, source_url)
        uniques = []
        for idx in migrated.execute("PRAGMA index_list(jobs)").fetchall():
            if idx["unique"]:
                cols = [
                    info["name"]
                    for info in migrated.execute(f'PRAGMA index_info("{idx["name"]}")').fetchall()
                ]
                uniques.append(cols)
        assert ["institution_id", "source_url"] in uniques
        assert ["source_url"] not in uniques

        # 数据原样保留，行 id 不变
        row = migrated.execute(
            "SELECT id, institution_id, title, raw_text FROM jobs"
        ).fetchone()
        assert row["id"] == 1
        assert row["title"] == "旧岗位"

        # 引用 jobs 的外键仍然成立（PRAGMA foreign_key_check 无输出）
        assert migrated.execute("PRAGMA foreign_key_check").fetchall() == []
