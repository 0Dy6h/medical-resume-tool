"""Extract the real requirement clauses from a Chinese job announcement.

The stored ``raw_text`` is whitespace-collapsed (``crawler`` runs
``normalize_text`` over it), so there are no line breaks to rely on — clauses
have to be recovered from the CJK enumeration and punctuation markers that
survive collapsing: ``一、`` ``（一）`` ``1、`` ``2.`` ``；`` ``。``.

The previous extractor (``classifier.extract_requirements``) kept any clause
containing one of eight trigger words, which on real announcements surfaced
mostly boilerplate — application deadlines, employer self-promotion, exam
rules — and dropped genuine requirements that used none of those words.  This
module instead locates the requirement *block* by its heading and keeps its
clauses, dropping only recognizable procedure and employer-subject sentences.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.classifier import normalize_text

# ── block boundaries ─────────────────────────────────────────────────

#: Section headings that open a requirement block.
REQUIREMENT_HEADINGS = (
    "招聘条件", "招聘基本条件", "基本条件", "任职条件", "任职要求",
    "应聘条件", "报考条件", "岗位要求", "岗位条件", "资格条件",
    "招聘对象和条件", "报名条件",
)

#: Section headings whose block is NOT requirements — used to end the block.
_NON_REQUIREMENT_HEADINGS = (
    "报名", "招聘程序", "招聘流程", "考试", "笔试", "面试", "体检", "考核",
    "公示", "聘用", "待遇", "薪酬", "联系", "咨询", "监督", "纪律",
    "其他", "附则", "岗位职责", "工作职责", "工作内容", "招聘岗位",
    "招聘计划", "招聘人数", "岗位信息", "报名方式", "报名时间", "资格审查",
    "录用", "有关事项", "注意事项",
)

#: A top-level section heading marker: 一、 二、 (一) （二） 第一 etc. at clause start.
_HEADING_MARKER = re.compile(
    r"^\s*(?:[一二三四五六七八九十]+\s*[、.]|（\s*[一二三四五六七八九十]+\s*）|第[一二三四五六七八九十]+[条章部分])"
)

# ── clause splitting ─────────────────────────────────────────────────

#: Enumeration markers that begin a sub-clause, e.g. "1、" "2." "（3）" "3）" "①".
_ENUM_MARKER = re.compile(
    r"(?:（\s*\d+\s*）|\(\s*\d+\s*\)|\d+\s*[、.．)）]|[①②③④⑤⑥⑦⑧⑨⑩]|（\s*[一二三四五六七八九十]+\s*）|[一二三四五六七八九十]+\s*[、])"
)

#: Sentence terminators.
_TERMINATORS = "；;。！!\n"

# ── boilerplate / procedure filters ──────────────────────────────────

#: A clause containing any of these is application procedure, not a requirement.
_PROCEDURE_TERMS = (
    "报名", "截止", "邮箱", "email", "投递", "简历发送", "笔试", "面试", "体检",
    "公示", "录用", "聘用", "考察", "资格审查", "资格初审", "资格复审", "现场确认",
    "上传照片", "身份证原件", "准考证", "http", "www", "网址", "网站", "附件",
    "咨询电话", "联系电话", "联系人", "监督电话", "举报", "地址", "邮编",
    "详见", "另行通知", "如下", "格式", "下载", "扫描件",
)

#: A clause whose subject is the employer, not the applicant.
_EMPLOYER_TERMS = (
    "医院拥有", "医院现有", "我院拥有", "我院现有", "我校现有", "我校拥有",
    "中心拥有", "现有职工", "现有床位", "开放床位", "编制床位", "成立于",
    "占地", "建筑面积", "年门诊", "年收入", "是一所", "是一家", "是国家",
    "综合实力", "位居", "排名", "隶属于", "始建于", "创建于", "前身",
    "拥有博士点", "博士点", "硕士点", "国家临床重点", "重点学科", "获批",
)

#: Requirement cue words that promote a clause even outside a clear block.
_REQUIREMENT_CUES = (
    "学历", "学位", "本科", "硕士", "博士", "研究生", "大专", "专科",
    "专业", "毕业", "资格证", "执业", "职称", "经验", "经历", "能力",
    "熟悉", "熟练", "掌握", "具备", "具有", "从事", "优先", "年龄",
    "证书", "技能", "英语", "计算机", "发表", "科研", "临床", "护理",
    "以上", "岗位所需", "相关", "要求", "条件",
)

#: Sub-section headings that end the requirement content even at sub-level
#: (chinacdc nests "（三）招聘方式及待遇" under the 招聘条件 block).
_STOP_SUBHEADINGS = (
    "待遇", "薪酬", "工资", "招聘方式", "招聘程序", "招聘流程", "报名",
    "考试", "笔试", "面试", "体检", "考核", "聘用", "录用", "公示",
    "联系", "咨询", "监督", "其他事项", "有关事项", "注意事项",
)

#: Strong markers of an application-eligibility clause (国籍/年龄/政治面貌/
#: 健康状况…).  These state who may apply at all, not what the job needs from
#: a resume; the structured profile carries no comparable facts for them, so
#: counting them as unmet gaps only drowns the real match signal (P0-1).
_ELIGIBILITY_MARKERS = (
    "国籍", "宪法", "年龄", "周岁", "政治面貌", "中共党员", "预备党员",
    "品行", "遵纪守法", "违法", "犯罪", "身体条件", "身心健康", "健康状况",
    "计划生育", "回避", "户籍", "生源",
)

#: Degree markers win over eligibility markers: a combined clause like
#: "硕士及以上学历，年龄不超过35周岁" must reach the degree gate, which is the
#: only component able to evaluate it arithmetically.
_DEGREE_MARKERS = ("学历", "学位", "大专", "专科", "本科", "硕士", "博士", "研究生")

_MIN_LEN = 4
_MAX_LEN = 140
_MAX_REQUIREMENTS = 15


def _is_heading_clause(clause: str) -> bool:
    """True when a clause is a section title rather than a requirement.

    Headings are short.  The check is length-gated because a real requirement
    can *contain* a heading phrase — "适应岗位要求的身体条件" holds "岗位要求"
    yet is a requirement, so a substring match alone would wrongly drop it.
    """
    if len(clause) > 8:
        return False
    if any(head in clause for head in REQUIREMENT_HEADINGS):
        return True
    if any(head in clause for head in _NON_REQUIREMENT_HEADINGS):
        return True
    return clause.endswith(("条件", "要求", "对象", "范围", "说明"))


@dataclass
class SegmentedRequirements:
    """Result of segmenting a job announcement."""

    requirements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.requirements)


#: A leading label like "岗位要求：" or "任职资格:" is not part of the
#: requirement itself and only dilutes the match; stripped from each clause.
_LEADING_LABEL = re.compile(
    r"^(?:岗位|任职|招聘|应聘|报考|基本|资格)?(?:要求|条件|资格|说明)\s*[：:]\s*"
)


def _split_clauses(text: str) -> list[str]:
    """Split whitespace-collapsed announcement text into candidate clauses.

    Splits on sentence terminators and on enumeration markers so a run of
    "1、… 2、… 3、…" that lost its line breaks becomes three clauses.
    """
    # Break before an enumeration marker that follows a space or terminator, so
    # "能力 2、具备" splits but a mid-word digit does not.
    marked = re.sub(r"(?<=[%s\s])(%s)" % (re.escape(_TERMINATORS), _ENUM_MARKER.pattern), r"\n\1", text)
    pieces = re.split(r"[%s]" % re.escape(_TERMINATORS), marked)
    clauses: list[str] = []
    for piece in pieces:
        piece = _ENUM_MARKER.sub("", piece, count=1) if _ENUM_MARKER.match(piece.strip()) else piece
        piece = _LEADING_LABEL.sub("", piece.strip())
        cleaned = piece.strip().strip("：:，,、.．)）(（ ")
        if cleaned:
            clauses.append(cleaned)
    return clauses


def _looks_procedural(clause: str) -> bool:
    return any(term in clause for term in _PROCEDURE_TERMS)


def _looks_like_employer_blurb(clause: str) -> bool:
    return any(term in clause for term in _EMPLOYER_TERMS)


def _has_requirement_cue(clause: str) -> bool:
    return any(cue in clause for cue in _REQUIREMENT_CUES)


def is_eligibility_clause(clause: str) -> bool:
    """True when a clause states application eligibility, not a resume-matchable
    requirement.

    Deliberately conservative: degree-bearing clauses are never eligibility (the
    degree gate evaluates them), so "硕士及以上学历，年龄不超过35周岁" still
    reaches the matcher while "具有中华人民共和国国籍" does not reach the gap list.
    """
    if any(marker in clause for marker in _DEGREE_MARKERS):
        return False
    return any(marker in clause for marker in _ELIGIBILITY_MARKERS)


def _requirement_block(text: str) -> tuple[str, bool]:
    """Return (text-of-requirement-block, found).

    Locates the first requirement heading and returns everything up to the next
    top-level non-requirement heading.  Falls back to the whole text when no
    heading is present (some announcements have none).
    """
    heading_pattern = "|".join(re.escape(h) for h in REQUIREMENT_HEADINGS)
    start = re.search(r"[一二三四五六七八九十]+\s*[、.]?\s*(?:%s)" % heading_pattern, text)
    if start is None:
        return text, False

    tail = text[start.end():]
    # End at the next top-level "N、<non-requirement heading>".
    stop_pattern = re.compile(
        r"[一二三四五六七八九十]+\s*[、.]\s*(?:%s)"
        % "|".join(re.escape(h) for h in _NON_REQUIREMENT_HEADINGS)
    )
    stop = stop_pattern.search(tail)
    block = tail[: stop.start()] if stop else tail
    return block, True


def segment_requirements(text: str) -> SegmentedRequirements:
    """Extract requirement clauses from a raw job announcement.

    When the text carries no requirement heading and no clause shows a cue —
    typically because the real requirements live in an attachment — an empty
    result is returned with a warning rather than a fabricated ``岗位提到：X``.
    """
    normalized = normalize_text(text)
    if not normalized:
        return SegmentedRequirements(warnings=["岗位正文为空"])

    block, found_block = _requirement_block(normalized)
    clauses = _split_clauses(block)

    requirements: list[str] = []
    seen: set[str] = set()
    for clause in clauses:
        # A stop sub-heading marks the end of requirement content within the
        # block (e.g. a nested "招聘方式及待遇" section); everything after is
        # procedure or terms of employment.
        if len(clause) <= 12 and any(term in clause for term in _STOP_SUBHEADINGS):
            break
        if not (_MIN_LEN <= len(clause) <= _MAX_LEN):
            continue
        if _is_heading_clause(clause):
            continue
        if _looks_procedural(clause) or _looks_like_employer_blurb(clause):
            continue
        # Inside an explicit requirement block, keep clauses even without a cue
        # word (many real ones read "无违法违纪记录"); outside a block, demand a
        # cue so we do not scoop up narrative text.
        if not found_block and not _has_requirement_cue(clause):
            continue
        if clause in seen:
            continue
        seen.add(clause)
        requirements.append(clause)
        if len(requirements) >= _MAX_REQUIREMENTS:
            break

    warnings: list[str] = []
    if not requirements:
        warnings.append("未能从正文中提取到明确的岗位要求，具体要求可能在附件中")
    return SegmentedRequirements(requirements=requirements, warnings=warnings)
