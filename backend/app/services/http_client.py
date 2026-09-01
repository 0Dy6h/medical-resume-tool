"""出站 HTTP 客户端统一构建（D3 爬虫安全 + A2 适配器可用化）。

所有真实抓取共用一套客户端配置：
  - TLS 证书校验开启（verify=True），不再放行自签名/不匹配证书；
  - 出站 URL 安全校验：仅 http/https、禁止私网/环回/链路本地/云元数据地址
    （含域名解析后的实际 IP，覆盖重定向目标）；
  - 响应大小上限（Content-Length 预检 + 已下载字节兜底）。

校验通过 httpx event_hooks 挂在客户端上：仅在真实网络请求（含重定向）
时触发，测试中 monkeypatch AsyncClient.get 不会经过钩子，因此不受影响。
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 单次响应上限 10MB
_DNS_CACHE: dict[str, list[str]] = {}
_DNS_CACHE_LIMIT = 256


class OutboundBlockedError(httpx.HTTPError):
    """出站请求被安全策略拦截（非 http/https、私网/保留地址、域名解析失败）。

    继承 httpx.HTTPError 而非 TransportError：策略性拦截不应触发网络重试。
    """


def assert_public_url(raw_url: str) -> None:
    """校验出站 URL：仅 http/https 且目标必须是公网地址。"""
    parsed = urlsplit(raw_url)
    if parsed.scheme not in ("http", "https"):
        raise OutboundBlockedError(f"仅允许 http/https 出站请求：{raw_url}")
    host = parsed.hostname
    if not host:
        raise OutboundBlockedError(f"出站 URL 缺少主机名：{raw_url}")
    _assert_public_host(host)


def _assert_public_host(host: str) -> None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        _assert_public_ip(ip, host)
        return
    resolved = _resolve_host(host)
    if not resolved:
        raise OutboundBlockedError(f"域名解析失败，拒绝出站：{host}")
    for ip_text in resolved:
        try:
            ip_obj = ipaddress.ip_address(ip_text)
        except ValueError:
            continue
        _assert_public_ip(ip_obj, host)


def _assert_public_ip(ip: Any, host: str) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise OutboundBlockedError(
            f"禁止访问内网/保留/云元数据地址：{host}（解析为 {ip}）"
        )


def _resolve_host(host: str) -> list[str]:
    cached = _DNS_CACHE.get(host)
    if cached is not None:
        return cached
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return []
    ips = sorted({info[4][0] for info in infos if info[4]})
    if len(_DNS_CACHE) >= _DNS_CACHE_LIMIT:
        _DNS_CACHE.clear()
    _DNS_CACHE[host] = ips
    return ips


async def guard_request(request: httpx.Request) -> None:
    """请求级安全钩子：出站前校验目标（重定向的每一跳都会经过）。"""
    assert_public_url(str(request.url))


async def guard_response(response: httpx.Response) -> None:
    """响应级安全钩子：Content-Length 预检 + 已下载字节兜底。"""
    length_header = response.headers.get("content-length")
    if length_header:
        try:
            length = int(length_header)
        except ValueError:
            return
        if length > MAX_RESPONSE_BYTES:
            raise OutboundBlockedError(
                f"响应过大（Content-Length={length} > {MAX_RESPONSE_BYTES}）"
            )
    body = getattr(response, "content", b"")
    if body and len(body) > MAX_RESPONSE_BYTES:
        raise OutboundBlockedError(
            f"响应过大（{len(body)} 字节 > {MAX_RESPONSE_BYTES}）"
        )


def build_crawl_client() -> httpx.AsyncClient:
    """构建所有真实抓取共用的 httpx 客户端。"""
    from app.config import config

    return httpx.AsyncClient(
        timeout=config.crawl_timeout,
        follow_redirects=True,
        headers={"User-Agent": "MedicalJobMVP/0.1"},
        verify=True,
        event_hooks={"request": [guard_request], "response": [guard_response]},
    )
