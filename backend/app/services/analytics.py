from __future__ import annotations

from collections import Counter, defaultdict
from html import escape
from typing import Any

from app.services.database import DatabaseEngine
from app.services.repositories import list_jobs, save_report


def _counter_payload(counter: Counter) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common()]


def analytics_summary(engine: DatabaseEngine, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    jobs = list_jobs(engine, filters or {})["items"]
    category = Counter(job["job_category"] for job in jobs)
    education = Counter(job["education"] or "未注明" for job in jobs)
    institution_types = Counter(job["institution_type"] for job in jobs)
    regions = Counter(job["region"] for job in jobs)
    tags = Counter(tag for job in jobs for tag in job["tags"] if tag not in {job["region"], job["institution_type"], job["job_category"]})
    focus: dict[str, Counter] = defaultdict(Counter)
    for job in jobs:
        focus[job["institution_name"]][job["job_category"]] += 1
    return {
        "totals": {
            "jobs": len(jobs),
            "institutions": len({job["institution_id"] for job in jobs}),
            "regions": len({job["region"] for job in jobs}),
        },
        "job_categories": _counter_payload(category),
        "education_levels": _counter_payload(education),
        "institution_types": _counter_payload(institution_types),
        "regions": _counter_payload(regions),
        "common_capabilities": _counter_payload(tags)[:20],
        "institution_focus": [
            {"institution": institution, "focus": _counter_payload(counter)[:5]}
            for institution, counter in sorted(focus.items())
        ],
    }


def generate_report(engine: DatabaseEngine, title: str, filters: dict[str, Any]) -> dict[str, Any]:
    summary = analytics_summary(engine, filters)
    lines = [
        f"# {title}",
        "",
        "## 样本范围",
        f"- 岗位样本：{summary['totals']['jobs']} 条",
        f"- 机构数量：{summary['totals']['institutions']} 家",
        f"- 覆盖地区：{summary['totals']['regions']} 个",
        "",
        "## 热门岗位方向",
    ]
    lines.extend(f"- {item['name']}：{item['count']} 条" for item in summary["job_categories"][:8])
    lines.extend(["", "## 共性基础能力"])
    lines.extend(f"- {item['name']}：出现 {item['count']} 次" for item in summary["common_capabilities"][:10])
    lines.extend(["", "## 学历要求"])
    lines.extend(f"- {item['name']}：{item['count']} 条" for item in summary["education_levels"][:8])
    lines.extend(["", "## 机构发力方向"])
    for item in summary["institution_focus"][:10]:
        focus_text = "、".join(f"{focus['name']} {focus['count']}" for focus in item["focus"])
        lines.append(f"- {item['institution']}：{focus_text}")
    lines.extend(
        [
            "",
            "## 数据来源",
            "本报告仅基于当前系统已抓取的公开官网招聘样本生成，保留每条岗位的来源链接、抓取时间和解析器信息，不代表全国完整就业市场。",
        ]
    )
    markdown = "\n".join(lines)
    html = "<!doctype html><html><head><meta charset='utf-8'><title>{}</title></head><body>{}</body></html>".format(
        escape(title),
        "".join(f"<p>{escape(line)}</p>" if line else "" for line in lines),
    )
    return save_report(engine, title, markdown, html, filters)
