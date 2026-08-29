"""U2 岗位库数据防线：可信度分级、trust/fresh_days 过滤、分析页可信度切片。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.crawler import ParsedJob
from app.services.database import create_engine, init_db, reset_db
from app.services.repositories import upsert_job


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db_path}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


def _parsed(institution_id: int, url: str, parser: str, fetched_at: str | None = None) -> ParsedJob:
    return ParsedJob(
        title=f"岗位-{parser}",
        department=None,
        location=None,
        education="硕士",
        profession="临床医学",
        job_category="临床",
        responsibilities="职责",
        requirements="要求",
        posted_at=None,
        deadline=None,
        source_url=url,
        source_text_hash=f"hash-{url}",
        raw_text="原文",
        tags=[],
        extraction_evidence={},
        fetched_at=fetched_at or datetime.now(timezone.utc).isoformat(),
        parser_name=parser,
        confidence=0.9,
    )


def _institution(client: TestClient, institution_id: int) -> dict:
    items = client.get("/api/institutions").json()
    return next(item for item in items if item["id"] == institution_id)


def _seed_jobs(client: TestClient) -> None:
    """插入四类数据：真实 / 占位 / fixture / 禁用机构历史。"""
    engine = client.app.state.engine
    # 机构 7（z2hospital，启用）：真实适配器产出
    upsert_job(engine, _institution(client, 7), _parsed(7, "https://example.com/real-1", "z2hospital-v1"))
    # 机构 7：generic 占位产出
    upsert_job(engine, _institution(client, 7), _parsed(7, "https://example.com/ph-1", "generic-list-v1"))
    # 机构 1（fixture，启用）：演示数据
    upsert_job(engine, _institution(client, 1), _parsed(1, "fixture://institution/1/job/99", "fixture-v1"))
    # 机构 8（禁用）：历史数据
    upsert_job(engine, _institution(client, 8), _parsed(8, "https://example.com/old-1", "tjh-v1"))


def test_jobs_carry_data_trust_labels(tmp_path):
    client = make_client(tmp_path)
    _seed_jobs(client)
    items = client.get("/api/jobs").json()["items"]
    trust_by_parser = {item["parser_name"]: item["data_trust"] for item in items}
    assert trust_by_parser["z2hospital-v1"] == "real"
    assert trust_by_parser["generic-list-v1"] == "placeholder"
    assert trust_by_parser["fixture-v1"] == "fixture"
    assert trust_by_parser["tjh-v1"] == "disabled"


def test_trust_real_excludes_placeholder_fixture_disabled(tmp_path):
    client = make_client(tmp_path)
    _seed_jobs(client)
    items = client.get("/api/jobs", params={"trust": "real"}).json()["items"]
    parsers = {item["parser_name"] for item in items}
    assert parsers == {"z2hospital-v1"}


def test_trust_slices_return_only_their_kind(tmp_path):
    client = make_client(tmp_path)
    _seed_jobs(client)
    placeholder = client.get("/api/jobs", params={"trust": "placeholder"}).json()["items"]
    assert {item["parser_name"] for item in placeholder} == {"generic-list-v1"}
    fixture = client.get("/api/jobs", params={"trust": "fixture"}).json()["items"]
    assert {item["parser_name"] for item in fixture} == {"fixture-v1"}
    disabled = client.get("/api/jobs", params={"trust": "disabled"}).json()["items"]
    assert {item["institution_id"] for item in disabled} == {8}


def test_fresh_days_filters_stale_jobs(tmp_path):
    client = make_client(tmp_path)
    engine = client.app.state.engine
    stale = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    upsert_job(engine, _institution(client, 7), _parsed(7, "https://example.com/new-1", "z2hospital-v1"))
    upsert_job(engine, _institution(client, 7), _parsed(7, "https://example.com/stale-1", "z2hospital-v1", fetched_at=stale))
    items = client.get("/api/jobs", params={"trust": "real", "fresh_days": 30}).json()["items"]
    assert {item["source_url"] for item in items} == {"https://example.com/new-1"}


def test_analytics_trust_breakdown_and_filter(tmp_path):
    client = make_client(tmp_path)
    _seed_jobs(client)
    payload = client.get("/api/analytics/summary").json()
    breakdown = {item["name"]: item["count"] for item in payload["trust_breakdown"]}
    assert breakdown == {"real": 1, "placeholder": 1, "fixture": 1, "disabled": 1}
    real_only = client.get("/api/analytics/summary", params={"trust": "real"}).json()
    assert real_only["totals"]["jobs"] == 1
    assert {item["name"] for item in real_only["trust_breakdown"]} == {"real"}


def test_job_detail_exposes_data_trust(tmp_path):
    client = make_client(tmp_path)
    _seed_jobs(client)
    items = client.get("/api/jobs").json()["items"]
    placeholder = next(item for item in items if item["data_trust"] == "placeholder")
    detail = client.get(f"/api/jobs/{placeholder['id']}").json()
    assert detail["data_trust"] == "placeholder"
