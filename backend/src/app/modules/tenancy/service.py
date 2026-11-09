import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.config import Settings
from app.core.errors import AppError, NotFound, TenantNotFound
from app.modules.tenancy.context import TenantContext
from app.modules.tenancy.models import Branch, BranchHours, Tenant, TenantDomain, TenantStatus
from app.modules.tenancy.schedule import Interval


class TenantSuspended(AppError):
    status, code, title = 403, "tenant_suspended", "Storefront is temporarily unavailable"


def to_context(t: Tenant) -> TenantContext:
    return TenantContext(t.id, t.slug, t.name, t.currency, t.country, t.locale, t.timezone, dict(t.branding))


def request_host(request: Request, settings: Settings) -> str:
    raw = request.headers.get("x-forwarded-host") if settings.trust_forwarded_host else None
    raw = raw or request.headers.get("host", "")
    return raw.split(",")[0].strip().rsplit(":", 1)[0].lower() if raw else ""


class TenantResolver:
    """Host -> tenant_domains; on platform API hosts only, `X-Tenant: <slug>` (mobile). See ADR-0002."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def resolve(self, request: Request) -> TenantContext:
        host = request_host(request, self.settings)
        tenant = await self.session.scalar(
            select(Tenant).join(TenantDomain, TenantDomain.tenant_id == Tenant.id).where(TenantDomain.host == host)
        )
        if tenant is None and host in self.settings.platform_api_hosts:
            slug = request.headers.get("x-tenant", "").strip().lower()
            if slug:
                tenant = await self.session.scalar(select(Tenant).where(Tenant.slug == slug))
        if tenant is None:
            raise TenantNotFound()
        if tenant.status != TenantStatus.ACTIVE:
            raise TenantSuspended()
        return to_context(tenant)

    async def by_id(self, tenant_id: uuid.UUID) -> TenantContext:
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None:
            raise TenantNotFound()
        return to_context(tenant)


class BranchService:
    """Reads branches of the bound tenant. RLS scopes rows; the explicit filter documents intent."""

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.session = session
        self.tenant = tenant

    async def list_active(self) -> Sequence[Branch]:
        rows = await self.session.scalars(
            select(Branch)
            .where(Branch.tenant_id == self.tenant.id, Branch.is_active.is_(True))
            .order_by(Branch.sort, Branch.name)
        )
        return rows.all()

    async def get(self, branch_id: uuid.UUID, *, active_only: bool = True) -> Branch:
        branch = await self.session.scalar(
            select(Branch).where(Branch.tenant_id == self.tenant.id, Branch.id == branch_id)
        )
        if branch is None or (active_only and not branch.is_active):
            raise NotFound("branch not found", code="branch_not_found")
        return branch

    async def hours(self, branch_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[Interval]]:
        rows = await self.session.scalars(
            select(BranchHours).where(BranchHours.tenant_id == self.tenant.id, BranchHours.branch_id.in_(branch_ids))
        )
        result: dict[uuid.UUID, list[Interval]] = defaultdict(list)
        for h in rows:
            result[h.branch_id].append(Interval(h.weekday, h.opens_at, h.closes_at))
        return result
