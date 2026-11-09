"""Owner manages the cafe's staff. Identity is platform-wide; access is a membership in this tenant."""

import uuid
from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.errors import BusinessRuleViolation, NotFound
from app.core.security import hash_password
from app.modules.audit.service import AuditService
from app.modules.identity.models import Membership, Role, StaffSession, StaffUser
from app.modules.identity.service import StaffContext

router = APIRouter(prefix="/v1/admin/staff", tags=["admin: staff"], route_class=DishkaRoute)

Email = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
]


class StaffOut(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    role: Role
    is_active: bool


class StaffIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    role: Role
    password: str | None = Field(
        None,
        min_length=10,
        max_length=200,
        description="Required for a new account; ignored if the email already exists",
    )


class RoleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role


class StaffAdminService:
    def __init__(self, session: AsyncSession, staff: StaffContext, audit: AuditService, clock: Clock) -> None:
        self.session = session
        self.staff = staff
        self.audit = audit
        self.clock = clock

    async def list(self) -> list[StaffOut]:
        rows = (
            await self.session.execute(
                select(Membership, StaffUser)
                .join(StaffUser, StaffUser.id == Membership.user_id)
                .where(Membership.tenant_id == self.staff.tenant_id)
                .order_by(StaffUser.name)
            )
        ).all()
        return [
            StaffOut(user_id=u.id, email=u.email, name=u.name, role=Role(m.role), is_active=u.is_active)
            for m, u in rows
        ]

    async def _membership(self, user_id: uuid.UUID) -> Membership:
        m = await self.session.get(Membership, (self.staff.tenant_id, user_id))
        if m is None:
            raise NotFound("staff member not found", code="not_found")
        return m

    async def _owners(self) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(Membership)
                .where(Membership.tenant_id == self.staff.tenant_id, Membership.role == Role.OWNER)
            )
            or 0
        )

    async def add(self, body: StaffIn) -> uuid.UUID:
        user = await self.session.scalar(select(StaffUser).where(StaffUser.email == body.email))
        if user is None:
            if not body.password:
                raise BusinessRuleViolation("a password is required for a new account", code="password_required")
            user = StaffUser(email=body.email, name=body.name, password_hash=hash_password(body.password))
            self.session.add(user)
            await self.session.flush()
        if await self.session.get(Membership, (self.staff.tenant_id, user.id)) is not None:
            raise BusinessRuleViolation("already a staff member", code="already_member")
        self.session.add(Membership(tenant_id=self.staff.tenant_id, user_id=user.id, role=body.role))
        self.audit.record(
            "staff.added",
            "staff_user",
            user.id,
            actor_type="staff",
            actor_id=self.staff.user_id,
            data={"role": body.role},
        )
        await self.session.commit()
        return user.id

    async def set_role(self, user_id: uuid.UUID, role: Role) -> None:
        m = await self._membership(user_id)
        if m.role == Role.OWNER and role != Role.OWNER and await self._owners() <= 1:
            raise BusinessRuleViolation("the cafe must keep at least one owner", code="last_owner")
        m.role = role
        self.audit.record(
            "staff.role_changed",
            "staff_user",
            user_id,
            actor_type="staff",
            actor_id=self.staff.user_id,
            data={"role": role},
        )
        await self.session.commit()

    async def remove(self, user_id: uuid.UUID) -> None:
        if user_id == self.staff.user_id:
            raise BusinessRuleViolation("you cannot remove yourself", code="cannot_remove_self")
        m = await self._membership(user_id)
        if m.role == Role.OWNER and await self._owners() <= 1:
            raise BusinessRuleViolation("the cafe must keep at least one owner", code="last_owner")
        await self.session.delete(m)
        # Revoke sessions if the person has no other cafe left: access must end immediately.
        others = await self.session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.user_id == user_id, Membership.tenant_id != self.staff.tenant_id)
        )
        if not others:
            await self.session.execute(
                update(StaffSession)
                .where(StaffSession.user_id == user_id, StaffSession.revoked_at.is_(None))
                .values(revoked_at=self.clock.now())
            )
        self.audit.record("staff.removed", "staff_user", user_id, actor_type="staff", actor_id=self.staff.user_id)
        await self.session.commit()


@router.get("", response_model=list[StaffOut])
async def list_staff(staff: FromDishka[StaffContext], svc: FromDishka[StaffAdminService]) -> list[StaffOut]:
    staff.require(Role.OWNER)
    return await svc.list()


class CreatedOut(BaseModel):
    id: uuid.UUID


@router.post("", response_model=CreatedOut, status_code=201)
async def add_staff(body: StaffIn, staff: FromDishka[StaffContext], svc: FromDishka[StaffAdminService]) -> CreatedOut:
    staff.require(Role.OWNER)
    return CreatedOut(id=await svc.add(body))


@router.patch("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def set_role(
    user_id: uuid.UUID, body: RoleIn, staff: FromDishka[StaffContext], svc: FromDishka[StaffAdminService]
) -> None:
    staff.require(Role.OWNER)
    await svc.set_role(user_id, body.role)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staff(user_id: uuid.UUID, staff: FromDishka[StaffContext], svc: FromDishka[StaffAdminService]) -> None:
    staff.require(Role.OWNER)
    await svc.remove(user_id)
