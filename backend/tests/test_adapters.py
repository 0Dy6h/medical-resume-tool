"""Tests for site-specific adapters using saved HTML fixtures."""
from pathlib import Path

import pytest
from openpyxl import Workbook

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def make_xlsx_bytes(rows: list[list[str]]) -> bytes:
    from io import BytesIO

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "岗位信息表"
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


class TestZ2HospitalAdapter:
    def test_extract_article_links_from_listing(self):
        from app.services.adapters.z2hospital import extract_article_links

        html = (FIXTURES / "z2hospital" / "listing.html").read_text(encoding="utf-8")
        links = extract_article_links(html, "https://www.z2hospital.com/channels/611.html")
        assert len(links) >= 10
        first = links[0]
        assert "招聘" in first["title"] or "启事" in first["title"]
        assert first["url"].startswith("https://www.z2hospital.com/contents/")
        assert first["date"]  # should have a date

    def test_extract_job_from_article(self):
        from app.services.adapters.z2hospital import extract_job_from_article

        html = (FIXTURES / "z2hospital" / "article.html").read_text(encoding="utf-8")
        institution = {"institution_type": "医院", "region": "浙江"}
        job = extract_job_from_article(
            html, "https://www.z2hospital.com/contents/611/24424.html", institution
        )
        assert job is not None
        assert job.parser_name == "z2hospital-article-v1"
        assert "招聘" in job.title or "超声" in job.title
        assert job.source_url == "https://www.z2hospital.com/contents/611/24424.html"
        assert job.confidence > 0

    def test_extract_job_from_detailed_article(self):
        from app.services.adapters.z2hospital import extract_job_from_article

        fixture_path = FIXTURES / "z2hospital" / "article_24348.html"
        if not fixture_path.exists():
            pytest.skip("article_24348 fixture not available")
        html = fixture_path.read_text(encoding="utf-8")
        institution = {"institution_type": "医院", "region": "浙江"}
        job = extract_job_from_article(
            html, "https://www.z2hospital.com/contents/611/24348.html", institution
        )
        assert job is not None
        assert "医师" in job.title or "招聘" in job.title


