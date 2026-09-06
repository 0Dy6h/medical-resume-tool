"""图片条件表 OCR 切片测试：URL 提取、诚实降级、真实识别（tesseract 在位时）、适配器注入。"""
from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.adapters.image_table_ocr import extract_image_urls, ocr_image_bytes
from app.services.adapters.z2hospital import extract_job_from_article

_TESSERACT = shutil.which("tesseract") or Path("C:/Program Files/Tesseract-OCR/tesseract.exe").exists()

INSTITUTION = {"institution_type": "hospital", "region": "浙江"}


def _render_png(lines: list[str]) -> bytes:
    """用系统中文字体把条件表文本渲染成 PNG（合成 fixture，无外部数据依赖）。"""
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for candidate in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"):
        if Path(candidate).exists():
            font = ImageFont.truetype(candidate, 28)
            break
    if font is None:  # pragma: no cover - 无中文字体的机器上跳过真实识别用例
        pytest.skip("系统无中文字体，无法合成图片 fixture")
    img = Image.new("RGB", (620, 48 * len(lines) + 40), "white")
    draw = ImageDraw.Draw(img)
    y = 20
    for line in lines:
        draw.text((24, y), line, fill="black", font=font)
        y += 48
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_extract_image_urls_absolutizes_and_filters_decorations():
    html = """
    <div class="main">
      <img src="/images/logo.png">
      <img src="data:image/png;base64,AAAA">
      <img src="/uploads/2026/07/condition-table.png">
      <img src="https://cdn.example.com/pic.jpg">
    </div>
    """
    urls = extract_image_urls(html, "https://www.z2hospital.com/channels/611.html")
    assert urls == [
        "https://www.z2hospital.com/uploads/2026/07/condition-table.png",
        "https://cdn.example.com/pic.jpg",
    ]


def test_ocr_image_bytes_degrades_honestly_on_garbage():
    # 损坏字节：不抛错、返回 None（诚实降级是本切片的核心契约）
    assert ocr_image_bytes(b"not-an-image-at-all") is None


@pytest.mark.skipif(not _TESSERACT, reason="本机未安装 Tesseract，无法做真实 OCR")
def test_ocr_image_bytes_reads_condition_table():
    png = _render_png(["岗位：护理研究人员", "学历：硕士研究生及以上"])
    text = ocr_image_bytes(png)
    assert text, "OCR 输出为空"
    assert any(kw in text for kw in ("硕士", "学历", "护理")), f"识别结果缺少关键词：{text[:80]}"


def test_fragmented_article_with_extra_body_enters_parsing():
    # 图片表格型公告：正文只剩标题碎片（<5 行）；OCR 文本经 extra_body 注入
    html = """
    <html><body><div class="main">
      <h1>护理研究人员招聘公告</h1>
      <p>一、岗位及条件</p>
    </div></body></html>
    """
    job = extract_job_from_article(html, "https://www.z2hospital.com/a/1.html", INSTITUTION)
    assert job is None or not job.requirements.strip(), "前置：碎片正文按诚实空态处理"

    job_ocr = extract_job_from_article(
        html,
        "https://www.z2hospital.com/a/1.html",
        INSTITUTION,
        extra_body="岗位及条件：护理研究人员；学历要求：硕士研究生及以上；其他：需完成住院医师规范化培训",
    )
    assert job_ocr is not None
    assert "硕士" in job_ocr.raw_text, "OCR 文本未并入解析输入"
