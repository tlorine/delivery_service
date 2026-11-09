import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Forbidden, Unauthorized
from app.core.security import hash_password, hash_token, new_token, verify_password
from app.modules.identity.models import ROLE_RANK, Membership, Role, StaffSession, StaffUser
from app.modules.tenancy.models import Tenant

SESSION_COOKIE = "staff_session"
# Constant-time-ish login: verify against a dummy hash when the user does not exist.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


@dataclass(frozen=True, slots=True)
class StaffContext:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: Role

    def require(self, minimum: Role) -> None:
        if ROLE_RANK[self.role] < ROLE_RANK[minimum]:
            raise Forbidden(f"requires role {minimum}", code="insufficient_role")


@dataclass(frozen=True, slots=True)
class AuthenticatedStaff:
    user: StaffUser
    session_id: uuid.UUID


def read_session_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    token = request.cookies.get(SESSION_COOKIE)
    if token and request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-requested-with") is None:
        # Cookie auth + state change requires a custom header: cross-site forms cannot send it (CSRF).
        raise Forbidden("missing X-Requested-With header", code="csrf_check_failed")
    return token


class AuthService:
    def __init__(self, session: AsyncSession, clock: Clock, settings: Settings) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings

    async def login(self, email: str, password: str) -> tuple[str, StaffUser]:
        user = await self.session.scalar(select(StaffUser).where(StaffUser.email == email.strip().lower()))
        valid = verify_password(user.password_hash if user else _DUMMY_HASH, password)
        if user is None or not valid or not user.is_active:
            raise Unauthorized("invalid email or password", code="invalid_credentials")
        token = new_token()
        self.session.add(
            StaffSession(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=self.clock.now() + timedelta(days=self.settings.staff_session_ttl_days),
            )
        )
        await self.session.commit()
        return token, user

    async def authenticate(self, request: Request) -> AuthenticatedStaff:
        token = read_session_token(request)
        if not token:
            raise Unauthorized()
        now = self.clock.now()
        row = (
            await self.session.execute(
                select(StaffSession, StaffUser)
                .join(StaffUser, StaffUser.id == StaffSession.user_id)
                .where(StaffSession.token_hash == hash_token(token))
            )
        ).first()
        if row is None:
            raise Unauthorized()
        staff_session, user = row
        if staff_session.revoked_at or staff_session.expires_at <= now or not user.is_active:
            raise Unauthorized("session expired", code="session_expired")
        # Sliding expiration, written at most once a day per session.
        new_expiry = now + timedelta(days=self.settings.staff_session_ttl_days)
        if new_expiry - staff_session.expires_at > timedelta(days=1):
            staff_session.expires_at = new_expiry
            await self.session.commit()  # runs before the tenant is bound; safe to commit here
        return AuthenticatedStaff(user, staff_session.id)

    async def memberships(self, user_id: uuid.UUID) -> list[Membership]:
        rows = await self.session.scalars(select(Membership).where(Membership.user_id == user_id))
        return list(rows)

    async def memberships_with_tenants(self, user_id: uuid.UUID) -> list[tuple[Membership, Tenant]]:
        rows = await self.session.execute(
            select(Membership, Tenant)
            .join(Tenant, Tenant.id == Membership.tenant_id)
            .where(Membership.user_id == user_id)
        )
        return [(m, t) for m, t in rows]

    async def staff_context(self, request: Request) -> StaffContext:
        """Authenticate and pick the tenant from X-Tenant-Id among the user's memberships."""
        staff = await self.authenticate(request)
        memberships = await self.memberships(staff.user.id)
        raw = request.headers.get("x-tenant-id")
        if raw:
            try:
                wanted = uuid.UUID(raw)
            except ValueError:
                raise Forbidden("invalid X-Tenant-Id", code="tenant_access_denied") from None
            chosen = next((m for m in memberships if m.tenant_id == wanted), None)
        else:
            chosen = memberships[0] if len(memberships) == 1 else None
        if chosen is None:
            raise Forbidden("no access to this tenant", code="tenant_access_denied")
        return StaffContext(staff.user.id, chosen.tenant_id, Role(chosen.role))

    async def logout(self, request: Request) -> None:
        staff = await self.authenticate(request)
        s = await self.session.get(StaffSession, staff.session_id)
        if s:
            s.revoked_at = self.clock.now()
        await self.session.commit()