class TestChinaCDCAdapter:
    def test_extract_article_links_from_listing(self):
        from app.services.adapters.chinacdc import extract_article_links

        html = (FIXTURES / "chinacdc" / "listing.html").read_text(encoding="utf-8")
        links = extract_article_links(html, "https://www.chinacdc.cn/rcjs/rczp/")
        assert len(links) >= 5
        assert any("招聘" in l["title"] for l in links)
        # Links should be absolute URLs
        assert all(l["url"].startswith("https://") for l in links)

    def test_extract_jobs_from_dept_notice(self):
        from app.services.adapters.chinacdc import extract_jobs_from_article

        fixture_path = FIXTURES / "chinacdc" / "article_dept.html"
        if not fixture_path.exists():
            pytest.skip("article_dept fixture not available")
        html = fixture_path.read_text(encoding="utf-8")
        institution = {"institution_type": "研究机构", "region": "北京"}
        jobs = extract_jobs_from_article(
            html, "https://www.chinacdc.cn/rcjs/rczp/202511/t20251105_313275.html", institution
        )
        assert len(jobs) >= 1
        job = jobs[0]
        assert job.parser_name == "chinacdc-dept-v1"
        assert job.confidence > 0

    def test_extract_jobs_from_annual_notice(self):
        from app.services.adapters.chinacdc import extract_jobs_from_article

        html = (FIXTURES / "chinacdc" / "article.html").read_text(encoding="utf-8")
        institution = {"institution_type": "研究机构", "region": "北京"}
        jobs = extract_jobs_from_article(
            html, "https://www.chinacdc.cn/rcjs/rczp/202603/t20260306_315301.html", institution
        )
        # Annual notice has positions in xlsx - should still return a record
        assert len(jobs) >= 1
        assert jobs[0].parser_name == "chinacdc-notice-v1"

    def test_extract_jobs_from_annual_notice_xlsx_attachment(self):
        from app.services.adapters.chinacdc import extract_jobs_from_article
        from app.services.attachments import extract_attachment_links

        html = (FIXTURES / "chinacdc" / "article.html").read_text(encoding="utf-8")
        source_url = "https://www.chinacdc.cn/rcjs/rczp/202603/t20260306_315301.html"
        attachments = extract_attachment_links(html, source_url)
        xlsx_url = next((item["url"] for item in attachments if item["extension"] == ".xlsx"), source_url + "#test.xlsx")
        institution = {"institution_type": "研究机构", "region": "北京"}
        jobs = extract_jobs_from_article(
            html,
            source_url,
            institution,
            attachment_bytes_by_url={
                xlsx_url: make_xlsx_bytes(
                    [
                        ["招聘单位", "岗位名称", "专业", "学历"],
                        ["中国疾控中心", "公共卫生研究岗", "公共卫生", "硕士"],
                    ]
                )
            },
        )

        parsed = [job for job in jobs if job.parser_name == "chinacdc-xlsx-v1"]
        assert len(parsed) == 1
        assert parsed[0].source_url == f"{xlsx_url}#岗位信息表-2"
        assert parsed[0].extraction_evidence["attachment_url"] == xlsx_url
        assert parsed[0].extraction_evidence["announcement_url"] == source_url

    def test_extract_jobs_from_annual_notice_marks_attachment_failure(self):
        from app.services.adapters.chinacdc import extract_jobs_from_article
        from app.services.attachments import extract_attachment_links

        html = (FIXTURES / "chinacdc" / "article.html").read_text(encoding="utf-8")
        source_url = "https://www.chinacdc.cn/rcjs/rczp/202603/t20260306_315301.html"
        attachments = extract_attachment_links(html, source_url)
        xlsx_url = next((item["url"] for item in attachments if item["extension"] == ".xlsx"), source_url + "#test.xlsx")
        institution = {"institution_type": "研究机构", "region": "北京"}

        jobs = extract_jobs_from_article(
            html,
            source_url,
            institution,
            attachment_errors_by_url={xlsx_url: "network unavailable"},
        )

        assert jobs[0].parser_name == "chinacdc-notice-v1"
        failed = jobs[0].extraction_evidence["attachments"][0]
        assert failed["status"] == "failed"
        assert failed["error"] == "network unavailable"


class TestNJMUAdapter:
    def test_extract_article_links_from_listing(self):
        from app.services.adapters.njmu import extract_article_links

        html = (FIXTURES / "njmu" / "listing.html").read_text(encoding="utf-8")
        links = extract_article_links(html, "https://rsc.njmu.edu.cn/10978/list.htm")
        assert len(links) >= 3
        assert any("招聘" in l["title"] for l in links)

    def test_extract_jobs_from_article(self):
        from app.services.adapters.njmu import extract_jobs_from_article

        html = (FIXTURES / "njmu" / "article.html").read_text(encoding="utf-8")
        institution = {"institution_type": "高校", "region": "江苏"}
        jobs = extract_jobs_from_article(
            html, "https://rsc.njmu.edu.cn/10978/2026/0410/c10978a299543/page.htm", institution
        )
        assert len(jobs) >= 1
        job = jobs[0]
        assert job.parser_name == "njmu-notice-v1"
        assert "南京医科大学" in job.title or "招聘" in job.title


class TestHRBMUAdapter:
    def test_extract_article_links_from_listing(self):
        from app.services.adapters.hrbmu import extract_article_links

        html = (FIXTURES / "hrbmu" / "listing.html").read_text(encoding="utf-8")
        links = extract_article_links(html, "http://hr.hrbmu.edu.cn/")
        assert len(links) >= 3
        assert any("招聘" in l["title"] or "公告" in l["title"] for l in links)

    def test_extract_jobs_from_table_article(self):
        from app.services.adapters.hrbmu import extract_jobs_from_table_article

        html = (FIXTURES / "hrbmu" / "article.html").read_text(encoding="utf-8")
        institution = {"institution_type": "高校", "region": "黑龙江"}
        jobs = extract_jobs_from_table_article(
            html, "http://hr.hrbmu.edu.cn/info/1117/1716.htm", institution
        )
        assert len(jobs) >= 1
        # Should have extracted position types from the table
        assert any("医师" in j.title or "岗位" in j.title for j in jobs)
        assert jobs[0].parser_name == "hrbmu-table-v1"


