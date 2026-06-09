import io
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import create_app
from app.services.crawler import ParsedJob
from app.services.database import connect, init_db, reset_db


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db_path}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


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

    run = client.post("/api/crawl-runs", json={"institution_ids": [1]})
    assert run.status_code == 201
    run_payload = run.json()
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

    rerun = client.post("/api/crawl-runs", json={"institution_ids": [1]})
    assert rerun.status_code == 201
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

    run = client.post("/api/crawl-runs", json={"institution_ids": [1]})

    assert run.status_code == 201
    payload = run.json()
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

    run = client.post("/api/crawl-runs", json={"institution_ids": [1, 2]})

    assert run.status_code == 201
    payload = run.json()
    assert payload["status"] == "partial"
    assert payload["failure_count"] == 1
    assert payload["success_count"] >= 3
    assert payload["errors"] == payload["error_summary"]
    assert payload["errors"][0]["institution_id"] == 2


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

    monkeypatch.setattr(main_module, "crawl_institution", crawl_same_text_different_url)

    first_run = client.post("/api/crawl-runs", json={"institution_ids": [1]})
    second_run = client.post("/api/crawl-runs", json={"institution_ids": [1]})

    assert first_run.status_code == 201
    assert second_run.status_code == 201
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

    monkeypatch.setattr(main_module.asyncio, "sleep", record_sleep)

    run = client.post("/api/crawl-runs", json={"institution_ids": [1, 2]})

    assert run.status_code == 201
    assert run.json()["status"] == "completed"
    assert sleep_calls == [1.0]


def test_job_detail_and_analytics_summary(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/crawl-runs", json={"institution_ids": [1, 2, 3]})

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


def test_profile_resume_draft_truth_constraints_and_exports(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/crawl-runs", json={"institution_ids": [1]})
    job = client.get("/api/jobs", params={"keyword": "科研"}).json()["items"][0]

    profile_payload = {
        "basic": {"name": "陈晓雨", "phone": "13800000000", "email": "chen@example.com", "city": "上海"},
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
    saved = client.put("/api/profile", json=profile_payload)
    assert saved.status_code == 200

    draft = client.post("/api/resume-drafts", json={"job_id": job["id"]})
    assert draft.status_code == 201
    draft_payload = draft.json()
    assert draft_payload["job_id"] == job["id"]
    assert draft_payload["sections"]
    assert draft_payload["evidence"]
    assert all(item["profile_field_id"] for item in draft_payload["evidence"])
    assert all("未在你的履历中找到对应证据" in gap["message"] for gap in draft_payload["gaps"])

    docx = client.post(f"/api/resume-drafts/{draft_payload['id']}/export", params={"format": "docx"})
    assert docx.status_code == 200
    assert docx.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert io.BytesIO(docx.content).getbuffer().nbytes > 1000

    pdf = client.post(f"/api/resume-drafts/{draft_payload['id']}/export", params={"format": "pdf"})
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")


def test_report_generation_contains_scope_and_sources(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/crawl-runs", json={"institution_ids": [1, 2]})

    report = client.post("/api/reports", json={"title": "医疗岗位样本分析"})
    assert report.status_code == 201
    payload = report.json()
    assert "医疗岗位样本分析" in payload["title"]
    assert "样本范围" in payload["markdown"]
    assert "数据来源" in payload["markdown"]
    assert payload["html"].startswith("<!doctype html>")
