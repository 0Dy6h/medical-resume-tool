#!/usr/bin/env python
"""清理 8000 库里累积的测试账号（带依赖行，FK 安全顺序删除）。

背景：试用整改循环的探针脚本（logs/trial_*、repro_* 等）在 backend/data/app.db
注册了大量测试账号；应用无删除端点，直接删库行有 FK 风险，故提供本工具。

用法（在 backend/ 目录）：

    uv run python scripts/cleanup_test_accounts.py             # dry-run（默认），只列出将删账号与依赖行数
    uv run python scripts/cleanup_test_accounts.py --apply     # 真删（先自动备份整个 db 文件）
    uv run python scripts/cleanup_test_accounts.py --also 123,has space,试用-账号   # 追加不匹配默认模式的账号
    uv run python scripts/cleanup_test_accounts.py --db data/other.db              # 指定库路径

默认只匹配测试账号命名模式：trial_* / verify* / smoke_* / pm_review_*。
不匹配且未用 --also 显式点名的账号一律不碰（真实用户如 1203525437@qq.com 天然受保护）。
"""
from __future__ import annotations

import argparse
import fnmatch
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.database import connect, create_engine  # noqa: E402

DEFAULT_PATTERNS = ["trial_*", "verify*", "smoke_*", "pm_review_*"]

# 依赖 users(id) 的表按安全顺序排列：先删子表再删 users。
# notifications 虽有 ON DELETE CASCADE，仍显式先删，避免对 CASCADE 行为的隐式依赖。
CHILD_TABLES = ["notifications", "subscriptions", "resume_drafts", "job_statuses", "profiles"]


def match_users(conn: sqlite3.Connection, patterns: list[str], extra: list[str]) -> list[dict]:
    """返回将删除的账号（含依赖行数）。模式匹配 + 显式点名，二者并集。"""
    rows = conn.execute("SELECT id, username, created_at FROM users ORDER BY id").fetchall()
    targets = []
    for row in rows:
        username = row["username"]
        if any(fnmatch.fnmatch(username, pat) for pat in patterns) or username in extra:
            targets.append(
                {
                    "id": row["id"],
                    "username": username,
                    "created_at": row["created_at"],
                    "deps": dependent_counts(conn, row["id"]),
                }
            )
    return targets


def dependent_counts(conn: sqlite3.Connection, user_id: int) -> dict[str, int]:
    counts = {}
    for table in CHILD_TABLES:
        counts[table] = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    return counts


def purge(conn: sqlite3.Connection, targets: list[dict]) -> int:
    """FK 安全顺序删除，返回删除的账号数。

    用 SAVEPOINT 做每账号原子性（不能用 `with conn:`——ClosingConnection 的
    __exit__ 会顺带 close 连接，第二个账号就会 "Cannot operate on a closed database"）。
    """
    deleted = 0
    for target in targets:
        uid = target["id"]
        conn.execute("SAVEPOINT cleanup_account")
        try:
            for table in CHILD_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        except Exception:
            conn.execute("ROLLBACK TO cleanup_account")
            conn.execute("RELEASE cleanup_account")
            raise
        conn.execute("RELEASE cleanup_account")
        deleted += 1
    conn.commit()
    return deleted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="清理测试账号（默认 dry-run）")
    parser.add_argument("--apply", action="store_true", help="真删（默认 dry-run 只列清单）")
    parser.add_argument("--db", default=str(Path(__file__).resolve().parents[1] / "data" / "app.db"), help="sqlite 库路径（默认 backend/data/app.db）")
    parser.add_argument("--also", default="", help="额外显式删除的用户名，逗号分隔（不匹配默认模式的垃圾账号用它点名）")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"[abort] 库文件不存在：{db_path}")
        return 2

    extra = [name.strip() for name in args.also.split(",") if name.strip()]
    engine = create_engine(f"sqlite:///{db_path}")
    conn = connect(engine)
    try:
        targets = match_users(conn, DEFAULT_PATTERNS, extra)
        total_deps = sum(sum(t["deps"].values()) for t in targets)
        print(f"库：{db_path}")
        print(f"匹配 {len(targets)} 个账号、{total_deps} 行依赖数据（模式：{', '.join(DEFAULT_PATTERNS)}"
              + (f"；另显式点名 {len(extra)} 个" if extra else "") + "）")
        for target in targets:
            deps = "、".join(f"{k} {v}" for k, v in target["deps"].items() if v)
            print(f"  #{target['id']:<4} {target['username']:<20} 创建于 {target['created_at']}"
                  + (f"  [{deps}]" if deps else ""))
        if not targets:
            print("没有可清理的账号。")
            return 0
        if not args.apply:
            print("\n[dry-run] 未做任何改动。确认无误后加 --apply 执行（会先自动备份整个库文件）。")
            return 0

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = db_path.with_name(f"{db_path.stem}-before-cleanup-{stamp}{db_path.suffix}")
        shutil.copy2(db_path, backup)
        print(f"\n已备份整库 → {backup}")

        deleted = purge(conn, targets)
        print(f"[apply] 已删除 {deleted} 个账号及其依赖行。")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
