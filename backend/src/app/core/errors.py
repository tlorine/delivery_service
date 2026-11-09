"""Application errors rendered as RFC 9457 problem details.

Domain code raises AppError subclasses; HTTP mapping lives here, not in services.
`code` is the stable machine identifier clients localize by.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"


class AppError(Exception):
    status: int = 400
    code: str = "bad_request"
    title: str = "Bad request"

    def __init__(self, detail: str | None = None, *, code: str | None = None, extra: dict[str, Any] | None = None):
        super().__init__(detail or self.title)
        self.detail = detail
        if code:
            self.code = code
        self.extra = extra or {}


class NotFound(AppError):
    status, code, title = 404, "not_found", "Not found"


class Unauthorized(AppError):
    status, code, title = 401, "unauthorized", "Unauthorized"


class Forbidden(AppError):
    status, code, title = 403, "forbidden", "Forbidden"


class Conflict(AppError):
    status, code, title = 409, "conflict", "Conflict"


class BusinessRuleViolation(AppError):
    """The request is well-formed but breaks a business rule (closed branch, outside zone, ...)."""

    status, code, title = 422, "business_rule_violation", "Request cannot be fulfilled"


class TenantNotFound(AppError):
    status, code, title = 404, "tenant_not_found", "Storefront not found"


class RateLimited(AppError):
    status, code, title = 429, "rate_limited", "Too many requests"


def _problem(status: int, code: str, title: str, detail: str | None, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {"type": "about:blank", "title": title, "status": status, "code": code}
    if detail:
        body["detail"] = detail
    body.update({k: v for k, v in extra.items() if v})
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _problem(exc.status, exc.code, exc.title, exc.detail, extra=exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", ())), "code": e.get("type", "invalid"), "message": e.get("msg", "")}
            for e in exc.errors()
        ]
        return _problem(422, "validation_error", "Validation error", None, errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return _problem(exc.status_code, code, str(exc.detail), None)
