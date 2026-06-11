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
                error_summary TEXT NOT NULL DEFAULT '[]'
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
                source_url TEXT NOT NULL UNIQUE,
                source_text_hash TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                tags TEXT NOT NULL,
                extraction_evidence TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                parser_name TEXT NOT NULL,
                confidence REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(job_category);
            CREATE INDEX IF NOT EXISTS idx_jobs_region ON jobs(region);
            CREATE INDEX IF NOT EXISTS idx_jobs_institution ON jobs(institution_id);

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

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                markdown TEXT NOT NULL,
                html TEXT NOT NULL,
                filters TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
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
