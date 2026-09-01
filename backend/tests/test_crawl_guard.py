"""U4 适配器可用化：零产出=失败、TLS 校验、出站安全护栏。"""
from __future__ import annotations

import asyncio
import socket
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.database import connect, init_db, reset_db
from app.services.http_client import (
    OutboundBlockedError,
    assert_public_url,
    build_crawl_client,
    guard_request,
    guard_response,
)


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
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


def crawl_and_wait(client: TestClient, institution_ids: list[int]) -> dict:
    user = client.post("/api/auth/register", json={"username": "crawler", "password": "secret123"})
    headers = {"Authorization": f"Bearer {user.json()['token']}"}
    run = client.post(
        "/api/crawl-runs", json={"institution_ids": institution_ids}, headers=headers
    )
    assert run.status_code == 201, run.text
    return wait_for_run(client, run.json()["id"])


def _set_strategy(client: TestClient, institution_id: int, url: str, strategy: str) -> None:
    with connect(client.app.state.engine) as conn:
        conn.execute(
            """
            UPDATE institutions
            SET listing_url = ?, crawl_strategy = ?, enabled = 1
            WHERE id = ?
            """,
            (url, strategy, institution_id),
        )
        conn.commit()


# ── 零产出 = 失败 ───────────────────────────────────────────────────


def test_zero_output_marks_institution_failed_with_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAWL_DELAY_SECONDS", "0")
    client = make_client(tmp_path)
    _set_strategy(client, 1, "https://nfyy.example.test/gkzp/", "nfyy")

    async def structure_changed_get(self, url):  # noqa: ANN001
        # 页面抓取成功，但结构变化：没有适配器期望的 div.main 容器。
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            text="<html><body><div class='layout'>招聘岗位已迁移</div></body></html>",
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", structure_changed_get)

    payload = crawl_and_wait(client, [1])

    assert payload["status"] == "failed"
    assert payload["failure_count"] == 1
    assert payload["success_count"] == 0
    error = payload["errors"][0]
    assert error["institution_id"] == 1
    assert error["error_type"] == "zero_output"
    assert "零产出" in error["error"]
    assert "结构变化" in error["error"]

    institutions = {item["id"]: item for item in client.get("/api/institutions").json()}
    assert institutions[1]["last_status"] == "failed"
    assert "零产出" in institutions[1]["last_error"]
    # 静默零产出不应入库任何岗位
    jobs = client.get("/api/jobs", params={"trust": "all"}).json()
    assert jobs["total"] == 0


def test_fixture_jobs_still_crawl_successfully(tmp_path):
    client = make_client(tmp_path)
    payload = crawl_and_wait(client, [1])

    assert payload["status"] == "completed"
    assert payload["failure_count"] == 0
    assert payload["success_count"] >= 1


def test_outbound_blocked_error_is_classified_separately(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAWL_DELAY_SECONDS", "0")
    client = make_client(tmp_path)
    _set_strategy(client, 1, "https://nfyy.example.test/gkzp/", "nfyy")

    import app.services.crawler as crawler_module
    from app.services.http_client import OutboundBlockedError as Blocked

    async def policy_blocked(institution):  # noqa: ANN001
        raise Blocked("禁止访问内网/保留/云元数据地址：internal.example.test")

    monkeypatch.setattr(crawler_module, "crawl_institution", policy_blocked)

    payload = crawl_and_wait(client, [1])

    assert payload["failure_count"] == 1
    error = payload["errors"][0]
    assert error["error_type"] == "outbound_blocked"


# ── 出站安全护栏 ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/admin",
        "http://localhost/x",
        "http://192.168.1.1/x",
        "http://10.0.0.5/x",
        "http://172.16.0.1/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/x",
        "http://0.0.0.0/x",
        "ftp://example.com/x",
        "file:///etc/passwd",
        "http:///no-host",
    ],
)
def test_blocked_outbound_urls(url):
    with pytest.raises(OutboundBlockedError):
        assert_public_url(url)


def test_public_literal_ip_allowed():
    assert_public_url("https://8.8.8.8/job/list")


def _addrinfo(ip: str) -> list:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


def test_domain_resolving_to_private_ip_blocked(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port: _addrinfo("192.168.0.10"))
    with pytest.raises(OutboundBlockedError):
        assert_public_url("https://internal.example.test/recruit")


def test_domain_resolving_to_public_ip_allowed(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port: _addrinfo("93.184.216.34"))
    assert_public_url("https://recruit.example.test/")


def test_unresolvable_domain_blocked(monkeypatch):
    def fail(host, port):  # noqa: ANN001
        raise OSError("dns lookup failed")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    with pytest.raises(OutboundBlockedError):
        assert_public_url("https://no-such.invalid/")


def test_guard_request_blocks_private_redirect_target():
    request = httpx.Request("GET", "http://10.1.2.3/secret")
    with pytest.raises(OutboundBlockedError):
        asyncio.run(guard_request(request))


def test_guard_response_rejects_oversize_content_length():
    response = httpx.Response(200, headers={"content-length": str(20 * 1024 * 1024)})
    with pytest.raises(OutboundBlockedError):
        asyncio.run(guard_response(response))


def test_guard_response_allows_normal_body():
    response = httpx.Response(200, content=b"x" * 1024)
    asyncio.run(guard_response(response))  # 不应抛出


def test_build_crawl_client_registers_tls_and_hooks():
    crawler_client = build_crawl_client()
    try:
        request_hooks = crawler_client.event_hooks.get("request", [])
        response_hooks = crawler_client.event_hooks.get("response", [])
        assert any(hook is guard_request for hook in request_hooks)
        assert any(hook is guard_response for hook in response_hooks)
    finally:
        asyncio.run(crawler_client.aclose())
