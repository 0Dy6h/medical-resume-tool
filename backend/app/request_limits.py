"""在表单/JSON 解析之前限制实际请求体，含无 Content-Length 的分块传输。"""
from starlette.datastructures import Headers
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _BodyTooLarge(MultiPartException):
    """使 multipart 解析器在超限时关闭已经创建的临时上传文件。"""


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        def rejection() -> JSONResponse:
            return JSONResponse(status_code=413, content={"detail": "请求内容过大，请缩小文件或内容后重试"})

        length = Headers(scope=scope).get("content-length")
        if length is not None:
            try:
                declared = int(length)
                if declared < 0:
                    raise ValueError
            except ValueError:
                await JSONResponse(status_code=422, content={"detail": "无效的 Content-Length"})(scope, receive, send)
                return
            if declared > self.max_bytes:
                await rejection()(scope, receive, send)
                return

        count = 0
        exceeded = False
        rejected = False

        async def bounded_receive() -> Message:
            nonlocal count, exceeded
            message = await receive()
            if message["type"] == "http.request":
                count += len(message.get("body", b""))
                if count > self.max_bytes:
                    exceeded = True
                    raise _BodyTooLarge("request body is too large")
            return message

        async def bounded_send(message: Message) -> None:
            nonlocal rejected
            if exceeded:
                # 解析框架可能先把读取异常转为 400，这里保持统一的 413。
                if not rejected:
                    rejected = True
                    await rejection()(scope, receive, send)
                return
            await send(message)

        try:
            await self.app(scope, bounded_receive, bounded_send)
        except _BodyTooLarge:
            if not rejected:
                await rejection()(scope, receive, send)
