from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.database import (
    DatabaseEngine,
    connect,
    from_json,
    row_to_dict,
    rows_to_dicts,
    to_json,
)
from app.services.keyword_match import refine_keyword_hits
from app.schemas import Profile


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 数据可信度分级（A1）─────────────────────────────────────────────
# real：真实适配器产出且机构当前启用；
# placeholder：generic 占位解析器产出（正文为占位文本，需人工复核）；
# fixture：内置演示数据；
# disabled：机构已禁用，其历史数据降级为历史档案。
FIXTURE_PARSERS = frozenset({"fixture-v1"})
PLACEHOLDER_PARSERS = frozenset({"generic-list-v1", "generic-page-v1"})


def classify_job_trust(parser_name: str | None, institution_enabled: bool) -> str:
    if not institution_enabled:
        return "disabled"
    if parser_name in FIXTURE_PARSERS:
        return "fixture"
    if parser_name in PLACEHOLDER_PARSERS:
        return "placeholder"
    return "real"


def enabled_institution_ids(conn: Any) -> set[int]:
    rows = conn.execute("SELECT id FROM institutions WHERE enabled = 1").fetchall()
    return {int(row["id"]) for row in rows}


def list_institutions(engine: DatabaseEngine) -> list[dict[str, Any]]:
    with connect(engine) as conn:
        rows = conn.execute("SELECT * FROM institutions ORDER BY id").fetchall()
    items = rows_to_dicts(rows)
    for item in items:
        item["enabled"] = bool(item["enabled"])
    return items


def get_institutions_by_ids(engine: DatabaseEngine, ids: list[int] | None) -> list[dict[str, Any]]:
    with connect(engine) as conn:
        if ids:
            placeholders = ",".join("?" for _ in ids)
            rows = conn.execute(f"SELECT * FROM institutions WHERE id IN ({placeholders}) ORDER BY id", ids).fetchall()
        else:
            rows = conn.execute("SELECT * FROM institutions WHERE enabled = 1 ORDER BY id").fetchall()
    items = rows_to_dicts(rows)
    for item in items:
        item["enabled"] = bool(item["enabled"])
    return items


