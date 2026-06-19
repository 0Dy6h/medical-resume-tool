import io
import time
import zipfile
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import crawler as crawler_module
from app.services.crawler import ParsedJob
from app.services.database import connect, create_engine, init_db, reset_db
from app.services.repositories import get_profile, get_resume_draft


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db_path}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


def wait_for_run(client: TestClient, run_id: int, timeout: float = 30.0) -> dict:
    """Poll a crawl run until it reaches a terminal status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get(f"/api/crawl-runs/{run_id}").json()
        if payload["status"] in {"completed", "partial", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"crawl run {run_id} did not finish within {timeout}s")


def crawl_and_wait(client: TestClient, institution_ids: list[int], timeout: float = 30.0) -> dict:
    """Start a crawl run and block until it finishes, returning the final run payload."""
    run = client.post("/api/crawl-runs", json={"institution_ids": institution_ids})
    assert run.status_code == 201
    assert run.json()["status"] == "running"
    return wait_for_run(client, run.json()["id"], timeout)


def auth_headers(client: TestClient, username: str = "tester", password: str = "secret123") -> dict[str, str]:
    """Register a fresh user and return an Authorization header for private endpoints."""
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def docx_document_xml(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        return zf.read("word/document.xml").decode("utf-8")


def test_init_db_migrates_legacy_user_scoped_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with connect(engine) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            INSERT INTO users (id, username, password_hash, password_salt, created_at)
            VALUES (1, 'legacy-user', 'hash', 'salt', '2026-06-18T00:00:00+00:00');

            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            INSERT INTO profiles (id, data, updated_at)
            VALUES (1, '{"skills":[{"id":"skill-1","name":"临床研究"}]}', '2026-06-18T00:00:00+00:00');

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

            INSERT INTO institutions (
                id, name, institution_type, region, official_url, listing_url, crawl_strategy, enabled
            ) VALUES (
                1, '旧机构', '医院', '上海', 'https://example.test', 'https://example.test/jobs', 'fixture', 1
            );

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
                id, institution_id, institution_name, institution_type, region, title, job_category,
                source_url, source_text_hash, raw_text, tags, extraction_evidence, fetched_at, parser_name, confidence
            ) VALUES (
                99, 1, '旧机构', '医院', '上海', '旧岗位', '科研',
                'fixture://legacy-job', 'legacy-hash', '旧岗位原文', '[]', '{}', '2026-06-18T00:00:00+00:00', 'legacy-parser', 0.9
            );

            CREATE TABLE resume_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                profile_id TEXT NOT NULL,
                title TEXT NOT NULL,
                sections TEXT NOT NULL,
                evidence TEXT NOT NULL,
                gaps TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            INSERT INTO resume_drafts (id, job_id, profile_id, title, sections, evidence, gaps, created_at, updated_at)
            VALUES (1, 99, '1', '旧草稿', '[]', '[]', '[]', '2026-06-18T00:00:00+00:00', '2026-06-18T00:00:00+00:00');
            """
        )
        conn.commit()

    init_db(engine)

    assert get_profile(engine, 1)["skills"][0]["name"] == "临床研究"
    assert get_resume_draft(engine, 1, 1)["title"] == "旧草稿"
    with connect(engine) as conn:
        profile_columns = {row["name"] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()}
        draft_columns = {row["name"] for row in conn.execute("PRAGMA table_info(resume_drafts)").fetchall()}
    assert "user_id" in profile_columns
    assert "user_id" in draft_columns
    assert "profile_id" not in draft_columns


