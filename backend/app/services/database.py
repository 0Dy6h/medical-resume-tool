from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote

from app.services.seeds import SEED_INSTITUTIONS


@dataclass(frozen=True)
class DatabaseEngine:
    database_url: str
    path: Path


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        super().__exit__(exc_type, exc, traceback)
        self.close()


def create_engine(database_url: str) -> DatabaseEngine:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// database URLs are supported in the MVP")
    raw_path = unquote(database_url.removeprefix("sqlite:///"))
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return DatabaseEngine(database_url=database_url, path=path)


def connect(engine: DatabaseEngine) -> sqlite3.Connection:
    conn = sqlite3.connect(engine.path, check_same_thread=False, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def from_json(value: str | None, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)


def reset_db(engine: DatabaseEngine) -> None:
    if engine.path.exists():
        engine.path.unlink()


def init_db(engine: DatabaseEngine) -> None:
    with connect(engine) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS institutions (
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

            CREATE TABLE IF NOT EXISTS crawl_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                institution_ids TEXT NOT NULL,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                error_summary TEXT NOT NULL DEFAULT '[]',
                trigger TEXT NOT NULL DEFAULT 'manual'
            );

            CREATE TABLE IF NOT EXISTS jobs (
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
                source_url TEXT NOT NULL,
                source_text_hash TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                tags TEXT NOT NULL,
                extraction_evidence TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                parser_name TEXT NOT NULL,
                confidence REAL NOT NULL,
                -- A4 溯源：岗位身份 = 机构 + 来源 URL，两家机构的同一公告互不吞并
                UNIQUE(institution_id, source_url)
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(job_category);
            CREATE INDEX IF NOT EXISTS idx_jobs_region ON jobs(region);
            CREATE INDEX IF NOT EXISTS idx_jobs_institution ON jobs(institution_id);

            CREATE TABLE IF NOT EXISTS job_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                source_text_hash TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                parser_name TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                captured_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_job_snapshots_job ON job_snapshots(job_id);

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resume_drafts (
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

            CREATE TABLE IF NOT EXISTS job_statuses (
                user_id INTEGER NOT NULL REFERENCES users(id),
                job_id INTEGER NOT NULL REFERENCES jobs(id),
                status TEXT NOT NULL,
                note TEXT,
                deadline TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, job_id)
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                markdown TEXT NOT NULL,
                html TEXT NOT NULL,
                filters TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    keyword TEXT NOT NULL,
    institution_ids TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    last_pushed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
    );

            CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
                subscription_name TEXT NOT NULL,
                keyword TEXT NOT NULL,
                job_count INTEGER NOT NULL,
                job_ids TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                read_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
            """
        )
        _migrate_subscriptions_add_last_pushed_at(conn)
        _migrate_crawl_runs_add_trigger(conn)
        _migrate_jobs_identity_key(conn)
        _migrate_user_scoped_tables(conn)
        count = conn.execute("SELECT COUNT(*) AS count FROM institutions").fetchone()["count"]
        if count == 0:
            conn.executemany(
                """
                INSERT INTO institutions (
                    id, name, institution_type, region, official_url, listing_url,
                    crawl_strategy, enabled
                ) VALUES (
                    :id, :name, :institution_type, :region, :official_url, :listing_url,
                    :crawl_strategy, :enabled
                )
                """,
                [{**item, "enabled": 1 if item["enabled"] else 0} for item in SEED_INSTITUTIONS],
            )
        conn.commit()


def _migrate_subscriptions_add_last_pushed_at(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(subscriptions)").fetchall()}
    if cols and "last_pushed_at" not in cols:
        conn.execute("ALTER TABLE subscriptions ADD COLUMN last_pushed_at TEXT")


def _migrate_crawl_runs_add_trigger(conn: sqlite3.Connection) -> None:
    """A3 自动抓取：既有库的 crawl_runs 补 trigger 列，历史记录视为手动触发。"""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(crawl_runs)").fetchall()}
    if cols and "trigger" not in cols:
        conn.execute("ALTER TABLE crawl_runs ADD COLUMN trigger TEXT NOT NULL DEFAULT 'manual'")


def _jobs_has_url_only_unique(conn: sqlite3.Connection) -> bool:
    """旧身份约束检测：存在仅覆盖 source_url 的唯一索引即为旧库。"""
    for row in conn.execute("PRAGMA index_list(jobs)").fetchall():
        if not row["unique"]:
            continue
        cols = [
            info["name"]
            for info in conn.execute(f'PRAGMA index_info("{row["name"]}")').fetchall()
        ]
        if cols == ["source_url"]:
            return True
    return False


def _migrate_jobs_identity_key(conn: sqlite3.Connection) -> None:
    """A4 溯源：jobs 唯一约束从全局 source_url 重建为 (institution_id, source_url)。

    旧约束会让两家机构共用同一公告 URL 时互相覆盖（错挂）；新身份键让镜像
    公告各自成行。按 SQLite 官方表重建流程执行，行 id 原样保留，引用 jobs
    的外键文本不受影响。
    """
    if not _jobs_has_url_only_unique(conn):
        return
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.executescript(
            """
            CREATE TABLE jobs_new (
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
                source_url TEXT NOT NULL,
                source_text_hash TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                tags TEXT NOT NULL,
                extraction_evidence TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                parser_name TEXT NOT NULL,
                confidence REAL NOT NULL,
                UNIQUE(institution_id, source_url)
            );

            INSERT INTO jobs_new (
                id, institution_id, institution_name, institution_type, region,
                title, department, location, education, profession, job_category,
                responsibilities, requirements, posted_at, deadline, source_url,
                source_text_hash, raw_text, tags, extraction_evidence, fetched_at,
                parser_name, confidence
            )
            SELECT
                id, institution_id, institution_name, institution_type, region,
                title, department, location, education, profession, job_category,
                responsibilities, requirements, posted_at, deadline, source_url,
                source_text_hash, raw_text, tags, extraction_evidence, fetched_at,
                parser_name, confidence
            FROM jobs;

            DROP TABLE jobs;
            ALTER TABLE jobs_new RENAME TO jobs;

            CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(job_category);
            CREATE INDEX IF NOT EXISTS idx_jobs_region ON jobs(region);
            CREATE INDEX IF NOT EXISTS idx_jobs_institution ON jobs(institution_id);
            """
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    allowed_tables = {"profiles", "resume_drafts"}
    if table not in allowed_tables:
        raise ValueError(f"Unsupported table for schema inspection: {table}")
    return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _migrate_user_scoped_tables(conn: sqlite3.Connection) -> None:
    profile_columns = _table_columns(conn, "profiles")
    if profile_columns and "user_id" not in profile_columns and {"id", "data", "updated_at"}.issubset(profile_columns):
        conn.executescript(
            """
            ALTER TABLE profiles RENAME TO profiles_legacy;

            CREATE TABLE profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            INSERT INTO profiles (user_id, data, updated_at)
            SELECT id, data, updated_at
            FROM profiles_legacy
            WHERE EXISTS (SELECT 1 FROM users WHERE users.id = profiles_legacy.id);

            DELETE FROM profiles_legacy
            WHERE EXISTS (SELECT 1 FROM users WHERE users.id = profiles_legacy.id);
            """
        )
        remaining_profiles = conn.execute("SELECT COUNT(*) AS count FROM profiles_legacy").fetchone()["count"]
        if remaining_profiles == 0:
            conn.execute("DROP TABLE profiles_legacy")

    draft_columns = _table_columns(conn, "resume_drafts")
    if draft_columns and "user_id" not in draft_columns and {"profile_id", "job_id", "title", "sections", "evidence", "gaps", "created_at", "updated_at"}.issubset(draft_columns):
        conn.executescript(
            """
            ALTER TABLE resume_drafts RENAME TO resume_drafts_legacy;

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

            INSERT INTO resume_drafts (id, user_id, job_id, title, sections, evidence, gaps, created_at, updated_at)
            SELECT id, CAST(profile_id AS INTEGER), job_id, title, sections, evidence, gaps, created_at, updated_at
            FROM resume_drafts_legacy
            WHERE EXISTS (SELECT 1 FROM users WHERE users.id = CAST(resume_drafts_legacy.profile_id AS INTEGER))
              AND EXISTS (SELECT 1 FROM jobs WHERE jobs.id = resume_drafts_legacy.job_id);

            DELETE FROM resume_drafts_legacy
            WHERE EXISTS (SELECT 1 FROM users WHERE users.id = CAST(resume_drafts_legacy.profile_id AS INTEGER))
              AND EXISTS (SELECT 1 FROM jobs WHERE jobs.id = resume_drafts_legacy.job_id);
            """
        )
        remaining_drafts = conn.execute("SELECT COUNT(*) AS count FROM resume_drafts_legacy").fetchone()["count"]
        if remaining_drafts == 0:
            conn.execute("DROP TABLE resume_drafts_legacy")
