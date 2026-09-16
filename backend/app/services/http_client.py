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
import zlib
from typing import Any
from urllib.parse import urlsplit

import anyio
import httpcore
import httpx

MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 单次响应上限 10MB


class OutboundBlockedError(httpx.HTTPError):
    """出站请求被安全策略拦截（非 http/https、私网/保留地址、域名解析失败）。

    继承 httpx.HTTPError 而非 TransportError：策略性拦截不应触发网络重试。
    """


def assert_public_url(raw_url: str) -> None:
    """校验出站 URL：仅 http/https 且目标必须是公网地址。"""
    try:
        parsed = urlsplit(raw_url)
        host = parsed.hostname
        parsed.port  # Validate malformed/out-of-range ports before any connection.
    except ValueError as exc:
        raise OutboundBlockedError("无效的出站 URL") from exc
    if parsed.scheme not in ("http", "https"):
        raise OutboundBlockedError(f"仅允许 http/https 出站请求：{raw_url}")
    if not host:
        raise OutboundBlockedError(f"出站 URL 缺少主机名：{raw_url}")
    if parsed.username is not None or parsed.password is not None:
        raise OutboundBlockedError("出站 URL 不允许包含登录凭据")
    _assert_public_host(host)


def _assert_public_host(host: str) -> list[str]:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        _assert_public_ip(ip, host)
        return [str(ip)]
    resolved = _resolve_host(host)
    if not resolved:
        raise OutboundBlockedError(f"域名解析失败，拒绝出站：{host}")
    for ip_text in resolved:
        try:
            ip_obj = ipaddress.ip_address(ip_text)
        except ValueError as exc:
            raise OutboundBlockedError(f"域名解析返回无效地址：{host}") from exc
        _assert_public_ip(ip_obj, host)
    return resolved


def _assert_public_ip(ip: Any, host: str) -> None:
    if (
        not ip.is_global
        or ip.is_private
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
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return []
    ips = sorted({info[4][0] for info in infos if info[4]})
    return ips


class PublicNetworkBackend(httpcore.AnyIOBackend):
    """Validate each new connection's DNS result and connect to that literal IP.

    httpcore keeps the original hostname for Host and TLS/SNI. Passing only a
    validated IP to the socket backend prevents a second DNS lookup from
    rebinding a previously-public hostname to a private destination.
    """

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = await anyio.to_thread.run_sync(_assert_public_host, host)
        last_error = None
        for address in addresses:
            try:
                return await super().connect_tcp(
                    address, port, timeout=timeout, local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise OutboundBlockedError(f"域名解析失败，拒绝出站：{host}")


class PublicHTTPTransport(httpx.AsyncHTTPTransport):
    def __init__(self):
        # AsyncHTTPTransport's pool owns exception mapping and stream lifetime;
        # the custom httpcore backend changes only how a socket is connected.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpcore.default_ssl_context(),
            network_backend=PublicNetworkBackend(),
            max_connections=10,
            max_keepalive_connections=5,
        )


async def guard_request(request: httpx.Request) -> None:
    """请求级安全钩子：出站前校验目标（重定向的每一跳都会经过）。"""
    await anyio.to_thread.run_sync(assert_public_url, str(request.url))


async def guard_response(response: httpx.Response) -> None:
    """Bound both wire bytes and decoded bytes before httpx buffers the body."""
    length_header = response.headers.get("content-length")
    if length_header:
        try:
            length = int(length_header)
        except ValueError:
            length = None
        if length is not None and (length < 0 or length > MAX_RESPONSE_BYTES):
            await response.aclose()
            raise OutboundBlockedError(
                f"响应过大（Content-Length={length} > {MAX_RESPONSE_BYTES}）"
            )
    try:
        body = response.content
    except httpx.ResponseNotRead:
        body = None
    if body is not None:
        if len(body) > MAX_RESPONSE_BYTES:
            await response.aclose()
            raise OutboundBlockedError(f"响应过大（{len(body)} 字节 > {MAX_RESPONSE_BYTES}）")
        return

    encoding = response.headers.get("content-encoding", "identity").strip().lower()
    # Request identity, but safely handle common servers which still compress.
    # zlib's max_length prevents one tiny compressed chunk allocating gigabytes.
    if encoding not in ("", "identity", "gzip", "deflate"):
        await response.aclose()
        raise OutboundBlockedError(f"不支持安全解析的响应压缩格式：{encoding}")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
    decoded = bytearray()
    received = 0
    try:
        async for chunk in response.aiter_raw():
            received += len(chunk)
            if received > MAX_RESPONSE_BYTES:
                raise OutboundBlockedError("响应过大（下载字节超限）")
            if encoding == "deflate" and decoder is None and chunk:
                decoder = zlib.decompressobj()
                try:
                    part = decoder.decompress(chunk, MAX_RESPONSE_BYTES - len(decoded) + 1)
                except zlib.error:
                    decoder = zlib.decompressobj(-zlib.MAX_WBITS)
                    part = decoder.decompress(chunk, MAX_RESPONSE_BYTES - len(decoded) + 1)
            else:
                part = decoder.decompress(chunk, MAX_RESPONSE_BYTES - len(decoded) + 1) if decoder else chunk
            if len(decoded) + len(part) > MAX_RESPONSE_BYTES or (decoder and decoder.unconsumed_tail):
                raise OutboundBlockedError("响应过大（解压后字节超限）")
            decoded.extend(part)
        if decoder and (not decoder.eof or decoder.unused_data):
            raise OutboundBlockedError("响应压缩数据不完整或包含额外内容")
    except zlib.error as exc:
        raise OutboundBlockedError("响应压缩数据损坏") from exc
    finally:
        await response.aclose()
    # Response hooks are executed before AsyncClient.aread(); cache the bounded
    # body just as Response.aread() does, without decoding it a second time.
    response._content = bytes(decoded)
    if encoding not in ("", "identity"):
        response.headers.pop("content-encoding", None)
        response.headers["content-length"] = str(len(decoded))


def build_crawl_client() -> httpx.AsyncClient:
    """构建所有真实抓取共用的 httpx 客户端。"""
    from app.config import config

    return httpx.AsyncClient(
        timeout=config.crawl_timeout,
        follow_redirects=True,
        headers={"User-Agent": "MedicalJobMVP/0.1", "Accept-Encoding": "identity"},
        verify=True,
        trust_env=False,
        transport=PublicHTTPTransport(),
        event_hooks={"request": [guard_request], "response": [guard_response]},
    )
