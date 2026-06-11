from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.database import init_db, reset_db
from app.services.profile_import import extract_docx_text, parse_profile_from_lines


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "import-test.db"
    app = create_app(f"sqlite:///{db_path}")
    reset_db(app.state.engine)
    init_db(app.state.engine)
    return TestClient(app)


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": "tester", "password": "secret123"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def sample_resume_docx() -> bytes:
    document = Document()
    document.add_heading("教育经历", level=1)
    document.add_paragraph("2021.09-2024.06 复旦大学 临床医学 硕士")
    document.add_paragraph("循证医学训练")
    document.add_paragraph("")
    document.add_paragraph("2017.09-2021.06 南京医科大学 临床医学 本科")
    document.add_heading("工作经历", level=1)
    document.add_paragraph("2023.01-2024.06 上海某三甲医院 科研助理")
    document.add_paragraph("维护随访数据库，协助统计分析")
    document.add_heading("科研项目经历", level=1)
    document.add_paragraph("慢病队列随访项目 项目成员")
    document.add_paragraph("完成 300 例随访记录核查")
    document.add_heading("发表论文", level=1)
    document.add_paragraph("慢病管理数据质量研究《中华公共卫生杂志》2024 doi:10.1234/abcd.5678")
    document.add_heading("获奖荣誉", level=1)
    document.add_paragraph("2023 优秀研究生 复旦大学 校级")
    document.add_heading("语言能力", level=1)
    document.add_paragraph("英语 CET-6")
    document.add_heading("专业技能", level=1)
    document.add_paragraph("SPSS、Python、数据管理")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_parse_profile_extracts_sections_and_fields():
    lines = extract_docx_text(sample_resume_docx())
    parsed = parse_profile_from_lines(lines)

    assert len(parsed["education"]) == 2
    first_education = parsed["education"][0]
    assert first_education["school"] == "复旦大学"
    assert first_education["degree"] == "硕士"
    assert first_education["major"] == "临床医学"
    assert first_education["start"] == "2021.09"
    assert first_education["end"] == "2024.06"
    assert first_education["highlights"] == ["循证医学训练"]

    assert len(parsed["experiences"]) == 1
    experience = parsed["experiences"][0]
    assert experience["organization"] == "上海某三甲医院"
    assert experience["role"] == "科研助理"
    assert experience["highlights"]

    assert len(parsed["projects"]) == 1
    project = parsed["projects"][0]
    assert project["name"] == "慢病队列随访项目"
    assert project["role"] == "项目成员"

    assert len(parsed["publications"]) == 1
    publication = parsed["publications"][0]
    assert publication["journal"] == "中华公共卫生杂志"
    assert publication["year"] == "2024"
    assert "10.1234/abcd.5678" in publication["doi"]

    assert len(parsed["awards"]) == 1
    award = parsed["awards"][0]
    assert award["year"] == "2023"
    assert award["level"] == "校级"
    assert award["issuer"] == "复旦大学"

    assert parsed["languages"][0]["name"] == "英语"
    assert parsed["languages"][0]["level"].upper().replace("-", "") == "CET6"

    skill_names = {item["name"] for item in parsed["skills"]}
    assert {"SPSS", "Python", "数据管理"} <= skill_names


def test_parse_profile_warns_on_unrecognized_document():
    parsed = parse_profile_from_lines(["这是一段没有任何板块标题的自由文本", "第二行内容"])
    assert all(not parsed[collection] for collection in ["education", "experiences", "projects"])
    assert parsed["warnings"]


def test_import_endpoint_returns_parsed_profile(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    response = client.post(
        "/api/profile/import",
        files={"file": ("resume.docx", sample_resume_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=auth,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["education"]
    assert payload["projects"]
    assert "warnings" in payload


def test_import_endpoint_requires_auth(tmp_path):
    client = make_client(tmp_path)
    response = client.post(
        "/api/profile/import",
        files={"file": ("resume.docx", sample_resume_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 401


def test_import_endpoint_rejects_non_docx(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    response = client.post("/api/profile/import", files={"file": ("resume.pdf", b"%PDF-1.4", "application/pdf")}, headers=auth)
    assert response.status_code == 400
    assert "docx" in response.text


def test_import_endpoint_rejects_corrupt_docx(tmp_path):
    client = make_client(tmp_path)
    auth = auth_headers(client)
    response = client.post(
        "/api/profile/import",
        files={"file": ("resume.docx", b"not a real docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=auth,
    )
    assert response.status_code == 400
