"""cleanup_test_accounts 工具测试：模式匹配、保护边界、FK 安全删除。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.database import connect, create_engine, init_db
from scripts.cleanup_test_accounts import CHILD_TABLES, match_users, purge


def make_db(tmp_path: Path) -> sqlite3.Connection:
    engine = create_engine(f"sqlite:///{tmp_path / 'cleanup-test.db'}")
    init_db(engine)
    conn = connect(engine)
    now = "2026-09-06T10:00:00"
    users = [
        ("1203525437@qq.com",),  # 真实用户，天然不受默认模式匹配
        ("trial_b5_r1",),
        ("trial_zhang",),
        ("verify_ui",),
        ("smoke_u5",),
        ("pm_review_2609",),
        ("123",),  # 垃圾名，不匹配默认模式，须 --also 显式点名
        ("has space",),
    ]
    for i, (username,) in enumerate(users, 1):
        conn.execute(
            "INSERT INTO users (id, username, password_hash, password_salt, created_at) VALUES (?,?,?,?,?)",
            (i, username, "h", "s", now),
        )
    # id=2 trial_b5_r1：全套依赖行；id=3 trial_zhang：仅 profile
    # （init_db 迁移会预置真实 institutions 种子，故不自指 id，用 lastrowid 回填）
    cur = conn.execute(
        "INSERT INTO institutions (name, institution_type, region, official_url, listing_url, crawl_strategy)"
        " VALUES ('测试医院','hospital','浙江','http://x','http://x/list','static')"
    )
    institution_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO jobs (institution_id, institution_name, institution_type, region, title, job_category,"
        " source_url, source_text_hash, raw_text, tags, extraction_evidence, fetched_at, parser_name, confidence)"
        " VALUES (?, '测试医院','hospital','浙江','科研助理','科研','http://x/y','hash','raw','[]','[]',?,'test',1.0)",
        (institution_id, now),
    )
    job_id = cur.lastrowid
    conn.execute("INSERT INTO profiles (user_id, data, updated_at) VALUES (2,'{}',?)", (now,))
    conn.execute("INSERT INTO resume_drafts (user_id, job_id, title, sections, evidence, gaps, created_at, updated_at) VALUES (2,?,'t','[]','[]','[]',?,?)", (job_id, now, now))
    conn.execute("INSERT INTO job_statuses (user_id, job_id, status, created_at, updated_at) VALUES (2,?,'saved',?,?)", (job_id, now, now))
    conn.execute("INSERT INTO subscriptions (user_id, name, keyword, institution_ids, last_checked_at, created_at, updated_at) VALUES (2,'订阅','中医','[]',?,?,?)", (now, now, now))
    conn.execute("INSERT INTO notifications (user_id, subscription_id, subscription_name, keyword, job_count, job_ids, summary, created_at) VALUES (2,1,'订阅','中医',0,'[]','s',?)", (now,))
    conn.execute("INSERT INTO profiles (user_id, data, updated_at) VALUES (3,'{}',?)", (now,))
    conn.commit()
    return conn


def test_match_users_hits_test_patterns_and_spares_real_users(tmp_path):
    conn = make_db(tmp_path)
    try:
        targets = match_users(conn, ["trial_*", "verify*", "smoke_*", "pm_review_*"], [])
        names = {t["username"] for t in targets}
        assert names == {"trial_b5_r1", "trial_zhang", "verify_ui", "smoke_u5", "pm_review_2609"}
        b5 = next(t for t in targets if t["username"] == "trial_b5_r1")
        assert b5["deps"] == {"notifications": 1, "subscriptions": 1, "resume_drafts": 1, "job_statuses": 1, "profiles": 1}
    finally:
        conn.close()


def test_explicit_extra_catches_garbage_names_without_patterns(tmp_path):
    conn = make_db(tmp_path)
    try:
        targets = match_users(conn, ["trial_*"], ["123", "has space"])
        assert {t["username"] for t in targets} == {"trial_b5_r1", "trial_zhang", "123", "has space"}
    finally:
        conn.close()


def test_purge_deletes_children_first_and_keeps_real_user(tmp_path):
    conn = make_db(tmp_path)
    try:
        targets = match_users(conn, ["trial_*", "verify*", "smoke_*", "pm_review_*"], ["123", "has space"])
        deleted = purge(conn, targets)
        assert deleted == 7
        remaining = {r["username"] for r in conn.execute("SELECT username FROM users").fetchall()}
        assert remaining == {"1203525437@qq.com"}
        # FK 安全：所有子表无孤儿行
        for table in CHILD_TABLES:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0, f"{table} 残留 {count} 行"
    finally:
        conn.close()
