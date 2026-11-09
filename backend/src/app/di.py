"""Dependency graph (Dishka). The same container serves the API, the worker and the CLI."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from dishka import AsyncContainer, Provider, Scope, from_context, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.requests import Request

from app.core.clock import Clock, SystemClock
from app.core.config import Settings
from app.core.db import bind_tenant, create_engine, create_sessionmaker
from app.core.errors import Unauthorized
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import SecretBox
from app.modules.audit.service import AuditService
from app.modules.cart.service import CartService
from app.modules.catalog.admin_service import CatalogAdminService
from app.modules.catalog.service import CatalogService
from app.modules.customers.service import CustomerService
from app.modules.delivery.geocoder import DadataGeocoder, DemoGeocoder, Geocoder, NullGeocoder
from app.modules.delivery.provider import DeliveryProvider
from app.modules.delivery.service import OwnCourierProvider
from app.modules.identity.admin import StaffAdminService
from app.modules.identity.service import AuthService, StaffContext
from app.modules.notifications.handlers import TelegramCustomerNotifier, TelegramStaffNotifier, build_handlers
from app.modules.notifications.worker import OutboxProcessor
from app.modules.ordering.service import OrderService
from app.modules.telegram.client import TelegramBotApi
from app.modules.telegram.service import TelegramIdentity, TelegramWebhook
from app.modules.tenancy.admin import TenantAdminService
from app.modules.tenancy.context import TenantContext
from app.modules.tenancy.service import BranchService, TenantResolver

ADMIN_PREFIX = "/v1/admin"


@dataclass(frozen=True, slots=True)
class Limiters:
    orders: SlidingWindowLimiter
    login: SlidingWindowLimiter
    carts: SlidingWindowLimiter
    suggest: SlidingWindowLimiter


class InfrastructureProvider(Provider):
    settings = from_context(provides=Settings, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def engine(self, settings: Settings) -> AsyncIterator[AsyncEngine]:
        engine = create_engine(settings.database_url, settings.db_pool_size)
        yield engine
        await engine.dispose()

    @provide(scope=Scope.APP)
    def sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return create_sessionmaker(engine)

    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        return SystemClock()

    @provide(scope=Scope.APP)
    def secret_box(self, settings: Settings) -> SecretBox:
        return SecretBox(settings.encryption_key.get_secret_value())

    @provide(scope=Scope.APP)
    async def http(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient() as client:
            yield client

    @provide(scope=Scope.APP)
    def telegram_api(self, http: httpx.AsyncClient, settings: Settings) -> TelegramBotApi:
        return TelegramBotApi(http, settings.telegram_api_base)

    @provide(scope=Scope.APP)
    def geocoder(self, http: httpx.AsyncClient, settings: Settings) -> Geocoder:
        if settings.geocoder == "dadata" and settings.dadata_api_key:
            return DadataGeocoder(http, settings.dadata_api_key.get_secret_value())
        if settings.geocoder == "demo":
            return DemoGeocoder()
        return NullGeocoder()

    @provide(scope=Scope.APP)
    def limiters(self, settings: Settings) -> Limiters:
        return Limiters(
            orders=SlidingWindowLimiter(settings.order_rate_limit_per_minute),
            login=SlidingWindowLimiter(settings.login_rate_limit_per_minute),
            carts=SlidingWindowLimiter(120),
            suggest=SlidingWindowLimiter(120),
        )

    @provide(scope=Scope.APP)
    def outbox(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        api: TelegramBotApi,
        box: SecretBox,
        clock: Clock,
        settings: Settings,
    ) -> OutboxProcessor:
        handlers = build_handlers(TelegramStaffNotifier(api, box, settings), TelegramCustomerNotifier(api, box))
        return OutboxProcessor(sessionmaker, handlers, clock, settings)

    @provide(scope=Scope.REQUEST)
    async def session(self, sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:  # closing rolls back anything not committed
            yield session


class TenantProvider(Provider):
    scope = Scope.REQUEST

    @provide
    async def tenant(self, request: Request, session: AsyncSession, settings: Settings, clock: Clock) -> TenantContext:
        """The single place where a request gets its tenant (ADR-0002)."""
        resolver = TenantResolver(session, settings)
        if request.url.path.startswith(ADMIN_PREFIX):
            staff = await AuthService(session, clock, settings).staff_context(request)
            request.state.staff = staff
            ctx = await resolver.by_id(staff.tenant_id)
        else:
            ctx = await resolver.resolve(request)
        await bind_tenant(session, ctx.id)
        return ctx

    @provide
    def staff(self, request: Request, tenant: TenantContext) -> StaffContext:
        staff: StaffContext | None = getattr(request.state, "staff", None)
        if staff is None or staff.tenant_id != tenant.id:
            raise Unauthorized()
        return staff


class ServicesProvider(Provider):
    scope = Scope.REQUEST

    auth = provide(AuthService)
    branches = provide(BranchService)
    catalog = provide(CatalogService)
    carts = provide(CartService)
    customers = provide(CustomerService)
    audit = provide(AuditService)
    delivery = provide(OwnCourierProvider, provides=DeliveryProvider)
    orders = provide(OrderService)
    telegram_identity = provide(TelegramIdentity)
    telegram_webhook = provide(TelegramWebhook)
    catalog_admin = provide(CatalogAdminService)
    tenant_admin = provide(TenantAdminService)
    staff_admin = provide(StaffAdminService)


def build_container(settings: Settings, *extra: Provider) -> AsyncContainer:
    return make_async_container(
        InfrastructureProvider(),
        TenantProvider(),
        ServicesProvider(),
        FastapiProvider(),
        *extra,
        context={Settings: settings},
    )
