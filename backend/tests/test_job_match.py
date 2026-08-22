import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.database import init_db, reset_db
from app.services.resume import summarize_match


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "match-test.db"
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


def crawl_and_wait(client: TestClient, institution_ids: list[int], timeout: float = 30.0) -> dict:
    run = client.post("/api/crawl-runs", json={"institution_ids": institution_ids})
    assert run.status_code == 201
    return wait_for_run(client, run.json()["id"], timeout)


def auth_headers(client: TestClient, username: str = "tester", password: str = "secret123") -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_summarize_match_counts_requirements_not_evidence_rows():
    evidence = [
        {"requirement": "本科及以上学历", "profile_field_id": "edu-1", "collection": "education"},
        {"requirement": "本科及以上学历", "profile_field_id": "edu-2", "collection": "education"},
    ]
    gaps = [{"requirement": "SCI论文", "message": "未找到"}]

    result = summarize_match(evidence, gaps)
    assert result["met"] == 1
    assert result["total"] == 2
    assert 0 <= result["degree_percent"] <= 100
    assert "blocking_gap" in result


def test_summarize_match_blocking_flag():
    gaps_blocking = [{"requirement": "硕士", "message": "学历不符", "blocking": True}]
    result = summarize_match([], gaps_blocking)
    assert result["blocking_gap"] is True
    assert result["met"] == 0
    assert result["total"] == 1

    gaps_non_blocking = [{"requirement": "论文", "message": "未找到"}]
    result = summarize_match([], gaps_non_blocking)
    assert result["blocking_gap"] is False


def test_jobs_list_match_none_without_profile(tmp_path):
    client = make_client(tmp_path)
    crawl_and_wait(client, [1])

    jobs = client.get("/api/jobs").json()
    assert jobs["total"] >= 1
    for item in jobs["items"]:
        assert item["match"] is None

    auth = auth_headers(client)
    jobs_authed = client.get("/api/jobs", headers=auth).json()
    for item in jobs_authed["items"]:
        assert item["match"] is None


def test_jobs_list_includes_match_when_profile_exists(tmp_path):
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

    jobs = client.get("/api/jobs", headers=auth).json()
    assert jobs["total"] >= 1

    target = next(item for item in jobs["items"] if item["id"] == job["id"])
    assert target["match"] is not None
    match = target["match"]
    assert match["met"] >= 0
    assert match["total"] >= match["met"]
    assert 0 <= match["degree_percent"] <= 100
    assert set(match.keys()) >= {"met", "total", "degree_percent", "blocking_gap"}
