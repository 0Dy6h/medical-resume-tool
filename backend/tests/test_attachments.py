from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.services.attachments import extract_attachment_links, parse_xlsx_table


def make_workbook_bytes(rows: list[list[str]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "岗位表"
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_extract_attachment_links_finds_supported_files():
    html = """
    <html><body>
      <a href="../docs/jobs.xlsx">岗位信息表.xlsx</a>
      <a href="/files/notice.PDF">公告附件.pdf</a>
      <a href="/files/readme.txt">说明</a>
    </body></html>
    """

    attachments = extract_attachment_links(html, "https://rsc.example.edu/rczp/article.htm")

    assert [item["name"] for item in attachments] == ["岗位信息表.xlsx", "公告附件.pdf"]
    assert attachments[0]["url"] == "https://rsc.example.edu/docs/jobs.xlsx"
    assert attachments[0]["extension"] == ".xlsx"
    assert attachments[1]["extension"] == ".pdf"


def test_parse_xlsx_table_returns_header_mapped_rows():
    content = make_workbook_bytes(
        [
            ["招聘单位", "岗位名称", "专业", "学历"],
            ["北京肿瘤医院", "临床医师", "临床医学", "博士"],
            ["北京肿瘤医院", "科研助理", "公共卫生", "硕士"],
        ]
    )

    rows = parse_xlsx_table(content)

    assert len(rows) == 2
    assert rows[0].sheet_name == "岗位表"
    assert rows[0].row_index == 2
    assert rows[0].headers == ["招聘单位", "岗位名称", "专业", "学历"]
    assert rows[0].values["岗位名称"] == "临床医师"
    assert "岗位名称：临床医师" in rows[0].raw_text


def test_parse_xlsx_table_ignores_empty_or_header_only_sheets():
    empty = make_workbook_bytes([])
    header_only = make_workbook_bytes([["岗位名称", "学历"]])

    assert parse_xlsx_table(empty) == []
    assert parse_xlsx_table(header_only) == []
