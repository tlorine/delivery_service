"""Staff-facing management of branches, opening hours, delivery zones and storefront settings."""

import uuid
from datetime import time
from typing import Annotated, Any

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import BusinessRuleViolation, NotFound
from app.modules.audit.service import AuditService
from app.modules.delivery.geo import validate_polygon
from app.modules.delivery.models import DeliveryZone
from app.modules.identity.models import Role
from app.modules.identity.service import StaffContext
from app.modules.payments.provider import enabled_methods
from app.modules.telegram.models import TelegramBot
from app.modules.telegram.service import link_code
from app.modules.tenancy.models import Branch, BranchHours, Tenant

router = APIRouter(prefix="/v1/admin", tags=["admin: settings"], route_class=DishkaRoute)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[int, Field(strict=True, ge=0, le=100_000_000)]


class In(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- schemas ------------------------------------------------------------------------------------


class HoursItem(In):
    weekday: int = Field(ge=0, le=6, description="0 = Monday")
    opens_at: time
    closes_at: time = Field(description="<= opens_at means the interval ends the next day")


class HoursIn(In):
    intervals: list[HoursItem] = Field(max_length=50)


class BranchAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    lat: float | None
    lon: float | None
    phone: str | None
    timezone: str
    is_active: bool
    delivery_enabled: bool
    pickup_enabled: bool
    prep_time_min: int
    delivery_time_min: int
    payment_methods: list[str]
    hours: list[HoursItem]


class BranchPatch(In):
    name: Name | None = None
    address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)] | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    is_active: bool | None = None
    delivery_enabled: bool | None = None
    pickup_enabled: bool | None = None
    prep_time_min: int | None = Field(None, ge=0, le=600)
    delivery_time_min: int | None = Field(None, ge=0, le=600)
    payment_methods: list[str] | None = Field(None, min_length=1)

    @field_validator("payment_methods")
    @classmethod
    def _known(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and not set(v) <= {m.value for m in enabled_methods()}:
            raise ValueError(f"supported: {sorted(m.value for m in enabled_methods())}")
        return v


class ZoneOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    polygon: dict[str, Any]
    fee_minor: int
    min_order_minor: int
    free_from_minor: int | None
    priority: int
    is_active: bool


class ZoneIn(In):
    name: Name
    polygon: dict[str, Any] = Field(description="GeoJSON Polygon, coordinates [lon, lat]")
    fee_minor: Money = 0
    min_order_minor: Money = 0
    free_from_minor: Money | None = None
    priority: int = 0
    is_active: bool = True


class ZonePatch(In):
    name: Name | None = None
    polygon: dict[str, Any] | None = None
    fee_minor: Money | None = None
    min_order_minor: Money | None = None
    free_from_minor: Money | None = None
    priority: int | None = None
    is_active: bool | None = None


class Branding(In):
    logo_url: Annotated[str, StringConstraints(pattern=r"^https://", max_length=1000)] | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    copyright: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    # Storefront accent; the storefront adjusts it for readable button text (WCAG AA).
    accent_color: (
        Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^#[0-9A-Fa-f]{6}$")] | None
    ) = None
    cover_url: Annotated[str, StringConstraints(pattern=r"^https://", max_length=1000)] | None = None


class SettingsOut(BaseModel):
    name: str
    slug: str
    currency: str
    timezone: str
    branding: Branding
    telegram_bot: str | None
    telegram_staff_chat_connected: bool
    telegram_link_command: str | None = Field(description="Send this in the staff group to connect notifications")


class SettingsPatch(In):
    name: Name | None = None
    branding: Branding | None = None


# ---- service ------------------------------------------------------------------------------------


class TenantAdminService:
    def __init__(self, session: AsyncSession, staff: StaffContext, audit: AuditService, settings: Settings) -> None:
        self.session = session
        self.staff = staff
        self.t = staff.tenant_id
        self.audit = audit
        self.settings = settings

    def _record(self, action: str, entity: str, entity_id: uuid.UUID | None, **data: Any) -> None:
        self.audit.record(
            action,
            entity,
            entity_id,
            actor_type="staff",
            actor_id=self.staff.user_id,
            data={k: str(v) for k, v in data.items()},
        )

    async def _branch(self, branch_id: uuid.UUID) -> Branch:
        branch = await self.session.scalar(select(Branch).where(Branch.tenant_id == self.t, Branch.id == branch_id))
        if branch is None:
            raise NotFound("branch not found", code="branch_not_found")
        return branch

    async def _zone(self, zone_id: uuid.UUID) -> DeliveryZone:
        zone = await self.session.scalar(
            select(DeliveryZone).where(DeliveryZone.tenant_id == self.t, DeliveryZone.id == zone_id)
        )
        if zone is None:
            raise NotFound("delivery zone not found", code="not_found")
        return zone

    async def branches(self) -> list[BranchAdminOut]:
        rows = (
            await self.session.scalars(
                select(Branch).where(Branch.tenant_id == self.t).order_by(Branch.sort, Branch.name)
            )
        ).all()
        hours = (
            await self.session.scalars(
                select(BranchHours)
                .where(BranchHours.tenant_id == self.t)
                .order_by(BranchHours.weekday, BranchHours.opens_at)
            )
        ).all()
        return [
            BranchAdminOut(
                id=b.id,
                name=b.name,
                address=b.address,
                lat=b.lat,
                lon=b.lon,
                phone=b.phone,
                timezone=b.timezone,
                is_active=b.is_active,
                delivery_enabled=b.delivery_enabled,
                pickup_enabled=b.pickup_enabled,
                prep_time_min=b.prep_time_min,
                delivery_time_min=b.delivery_time_min,
                payment_methods=b.payment_methods,
                hours=[
                    HoursItem(weekday=h.weekday, opens_at=h.opens_at, closes_at=h.closes_at)
                    for h in hours
                    if h.branch_id == b.id
                ],
            )
            for b in rows
        ]

    async def update_branch(self, branch_id: uuid.UUID, patch: BranchPatch) -> None:
        branch = await self._branch(branch_id)
        changes = patch.model_dump(exclude_unset=True)
        for k, v in changes.items():
            setattr(branch, k, v)
        if not (branch.delivery_enabled or branch.pickup_enabled) and branch.is_active:
            raise BusinessRuleViolation("enable delivery or pickup, or deactivate the branch", code="no_fulfillment")
        self._record("branch.updated", "branch", branch.id, **changes)
        await self.session.commit()

    async def set_hours(self, branch_id: uuid.UUID, body: HoursIn) -> None:
        branch = await self._branch(branch_id)
        for item in body.intervals:
            if item.opens_at == item.closes_at and item.opens_at != time(0):
                raise BusinessRuleViolation(
                    "an interval cannot be empty; use 00:00-00:00 for 24 hours", code="invalid_hours"
                )
        await self.session.execute(
            delete(BranchHours).where(BranchHours.tenant_id == self.t, BranchHours.branch_id == branch.id)
        )
        for item in body.intervals:
            self.session.add(BranchHours(tenant_id=self.t, branch_id=branch.id, **item.model_dump()))
        self._record("branch.hours_set", "branch", branch.id, intervals=len(body.intervals))
        await self.session.commit()

    async def zones(self, branch_id: uuid.UUID) -> list[ZoneOut]:
        await self._branch(branch_id)
        rows = (
            await self.session.scalars(
                select(DeliveryZone)
                .where(DeliveryZone.tenant_id == self.t, DeliveryZone.branch_id == branch_id)
                .order_by(DeliveryZone.priority)
            )
        ).all()
        return [ZoneOut.model_validate(z, from_attributes=True) for z in rows]

    @staticmethod
    def _check_polygon(polygon: dict[str, Any]) -> None:
        try:
            validate_polygon(polygon)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise BusinessRuleViolation(str(exc), code="invalid_polygon") from exc

    async def create_zone(self, branch_id: uuid.UUID, body: ZoneIn) -> uuid.UUID:
        await self._branch(branch_id)
        self._check_polygon(body.polygon)
        zone = DeliveryZone(tenant_id=self.t, branch_id=branch_id, **body.model_dump())
        self.session.add(zone)
        await self.session.flush()
        self._record("delivery_zone.created", "delivery_zone", zone.id, name=body.name, fee_minor=body.fee_minor)
        await self.session.commit()
        return zone.id

    async def update_zone(self, zone_id: uuid.UUID, patch: ZonePatch) -> None:
        zone = await self._zone(zone_id)
        changes = patch.model_dump(exclude_unset=True)
        if "polygon" in changes:
            self._check_polygon(changes["polygon"])
        for k, v in changes.items():
            setattr(zone, k, v)
        self._record(
            "delivery_zone.updated", "delivery_zone", zone.id, **{k: v for k, v in changes.items() if k != "polygon"}
        )
        await self.session.commit()

    async def delete_zone(self, zone_id: uuid.UUID) -> None:
        zone = await self._zone(zone_id)
        await self.session.delete(zone)
        self._record("delivery_zone.deleted", "delivery_zone", zone_id)
        await self.session.commit()

    async def get_settings(self) -> SettingsOut:
        tenant = await self.session.get(Tenant, self.t)
        assert tenant is not None
        bot = await self.session.scalar(select(TelegramBot).where(TelegramBot.tenant_id == self.t))
        command = f"/link {link_code(self.settings.session_secret.get_secret_value(), bot.bot_id)}" if bot else None
        known = set(Branding.model_fields)
        return SettingsOut(
            name=tenant.name,
            slug=tenant.slug,
            currency=tenant.currency,
            timezone=tenant.timezone,
            branding=Branding(**{k: v for k, v in tenant.branding.items() if k in known}),
            telegram_bot=f"@{bot.username}" if bot else None,
            telegram_staff_chat_connected=bool(bot and bot.notify_chat_id),
            telegram_link_command=command,
        )

    async def update_settings(self, patch: SettingsPatch) -> None:
        tenant = await self.session.get(Tenant, self.t)
        assert tenant is not None
        if patch.name is not None:
            tenant.name = patch.name
        if patch.branding is not None:
            tenant.branding = {**tenant.branding, **patch.branding.model_dump(exclude_unset=True)}
        self._record("settings.updated", "tenant", tenant.id, fields=",".join(patch.model_dump(exclude_unset=True)))
        await self.session.commit()


# ---- routes -------------------------------------------------------------------------------------


@router.get("/branches", response_model=list[BranchAdminOut], tags=["admin: branches"])
async def list_branches(staff: FromDishka[StaffContext], svc: FromDishka[TenantAdminService]) -> list[BranchAdminOut]:
    staff.require(Role.OPERATOR)
    return await svc.branches()


@router.patch("/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["admin: branches"])
async def update_branch(
    branch_id: uuid.UUID, body: BranchPatch, staff: FromDishka[StaffContext], svc: FromDishka[TenantAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.update_branch(branch_id, body)


@router.put("/branches/{branch_id}/hours", status_code=status.HTTP_204_NO_CONTENT, tags=["admin: branches"])
async def set_hours(
    branch_id: uuid.UUID, body: HoursIn, staff: FromDishka[StaffContext], svc: FromDishka[TenantAdminService]
) -> None:
    """Replaces the whole weekly schedule."""
    staff.require(Role.MANAGER)
    await svc.set_hours(branch_id, body)


@router.get("/branches/{branch_id}/delivery-zones", response_model=list[ZoneOut], tags=["admin: delivery"])
async def list_zones(
    branch_id: uuid.UUID, staff: FromDishka[StaffContext], svc: FromDishka[TenantAdminService]
) -> list[ZoneOut]:
    staff.require(Role.OPERATOR)
    return await svc.zones(branch_id)


class CreatedOut(BaseModel):
    id: uuid.UUID


@router.post(
    "/branches/{branch_id}/delivery-zones", response_model=CreatedOut, status_code=201, tags=["admin: delivery"]
)
async def create_zone(
    branch_id: uuid.UUID, body: ZoneIn, staff: FromDishka[StaffContext], svc: FromDishka[TenantAdminService]
) -> CreatedOut:
    staff.require(Role.MANAGER)
    return CreatedOut(id=await svc.create_zone(branch_id, body))


@router.patch("/delivery-zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["admin: delivery"])
async def update_zone(
    zone_id: uuid.UUID, body: ZonePatch, staff: FromDishka[StaffContext], svc: FromDishka[TenantAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.update_zone(zone_id, body)


@router.delete("/delivery-zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["admin: delivery"])
async def delete_zone(zone_id: uuid.UUID, staff: FromDishka[StaffContext], svc: FromDishka[TenantAdminService]) -> None:
    staff.require(Role.MANAGER)
    await svc.delete_zone(zone_id)


@router.get("/settings", response_model=SettingsOut)
async def get_settings(staff: FromDishka[StaffContext], svc: FromDishka[TenantAdminService]) -> SettingsOut:
    staff.require(Role.OWNER)
    return await svc.get_settings()


@router.patch("/settings", status_code=status.HTTP_204_NO_CONTENT)
async def update_settings(
    body: SettingsPatch, staff: FromDishka[StaffContext], svc: FromDishka[TenantAdminService]
) -> None:
    staff.require(Role.OWNER)
    await svc.update_settings(body)
