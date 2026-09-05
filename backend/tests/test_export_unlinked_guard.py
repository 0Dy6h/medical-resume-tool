"""U3 导出证据护栏：投递版导出不得静默携带未绑定档案证据的内容。

行为约定（对应方案 B3）：
- application 模式 + 存在无证据条目 + 未 override → 409，detail 携带条目数；
- override=true 表示用户已显式确认 → 放行，且投递版仍不出现「无档案证据」标注；
- diagnostic 模式不拦截：无证据条目在匹配附录中被明确标注，用于自查；
- 全部条目绑定证据且已审阅 → 无需 override 即可导出（对照用例，防误伤）。
"""

import io
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.database import init_db, reset_db

PROFILE = {
    "basics": {"name": "未关联护栏"},
    "education": [{"id": "edu-1", "school": "复旦大学", "degree": "硕士", "major": "临床医学"}],
    "skills": [{"id": "skill-1", "name": "SPSS"}, {"id": "skill-2", "name": "英语阅读能力良好"}],
}


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db_path}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


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
    assert run.status_code == 201, run.text
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get(f"/api/crawl-runs/{run.json()['id']}").json()
        if payload["status"] in {"completed", "partial", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"crawl run did not finish within {timeout}s")


def auth_headers(client: TestClient, username: str = "tester", password: str = "secret123") -> dict:
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def docx_document_xml(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        return zf.read("word/document.xml").decode("utf-8")


def _decide_all(sections: list[dict]) -> None:
    for section in sections:
        for item in section["items"]:
            item["decision"] = "adopt"


def _strip_first_link(sections: list[dict]) -> str | None:
    """抹掉第一个正文条目的 profile_field_id，返回其文本。"""
    for section in sections:
        if section["id"] in {"identity", "target", "gaps"}:
            continue
        if str(section.get("title", "")).strip() == "投递前需补充确认":
            continue
        for item in section["items"]:
            if item.get("profile_field_id"):
                text = item["text"]
                item["profile_field_id"] = ""
                return text
    return None


def _make_draft(client: TestClient, auth: dict, strip_link: bool) -> tuple[dict, str | None]:
    crawl_and_wait(client, [1])
    job = client.get("/api/jobs", params={"keyword": "科研"}).json()["items"][0]
    client.put("/api/profile", json=PROFILE, headers=auth)
    draft = client.post("/api/resume-drafts", json={"job_id": job["id"]}, headers=auth).json()

    sections = draft["sections"]
    _decide_all(sections)
    unlinked_text = _strip_first_link(sections) if strip_link else None
    client.put(f"/api/resume-drafts/{draft['id']}", json={"sections": sections}, headers=auth)
    return draft, unlinked_text


def test_application_export_blocked_by_unlinked_items(tmp_path):
    """审阅已通过但存在无证据条目 → 未确认时投递版导出被 409 拦截。"""
    client = make_client(tmp_path)
    auth = auth_headers(client)
    draft, unlinked_text = _make_draft(client, auth, strip_link=True)
    assert unlinked_text is not None

    resp = client.post(
        f"/api/resume-drafts/{draft['id']}/export",
        params={"format": "docx", "mode": "application"},
        headers=auth,
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "未关联档案证据" in detail
    assert "1 项" in detail


def test_application_export_unlinked_succeeds_with_override(tmp_path):
    """用户显式确认（override=true）后放行；投递版不出现证据标注。"""
    client = make_client(tmp_path)
    auth = auth_headers(client)
    draft, unlinked_text = _make_draft(client, auth, strip_link=True)

    resp = client.post(
        f"/api/resume-drafts/{draft['id']}/export",
        params={"format": "docx", "mode": "application", "override": True},
        headers=auth,
    )
    assert resp.status_code == 200
    xml = docx_document_xml(resp.content)
    # DOCX 把条目拆成结构化 run（“ / ”分隔符不保留），断言片段级存在。
    assert "复旦大学" in xml
    assert "临床医学" in xml
    assert "无档案证据" not in xml


def test_diagnostic_export_unlinked_not_blocked(tmp_path):
    """诊断模式不拦截：无证据条目在附录中标注，供用户自查。"""
    client = make_client(tmp_path)
    auth = auth_headers(client)
    draft, unlinked_text = _make_draft(client, auth, strip_link=True)

    resp = client.post(
        f"/api/resume-drafts/{draft['id']}/export",
        params={"format": "docx", "mode": "diagnostic"},
        headers=auth,
    )
    assert resp.status_code == 200
    xml = docx_document_xml(resp.content)
    assert "用户手动添加，无档案证据" in xml
    assert unlinked_text in xml


def test_application_export_linked_draft_not_blocked(tmp_path):
    """对照：全部条目绑定证据且已审阅 → 无需 override 即可导出。"""
    client = make_client(tmp_path)
    auth = auth_headers(client)
    draft, unlinked_text = _make_draft(client, auth, strip_link=False)
    assert unlinked_text is None

    resp = client.post(
        f"/api/resume-drafts/{draft['id']}/export",
        params={"format": "docx", "mode": "application"},
        headers=auth,
    )
    assert resp.status_code == 200


def test_application_export_blocks_forged_profile_field_id(tmp_path):
    """伪造 profile_field_id（不存在于当前档案）→ 投递版导出 409 拦截。

    2026-09-05 夜班实测发现：守卫此前只查引用非空，任意非空字符串
    （如 "999999"）即可伪装成已绑定档案证据进入投递版，违反真实简历红线。
    """
    client = make_client(tmp_path)
    auth = auth_headers(client)
    draft, _ = _make_draft(client, auth, strip_link=False)

    sections = draft["sections"]
    forged = 0
    for section in sections:
        if section["id"] in {"identity", "target", "gaps"}:
            continue
        if str(section.get("title", "")).strip() == "投递前需补充确认":
            continue
        for item in section["items"]:
            if item.get("profile_field_id"):
                item["profile_field_id"] = "999999-forged"
                forged += 1
    assert forged > 0
    client.put(f"/api/resume-drafts/{draft['id']}", json={"sections": sections}, headers=auth)

    resp = client.post(
        f"/api/resume-drafts/{draft['id']}/export",
        params={"format": "docx", "mode": "application"},
        headers=auth,
    )
    assert resp.status_code == 409
    assert "未关联档案证据" in resp.json()["detail"]

    # 诊断模式不受限：伪造引用条目在附录中标注，供自查
    diag = client.post(
        f"/api/resume-drafts/{draft['id']}/export",
        params={"format": "docx", "mode": "diagnostic"},
        headers=auth,
    )
    assert diag.status_code == 200
    assert "999999-forged" not in docx_document_xml(diag.content)


def test_put_draft_rejects_invalid_decision(tmp_path):
    """decision 任意字符串（如 "maybe"）→ 422，不再静默入库回显。"""
    client = make_client(tmp_path)
    auth = auth_headers(client)
    draft, _ = _make_draft(client, auth, strip_link=False)

    sections = draft["sections"]
    for section in sections:
        for item in section["items"]:
            item["decision"] = "maybe"
    resp = client.put(
        f"/api/resume-drafts/{draft['id']}", json={"sections": sections}, headers=auth
    )
    assert resp.status_code == 422
