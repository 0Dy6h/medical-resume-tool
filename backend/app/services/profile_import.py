"""docx 履历资料导入：文本提取 + 规则解析。

解析是无状态的：上传的 docx 只在内存中转成行文本，再按板块标题切分、
逐条目抽取结构化字段。识别不出的内容保留在 highlights 或 warnings 中，不丢弃。
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from docx import Document

from app.services.classifier import normalize_text


SECTION_ALIASES: dict[str, list[str]] = {
    "education": ["教育经历", "教育背景", "学习经历", "学历信息"],
    "experiences": ["工作经历", "实习经历", "工作/实习经历", "工作与实习经历", "职业经历", "工作实习经历"],
    "projects": ["科研项目", "项目经历", "科研经历", "课题经历", "科研/项目经历", "科研项目经历", "课题"],
    "publications": ["发表论文", "论文发表", "学术成果", "学术论文", "论文", "出版物"],
    "certificates": ["证书资质", "资格证书", "资质证书", "证书"],
    "skills": ["专业技能", "技能能力", "技能特长", "技能"],
    "teaching": ["教学经历", "授课经历", "教学工作"],
    "awards": ["获奖荣誉", "荣誉奖项", "获奖经历", "获奖情况", "奖励荣誉", "获奖", "荣誉"],
    "languages": ["语言能力", "语言水平", "外语能力", "外语水平", "语言"],
}

_ALIAS_TO_COLLECTION = {
    alias: collection for collection, aliases in SECTION_ALIASES.items() for alias in aliases
}

_HEADING_DECORATION = re.compile(r"^[\s\d一二三四五六七八九十、.．()（）\[\]【】*#:：\-—]+|[\s:：、.．*#\-—]+$")
_BULLET_PREFIX = re.compile(r"^[•·●◦▪‣*\-–—]+\s*|^\d{1,2}[.、)）]\s*")
_DATE_RANGE = re.compile(
    r"(?P<start>\d{4}(?:[年./-]\d{1,2})?月?)\s*[-–—~～至到]+\s*(?P<end>至今|现在|\d{4}(?:[年./-]\d{1,2})?月?)"
)
_YEAR = re.compile(r"(?:19|20)\d{2}")
_YEAR_LEAD = re.compile(r"^\d{4}")
_DOI = re.compile(r"10\.\d{4,9}/\S+")
_JOURNAL = re.compile(r"《([^》]+)》")
_DEGREE = re.compile(r"博士|硕士|学士|本科|大专")

_SCHOOL_SUFFIXES = ["大学", "学院", "学校", "医学部"]
_ORG_SUFFIXES = ["医院", "大学", "学院", "中心", "研究所", "公司", "集团", "卫生院", "疾控", "诊所", "实验室", "科室"]
_ROLE_SUFFIXES = [
    "助理", "医师", "护师", "护士", "研究员", "工程师", "专员", "主管", "经理",
    "组长", "干事", "秘书", "实习生", "技师", "药师", "讲师", "教师", "助教", "成员", "负责人",
]
_PROJECT_ROLE_SUFFIXES = ["负责人", "主持", "成员", "参与", "骨干"]
_PROJECT_NAME_HINTS = ["项目", "课题", "研究", "队列", "平台", "基金"]
_ISSUER_SUFFIXES = ["部", "局", "委员会", "协会", "学会", "中心", "大学", "学院", "医院", "厅", "办公室"]
_AWARD_LEVEL = re.compile(r"国家级|省部级|省级|市级|校级|院级|特等奖|一等奖|二等奖|三等奖|金奖|银奖|铜奖|优秀奖")
_LANGUAGE_NAME = re.compile(r"英语|日语|法语|德语|俄语|韩语|西班牙语|阿拉伯语|普通话")
_LANGUAGE_LEVEL = re.compile(r"CET-?[46]|四级|六级|专业四级|专业八级|专四|专八|N[1-5]|雅思\s*[\d.]*|托福\s*\d*|IELTS\s*[\d.]*|TOEFL\s*\d*")
_TOKEN_SPLIT = re.compile(r"[\s,，;；、|/]+")


def extract_docx_text(content: bytes) -> list[str]:
    document = Document(BytesIO(content))
    lines: list[str] = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [normalize_text(cell.text) for cell in row.cells]
            unique = [cell for cell in dict.fromkeys(cells) if cell]
            if unique:
                lines.append("；".join(unique))
    return lines


def parse_profile_from_lines(lines: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {collection: [] for collection in SECTION_ALIASES}
    warnings: list[str] = []
    unassigned: list[str] = []
    current: str | None = None
    buffer: list[str] = []

    for raw in lines:
        line = normalize_text(raw)
        collection = _match_heading(line)
        if collection:
            if current:
                result[current].extend(_build_entries(current, buffer))
            current = collection
            buffer = []
        elif current:
            buffer.append(line)
        elif line:
            unassigned.append(line)
    if current:
        result[current].extend(_build_entries(current, buffer))

    if unassigned:
        preview = "；".join(unassigned[:3])
        warnings.append(f"有 {len(unassigned)} 行内容未能归入任何板块：{preview}")
    if not any(result[collection] for collection in SECTION_ALIASES):
        warnings.append("未从文档中识别出履历条目，请检查是否包含「教育经历」「项目经历」等板块标题")
    result["warnings"] = warnings
    return result


def _match_heading(line: str) -> str | None:
    if not line or len(line) > 12:
        return None
    cleaned = _HEADING_DECORATION.sub("", line)
    return _ALIAS_TO_COLLECTION.get(cleaned)


def _build_entries(collection: str, lines: list[str]) -> list[dict[str, Any]]:
    if collection in {"education", "experiences", "projects"}:
        blocks = _split_blocks(lines)
        builder = {
            "education": _build_education,
            "experiences": _build_experience,
            "projects": _build_project,
        }[collection]
        return [builder(block) for block in blocks]
    builder_by_line = {
        "publications": _build_publication,
        "certificates": _build_certificate,
        "teaching": _build_teaching,
        "awards": _build_award,
        "languages": _build_language,
    }
    entries: list[dict[str, Any]] = []
    for line in lines:
        text = _BULLET_PREFIX.sub("", line).strip()
        if not text:
            continue
        if collection == "skills":
            entries.extend({"name": part} for part in _TOKEN_SPLIT.split(text) if part)
        else:
            entries.append(builder_by_line[collection](text))
    return entries


def _split_blocks(lines: list[str]) -> list[list[str]]:
    """空行或年份起始行视为新条目的开始。"""
    blocks: list[list[str]] = []
    block: list[str] = []
    for line in lines:
        text = _BULLET_PREFIX.sub("", line).strip()
        if not text:
            if block:
                blocks.append(block)
                block = []
            continue
        if block and _YEAR_LEAD.match(text):
            blocks.append(block)
            block = []
        block.append(text)
    if block:
        blocks.append(block)
    return blocks


def _build_education(block: list[str]) -> dict[str, Any]:
    head, highlights = block[0], block[1:]
    start, end, remaining = _take_date_range(head)
    degree_match = _DEGREE.search(remaining)
    degree = degree_match.group(0) if degree_match else ""
    tokens = _tokens(remaining)
    school = _pick_token(tokens, _SCHOOL_SUFFIXES)
    major = next(
        (token for token in tokens if token not in {school, degree} and not _DEGREE.fullmatch(token) and 2 <= len(token) <= 20),
        "",
    )
    return _entry(school=school, degree=degree, major=major, start=start, end=end, highlights=highlights)


def _build_experience(block: list[str]) -> dict[str, Any]:
    head, highlights = block[0], block[1:]
    start, end, remaining = _take_date_range(head)
    tokens = _tokens(remaining)
    organization = _pick_token(tokens, _ORG_SUFFIXES)
    role = _pick_token([token for token in tokens if token != organization], _ROLE_SUFFIXES)
    return _entry(organization=organization, role=role, start=start, end=end, highlights=highlights)


def _build_project(block: list[str]) -> dict[str, Any]:
    head, highlights = block[0], block[1:]
    _, _, remaining = _take_date_range(head)
    tokens = _tokens(remaining)
    role = _pick_token(tokens, _PROJECT_ROLE_SUFFIXES)
    name = _pick_token([token for token in tokens if token != role], _PROJECT_NAME_HINTS)
    if not name:
        name = next((token for token in tokens if token != role), remaining)
    return _entry(name=name, role=role, highlights=highlights)


def _build_publication(line: str) -> dict[str, Any]:
    doi_match = _DOI.search(line)
    journal_match = _JOURNAL.search(line)
    year_match = _YEAR.search(line)
    return _entry(
        title=line,
        journal=journal_match.group(1) if journal_match else "",
        year=year_match.group(0) if year_match else "",
        doi=doi_match.group(0) if doi_match else "",
    )


def _build_certificate(line: str) -> dict[str, Any]:
    year_match = _YEAR.search(line)
    tokens = _tokens(line)
    issuer = _pick_token(tokens, _ISSUER_SUFFIXES)
    name = next((token for token in tokens if token != issuer and not _YEAR.fullmatch(token)), line)
    return _entry(name=name, issuer=issuer, year=year_match.group(0) if year_match else "")


def _build_teaching(line: str) -> dict[str, Any]:
    year_match = _YEAR.search(line)
    tokens = _tokens(line)
    institution = _pick_token(tokens, _SCHOOL_SUFFIXES + ["医院"])
    role = _pick_token([token for token in tokens if token != institution], ["主讲", "助教", "带教", "讲师", "授课"])
    course = next(
        (token for token in tokens if token not in {institution, role} and not _YEAR.fullmatch(token) and ("课" in token or "学" in token)),
        "",
    )
    return _entry(course=course, role=role, institution=institution, year=year_match.group(0) if year_match else "")


def _build_award(line: str) -> dict[str, Any]:
    year_match = _YEAR.search(line)
    level_match = _AWARD_LEVEL.search(line)
    tokens = _tokens(line)
    issuer = _pick_token(tokens, _ISSUER_SUFFIXES)
    name = next((token for token in tokens if token != issuer and not _YEAR.fullmatch(token)), line)
    return _entry(
        name=name,
        issuer=issuer,
        year=year_match.group(0) if year_match else "",
        level=level_match.group(0) if level_match else "",
    )


def _build_language(line: str) -> dict[str, Any]:
    name_match = _LANGUAGE_NAME.search(line)
    level_match = _LANGUAGE_LEVEL.search(line)
    return _entry(
        name=name_match.group(0) if name_match else line,
        level=normalize_text(level_match.group(0)) if level_match else "",
    )


def _take_date_range(text: str) -> tuple[str, str, str]:
    match = _DATE_RANGE.search(text)
    if not match:
        return "", "", text
    start = match.group("start").rstrip("月")
    end = match.group("end").rstrip("月")
    remaining = normalize_text(text[: match.start()] + " " + text[match.end() :])
    return start, end, remaining


def _tokens(text: str) -> list[str]:
    return [token for token in _TOKEN_SPLIT.split(text) if token]


def _pick_token(tokens: list[str], suffixes: list[str]) -> str:
    for token in tokens:
        if any(suffix in token for suffix in suffixes):
            return token
    return ""


def _entry(**fields: Any) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value}