def test_init_db_preserves_unmatched_legacy_profile_and_draft_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'orphan-legacy.db'}")
    with connect(engine) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            INSERT INTO profiles (id, data, updated_at)
            VALUES (42, '{"skills":[{"id":"skill-orphan","name":"孤儿旧履历"}]}', '2026-06-18T00:00:00+00:00');

            CREATE TABLE resume_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                profile_id TEXT NOT NULL,
                title TEXT NOT NULL,
                sections TEXT NOT NULL,
                evidence TEXT NOT NULL,
                gaps TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            INSERT INTO resume_drafts (id, job_id, profile_id, title, sections, evidence, gaps, created_at, updated_at)
            VALUES (7, 999, '42', '孤儿旧草稿', '[]', '[]', '[]', '2026-06-18T00:00:00+00:00', '2026-06-18T00:00:00+00:00');
            """
        )
        conn.commit()

    init_db(engine)

    with connect(engine) as conn:
        orphan_profile = conn.execute("SELECT data FROM profiles_legacy WHERE id = 42").fetchone()
        orphan_draft = conn.execute("SELECT title FROM resume_drafts_legacy WHERE id = 7").fetchone()
        migrated_profiles = conn.execute("SELECT COUNT(*) AS count FROM profiles").fetchone()["count"]
        migrated_drafts = conn.execute("SELECT COUNT(*) AS count FROM resume_drafts").fetchone()["count"]

    assert orphan_profile is not None
    assert "孤儿旧履历" in orphan_profile["data"]
    assert orphan_draft["title"] == "孤儿旧草稿"
    assert migrated_profiles == 0
    assert migrated_drafts == 0


def test_health_and_seed_institutions(tmp_path):
    client = make_client(tmp_path)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    institutions = client.get("/api/institutions")
    assert institutions.status_code == 200
    payload = institutions.json()
    assert len(payload) >= 30
    assert {"医院", "高校", "研究机构"}.issubset({item["institution_type"] for item in payload})


def test_crawl_fixture_creates_tagged_jobs_without_duplicates(tmp_path):
    client = make_client(tmp_path)

    run_payload = crawl_and_wait(client, [1])
    assert run_payload["status"] == "completed"
    assert run_payload["success_count"] >= 3

    jobs = client.get("/api/jobs", params={"keyword": "护理"})
    assert jobs.status_code == 200
    payload = jobs.json()
    assert payload["total"] >= 1
    first = payload["items"][0]
    assert first["source_url"].startswith("fixture://")
    assert first["source_text_hash"]
    assert "护理" in first["tags"]

    crawl_and_wait(client, [1])
    after = client.get("/api/jobs").json()
    assert after["total"] == payload["total"] or after["total"] >= payload["total"]
    urls = [item["source_url"] for item in after["items"]]
    assert len(urls) == len(set(urls))


def test_crawl_retries_timeout_then_persists_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAWL_DELAY_SECONDS", "0")
    monkeypatch.setenv("CRAWL_RETRY_BASE_SECONDS", "0")
    client = make_client(tmp_path)
    with connect(client.app.state.engine) as conn:
        conn.execute(
            """
            UPDATE institutions
            SET listing_url = ?, crawl_strategy = ?, enabled = 1
            WHERE id = 1
            """,
            ("https://example.test/recruit", "generic"),
        )
        conn.commit()

    attempts = 0

    async def flaky_get(self, url):  # noqa: ANN001
        nonlocal attempts
        attempts += 1
        request = httpx.Request("GET", url)
        if attempts == 1:
            raise httpx.TimeoutException("timed out", request=request)
        return httpx.Response(
            200,
            text="<html><body><a href='/job/1'>护理岗位招聘</a></body></html>",
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", flaky_get)

    payload = crawl_and_wait(client, [1])

    assert payload["status"] == "completed"
    assert payload["failure_count"] == 0
    assert payload["success_count"] == 1
    assert attempts == 2
    jobs = client.get("/api/jobs").json()
    assert jobs["total"] == 1


def test_crawl_run_reports_partial_status_and_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAWL_DELAY_SECONDS", "0")
    monkeypatch.setenv("CRAWL_RETRY_BASE_SECONDS", "0")
    client = make_client(tmp_path)
    with connect(client.app.state.engine) as conn:
        conn.execute(
            """
            UPDATE institutions
            SET listing_url = ?, crawl_strategy = ?, enabled = 1
            WHERE id = 2
            """,
            ("https://example.test/unreachable", "generic"),
        )
        conn.commit()

    async def failing_get(self, url):  # noqa: ANN001
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("network unavailable", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", failing_get)

    payload = crawl_and_wait(client, [1, 2])

    assert payload["status"] == "partial"
    assert payload["failure_count"] == 1
    assert payload["success_count"] >= 3
    assert payload["errors"] == payload["error_summary"]
    assert payload["errors"][0]["institution_id"] == 2


def test_execute_crawl_run_updates_progress_incrementally(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAWL_DELAY_SECONDS", "0")
    client = make_client(tmp_path)
    engine = client.app.state.engine

    from app.services.crawler import execute_crawl_run
    from app.services.repositories import create_crawl_run, get_institutions_by_ids

    institutions = get_institutions_by_ids(engine, [1])
    run_id = create_crawl_run(engine, [item["id"] for item in institutions])

    final = execute_crawl_run(engine, run_id, institutions, delay=0)

    assert final["status"] == "completed"
    assert final["success_count"] >= 3
    persisted = client.get(f"/api/crawl-runs/{run_id}").json()
    assert persisted["status"] == "completed"
    assert persisted["success_count"] == final["success_count"]


def test_crawl_deduplicates_by_source_text_hash_and_refreshes_fetched_at(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAWL_DELAY_SECONDS", "0")
    client = make_client(tmp_path)
    calls = 0

    def make_job(source_url: str, fetched_at: str) -> ParsedJob:
        return ParsedJob(
            title="护理岗位招聘",
            department="护理部",
            location="广东",
            education="本科",
            profession="护理学",
            job_category="护理",
            responsibilities="承担病区护理。",
            requirements="护理学本科。",
            posted_at=None,
            deadline=None,
            source_url=source_url,
            source_text_hash="same-source-text-hash",
            raw_text="护理岗位招聘\n护理学本科。",
            tags=["护理"],
            extraction_evidence={},
            fetched_at=fetched_at,
            parser_name="test-parser-v1",
            confidence=0.9,
        )

    async def crawl_same_text_different_url(institution):  # noqa: ANN001
        nonlocal calls
        calls += 1
        return [
            make_job(
                source_url=f"https://example.test/jobs/{calls}",
                fetched_at=f"2026-06-09T00:00:0{calls}+00:00",
            )
        ]

    monkeypatch.setattr(crawler_module, "crawl_institution", crawl_same_text_different_url)

    crawl_and_wait(client, [1])
    crawl_and_wait(client, [1])

    jobs = client.get("/api/jobs").json()
    assert jobs["total"] == 1
    assert jobs["items"][0]["source_url"] == "https://example.test/jobs/1"
    assert jobs["items"][0]["source_text_hash"] == "same-source-text-hash"
    assert jobs["items"][0]["fetched_at"] == "2026-06-09T00:00:02+00:00"


def test_crawl_defaults_to_one_second_delay_between_institutions(tmp_path, monkeypatch):
    monkeypatch.delenv("CRAWL_DELAY_SECONDS", raising=False)
    client = make_client(tmp_path)
    sleep_calls = []

    async def record_sleep(seconds):  # noqa: ANN001
        sleep_calls.append(seconds)

    monkeypatch.setattr(crawler_module.asyncio, "sleep", record_sleep)

    payload = crawl_and_wait(client, [1, 2])

    assert payload["status"] == "completed"
    assert sleep_calls == [1.0]


def test_job_detail_and_analytics_summary(tmp_path):
    client = make_client(tmp_path)
    crawl_and_wait(client, [1, 2, 3])

    jobs = client.get("/api/jobs").json()["items"]
    detail = client.get(f"/api/jobs/{jobs[0]['id']}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["raw_snapshot"]["source_url"]
    assert detail_payload["parser_name"]
    assert 0 <= detail_payload["confidence"] <= 1

    summary = client.get("/api/analytics/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["totals"]["jobs"] >= 3
    assert payload["job_categories"]
    assert payload["common_capabilities"]


def test_analytics_summary_surfaces_parser_quality_review(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAWL_DELAY_SECONDS", "0")
    client = make_client(tmp_path)

    async def crawl_quality_sample(institution):  # noqa: ANN001
        return [
            ParsedJob(
                title="临床医师",
                department="北京肿瘤医院",
                location="北京",
                education="博士",
                profession="临床医学",
                job_category="临床医疗",
                responsibilities="承担临床诊疗。",
                requirements="临床医学博士。",
                posted_at=None,
                deadline=None,
                source_url="https://example.test/jobs.xlsx#岗位信息表-2",
                source_text_hash="quality-review-xlsx-row",
                raw_text="岗位名称：临床医师；学历：博士",
                tags=["临床医疗", "北京"],
                extraction_evidence={
                    "attachment_url": "https://example.test/jobs.xlsx",
                    "row_index": 2,
                },
                fetched_at="2026-06-10T00:00:00+00:00",
                parser_name="bjmu-xlsx-v1",
                confidence=0.88,
            ),
            ParsedJob(
                title="年度招聘公告",
                department=None,
                location="北京",
                education=None,
                profession=None,
                job_category="综合",
                responsibilities="详见附件。",
                requirements="详见附件。",
                posted_at=None,
                deadline=None,
                source_url="https://example.test/notice.htm",
                source_text_hash="quality-review-notice",
                raw_text="年度招聘公告，附件解析失败。",
                tags=["综合", "北京"],
                extraction_evidence={
                    "attachments": [
                        {
                            "name": "岗位信息表.xlsx",
                            "url": "https://example.test/jobs.xlsx",
                            "extension": ".xlsx",
                            "status": "failed",
                            "error": "File is not a zip file",
                        }
                    ]
                },
                fetched_at="2026-06-10T00:01:00+00:00",
                parser_name="bjmu-notice-v1",
                confidence=0.52,
            ),
        ]

    monkeypatch.setattr(crawler_module, "crawl_institution", crawl_quality_sample)
    crawl_and_wait(client, [1])

    summary = client.get("/api/analytics/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["totals"]["parsers"] == 2
    assert payload["totals"]["low_confidence_jobs"] == 1
    assert payload["totals"]["attachment_sourced_jobs"] == 1
    assert payload["totals"]["failed_attachment_events"] == 1

    quality_by_parser = {item["parser_name"]: item for item in payload["parser_quality"]}
    assert quality_by_parser["bjmu-xlsx-v1"]["jobs"] == 1
    assert quality_by_parser["bjmu-xlsx-v1"]["attachment_sourced_jobs"] == 1
    assert quality_by_parser["bjmu-xlsx-v1"]["average_confidence"] == 0.88
    assert quality_by_parser["bjmu-xlsx-v1"]["review_status"] == "stable"
    assert quality_by_parser["bjmu-notice-v1"]["low_confidence_jobs"] == 1
    assert quality_by_parser["bjmu-notice-v1"]["failed_attachment_events"] == 1
    assert quality_by_parser["bjmu-notice-v1"]["review_status"] == "review"


def test_profile_resume_draft_truth_constraints_and_exports(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    crawl_and_wait(client, [1])
    job = client.get("/api/jobs", params={"keyword": "科研"}).json()["items"][0]

    empty_draft = client.post("/api/resume-drafts", json={"job_id": job["id"]}, headers=auth)
    assert empty_draft.status_code == 400
    assert "请先填写或导入履历内容" in empty_draft.text

    profile_payload = {
        "education": [
            {
                "id": "edu-1",
                "school": "复旦大学",
                "degree": "硕士",
                "major": "临床医学",
                "start": "2021",
                "end": "2024",
                "highlights": ["循证医学训练", "临床研究设计"],
            }
        ],
        "experiences": [
            {
                "id": "exp-1",
                "organization": "上海某三甲医院",
                "role": "科研助理",
                "start": "2023",
                "end": "2024",
                "highlights": ["参与伦理材料整理", "维护随访数据库", "协助统计分析"],
                "skills": ["临床研究", "SPSS", "数据管理"],
            }
        ],
        "projects": [
            {
                "id": "proj-1",
                "name": "慢病队列随访项目",
                "role": "项目成员",
                "highlights": ["完成 300 例随访记录核查", "输出阶段性数据质量报告"],
                "skills": ["随访", "数据质控"],
            }
        ],
        "publications": [],
        "certificates": [{"id": "cert-1", "name": "大学英语六级", "issuer": "教育部考试中心", "year": "2022"}],
        "skills": [{"id": "skill-1", "name": "SPSS"}, {"id": "skill-2", "name": "临床研究"}],
        "teaching": [],
        "awards": [],
        "languages": [{"id": "lang-1", "name": "英语", "level": "CET-6"}],
    }
    saved = client.put("/api/profile", json=profile_payload, headers=auth)
    assert saved.status_code == 200

    draft = client.post("/api/resume-drafts", json={"job_id": job["id"]}, headers=auth)
    assert draft.status_code == 201
    draft_payload = draft.json()
    assert draft_payload["job_id"] == job["id"]
    assert draft_payload["sections"]
    assert draft_payload["evidence"]
    assert all(item["profile_field_id"] for item in draft_payload["evidence"])
    assert all(item["source_label"] for item in draft_payload["evidence"])
    assert all(item["evidence_strength"] in {"strong", "partial", "weak"} for item in draft_payload["evidence"])
    assert all("未在你的履历中找到对应证据" in gap["message"] for gap in draft_payload["gaps"])

    docx = client.post(f"/api/resume-drafts/{draft_payload['id']}/export", params={"format": "docx"}, headers=auth)
    assert docx.status_code == 200
    assert docx.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert io.BytesIO(docx.content).getbuffer().nbytes > 1000

    pdf = client.post(f"/api/resume-drafts/{draft_payload['id']}/export", params={"format": "pdf"}, headers=auth)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")


def test_resume_export_includes_identity_header_and_basics_persist(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    crawl_and_wait(client, [1])
    job = client.get("/api/jobs", params={"keyword": "科研"}).json()["items"][0]

    profile_payload = {
        "basics": {
            "name": "林晓",
            "phone": "13800000000",
            "email": "lin@example.com",
            "intended_position": "科研助理",
        },
        "education": [{"id": "edu-1", "school": "复旦大学", "degree": "硕士", "major": "临床医学"}],
        "experiences": [],
        "projects": [],
        "publications": [],
        "certificates": [],
        "skills": [{"id": "skill-1", "name": "SPSS"}],
        "teaching": [],
        "awards": [],
        "languages": [],
    }
    saved = client.put("/api/profile", json=profile_payload, headers=auth)
    assert saved.status_code == 200

    fetched = client.get("/api/profile", headers=auth).json()
    assert fetched["basics"]["name"] == "林晓"

    draft = client.post("/api/resume-drafts", json={"job_id": job["id"]}, headers=auth).json()
    assert draft["sections"][0]["id"] == "identity"
    assert draft["sections"][0]["items"][0]["text"] == "林晓"

    docx = client.post(
        f"/api/resume-drafts/{draft['id']}/export", params={"format": "docx"}, headers=auth
    )
    assert docx.status_code == 200
    assert docx.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "林晓" in docx_document_xml(docx.content)

    pdf = client.post(
        f"/api/resume-drafts/{draft['id']}/export", params={"format": "pdf"}, headers=auth
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_user_job_status_is_private_and_visible_on_job_payloads(tmp_path):
    client = make_client(tmp_path)
    first_auth = auth_headers(client, username="first-user")
    second_auth = auth_headers(client, username="second-user")
    crawl_and_wait(client, [1])
    job = client.get("/api/jobs").json()["items"][0]

    created = client.put(
        f"/api/jobs/{job['id']}/status",
        json={"status": "preparing", "note": "重点准备科研证据", "deadline": "2026-07-01"},
        headers=first_auth,
    )

    assert created.status_code == 200
    assert created.json()["status"] == "preparing"
    assert created.json()["note"] == "重点准备科研证据"

    first_list = client.get("/api/jobs", headers=first_auth).json()["items"]
    first_item = next(item for item in first_list if item["id"] == job["id"])
    assert first_item["user_status"]["status"] == "preparing"
    assert first_item["user_status"]["deadline"] == "2026-07-01"

    second_detail = client.get(f"/api/jobs/{job['id']}", headers=second_auth).json()
    assert second_detail["user_status"] is None

    cleared = client.delete(f"/api/jobs/{job['id']}/status", headers=first_auth)
    assert cleared.status_code == 204
    assert client.get(f"/api/jobs/{job['id']}", headers=first_auth).json()["user_status"] is None


def test_job_payloads_reject_invalid_optional_auth_tokens(tmp_path):
    client = make_client(tmp_path)
    crawl_and_wait(client, [1])
    job = client.get("/api/jobs").json()["items"][0]
    invalid_auth = {"Authorization": "Bearer invalid-token"}

    assert client.get("/api/jobs").json()["items"][0]["user_status"] is None
    assert client.get(f"/api/jobs/{job['id']}").json()["user_status"] is None
    assert client.get("/api/jobs", headers=invalid_auth).status_code == 401
    assert client.get(f"/api/jobs/{job['id']}", headers=invalid_auth).status_code == 401


def test_deleting_status_for_missing_job_returns_404(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)

    missing = client.delete("/api/jobs/999999/status", headers=auth)

    assert missing.status_code == 404
    assert missing.json()["detail"] == "岗位不存在"


def test_resume_export_modes_keep_application_copy_free_of_gap_diagnostics(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    crawl_and_wait(client, [1])
    job = client.get("/api/jobs", params={"keyword": "科研"}).json()["items"][0]
    profile_payload = {
        "education": [],
        "experiences": [],
        "projects": [],
        "publications": [],
        "certificates": [],
        "skills": [{"id": "skill-1", "name": "绘画"}],
        "teaching": [],
        "awards": [],
        "languages": [],
    }
    client.put("/api/profile", json=profile_payload, headers=auth)
    draft = client.post("/api/resume-drafts", json={"job_id": job["id"]}, headers=auth).json()
    assert any(section["id"] == "gaps" for section in draft["sections"])

    application = client.post(
        f"/api/resume-drafts/{draft['id']}/export",
        params={"format": "docx", "mode": "application"},
        headers=auth,
    )
    diagnostic = client.post(
        f"/api/resume-drafts/{draft['id']}/export",
        params={"format": "docx", "mode": "diagnostic"},
        headers=auth,
    )
    application_pdf = client.post(
        f"/api/resume-drafts/{draft['id']}/export",
        params={"format": "pdf", "mode": "application"},
        headers=auth,
    )

    assert application.status_code == 200
    assert diagnostic.status_code == 200
    assert application_pdf.status_code == 200
    application_xml = docx_document_xml(application.content)
    diagnostic_xml = docx_document_xml(diagnostic.content)
    assert "投递前需补充确认" not in application_xml
    assert "未在你的履历中找到对应证据" not in application_xml
    assert "投递前需补充确认" in diagnostic_xml
    assert "未在你的履历中找到对应证据" in diagnostic_xml
    assert b"\xe6\x8a\x95\xe9\x80\x92\xe5\x89\x8d\xe9\x9c\x80\xe8\xa1\xa5\xe5\x85\x85\xe7\xa1\xae\xe8\xae\xa4" not in application_pdf.content
    assert b"\xe6\x9c\xaa\xe5\x9c\xa8\xe4\xbd\xa0\xe7\x9a\x84\xe5\xb1\xa5\xe5\x8e\x86\xe4\xb8\xad\xe6\x89\xbe\xe5\x88\xb0\xe5\xaf\xb9\xe5\xba\x94\xe8\xaf\x81\xe6\x8d\xae" not in application_pdf.content


def test_job_status_deadline_must_be_iso_date(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    crawl_and_wait(client, [1])
    job = client.get("/api/jobs").json()["items"][0]

    invalid = client.put(
        f"/api/jobs/{job['id']}/status",
        json={"status": "preparing", "deadline": "明天"},
        headers=auth,
    )

    assert invalid.status_code == 422


def test_report_generation_contains_scope_and_sources(tmp_path):
    client = make_client(tmp_path)
    crawl_and_wait(client, [1, 2])

    report = client.post("/api/reports", json={"title": "医疗岗位样本分析"})
    assert report.status_code == 201
    payload = report.json()
    assert "医疗岗位样本分析" in payload["title"]
    assert "样本范围" in payload["markdown"]
    assert "数据来源" in payload["markdown"]
    assert payload["html"].startswith("<!doctype html>")
    assert "<h1>医疗岗位样本分析</h1>" in payload["html"]
    assert "<h2>样本范围</h2>" in payload["html"]
    assert "<ul>" in payload["html"]
    assert "<li>" in payload["html"]


def test_report_html_escapes_title_and_lines(tmp_path):
    client = make_client(tmp_path)
    crawl_and_wait(client, [1])

    report = client.post("/api/reports", json={"title": "<script>alert(1)</script>"})

    assert report.status_code == 201
    html = report.json()["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_profile_extended_collections_can_supply_resume_evidence(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    crawl_and_wait(client, [3])
    job = client.get("/api/jobs", params={"keyword": "教学"}).json()["items"][0]

    profile_payload = {
        "education": [],
        "experiences": [],
        "projects": [],
        "publications": [
            {
                "id": "pub-1",
                "title": "公共卫生数据分析研究",
                "journal": "中华公共卫生杂志",
                "year": "2025",
                "authors": "林晓等",
            }
        ],
        "certificates": [],
        "skills": [],
        "teaching": [{"id": "teach-1", "course": "流行病学", "role": "助教", "institution": "复旦大学", "year": "2024"}],
        "awards": [{"id": "award-1", "name": "教学优秀奖", "issuer": "复旦大学", "year": "2024", "level": "校级"}],
        "languages": [],
    }

    saved = client.put("/api/profile", json=profile_payload, headers=auth)
    assert saved.status_code == 200
    draft = client.post("/api/resume-drafts", json={"job_id": job["id"]}, headers=auth)

    assert draft.status_code == 201
    payload = draft.json()
    section_ids = {section["id"] for section in payload["sections"]}
    evidence_collections = {item["collection"] for item in payload["evidence"]}
    assert {"publications", "teaching", "awards"} & section_ids
    assert {"publications", "teaching", "awards"} & evidence_collections


def test_pdf_export_accepts_chinese_resume_content(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    crawl_and_wait(client, [3])
    job = client.get("/api/jobs", params={"keyword": "教学"}).json()["items"][0]
    profile_payload = {
        "education": [{"id": "edu-1", "school": "复旦大学", "degree": "博士", "major": "公共卫生"}],
        "experiences": [],
        "projects": [],
        "publications": [{"id": "pub-1", "title": "教学与公共卫生数据分析", "journal": "医学教育", "year": "2025"}],
        "certificates": [],
        "skills": [{"id": "skill-1", "name": "教学"}, {"id": "skill-2", "name": "公共卫生"}],
        "teaching": [{"id": "teach-1", "course": "流行病学", "role": "主讲", "institution": "复旦大学"}],
        "awards": [{"id": "award-1", "name": "教学优秀奖", "issuer": "复旦大学"}],
        "languages": [],
    }
    client.put("/api/profile", json=profile_payload, headers=auth)
    draft = client.post("/api/resume-drafts", json={"job_id": job["id"]}, headers=auth).json()

    pdf = client.post(f"/api/resume-drafts/{draft['id']}/export", params={"format": "pdf"}, headers=auth)

    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