def create_crawl_run(engine: DatabaseEngine, institution_ids: list[int], trigger: str = "manual") -> int:
    with connect(engine) as conn:
        cur = conn.execute(
            """
            INSERT INTO crawl_runs (status, started_at, institution_ids, error_summary, trigger)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("running", now_iso(), to_json(institution_ids), "[]", trigger),
        )
        conn.commit()
        return int(cur.lastrowid)


def complete_crawl_run(
    engine: DatabaseEngine,
    run_id: int,
    *,
    success_count: int,
    failure_count: int,
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute("SELECT institution_ids FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
        institution_count = len(from_json(row["institution_ids"], [])) if row else 0
        if failure_count == 0:
            status = "completed"
        elif failure_count >= institution_count:
            status = "failed"
        else:
            status = "partial"
        conn.execute(
            """
            UPDATE crawl_runs
            SET status = ?, completed_at = ?, success_count = ?, failure_count = ?, error_summary = ?
            WHERE id = ?
            """,
            (status, now_iso(), success_count, failure_count, to_json(errors), run_id),
        )
        conn.commit()
    return get_crawl_run(engine, run_id)


def update_crawl_progress(
    engine: DatabaseEngine,
    run_id: int,
    *,
    success_count: int,
    failure_count: int,
    errors: list[dict[str, Any]],
) -> None:
    """Persist intermediate progress so polling clients can see live counts."""
    with connect(engine) as conn:
        conn.execute(
            """
            UPDATE crawl_runs
            SET success_count = ?, failure_count = ?, error_summary = ?
            WHERE id = ?
            """,
            (success_count, failure_count, to_json(errors), run_id),
        )
        conn.commit()


def get_crawl_run(engine: DatabaseEngine, run_id: int) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise KeyError(run_id)
    return _crawl_run_row_to_dict(row)


def list_crawl_runs(engine: DatabaseEngine, limit: int = 10) -> list[dict[str, Any]]:
    """按最新优先返回抓取任务（含手动与自动触发）。"""
    with connect(engine) as conn:
        rows = conn.execute(
            "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_crawl_run_row_to_dict(row) for row in rows]


def _crawl_run_row_to_dict(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["institution_ids"] = from_json(item["institution_ids"], [])
    errors = from_json(item["error_summary"], [])
    item["error_summary"] = errors
    item["errors"] = errors
    return item


def upsert_job(engine: DatabaseEngine, institution: dict[str, Any], parsed: Any) -> bool:
    """按身份键 (institution_id, source_url) 落库（A4 溯源语义）。

    返回 True 表示新增岗位；内容改版时旧正文先归档到 job_snapshots 再更新，
    历史正文始终可查；不同机构/不同 URL 的相同文本公告互不吞并。
    """
    payload = {
        "institution_id": institution["id"],
        "institution_name": institution["name"],
        "institution_type": institution["institution_type"],
        "region": institution["region"],
        "title": parsed.title,
        "department": parsed.department,
        "location": parsed.location,
        "education": parsed.education,
        "profession": parsed.profession,
        "job_category": parsed.job_category,
        "responsibilities": parsed.responsibilities,
        "requirements": parsed.requirements,
        "posted_at": parsed.posted_at,
        "deadline": parsed.deadline,
        "source_url": parsed.source_url,
        "source_text_hash": parsed.source_text_hash,
        "raw_text": parsed.raw_text,
        "tags": to_json(parsed.tags),
        "extraction_evidence": to_json(parsed.extraction_evidence),
        "fetched_at": parsed.fetched_at,
        "parser_name": parsed.parser_name,
        "confidence": parsed.confidence,
    }
    with connect(engine) as conn:
        existing = conn.execute(
            "SELECT id, source_text_hash FROM jobs WHERE institution_id = ? AND source_url = ?",
            (institution["id"], parsed.source_url),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO jobs (
                    institution_id, institution_name, institution_type, region, title, department,
                    location, education, profession, job_category, responsibilities, requirements,
                    posted_at, deadline, source_url, source_text_hash, raw_text, tags,
                    extraction_evidence, fetched_at, parser_name, confidence
                ) VALUES (
                    :institution_id, :institution_name, :institution_type, :region, :title, :department,
                    :location, :education, :profession, :job_category, :responsibilities, :requirements,
                    :posted_at, :deadline, :source_url, :source_text_hash, :raw_text, :tags,
                    :extraction_evidence, :fetched_at, :parser_name, :confidence
                )
                """,
                payload,
            )
            conn.commit()
            return True

        if existing["source_text_hash"] == parsed.source_text_hash:
            # 同一身份、内容未变：仅刷新抓取时间，保留首次入库语义
            conn.execute(
                "UPDATE jobs SET fetched_at = ? WHERE id = ?",
                (parsed.fetched_at, existing["id"]),
            )
            conn.commit()
            return False

        # 内容改版：归档旧版本，再更新为最新内容（公告改版后历史正文可查）
        previous = conn.execute(
            "SELECT source_text_hash, raw_text, parser_name, fetched_at FROM jobs WHERE id = ?",
            (existing["id"],),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO job_snapshots (job_id, source_text_hash, raw_text, parser_name, fetched_at, captured_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                existing["id"],
                previous["source_text_hash"],
                previous["raw_text"],
                previous["parser_name"],
                previous["fetched_at"],
                now_iso(),
            ),
        )
        conn.execute(
            """
            UPDATE jobs SET
                title=:title, department=:department, location=:location, education=:education,
                profession=:profession, job_category=:job_category, responsibilities=:responsibilities,
                requirements=:requirements, posted_at=:posted_at, deadline=:deadline,
                source_text_hash=:source_text_hash, raw_text=:raw_text, tags=:tags,
                extraction_evidence=:extraction_evidence, fetched_at=:fetched_at,
                parser_name=:parser_name, confidence=:confidence
            WHERE id=:job_id
            """,
            {**payload, "job_id": existing["id"]},
        )
        conn.commit()
        return False


