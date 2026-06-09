from __future__ import annotations

import re
from collections import Counter


TAG_KEYWORDS = {
    "临床": ["临床", "医师", "住院医师", "主治", "诊疗", "病房", "门诊", "手术"],
    "护理": ["护理", "护士", "护师", "静脉", "病区", "急诊护理"],
    "医技": ["检验", "影像", "放射", "超声", "病理", "技师", "医学技术"],
    "药学": ["药学", "药师", "药物", "临床药师", "制剂"],
    "科研": ["科研", "博士后", "课题", "基金", "论文", "实验", "队列", "数据分析"],
    "教学": ["教学", "课程", "带教", "讲师", "教师", "教研"],
    "公卫": ["公共卫生", "流行病", "疾控", "卫生统计", "预防医学", "健康管理"],
    "行政运营": ["行政", "运营", "人事", "财务", "信息", "管理", "办公室"],
    "数据": ["数据", "统计", "Python", "R语言", "SPSS", "SAS", "数据库", "机器学习"],
    "英语": ["英语", "CET", "SCI", "英文"],
    "伦理合规": ["伦理", "GCP", "合规", "质控", "注册"],
}

EDUCATION_ORDER = ["博士", "硕士", "本科", "大专"]
SOFT_SKILLS = ["沟通", "协作", "责任心", "学习能力", "执行力", "服务意识"]


def normalize_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def infer_job_category(title: str, body: str) -> str:
    haystack = f"{title} {body}"
    scores = Counter()
    for category in ["临床", "护理", "医技", "药学", "科研", "教学", "公卫", "行政运营"]:
        for word in TAG_KEYWORDS[category]:
            if word.lower() in haystack.lower():
                scores[category] += 1
    if not scores:
        return "其他医疗相关"
    return scores.most_common(1)[0][0]


def infer_education(text: str) -> str:
    for level in EDUCATION_ORDER:
        if level in text:
            return level
    return "不限/未注明"


def infer_profession(text: str) -> str:
    candidates = [
        "临床医学",
        "护理学",
        "医学检验",
        "医学影像",
        "药学",
        "公共卫生",
        "流行病与卫生统计",
        "基础医学",
        "生物医学工程",
        "卫生管理",
    ]
    found = [item for item in candidates if item in text]
    return "、".join(found) if found else "医学相关"


def extract_tags(title: str, body: str, institution_type: str, region: str) -> list[str]:
    haystack = f"{title} {body}"
    tags: set[str] = {institution_type, region, infer_job_category(title, body), infer_education(haystack)}
    for tag, keywords in TAG_KEYWORDS.items():
        if any(word.lower() in haystack.lower() for word in keywords):
            tags.add(tag)
    for skill in SOFT_SKILLS:
        if skill in haystack:
            tags.add(skill)
    if "执业" in haystack or "资格证" in haystack or "护士资格" in haystack:
        tags.add("证书资质")
    if "博士后" in haystack or "高级职称" in haystack:
        tags.add("高层次人才")
    if "应届" in haystack:
        tags.add("应届")
    return sorted(tags)


def extract_requirements(text: str) -> list[str]:
    normalized = normalize_text(text)
    parts = re.split(r"[；;。]\s*|\n+", normalized)
    requirements = []
    for part in parts:
        if any(word in part for word in ["要求", "具备", "熟悉", "优先", "学历", "专业", "资格", "能力"]):
            cleaned = part.strip(" ：:，,")
            if 4 <= len(cleaned) <= 120:
                requirements.append(cleaned)
    if not requirements:
        for keyword in ["临床研究", "数据分析", "护理", "科研", "教学", "沟通", "英语", "SPSS", "Python"]:
            if keyword in normalized:
                requirements.append(f"岗位提到：{keyword}")
    return list(dict.fromkeys(requirements))[:10]


def confidence_for(text: str, title: str) -> float:
    score = 0.55
    if title:
        score += 0.1
    if len(text) > 80:
        score += 0.1
    if any(level in text for level in EDUCATION_ORDER):
        score += 0.1
    if extract_requirements(text):
        score += 0.1
    return min(score, 0.95)
