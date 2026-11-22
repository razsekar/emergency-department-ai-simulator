"""Consistent, safe error responses (no stack traces, internals or echoed input leaked)."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")


class AppError(Exception):
    status_code = 400
    code = "app_error"
    headers: dict[str, str] | None = None

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


def _envelope(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


_HTTP_CODES = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code, exc.message),
                            headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Field locations and messages only: never echo the submitted values back.
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e.get('loc', ()) if p != 'body')}: {e.get('msg', 'invalid')}"
            for e in exc.errors()
        )
        return JSONResponse(status_code=422, content=_envelope("validation_error", f"Invalid request ({problems})"))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(status_code=exc.status_code, content=_envelope(code, message), headers=exc.headers)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error")
        return JSONResponse(status_code=500, content=_envelope("internal_error", "Internal server error"))
