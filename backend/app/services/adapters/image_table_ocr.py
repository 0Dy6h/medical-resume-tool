"""图片条件表 OCR：把公告里以 PNG 图片发布的「岗位及条件」表转成文本。

背景：浙大二院（z2hospital）部分招聘公告把条件表发布为图片，正文只剩标题碎片，
纯文本管线只能诚实空态（requirements 为空）。本模块在运行态对该类公告做图片 OCR，
把识别文本并入正文重新解析；tesseract 印刷体中文识别质量有限，解析端按普通文本
口径走诚实降级（识别不出来就仍是空态）。

诚实降级链：依赖缺失 / Tesseract 不可用 / 图片损坏 / OCR 空文本 → 返回 None，
调用方按「无 OCR 文本」继续原管线，绝不抛错打断抓取。
环境开关 IMAGE_TABLE_OCR_ENABLED（默认开）；语言与命令和履历图片导入共用
PROFILE_IMPORT_OCR_LANGUAGES / TESSERACT_CMD。
"""
from __future__ import annotations

import os
from io import BytesIO
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# 最多 OCR 的图片张数：条件表公告通常 1-2 张，防异常页面拖垮抓取时长。
MAX_IMAGES = 4

_OCR_LANGUAGES = os.getenv("PROFILE_IMPORT_OCR_LANGUAGES", "chi_sim+eng")


def extract_image_urls(html: str, base_url: str, *, limit: int = MAX_IMAGES) -> list[str]:
    """提取正文图片的绝对 URL；跳过 data: URI 与明显装饰图（icon/logo）。"""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        lowered = src.lower()
        if any(kw in lowered for kw in ("icon", "logo", "banner", ".gif")):
            continue
        absolute = urljoin(base_url, src)
        if absolute not in urls:
            urls.append(absolute)
        if len(urls) >= limit:
            break
    return urls


def ocr_image_bytes(content: bytes) -> str | None:
    """单张图片 → 识别文本；任何失败都诚实返回 None。"""
    try:
        from PIL import Image, ImageOps
        import pytesseract
    except ImportError:
        return None

    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    try:
        with Image.open(BytesIO(content)) as image:
            prepared = ImageOps.exif_transpose(image).convert("RGB")
            try:
                text = pytesseract.image_to_string(prepared, lang=_OCR_LANGUAGES)
            except Exception:
                if _OCR_LANGUAGES != "eng":
                    text = pytesseract.image_to_string(prepared, lang="eng")
                else:
                    return None
    except Exception:
        return None
    text = (text or "").strip()
    return text or None


async def ocr_condition_tables(client, html: str, base_url: str) -> str:
    """下载公告内图片并 OCR，返回合并文本（无可用文本返回空串）。

    client 需为 httpx.AsyncClient（build_crawl_client 产物），由调用方持有会话。
    """
    parts: list[str] = []
    for url in extract_image_urls(html, base_url):
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except Exception:
            continue
        text = ocr_image_bytes(resp.content)
        if text:
            parts.append(text)
        if len(parts) >= MAX_IMAGES:
            break
    return "\n".join(parts).strip()