def list_job_snapshots(engine: DatabaseEngine, job_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """岗位历史版本（最新改版在前），用于详情页溯源。"""
    with connect(engine) as conn:
        rows = conn.execute(
            """
            SELECT source_text_hash, raw_text, parser_name, fetched_at, captured_at
            FROM job_snapshots WHERE job_id = ? ORDER BY id DESC LIMIT ?
            """,
            (job_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


FAILURE_REVIEW_THRESHOLD = 2  # 连续失败达到该次数即进入 review 状态（B1）


def mark_institution(engine: DatabaseEngine, institution_id: int, status: str, error: str | None = None) -> None:
    """记录单机构最近一次抓取结果，并维护连续失败计数（B1 健康度）。

    - 成功：计数清零；
    - 失败：计数 +1，达到 FAILURE_REVIEW_THRESHOLD 后 last_status 升级为
      'review'，提示需要人工复核（连续失败 / 持续失明）。
    """
    now = now_iso()
    with connect(engine) as conn:
        if status == "success":
            conn.execute(
                """
                UPDATE institutions
                SET last_crawled_at = ?, last_status = ?, last_error = ?, consecutive_failures = 0
                WHERE id = ?
                """,
                (now, status, error, institution_id),
            )
        else:
            conn.execute(
                """
                UPDATE institutions
                SET last_crawled_at = ?, last_error = ?,
                    consecutive_failures = consecutive_failures + 1,
                    last_status = CASE
                        WHEN consecutive_failures + 1 >= ? THEN 'review'
                        ELSE ?
                    END
                WHERE id = ?
                """,
                (now, error, FAILURE_REVIEW_THRESHOLD, status, institution_id),
            )
        conn.commit()


def _inflate_job(item: dict[str, Any], enabled_ids: set[int] | None = None) -> dict[str, Any]:
    item["tags"] = from_json(item.get("tags"), [])
    item["extraction_evidence"] = from_json(item.get("extraction_evidence"), {})
    item.setdefault("user_status", None)
    if enabled_ids is not None:
        item["data_trust"] = classify_job_trust(
            item.get("parser_name"), int(item["institution_id"]) in enabled_ids
        )
    return item


def build_jobs_where_clause(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    """Build WHERE clause - result is SQL injection safe (uses ? placeholders)."""
    clauses: list[str] = []
    params: list[Any] = []
    keyword = filters.get("keyword")
    if keyword:
        clauses.append("(title LIKE ? OR raw_text LIKE ? OR institution_name LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like, like])
    for key, column in [
        ("institution_id", "institution_id"),
        ("region", "region"),
        ("job_category", "job_category"),
        ("education", "education"),
        ("institution_type", "institution_type"),
    ]:
        value = filters.get(key)
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    tag = filters.get("tag")
    if tag:
        clauses.append("tags LIKE ?")
        params.append(f"%{tag}%")
    trust = filters.get("trust")
    if trust == "real":
        clauses.append(f"parser_name NOT IN ({','.join('?' * (len(FIXTURE_PARSERS) + len(PLACEHOLDER_PARSERS)))})")
        params.extend(sorted(FIXTURE_PARSERS | PLACEHOLDER_PARSERS))
        clauses.append("institution_id IN (SELECT id FROM institutions WHERE enabled = 1)")
    elif trust == "placeholder":
        clauses.append(f"parser_name IN ({','.join('?' * len(PLACEHOLDER_PARSERS))})")
        params.extend(sorted(PLACEHOLDER_PARSERS))
        # 已禁用机构的历史记录在内存分类中降级为 disabled（classify_job_trust 的
        # 优先级），SQL 切片必须同一口径，否则筛选计数与行内可信度标签互相矛盾。
        clauses.append("institution_id IN (SELECT id FROM institutions WHERE enabled = 1)")
    elif trust == "fixture":
        clauses.append(f"parser_name IN ({','.join('?' * len(FIXTURE_PARSERS))})")
        params.extend(sorted(FIXTURE_PARSERS))
        clauses.append("institution_id IN (SELECT id FROM institutions WHERE enabled = 1)")
    elif trust == "disabled":
        clauses.append("institution_id IN (SELECT id FROM institutions WHERE enabled = 0)")
    fresh_days = filters.get("fresh_days")
    if fresh_days:
        threshold = (datetime.now(timezone.utc) - timedelta(days=int(fresh_days))).isoformat()
        clauses.append("fetched_at >= ?")
        params.append(threshold)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    assert where.count("?") == len(params), "Param count mismatch"
    return where, params


def _job_status_payload(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    return {
        "job_id": item["job_id"],
        "status": item["status"],
        "note": item["note"],
        "deadline": item["deadline"],
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


def _attach_job_statuses(engine: DatabaseEngine, jobs: list[dict[str, Any]], user_id: int | None) -> list[dict[str, Any]]:
    if user_id is None or not jobs:
        return jobs
    job_ids = [item["id"] for item in jobs]
    placeholders = ",".join("?" for _ in job_ids)
    with connect(engine) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM job_statuses
            WHERE user_id = ? AND job_id IN ({placeholders})
            """,
            [user_id, *job_ids],
        ).fetchall()
    by_job_id = {row["job_id"]: _job_status_payload(row) for row in rows}
    for item in jobs:
        item["user_status"] = by_job_id.get(item["id"])
    return jobs


def list_jobs(engine: DatabaseEngine, filters: dict[str, Any], user_id: int | None = None) -> dict[str, Any]:
    where, params = build_jobs_where_clause(filters)
    limit = filters.get("limit", 100)
    offset = filters.get("offset", 0)
    with connect(engine) as conn:
        total = conn.execute(f"SELECT COUNT(*) AS count FROM jobs {where}", params).fetchone()["count"]
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY fetched_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
        enabled_ids = enabled_institution_ids(conn)
    items = [_inflate_job(dict(row), enabled_ids) for row in rows]
    return {
        "total": total,
        "items": _attach_job_statuses(engine, items, user_id),
        "limit": limit,
        "offset": offset,
    }


def get_job(engine: DatabaseEngine, job_id: int, user_id: int | None = None) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        enabled_ids = enabled_institution_ids(conn)
    job = _inflate_job(dict(row), enabled_ids)
    return _attach_job_statuses(engine, [job], user_id)[0]


def upsert_job_status(
    engine: DatabaseEngine,
    user_id: int,
    job_id: int,
    *,
    status: str,
    note: str | None = None,
    deadline: str | None = None,
) -> dict[str, Any]:
    timestamp = now_iso()
    with connect(engine) as conn:
        job = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            raise KeyError(job_id)
        existing = conn.execute(
            "SELECT created_at FROM job_statuses WHERE user_id = ? AND job_id = ?",
            (user_id, job_id),
        ).fetchone()
        created_at = existing["created_at"] if existing else timestamp
        conn.execute(
            """
            INSERT INTO job_statuses (user_id, job_id, status, note, deadline, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, job_id) DO UPDATE SET
                status=excluded.status,
                note=excluded.note,
                deadline=excluded.deadline,
                updated_at=excluded.updated_at
            """,
            (user_id, job_id, status, note, deadline, created_at, timestamp),
        )
        conn.commit()
    status_row = get_job_status(engine, user_id, job_id)
    assert status_row is not None
    return status_row


def get_job_status(engine: DatabaseEngine, user_id: int, job_id: int) -> dict[str, Any] | None:
    with connect(engine) as conn:
        row = conn.execute(
            "SELECT * FROM job_statuses WHERE user_id = ? AND job_id = ?",
            (user_id, job_id),
        ).fetchone()
    return _job_status_payload(row)


def delete_job_status(engine: DatabaseEngine, user_id: int, job_id: int) -> None:
    with connect(engine) as conn:
        conn.execute("DELETE FROM job_statuses WHERE user_id = ? AND job_id = ?", (user_id, job_id))
        conn.commit()


def create_user(engine: DatabaseEngine, username: str, password_hash: str, password_salt: str) -> dict[str, Any]:
    created = now_iso()
    with connect(engine) as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing is not None:
            raise ValueError("username already exists")
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, password_salt, created),
        )
        conn.commit()
        user_id = int(cur.lastrowid)
    return {"id": user_id, "username": username, "created_at": created}


def get_user_by_username(engine: DatabaseEngine, username: str) -> dict[str, Any] | None:
    with connect(engine) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row is not None else None


def get_user_by_id(engine: DatabaseEngine, user_id: int) -> dict[str, Any] | None:
    with connect(engine) as conn:
        row = conn.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row is not None else None


def save_profile(engine: DatabaseEngine, user_id: int, profile: Profile) -> dict[str, Any]:
    """Persist a typed Profile as JSON in the profiles table.

    Returns the profile as a JSON-safe dict with updated_at attached.
    """
    updated = now_iso()
    with connect(engine) as conn:
        conn.execute(
            """
            INSERT INTO profiles (user_id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at
            """,
            (user_id, to_json(profile.model_dump()), updated),
        )
        conn.commit()
    result = profile.model_dump()
    result["updated_at"] = updated
    return result


def get_profile(engine: DatabaseEngine, user_id: int) -> Profile:
    """Load the user's stored profile as a typed ``Profile``.

    Falls back to an empty profile when none exists.  Legacy dict-shaped JSON
    is migrated through ``Profile.from_legacy_dict``.
    """
    with connect(engine) as conn:
        row = conn.execute("SELECT data, updated_at FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return Profile()
    data = from_json(row["data"], {})
    profile = Profile.from_legacy_dict(data)
    return profile


def create_resume_draft(engine: DatabaseEngine, user_id: int, job_id: int, title: str, sections: list[dict[str, Any]], evidence: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> dict[str, Any]:
    created = now_iso()
    with connect(engine) as conn:
        cur = conn.execute(
            """
            INSERT INTO resume_drafts (user_id, job_id, title, sections, evidence, gaps, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, job_id, title, to_json(sections), to_json(evidence), to_json(gaps), created, created),
        )
        conn.commit()
        draft_id = int(cur.lastrowid)
    return get_resume_draft(engine, user_id, draft_id)


def get_resume_draft(engine: DatabaseEngine, user_id: int, draft_id: int) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute(
            "SELECT * FROM resume_drafts WHERE id = ? AND user_id = ?",
            (draft_id, user_id),
        ).fetchone()
    if row is None:
        raise KeyError(draft_id)
    item = dict(row)
    item["profile_id"] = str(item["user_id"])
    item["sections"] = from_json(item["sections"], [])
    item["evidence"] = from_json(item["evidence"], [])
    item["gaps"] = from_json(item["gaps"], [])
    return item


def update_resume_draft_sections(engine: DatabaseEngine, user_id: int, draft_id: int, sections: list[dict[str, Any]]) -> dict[str, Any]:
    with connect(engine) as conn:
        cur = conn.execute(
            "UPDATE resume_drafts SET sections = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (to_json(sections), now_iso(), draft_id, user_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise KeyError(draft_id)
    return get_resume_draft(engine, user_id, draft_id)


def list_resume_drafts_by_user(engine: DatabaseEngine, user_id: int) -> list[dict[str, Any]]:
    with connect(engine) as conn:
        rows = conn.execute(
            "SELECT * FROM resume_drafts WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    items = rows_to_dicts(rows)
    for item in items:
        item["profile_id"] = str(item["user_id"])
        item["sections"] = from_json(item["sections"], [])
        item["evidence"] = from_json(item["evidence"], [])
        item["gaps"] = from_json(item["gaps"], [])
    return items


def list_resume_drafts(
    engine: DatabaseEngine, user_id: int, job_id: int | None = None
) -> list[dict[str, Any]]:
    """List a user's resume drafts, newest first, optionally filtered by job.

    User isolation is enforced in the SQL WHERE clause.  ``sections`` is parsed
    so the caller can compute review status, but evidence/gaps are not loaded.
    """
    query = "SELECT id, job_id, title, sections, created_at, updated_at FROM resume_drafts WHERE user_id = ?"
    params: list[Any] = [user_id]
    if job_id is not None:
        query += " AND job_id = ?"
        params.append(job_id)
    query += " ORDER BY created_at DESC, id DESC"
    with connect(engine) as conn:
        rows = conn.execute(query, params).fetchall()
    items = rows_to_dicts(rows)
    for item in items:
        item["sections"] = from_json(item["sections"], [])
    return items


def save_report(engine: DatabaseEngine, title: str, markdown: str, html: str, filters: dict[str, Any]) -> dict[str, Any]:
    created = now_iso()
    with connect(engine) as conn:
        cur = conn.execute(
            "INSERT INTO reports (title, markdown, html, filters, created_at) VALUES (?, ?, ?, ?, ?)",
            (title, markdown, html, to_json(filters), created),
        )
        conn.commit()
        report_id = int(cur.lastrowid)
    return {"id": report_id, "title": title, "markdown": markdown, "html": html, "filters": filters, "created_at": created}


# ── Subscriptions (PRD 4.1) ──────────────────────────────────────────


def create_subscription(
    engine: DatabaseEngine,
    user_id: int,
    name: str,
    keyword: str,
    institution_ids: list[int],
) -> dict[str, Any]:
    """Create a subscription. last_checked_at and last_pushed_at are set to creation time."""
    now = now_iso()
    with connect(engine) as conn:
        cur = conn.execute(
            """
            INSERT INTO subscriptions (
                user_id, name, keyword, institution_ids,
                last_checked_at, last_pushed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, keyword, to_json(institution_ids), now, now, now, now),
        )
        conn.commit()
        sub_id = int(cur.lastrowid)
    return get_subscription(engine, user_id, sub_id)


def get_subscription(engine: DatabaseEngine, user_id: int, subscription_id: int) -> dict[str, Any]:
    """Get a subscription by id, scoped to user. Raises KeyError if not found."""
    with connect(engine) as conn:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE id = ? AND user_id = ?",
            (subscription_id, user_id),
        ).fetchone()
    if row is None:
        raise KeyError(subscription_id)
    item = dict(row)
    item["institution_ids"] = from_json(item["institution_ids"], [])
    return item


def list_subscriptions(engine: DatabaseEngine, user_id: int) -> list[dict[str, Any]]:
    """List all subscriptions for a user, ordered by creation time (newest first)."""
    with connect(engine) as conn:
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        item["institution_ids"] = from_json(item["institution_ids"], [])
    return items


def delete_subscription(engine: DatabaseEngine, user_id: int, subscription_id: int) -> None:
    """Delete a subscription. Raises KeyError if not found."""
    with connect(engine) as conn:
        cur = conn.execute(
            "DELETE FROM subscriptions WHERE id = ? AND user_id = ?",
            (subscription_id, user_id),
        )
        if cur.rowcount == 0:
            raise KeyError(subscription_id)
        conn.commit()


def mark_subscription_read(engine: DatabaseEngine, user_id: int, subscription_id: int) -> dict[str, Any]:
    """Advance last_checked_at to now, resetting the new count.

    Returns the updated subscription.
    """
    now = now_iso()
    with connect(engine) as conn:
        cur = conn.execute(
            "UPDATE subscriptions SET last_checked_at = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (now, now, subscription_id, user_id),
        )
        if cur.rowcount == 0:
            raise KeyError(subscription_id)
        conn.commit()
    return get_subscription(engine, user_id, subscription_id)


def find_new_jobs_for_subscription(
    engine: DatabaseEngine,
    keyword: str,
    institution_ids: list[int],
    last_checked_at: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """列出订阅关键词命中、且晚于检查点抓取的岗位（新→旧）。

    SQL LIKE 粗筛后，对纯 ASCII 关键词做词边界精筛（ICU 不命中 RICU）。
    """
    if not institution_ids:
        return []
    placeholders = ",".join("?" for _ in institution_ids)
    like = f"%{keyword.strip()}%"
    with connect(engine) as conn:
        rows = conn.execute(
            f"""
            SELECT id, title, institution_name, raw_text, fetched_at FROM jobs
            WHERE institution_id IN ({placeholders})
              AND fetched_at > ?
              AND (title LIKE ? OR raw_text LIKE ? OR institution_name LIKE ?)
            ORDER BY fetched_at DESC
            LIMIT ?
            """,
            [*institution_ids, last_checked_at, like, like, like, limit],
        ).fetchall()
    return refine_keyword_hits([dict(row) for row in rows], keyword)


def count_new_jobs_for_subscription(
    engine: DatabaseEngine,
    keyword: str,
    institution_ids: list[int],
    last_checked_at: str,
) -> int:
    """Count jobs matching keyword + institution that were fetched after last_checked_at."""
    return len(find_new_jobs_for_subscription(engine, keyword, institution_ids, last_checked_at))


def has_matching_jobs_last_30d(
    engine: DatabaseEngine,
    keyword: str,
    institution_ids: list[int],
    now: str | None = None,
) -> bool:
    """Check if any matching job was fetched in the last 30 days.

    SQL LIKE 粗筛后做与 ``find_new_jobs_for_subscription`` 相同的 ASCII 词边界
    精筛（B2 语义：ICU 不得命中 RICU），保证告警比率与扫描口径一致。
    """
    if not institution_ids:
        return False
    from datetime import datetime, timedelta, timezone
    if now is None:
        threshold_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    else:
        threshold_iso = (datetime.fromisoformat(now) - timedelta(days=30)).isoformat()
    placeholders = ",".join("?" for _ in institution_ids)
    like = f"%{keyword}%"
    with connect(engine) as conn:
        rows = conn.execute(
            f"""
            SELECT title, institution_name, raw_text FROM jobs
            WHERE institution_id IN ({placeholders})
              AND fetched_at >= ?
              AND (title LIKE ? OR raw_text LIKE ? OR institution_name LIKE ?)
            """,
            [*institution_ids, threshold_iso, like, like, like],
        ).fetchall()
    return bool(refine_keyword_hits([dict(r) for r in rows], keyword))


def count_total_matching_jobs(
    engine: DatabaseEngine,
    keyword: str,
    institution_ids: list[int],
) -> int:
    """Count total jobs matching keyword + institutions (for broad-keyword check).

    ASCII 关键词做词边界精筛（与扫描口径一致，避免 RICU 计入 ICU 导致宽词误报）。
    """
    if not institution_ids:
        return 0
    placeholders = ",".join("?" for _ in institution_ids)
    like = f"%{keyword}%"
    with connect(engine) as conn:
        rows = conn.execute(
            f"""
            SELECT title, institution_name, raw_text FROM jobs
            WHERE institution_id IN ({placeholders})
              AND (title LIKE ? OR raw_text LIKE ? OR institution_name LIKE ?)
            """,
            [*institution_ids, like, like, like],
        ).fetchall()
    return len(refine_keyword_hits([dict(r) for r in rows], keyword))


def count_total_jobs_in_institutions(engine: DatabaseEngine, institution_ids: list[int]) -> int:
    """Count total jobs across the given institutions."""
    if not institution_ids:
        return 0
    placeholders = ",".join("?" for _ in institution_ids)
    with connect(engine) as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS count FROM jobs WHERE institution_id IN ({placeholders})",
            institution_ids,
        ).fetchone()
    return int(row["count"])


def get_institutions_status(engine: DatabaseEngine, institution_ids: list[int]) -> list[dict[str, Any]]:
    """Get institution status info for subscription display.

    Returns list of {id, name, is_maintenance}.
    An institution is in maintenance when enabled=false or last_status='failed'.
    """
    if not institution_ids:
        return []
    placeholders = ",".join("?" for _ in institution_ids)
    with connect(engine) as conn:
        rows = conn.execute(
            f"""
            SELECT id, name, enabled, last_status
            FROM institutions
            WHERE id IN ({placeholders})
            ORDER BY id
            """,
            institution_ids,
        ).fetchall()
    result = []
    for row in rows:
        is_maintenance = (
            not bool(row["enabled"])
            or row["last_status"] == "failed"
        )
        result.append({
            "id": row["id"],
            "name": row["name"],
            "is_maintenance": is_maintenance,
        })
    return result


def filter_active_institution_ids(
    engine: DatabaseEngine, institution_ids: list[int]
) -> list[int]:
    """Return only non-maintenance institution IDs from the given list."""
    statuses = get_institutions_status(engine, institution_ids)
    return [s["id"] for s in statuses if not s["is_maintenance"]]


def list_all_subscriptions(engine: DatabaseEngine) -> list[dict[str, Any]]:
    """List all subscriptions across all users (for scheduler scans)."""
    with connect(engine) as conn:
        rows = conn.execute("SELECT * FROM subscriptions ORDER BY id").fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        item["institution_ids"] = from_json(item["institution_ids"], [])
    return items


def scan_subscriptions(
    engine: DatabaseEngine,
    now: datetime,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Scan subscriptions and push in-app notifications for new matching jobs.

    - Finds jobs fetched after last_pushed_at (falling back to last_checked_at) at
      non-maintenance institutions matching the subscription keyword.
    - If new jobs are found, writes a notification (with a short summary) to the
      subscription owner and advances last_pushed_at to *now*.
    - Does NOT change last_checked_at or new_count (those are read-checkpoint concepts).

    Returns a summary dict with scanned/pushed/notified counts.
    """
    now_str = now.isoformat()
    if user_id is not None:
        subs = list_subscriptions(engine, user_id)
    else:
        subs = list_all_subscriptions(engine)

    scanned = 0
    pushed = 0
    notified = 0
    for sub in subs:
        scanned += 1
        keyword = (sub.get("keyword") or "").strip()
        if not keyword:
            continue
        institution_ids = sub["institution_ids"]
        active_ids = filter_active_institution_ids(engine, institution_ids)
        if not active_ids:
            continue
        checkpoint = sub.get("last_pushed_at") or sub["last_checked_at"]
        new_jobs = find_new_jobs_for_subscription(engine, keyword, active_ids, checkpoint)
        if not new_jobs:
            continue
        titles = [row["title"] for row in new_jobs[:3]]
        more = len(new_jobs) - len(titles)
        summary = "、".join(titles) + (f" 等 {more} 条" if more > 0 else "")
        create_notification(
            engine,
            sub["user_id"],
            sub["id"],
            subscription_name=sub["name"],
            keyword=keyword,
            job_ids=[row["id"] for row in new_jobs],
            summary=summary,
            now_str=now_str,
        )
        with connect(engine) as conn:
            conn.execute(
                "UPDATE subscriptions SET last_pushed_at = ?, updated_at = ? WHERE id = ?",
                (now_str, now_str, sub["id"]),
            )
            conn.commit()
        pushed += 1
        notified += 1
    return {"scanned": scanned, "pushed": pushed, "notified": notified}


def create_notification(
    engine: DatabaseEngine,
    user_id: int,
    subscription_id: int,
    *,
    subscription_name: str,
    keyword: str,
    job_ids: list[int],
    summary: str,
    now_str: str,
) -> int:
    with connect(engine) as conn:
        cur = conn.execute(
            """
            INSERT INTO notifications (
                user_id, subscription_id, subscription_name, keyword,
                job_count, job_ids, summary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                subscription_id,
                subscription_name,
                keyword,
                len(job_ids),
                to_json(job_ids),
                summary,
                now_str,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_notifications(engine: DatabaseEngine, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """用户站内通知（最新在前），附带 unread 计数语义由 count_unread_notifications 提供。"""
    with connect(engine) as conn:
        rows = conn.execute(
            """
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["job_ids"] = from_json(item["job_ids"], [])
        item["read"] = item["read_at"] is not None
        items.append(item)
    return items


def count_unread_notifications(engine: DatabaseEngine, user_id: int) -> int:
    with connect(engine) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM notifications WHERE user_id = ? AND read_at IS NULL",
            (user_id,),
        ).fetchone()
    return int(row["count"])


def mark_notification_read(engine: DatabaseEngine, user_id: int, notification_id: int) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute(
            "SELECT * FROM notifications WHERE id = ? AND user_id = ?",
            (notification_id, user_id),
        ).fetchone()
        if row is None:
            raise KeyError(notification_id)
        conn.execute(
            "UPDATE notifications SET read_at = ? WHERE id = ? AND read_at IS NULL",
            (now_iso(), notification_id),
        )
        conn.commit()
    item = dict(row)
    item["job_ids"] = from_json(item["job_ids"], [])
    item["read"] = True
    return item


def mark_all_notifications_read(engine: DatabaseEngine, user_id: int) -> int:
    """全部标记已读，返回本次标记的条数。"""
    with connect(engine) as conn:
        cur = conn.execute(
            "UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL",
            (now_iso(), user_id),
        )
        conn.commit()
        return int(cur.rowcount)
