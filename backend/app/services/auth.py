"""用户认证：密码哈希 + 签名 token。

零外部依赖，全部基于标准库：
- 密码：scrypt + 随机盐，verify 用 hmac.compare_digest 防时序攻击。
- 会话：自签名 token，格式 base64url(payload).hmac_sig，payload 含 uid/name/exp。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time


# 签名密钥：部署时务必通过环境变量 AUTH_SECRET 固定，否则进程重启后已签发的 token 全部失效。
SECRET = os.getenv("AUTH_SECRET") or secrets.token_hex(32)

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
