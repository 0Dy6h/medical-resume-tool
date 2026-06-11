from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.database import (
    DatabaseEngine,
    connect,
    from_json,
    row_to_dict,
    rows_to_dicts,
    to_json,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def create_crawl_run(engine: DatabaseEngine, institution_ids: list[int]) -> int:
    with connect(engine) as conn:
        cur = conn.execute(
            """
            INSERT INTO crawl_runs (status, started_at, institution_ids, error_summary)
            VALUES (?, ?, ?, ?)
            """,
            ("running", now_iso(), to_json(institution_ids), "[]"),
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
    item = dict(row)
    item["institution_ids"] = from_json(item["institution_ids"], [])
    errors = from_json(item["error_summary"], [])
    item["error_summary"] = errors
    item["errors"] = errors
    return item


def upsert_job(engine: DatabaseEngine, institution: dict[str, Any], parsed: Any) -> bool:
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
        duplicate_by_hash = conn.execute(
            "SELECT id FROM jobs WHERE source_text_hash = ?",
            (parsed.source_text_hash,),
        ).fetchone()
        if duplicate_by_hash:
            conn.execute(
                "UPDATE jobs SET fetched_at = ? WHERE id = ?",
                (parsed.fetched_at, duplicate_by_hash["id"]),
            )
            conn.commit()
            return False
        exists = conn.execute("SELECT id FROM jobs WHERE source_url = ?", (parsed.source_url,)).fetchone()
        if exists:
            conn.execute(
                """
                UPDATE jobs SET
                    title=:title, department=:department, location=:location, education=:education,
                    profession=:profession, job_category=:job_category, responsibilities=:responsibilities,
                    requirements=:requirements, posted_at=:posted_at, deadline=:deadline,
                    source_text_hash=:source_text_hash, raw_text=:raw_text, tags=:tags,
                    extraction_evidence=:extraction_evidence, fetched_at=:fetched_at,
                    parser_name=:parser_name, confidence=:confidence
                WHERE source_url=:source_url
                """,
                payload,
            )
            conn.commit()
            return False
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


def mark_institution(engine: DatabaseEngine, institution_id: int, status: str, error: str | None = None) -> None:
    with connect(engine) as conn:
        conn.execute(
            """
            UPDATE institutions
            SET last_crawled_at = ?, last_status = ?, last_error = ?
            WHERE id = ?
            """,
            (now_iso(), status, error, institution_id),
        )
        conn.commit()


def _inflate_job(item: dict[str, Any]) -> dict[str, Any]:
    item["tags"] = from_json(item.get("tags"), [])
    item["extraction_evidence"] = from_json(item.get("extraction_evidence"), {})
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
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    assert where.count("?") == len(params), "Param count mismatch"
    return where, params


def list_jobs(engine: DatabaseEngine, filters: dict[str, Any]) -> dict[str, Any]:
    where, params = build_jobs_where_clause(filters)
    limit = filters.get("limit", 100)
    offset = filters.get("offset", 0)
    with connect(engine) as conn:
        total = conn.execute(f"SELECT COUNT(*) AS count FROM jobs {where}", params).fetchone()["count"]
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY fetched_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
    return {
        "total": total,
        "items": [_inflate_job(dict(row)) for row in rows],
        "limit": limit,
        "offset": offset,
    }


def get_job(engine: DatabaseEngine, job_id: int) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(job_id)
    return _inflate_job(dict(row))


def save_profile(engine: DatabaseEngine, profile: dict[str, Any]) -> dict[str, Any]:
    updated = now_iso()
    with connect(engine) as conn:
        conn.execute(
            """
            INSERT INTO profiles (id, data, updated_at)
            VALUES ('default', ?, ?)
            ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at
            """,
            (to_json(profile), updated),
        )
        conn.commit()
    return {**profile, "updated_at": updated}


def get_profile(engine: DatabaseEngine) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute("SELECT data, updated_at FROM profiles WHERE id = 'default'").fetchone()
    if row is None:
        return {
            "education": [],
            "experiences": [],
            "projects": [],
            "publications": [],
            "certificates": [],
            "skills": [],
            "teaching": [],
            "awards": [],
            "languages": [],
            "updated_at": None,
        }
    data = from_json(row["data"], {})
    data.pop("basic", None)
    data["updated_at"] = row["updated_at"]
    return data


def create_resume_draft(engine: DatabaseEngine, job_id: int, title: str, sections: list[dict[str, Any]], evidence: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> dict[str, Any]:
    created = now_iso()
    with connect(engine) as conn:
        cur = conn.execute(
            """
            INSERT INTO resume_drafts (job_id, profile_id, title, sections, evidence, gaps, created_at, updated_at)
            VALUES (?, 'default', ?, ?, ?, ?, ?, ?)
            """,
            (job_id, title, to_json(sections), to_json(evidence), to_json(gaps), created, created),
        )
        conn.commit()
        draft_id = int(cur.lastrowid)
    return get_resume_draft(engine, draft_id)


def get_resume_draft(engine: DatabaseEngine, draft_id: int) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute("SELECT * FROM resume_drafts WHERE id = ?", (draft_id,)).fetchone()
    if row is None:
        raise KeyError(draft_id)
    item = dict(row)
    item["sections"] = from_json(item["sections"], [])
    item["evidence"] = from_json(item["evidence"], [])
    item["gaps"] = from_json(item["gaps"], [])
    return item


def update_resume_draft_sections(engine: DatabaseEngine, draft_id: int, sections: list[dict[str, Any]]) -> dict[str, Any]:
    with connect(engine) as conn:
        conn.execute(
            "UPDATE resume_drafts SET sections = ?, updated_at = ? WHERE id = ?",
            (to_json(sections), now_iso(), draft_id),
        )
        conn.commit()
    return get_resume_draft(engine, draft_id)


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
