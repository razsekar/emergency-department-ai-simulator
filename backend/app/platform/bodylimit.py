"""Reject oversized request bodies from the Content-Length header, before the body is read.

Multipart parsing would otherwise spool a huge upload to disk before the upload handler can apply its
own limit. Requests that send no Content-Length (chunked) are not covered here; the upload handler still
reads at most limit+1 bytes. Pure ASGI middleware so streaming responses (SSE) are untouched.
"""
import json

from starlette.types import ASGIApp, Receive, Scope, Send


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            raw = dict(scope["headers"]).get(b"content-length")
            try:
                too_big = raw is not None and int(raw) > self.max_bytes
            except ValueError:
                too_big = True  # malformed Content-Length
            if too_big:
                body = json.dumps({"error": {"code": "payload_too_large",
                                             "message": "Request body is too large."}}).encode()
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