class TestBJMUAdapter:
    def test_extract_article_links_from_listing(self):
        from app.services.adapters.bjmu import extract_article_links

        html = (FIXTURES / "bjmu" / "listing.html").read_text(encoding="utf-8")
        links = extract_article_links(html, "https://rsc.bjmu.edu.cn/rczp/js/index.htm")
        assert len(links) >= 5
        assert any("招聘" in l["title"] for l in links)

    def test_extract_jobs_from_article(self):
        from app.services.adapters.bjmu import extract_jobs_from_article

        html = (FIXTURES / "bjmu" / "article.html").read_text(encoding="utf-8")
        institution = {"institution_type": "高校", "region": "北京"}
        jobs = extract_jobs_from_article(
            html, "https://rsc.bjmu.edu.cn/rczp/js/test.htm", institution
        )
        assert len(jobs) >= 1
        assert jobs[0].parser_name == "bjmu-notice-v1"
        assert jobs[0].confidence > 0

    def test_extract_article_attachment_links(self):
        from app.services.attachments import extract_attachment_links

        html = (FIXTURES / "bjmu" / "article.html").read_text(encoding="utf-8")
        attachments = extract_attachment_links(html, "https://rsc.bjmu.edu.cn/rczp/js/test.htm")

        assert any(item["extension"] == ".xlsx" for item in attachments)
        assert any("岗位信息表" in item["name"] for item in attachments)

    def test_extract_jobs_from_xlsx_attachment(self):
        from app.services.adapters.bjmu import extract_jobs_from_article
        from app.services.attachments import extract_attachment_links

        html = (FIXTURES / "bjmu" / "article.html").read_text(encoding="utf-8")
        source_url = "https://rsc.bjmu.edu.cn/rczp/js/test.htm"
        attachments = extract_attachment_links(html, source_url)
        xlsx_url = next(item["url"] for item in attachments if item["extension"] == ".xlsx")
        institution = {"institution_type": "高校", "region": "北京"}

        jobs = extract_jobs_from_article(
            html,
            source_url,
            institution,
            attachment_bytes_by_url={
                xlsx_url: make_xlsx_bytes(
                    [
                        ["招聘单位", "岗位名称", "专业", "学历"],
                        ["北京肿瘤医院", "临床医师", "临床医学", "博士"],
                        ["北京肿瘤医院", "科研助理", "公共卫生", "硕士"],
                    ]
                )
            },
        )

        parsed = [job for job in jobs if job.parser_name == "bjmu-xlsx-v1"]
        assert len(parsed) == 2
        assert parsed[0].source_url == f"{xlsx_url}#岗位信息表-2"
        assert parsed[0].extraction_evidence["attachment_url"] == xlsx_url
        assert parsed[0].extraction_evidence["attachment_name"].endswith(".xlsx")
        assert parsed[0].extraction_evidence["sheet_name"] == "岗位信息表"
        assert parsed[0].extraction_evidence["row_index"] == 2
        assert parsed[0].extraction_evidence["headers"] == ["招聘单位", "岗位名称", "专业", "学历"]

    def test_extract_jobs_marks_corrupt_xlsx_as_failed_attachment(self):
        from app.services.adapters.bjmu import extract_jobs_from_article
        from app.services.attachments import extract_attachment_links

        html = (FIXTURES / "bjmu" / "article.html").read_text(encoding="utf-8")
        source_url = "https://rsc.bjmu.edu.cn/rczp/js/test.htm"
        attachments = extract_attachment_links(html, source_url)
        xlsx_url = next(item["url"] for item in attachments if item["extension"] == ".xlsx")
        institution = {"institution_type": "高校", "region": "北京"}

        jobs = extract_jobs_from_article(
            html,
            source_url,
            institution,
            attachment_bytes_by_url={xlsx_url: b"not an xlsx file"},
        )

        assert jobs[0].parser_name == "bjmu-notice-v1"
        failed = jobs[0].extraction_evidence["attachments"][0]
        assert failed["status"] == "failed"
        assert "File is not a zip file" in failed["error"]
        assert all(job.parser_name != "bjmu-xlsx-v1" for job in jobs)
