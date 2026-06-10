#!/usr/bin/env python
"""语法检查脚本 - 验证整改后的文件没有语法错误。"""

import sys
import py_compile
from pathlib import Path

BACKEND_ROOT = Path(__file__).parent / "backend"

# 已修改的文件
MODIFIED_FILES = [
    "app/config.py",
    "app/main.py",
    "app/schemas.py",
    "app/services/adapters/adapter_base.py",
    "app/services/adapters/chinacdc.py",
    "app/services/adapters/bjmu.py",
    "app/services/adapters/hrbmu.py",
    "app/services/adapters/njmu.py",
    "app/services/analytics.py",
    "app/services/crawler.py",
    "app/services/repositories.py",
    "tests/test_attachments.py",
]

def check_syntax():
    """检查所有修改文件的语法。"""
    errors = []
    for file_path in MODIFIED_FILES:
        full_path = BACKEND_ROOT / file_path
        if not full_path.exists():
            errors.append(f"❌ 文件不存在: {file_path}")
            continue

        try:
            py_compile.compile(str(full_path), doraise=True)
            print(f"✅ {file_path}")
        except py_compile.PyCompileError as exc:
            errors.append(f"❌ {file_path}: {exc}")

    if errors:
        print("\n语法错误：")
        for error in errors:
            print(error)
        return 1

    print(f"\n✅ 所有 {len(MODIFIED_FILES)} 个文件语法正确")
    return 0

if __name__ == "__main__":
    sys.exit(check_syntax())
