"""Regression for real HTTP downloads, beyond TestClient's header handling."""
from __future__ import annotations

import copy
import http.client
import re
import socket
import threading
import time
from urllib.parse import unquote

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import Response

from app.services.exporter import build_export_filename, content_disposition_header


CONTROL_CHARACTERS = "".join(chr(value) for value in [*range(32), *range(127, 160)])


def decoded_name(header: str) -> str:
    assert header.isascii()
    assert not any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in header)
    match = re.fullmatch(r'attachment; filename="[^"\\]*"; filename\*=UTF-8\'\'(.+)', header)
    assert match, header
    return unquote(match.group(1))


def test_multiline_identity_only_affects_filename_first_line():
    draft = {"id": 1, "title": "科研助理 定制简历", "sections": [
        {"id": "identity", "items": [{"text": "合成测试\r\n保留在正文中的第二行"}]},
    ]}
    original = copy.deepcopy(draft)
    name = build_export_filename(draft, "docx")
    assert name.startswith("合成测试-科研助理-简历-")
    assert name.endswith(".docx")
    assert "第二行" not in name
    assert decoded_name(content_disposition_header(name)) == name
    assert draft == original


def test_header_removes_all_http_controls_and_filename_delimiters():
    filename = '合成"/\\<>:|?*' + CONTROL_CHARACTERS + '测试\r\nX-Evil: injected.docx'
    name = decoded_name(content_disposition_header(filename))
    assert "合成" in name and "测试" in name
    assert name.endswith(".docx")
    assert not any(char in name for char in CONTROL_CHARACTERS + '<>:"/\\|?*')


@pytest.mark.parametrize("filename", ["resume-1.docx", "张三-临床研究-简历.pdf"])
def test_normal_readable_names_and_extensions_are_preserved(filename):
    assert decoded_name(content_disposition_header(filename)) == filename


@pytest.mark.parametrize("filename", ["", CONTROL_CHARACTERS + '"\\/<>:|?* .'])
def test_empty_names_have_a_safe_fallback(filename):
    assert decoded_name(content_disposition_header(filename)) == "resume"


def test_real_uvicorn_http_download_with_multiline_and_hostile_names():
    app = FastAPI()
    draft = {"id": 7, "title": "科研\n助理 定制简历", "sections": [
        {"id": "identity", "items": [{"text": "合成测试\r\n第二行"}]},
    ]}
    payload = b"download response fixture"

    @app.get("/download/{kind}")
    def download(kind: str):
        filename = (build_export_filename(draft, "docx") if kind == "generated"
                    else '合成"\\' + CONTROL_CHARACTERS + '测试\r\nX-Evil: yes.docx')
        return Response(payload, headers={"Content-Disposition": content_disposition_header(filename)})

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started
            for kind in ("generated", "direct"):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                try:
                    connection.request("GET", "/download/" + kind)
                    response = connection.getresponse()
                    assert response.status == 200
                    assert response.read() == payload
                    assert response.getheader("X-Evil") is None
                    assert decoded_name(response.getheader("Content-Disposition")).endswith(".docx")
                finally:
                    connection.close()
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive()
