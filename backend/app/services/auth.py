"""用户认证：密码哈希 + 签名 token。

零外部依赖，全部基于标准库：
- 密码：scrypt + 随机盐，verify 用 hmac.compare_digest 防时序攻击。
- 会话：自签名 token，格式 base64url(payload).hmac_sig，payload 含 uid/name/exp。
- 密钥（D2）：优先环境变量 AUTH_SECRET；未设置时自动生成并持久化到
  data/.auth_secret，进程重启不掉线。0600 权限，禁止入库。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import stat
import sys
import time
from pathlib import Path


logger = logging.getLogger(__name__)


def _load_or_create_secret() -> tuple[str, bool]:
    """返回 (secret, is_persistent)。环境变量优先；否则落盘复用。"""
    env_secret = os.getenv("AUTH_SECRET")
    if env_secret:
        return env_secret, False

    data_dir = Path(os.getenv("DATA_DIR", "data"))
    secret_path = data_dir / ".auth_secret"
    try:
        if secret_path.exists():
            stored = secret_path.read_text(encoding="utf-8").strip()
            if stored:
                return stored, True
        secret = secrets.token_hex(32)
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret_path.write_text(secret + "\n", encoding="utf-8")
        if sys.platform != "win32":
            os.chmod(secret_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        return secret, True
    except OSError:
        # 文件系统只读等场景退回临时密钥（与旧行为一致），但显式告警
        logger.warning(
            "AUTH_SECRET 无法持久化（%s），回退为进程内临时密钥，重启将掉线", secret_path
        )
        return secrets.token_hex(32), False


SECRET, _SECRET_PERSISTED = _load_or_create_secret()

if not os.getenv("AUTH_SECRET"):
    if _SECRET_PERSISTED:
        logger.info("AUTH_SECRET 未设置，已生成并持久化到 data/.auth_secret（重启不掉线）")
    else:
        logger.warning("AUTH_SECRET 未设置且无法持久化，重启后所有 token 将失效")

TOKEN_TTL_SECONDS = 7 * 24 * 3600
_SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password: str) -> tuple[str, str]:
    """返回 (hash_hex, salt_hex)。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT_PARAMS)
    return digest.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT_PARAMS)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), password_hash)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(payload_b64: str) -> str:
    signature = hmac.new(SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256)
    return _b64encode(signature.digest())


def make_token(user_id: int, username: str, ttl: int = TOKEN_TTL_SECONDS) -> str:
    payload = {"uid": user_id, "name": username, "exp": int(time.time()) + ttl}
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str | None) -> dict | None:
    """校验签名与过期时间，有效则返回 payload，否则 None。"""
    if not token or "." not in token:
        return None
    payload_b64, _, signature = token.partition(".")
    if not hmac.compare_digest(signature, _sign(payload_b64)):
        return None
    try:
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or "uid" not in payload or "exp" not in payload:
        return None
    if int(payload["exp"]) < int(time.time()):
        return None
    return payload
