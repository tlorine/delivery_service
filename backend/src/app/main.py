import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, request_id_var
from app.di import build_container
from app.modules.cart.router import router as cart_router
from app.modules.catalog.admin_router import router as catalog_admin_router
from app.modules.catalog.router import router as menu_router
from app.modules.delivery.router import router as address_router
from app.modules.identity.admin import router as staff_admin_router
from app.modules.identity.router import router as auth_router
from app.modules.ordering.admin_router import router as admin_orders_router
from app.modules.ordering.analytics import router as analytics_router
from app.modules.ordering.router import router as orders_router
from app.modules.telegram.router import router as telegram_router
from app.modules.tenancy.admin import router as tenant_admin_router
from app.modules.tenancy.router import router as storefront_router

log = logging.getLogger("app.http")


def create_app(settings: Settings | None = None, container: AsyncContainer | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await container.close()

    app = FastAPI(
        lifespan=lifespan,
        title="Delivery Platform API",
        version="1.0.0",
        openapi_url="/v1/openapi.json",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error", extra={"method": request.method, "path": request.url.path})
            response = JSONResponse(
                {"type": "about:blank", "title": "Internal error", "status": 500, "code": "internal_error"},
                status_code=500,
                media_type="application/problem+json",
            )
        # Path without query string; route templates would be better, but paths carry no personal data.
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        response.headers["X-Request-Id"] = rid
        request_id_var.reset(token)
        return response

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-Cart-Token",
                "Idempotency-Key",
                "X-Tenant",
                "X-Tenant-Id",
                "X-Client",
                "X-Requested-With",
                "X-Request-Id",
            ],
        )

    for router in (
        storefront_router,
        menu_router,
        address_router,
        cart_router,
        orders_router,
        auth_router,
        admin_orders_router,
        telegram_router,
        catalog_admin_router,
        tenant_admin_router,
        staff_admin_router,
        analytics_router,
    ):
        app.include_router(router)

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> JSONResponse:
        try:
            engine = await container.get(AsyncEngine)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            log.exception("readiness check failed")
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    setup_dishka(container, app)
    return app


def app_factory() -> FastAPI:
    return create_app()
