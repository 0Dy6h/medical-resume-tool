import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import Profile
from app.services.database import init_db, reset_db
from app.services.resume import analyze_job_match


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "detail-match-test.db"
    app = create_app(f"sqlite:///{db_path}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


def wait_for_run(client: TestClient, run_id: int, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get(f"/api/crawl-runs/{run_id}").json()
        if payload["status"] in {"completed", "partial", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"crawl run {run_id} did not finish within {timeout}s")


_crawl_seq = {"n": 0}


def _crawl_headers(client: TestClient) -> dict[str, str]:
    """注册一次性用户并返回 Authorization 头（抓取端点需要登录）。"""
    _crawl_seq["n"] += 1
    response = client.post(
        "/api/auth/register",
        json={"username": f"crawler-{_crawl_seq['n']}", "password": "secret123"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}

def crawl_and_wait(client: TestClient, institution_ids: list[int], timeout: float = 30.0) -> dict:
    run = client.post(
        "/api/crawl-runs", json={"institution_ids": institution_ids}, headers=_crawl_headers(client)
    )
    assert run.status_code == 201
    return wait_for_run(client, run.json()["id"], timeout)


def auth_headers(client: TestClient, username: str = "tester", password: str = "secret123") -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_analyze_job_match_four_states():
    """All four status classifications appear in a single call."""
    evidence = [
        {"requirement": "REQ_MET", "source_label": "教育经历", "source_text": "复旦大学 硕士"},
        {"requirement": "REQ_PARTIAL", "source_label": "技能能力", "source_text": "SPSS"},
    ]
    gaps = [
        {"requirement": "REQ_PARTIAL", "message": "部分满足但仍有差距"},
        {"requirement": "REQ_BLOCKING", "message": "学历不符", "blocking": True},
        {"requirement": "REQ_UNMET", "message": "未找到对应证据"},
    ]
    profile = Profile()
    job = {"raw_text": "dummy"}
    with patch("app.services.resume.match_profile_to_job", return_value=(evidence, gaps)):
        result = analyze_job_match(profile, job)

    by_req = {item["requirement"]: item for item in result}
    assert by_req["REQ_MET"]["status"] == "met"
    assert by_req["REQ_PARTIAL"]["status"] == "partial"
    assert by_req["REQ_BLOCKING"]["status"] == "blocking"
    assert by_req["REQ_UNMET"]["status"] == "unmet"

    assert by_req["REQ_MET"]["evidence"] == [{"source": "教育经历", "text": "复旦大学 硕士"}]
    assert by_req["REQ_BLOCKING"]["advice"] == "学历不符"
    assert by_req["REQ_UNMET"]["advice"] == "未找到对应证据"
    assert by_req["REQ_MET"]["advice"] is None


def test_analyze_job_match_blocking_beats_evidence():
    """A blocking gap overrides evidence on the same requirement."""
    evidence = [{"requirement": "REQ", "source_label": "教育", "source_text": "某大学"}]
    gaps = [{"requirement": "REQ", "message": "学历不符", "blocking": True}]
    profile = Profile()
    job = {"raw_text": "dummy"}
    with patch("app.services.resume.match_profile_to_job", return_value=(evidence, gaps)):
        result = analyze_job_match(profile, job)

    assert len(result) == 1
    assert result[0]["status"] == "blocking"
    assert result[0]["evidence"] == [{"source": "教育", "text": "某大学"}]
    assert result[0]["advice"] == "学历不符"


def test_job_detail_includes_match_analysis_with_profile(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    crawl_and_wait(client, [1])
    job = client.get("/api/jobs").json()["items"][0]

    profile_payload = {
        "education": [{"id": "edu-1", "school": "复旦大学", "degree": "硕士", "major": "临床医学"}],
        "skills": [{"id": "skill-1", "name": "SPSS"}],
    }
    saved = client.put("/api/profile", json=profile_payload, headers=auth)
    assert saved.status_code == 200

    detail = client.get(f"/api/jobs/{job['id']}", headers=auth).json()
    assert detail["match_analysis"] is not None
    assert isinstance(detail["match_analysis"], list)
    assert len(detail["match_analysis"]) > 0
    for item in detail["match_analysis"]:
        assert "requirement" in item
        assert "status" in item
        assert item["status"] in ("met", "partial", "blocking", "unmet")


def test_job_detail_match_analysis_none_without_profile(tmp_path):
    client = make_client(tmp_path)
    crawl_and_wait(client, [1])
    job = client.get("/api/jobs").json()["items"][0]

    detail = client.get(f"/api/jobs/{job['id']}").json()
    assert detail["match_analysis"] is None
