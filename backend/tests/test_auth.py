from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.auth import hash_password, make_token, verify_password, verify_token
from app.services.database import init_db, reset_db


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "auth-test.db"
    app = create_app(f"sqlite:///{db_path}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


def test_password_hash_roundtrip():
    password_hash, salt = hash_password("secret123")
    assert verify_password("secret123", password_hash, salt)
    assert not verify_password("wrong", password_hash, salt)


def test_password_hash_uses_random_salt():
    hash_a, salt_a = hash_password("secret123")
    hash_b, salt_b = hash_password("secret123")
    assert salt_a != salt_b
    assert hash_a != hash_b


def test_token_roundtrip_and_tampering():
    token = make_token(7, "alice")
    payload = verify_token(token)
    assert payload is not None
    assert payload["uid"] == 7
    assert payload["name"] == "alice"
    assert verify_token(token + "x") is None
    assert verify_token("garbage") is None
    assert verify_token(None) is None


def test_expired_token_rejected():
    expired = make_token(1, "bob", ttl=-10)
    assert verify_token(expired) is None


def test_register_then_login(tmp_path):
    client = make_client(tmp_path)

    registered = client.post("/api/auth/register", json={"username": "alice", "password": "secret123"})
    assert registered.status_code == 201
    assert registered.json()["username"] == "alice"
    assert registered.json()["token"]

    logged_in = client.post("/api/auth/login", json={"username": "alice", "password": "secret123"})
    assert logged_in.status_code == 200
    token = logged_in.json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_duplicate_username_rejected(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/auth/register", json={"username": "alice", "password": "secret123"})
    again = client.post("/api/auth/register", json={"username": "alice", "password": "another1"})
    assert again.status_code == 400


def test_register_username_rejects_whitespace(tmp_path):
    client = make_client(tmp_path)
    for name in ("has space", " leading", "trailing ", "tab\tuser", "全角\u3000空格"):
        response = client.post("/api/auth/register", json={"username": name, "password": "secret123"})
        assert response.status_code == 422, name


def test_register_username_allows_chinese(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/auth/register", json={"username": "中文用户名", "password": "secret123"})
    assert response.status_code == 201
    assert response.json()["username"] == "中文用户名"


def test_wrong_password_rejected(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/auth/register", json={"username": "alice", "password": "secret123"})
    bad = client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass"})
    assert bad.status_code == 401


def test_profile_requires_auth(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/profile").status_code == 401
    assert client.put("/api/profile", json={"education": []}).status_code == 401


def test_profile_is_isolated_per_user(tmp_path):
    client = make_client(tmp_path)
    token_a = client.post("/api/auth/register", json={"username": "alice", "password": "secret123"}).json()["token"]
    token_b = client.post("/api/auth/register", json={"username": "bob", "password": "secret123"}).json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    client.put("/api/profile", json={"skills": [{"id": "s1", "name": "SPSS"}]}, headers=headers_a)

    profile_b = client.get("/api/profile", headers=headers_b).json()
    assert profile_b["skills"] == []

    profile_a = client.get("/api/profile", headers=headers_a).json()
    # The typed Profile schema round-trips every declared field, so compare the
    # fields the caller sent rather than the whole serialized shape.
    assert len(profile_a["skills"]) == 1
    assert profile_a["skills"][0]["id"] == "s1"
    assert profile_a["skills"][0]["name"] == "SPSS"


def test_resume_draft_not_visible_across_users(tmp_path):
    client = make_client(tmp_path)
    token_a = client.post("/api/auth/register", json={"username": "alice", "password": "secret123"}).json()["token"]
    token_b = client.post("/api/auth/register", json={"username": "bob", "password": "secret123"}).json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    run = client.post("/api/crawl-runs", json={"institution_ids": [1]}, headers=headers_a)
    run_id = run.json()["id"]
    import time

    for _ in range(200):
        if client.get(f"/api/crawl-runs/{run_id}").json()["status"] in {"completed", "partial", "failed"}:
            break
        time.sleep(0.02)
    job = client.get("/api/jobs", params={"keyword": "护理"}).json()["items"][0]

    client.put("/api/profile", json={"skills": [{"id": "s1", "name": "病区护理与患者沟通"}]}, headers=headers_a)
    draft = client.post("/api/resume-drafts", json={"job_id": job["id"]}, headers=headers_a)
    assert draft.status_code == 201
    draft_id = draft.json()["id"]

    # bob cannot read alice's draft
    assert client.get(f"/api/resume-drafts/{draft_id}", headers=headers_b).status_code == 404
    # alice can
    assert client.get(f"/api/resume-drafts/{draft_id}", headers=headers_a).status_code == 200
