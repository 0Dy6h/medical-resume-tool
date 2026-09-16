import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# app.main 在 import 时会创建默认 app；测试收集也必须隔离默认数据库与密钥。
# 由系统临时目录承载 SQLite，避免 Windows 通过 WSL/网络路径操作数据库锁。
_runtime = TemporaryDirectory(prefix="resume-tests-", ignore_cleanup_errors=True)
os.environ["DATA_DIR"] = _runtime.name
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_runtime.name) / 'default.db'}"
os.environ["SUBSCRIPTION_SCAN_ENABLED"] = "false"
os.environ["AUTO_CRAWL_ENABLED"] = "false"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
