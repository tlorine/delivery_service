import uuid

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.core.http import client_ip
from app.di import Limiters
from app.modules.identity.service import SESSION_COOKIE, AuthService

router = APIRouter(prefix="/v1/admin/auth", tags=["admin: auth"], route_class=DishkaRoute)


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class MembershipOut(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role: str


class MeOut(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    memberships: list[MembershipOut]


class LoginOut(MeOut):
    token: str = Field(description="Also set as an HttpOnly cookie; use as Bearer for non-browser clients")


async def _me(auth: AuthService, user_id: uuid.UUID, email: str, name: str) -> MeOut:
    rows = await auth.memberships_with_tenants(user_id)
    return MeOut(
        user_id=user_id,
        email=email,
        name=name,
        memberships=[
            MembershipOut(tenant_id=t.id, tenant_name=t.name, tenant_slug=t.slug, role=m.role) for m, t in rows
        ],
    )


@router.post("/login", response_model=LoginOut)
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    auth: FromDishka[AuthService],
    limiters: FromDishka[Limiters],
    settings: FromDishka[Settings],
) -> LoginOut:
    limiters.login.hit(f"login-ip:{client_ip(request, settings)}")
    limiters.login.hit(f"login-email:{body.email.strip().lower()}")
    token, user = await auth.login(body.email, body.password)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.staff_session_ttl_days * 86400,
        path="/v1/admin",
    )
    me = await _me(auth, user.id, user.email, user.name)
    return LoginOut(**me.model_dump(), token=token)


@router.get("/me", response_model=MeOut)
async def me(request: Request, auth: FromDishka[AuthService]) -> MeOut:
    staff = await auth.authenticate(request)
    return await _me(auth, staff.user.id, staff.user.email, staff.user.name)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, auth: FromDishka[AuthService]) -> None:
    await auth.logout(request)
    response.delete_cookie(SESSION_COOKIE, path="/v1/admin")
