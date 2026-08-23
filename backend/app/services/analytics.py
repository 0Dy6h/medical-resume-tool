from __future__ import annotations

from collections import Counter, defaultdict
from html import escape
from typing import Any

from app.config import config
from app.services.database import DatabaseEngine, connect, from_json
from app.services.repositories import build_jobs_where_clause, now_iso, save_report


LOW_CONFIDENCE_THRESHOLD = config.low_confidence_threshold


def _counter_payload(counter: Counter) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common()]


def _group_count(conn: Any, column: str, where: str, params: list[Any]) -> Counter:
    """Run GROUP BY column → Counter, treating NULL/empty as the given fallback caller decides."""
    rows = conn.execute(
        f"SELECT {column} AS name, COUNT(*) AS count FROM jobs {where} GROUP BY {column}",
        params,
    ).fetchall()
    return Counter({row["name"]: row["count"] for row in rows})


def analytics_summary(engine: DatabaseEngine, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    where, params = build_jobs_where_clause(filters or {})
    with connect(engine) as conn:
        total_jobs = conn.execute(f"SELECT COUNT(*) AS count FROM jobs {where}", params).fetchone()["count"]
        category = _group_count(conn, "job_category", where, params)
        education_raw = _group_count(conn, "education", where, params)
        institution_types = _group_count(conn, "institution_type", where, params)
        regions = _group_count(conn, "region", where, params)
        totals_row = conn.execute(
            f"""
            SELECT COUNT(DISTINCT institution_id) AS institutions,
                   COUNT(DISTINCT region) AS regions
            FROM jobs {where}
            """,
            params,
        ).fetchone()
        focus_rows = conn.execute(
            f"""
            SELECT institution_name, job_category, COUNT(*) AS count
            FROM jobs {where}
            GROUP BY institution_name, job_category
            """,
            params,
        ).fetchall()
        # Pull only the small JSON/scalar columns we still need to aggregate in Python.
        tag_evidence_rows = conn.execute(
            f"""
            SELECT region, institution_type, job_category, parser_name, confidence,
                   tags, extraction_evidence
            FROM jobs {where}
            """,
            params,
        ).fetchall()

    education = Counter({(name or "未注明"): count for name, count in education_raw.items()})

    focus: dict[str, Counter] = defaultdict(Counter)
    for row in focus_rows:
        focus[row["institution_name"]][row["job_category"]] = row["count"]

    tags: Counter = Counter()
    parser_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "jobs": 0,
            "low_confidence_jobs": 0,
            "attachment_sourced_jobs": 0,
            "failed_attachment_events": 0,
            "confidence_sum": 0.0,
        }
    )
    for row in tag_evidence_rows:
        exclude = {row["region"], row["institution_type"], row["job_category"]}
        for tag in from_json(row["tags"], []):
            if tag not in exclude:
                tags[tag] += 1
        parser_name = row["parser_name"] or "unknown"
        stats = parser_stats[parser_name]
        confidence = float(row["confidence"] or 0)
        evidence = from_json(row["extraction_evidence"], {}) or {}
        stats["jobs"] += 1
        stats["confidence_sum"] += confidence
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            stats["low_confidence_jobs"] += 1
        if evidence.get("attachment_url"):
            stats["attachment_sourced_jobs"] += 1
        attachments = evidence.get("attachments")
        if isinstance(attachments, list):
            stats["failed_attachment_events"] += sum(
                1 for item in attachments if isinstance(item, dict) and item.get("status") == "failed"
            )

    parser_quality = _parser_quality_payload(parser_stats)
    return {
        "generated_at": now_iso(),
        "totals": {
            "jobs": total_jobs,
            "institutions": totals_row["institutions"] if totals_row else 0,
            "regions": totals_row["regions"] if totals_row else 0,
            "parsers": len(parser_stats),
            "low_confidence_jobs": sum(item["low_confidence_jobs"] for item in parser_stats.values()),
            "attachment_sourced_jobs": sum(item["attachment_sourced_jobs"] for item in parser_stats.values()),
            "failed_attachment_events": sum(item["failed_attachment_events"] for item in parser_stats.values()),
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
        "parser_quality": parser_quality,
    }


def _parser_quality_payload(parser_stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    severity = {"review": 0, "watch": 1, "stable": 2}
    for parser_name, stats in parser_stats.items():
        jobs = stats["jobs"]
        average_confidence = round(stats["confidence_sum"] / jobs, 2) if jobs else 0.0
        low_confidence_ratio = (stats["low_confidence_jobs"] / jobs) if jobs else 0.0
        review_status = _review_status(stats, average_confidence, low_confidence_ratio)
        payload.append(
            {
                "parser_name": parser_name,
                "jobs": jobs,
                "low_confidence_jobs": stats["low_confidence_jobs"],
                "attachment_sourced_jobs": stats["attachment_sourced_jobs"],
                "failed_attachment_events": stats["failed_attachment_events"],
                "average_confidence": average_confidence,
                "review_status": review_status,
            }
        )
    return sorted(
        payload,
        key=lambda item: (
            severity[item["review_status"]],
            -item["failed_attachment_events"],
            -item["low_confidence_jobs"],
            -item["jobs"],
            item["parser_name"],
        ),
    )


def _review_status(stats: dict[str, Any], average_confidence: float, low_confidence_ratio: float) -> str:
    # PRD 4.6: review = attachment parse failures in the snapshot.
    # (The PRD's "3 consecutive days of failures / sustained decline" needs a
    #  daily health-snapshot table — out of scope; single-snapshot failure
    #  count is the MVP proxy. See exclusions.)
    if stats["failed_attachment_events"] > 0:
        return "review"
    # watch = avg confidence < 0.7 OR low-confidence share > 20%.
    if average_confidence < 0.7 or low_confidence_ratio > 0.2:
        return "watch"
    return "stable"


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
    html = _render_html(title, lines)
    return save_report(engine, title, markdown, html, filters)


def _render_html(title: str, lines: list[str]) -> str:
    """Convert the markdown-shaped lines into semantic HTML (h1/h2/ul/li/p)."""
    parts: list[str] = []
    list_open = False

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            parts.append("</ul>")
            list_open = False

    for line in lines:
        if not line:
            close_list()
            continue
        if line.startswith("# "):
            close_list()
            parts.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            close_list()
            parts.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not list_open:
                parts.append("<ul>")
                list_open = True
            parts.append(f"<li>{escape(line[2:])}</li>")
        else:
            close_list()
            parts.append(f"<p>{escape(line)}</p>")
    close_list()
    body = "".join(parts)
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>"
        f"{escape(title)}</title></head><body>{body}</body></html>"
    )
