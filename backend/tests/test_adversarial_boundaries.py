"""用隔离数据库与生成的资料检验鉴权/导入边界，不调用真实 OCR 或抓取。"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from io import BytesIO
from threading import Event

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageSequence

import app.main as main
from app.services.auth import verify_token
from app.services.adapters import image_table_ocr
from app.services.profile_import import legacy


def client_and_auth(tmp_path):
    client = TestClient(main.create_app(f"sqlite:///{tmp_path / 'isolated.db'}"))
    response = client.post(
        "/api/auth/register", json={"username": "audit", "password": "offline-test-pass"}
    )
    assert response.status_code == 201
    return client, {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.mark.parametrize("token", ["é.signature", "payload.é", "payload.签名"])
def test_non_ascii_token_is_invalid_without_raising(token):
    assert verify_token(token) is None


def test_malformed_authorization_returns_401(tmp_path):
    client, _ = client_and_auth(tmp_path)
    response = client.get("/api/auth/me", headers={b"Authorization": b"Bearer payload.\xe9"})
    assert response.status_code == 401


def test_import_size_limit_is_enforced_before_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "MAX_IMPORT_FILE_BYTES", 32, raising=False)
    client, auth = client_and_auth(tmp_path)
    response = client.post(
        "/api/profile/import", files={"file": ("resume.txt", b"a" * 33, "text/plain")}, headers=auth
    )
    assert response.status_code == 413


def test_chunked_request_limit_is_enforced_before_form_parsing(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "MAX_REQUEST_BYTES", 512, raising=False)
    client, auth = client_and_auth(tmp_path)
    body = (
        b'--part\r\nContent-Disposition: form-data; name="file"; filename="resume.txt"\r\n'
        b'Content-Type: text/plain\r\n\r\n' + b"a" * 600 + b"\r\n--part--\r\n"
    )
    response = client.post(
        "/api/profile/import", content=iter([body[:100], body[100:]]),
        headers={**auth, "Content-Type": "multipart/form-data; boundary=part"},
    )
    assert response.status_code == 413


def test_ocr_reads_each_original_frame_and_never_traverses_beyond_cap(monkeypatch):
    frames = [Image.new("RGB", (4, 4), (number, 0, 0)) for number in [20, 40, 60]]
    buffer = BytesIO()
    frames[0].save(buffer, format="TIFF", save_all=True, append_images=frames[1:])
    visited = []
    iterator = ImageSequence.Iterator

    def tracked_frames(image):
        for frame in iterator(image):
            visited.append(frame.tell())
            yield frame

    monkeypatch.setattr(ImageSequence, "Iterator", tracked_frames)
    monkeypatch.setattr(legacy, "MAX_IMAGE_FRAMES", 2)
    monkeypatch.setattr(legacy, "_image_to_string", lambda _, image: f"page {image.getpixel((0, 0))[0]}")
    lines, warnings = legacy._ocr_image_bytes(buffer.getvalue(), source_label="resume.tiff")
    assert [line for line in lines if line] == ["page 20", "page 40"]
    assert visited == [0, 1]
    assert any("仅 OCR 前 2 帧" in warning for warning in warnings)


@pytest.mark.parametrize("source", ["profile", "recruitment"])
def test_renamed_eps_never_enters_an_unsupported_image_parser(monkeypatch, source):
    # Replace the unsupported decoder with a harmless sentinel. A vulnerable
    # image opener enters it before pixel/OCR limits can run; no looping payload
    # or external OCR process is needed to observe this format boundary.
    Image.init()
    entered = []

    def eps_decoder(*args, **kwargs):
        entered.append(True)
        raise ValueError("unsupported decoder reached")

    monkeypatch.setitem(Image.OPEN, "EPS", (eps_decoder, lambda prefix: prefix.startswith(b"%!PS")))
    content = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 1 1\n%%EOF\n"
    if source == "profile":
        with pytest.raises(legacy.ProfileImportError):
            legacy.extract_profile_text("renamed.png", content)
    else:
        assert image_table_ocr.ocr_image_bytes(content) is None
    assert not entered, "unsupported EPS input was parsed before being rejected"


@pytest.mark.parametrize("source", ["profile", "recruitment"])
def test_supported_png_still_reaches_offline_ocr(monkeypatch, source):
    import pytesseract

    buffer = BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    monkeypatch.setattr(pytesseract, "image_to_string", lambda *args, **kwargs: "姓名：合成测试")
    if source == "profile":
        assert legacy.extract_profile_text("resume.png", buffer.getvalue()).lines == ["姓名：合成测试"]
    else:
        assert image_table_ocr.ocr_image_bytes(buffer.getvalue()) == "姓名：合成测试"


def test_slow_import_does_not_block_health_or_other_users(tmp_path, monkeypatch):
    client, auth = client_and_auth(tmp_path)
    started = Event()
    release = Event()

    def extract(filename, content):
        started.set()
        assert release.wait(5), "测试提取器超时"
        return legacy.ProfileTextExtraction(["姓名：张三"])

    monkeypatch.setattr(main, "extract_profile_text", extract)
    timed_out = False
    with client, ThreadPoolExecutor(max_workers=2) as executor:
        uploading = executor.submit(
            client.post, "/api/profile/import",
            files={"file": ("resume.txt", b"fixture", "text/plain")}, headers=auth,
        )
        assert started.wait(2)
        health = executor.submit(client.get, "/health")
        try:
            assert health.result(timeout=1).status_code == 200
        except TimeoutError:
            timed_out = True
        finally:
            release.set()
        assert uploading.result(timeout=3).status_code == 200
    assert not timed_out, "资料提取阻塞了 API 的事件循环"
