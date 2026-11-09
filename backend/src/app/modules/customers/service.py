import uuid

from sqlalchemy import text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.modules.customers.models import Customer
from app.modules.tenancy.context import TenantContext


class CustomerService:
    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.session = session
        self.tenant = tenant

    async def upsert_by_phone(self, phone: str, name: str, telegram_user_id: int | None = None) -> uuid.UUID:
        if telegram_user_id is not None:
            # One Telegram account belongs to one customer: if it was linked to another phone before,
            # the person changed numbers - move the link.
            await self.session.execute(
                update(Customer)
                .where(
                    Customer.tenant_id == self.tenant.id,
                    Customer.telegram_user_id == telegram_user_id,
                    Customer.phone.is_distinct_from(phone),
                )
                .values(telegram_user_id=None)
            )
        set_: dict[str, object] = {"name": name, "updated_at": text("now()")}
        if telegram_user_id is not None:
            set_["telegram_user_id"] = telegram_user_id
        stmt = (
            insert(Customer)
            .values(id=new_id(), tenant_id=self.tenant.id, phone=phone, name=name, telegram_user_id=telegram_user_id)
            .on_conflict_do_update(
                index_elements=[Customer.tenant_id, Customer.phone],
                index_where=text("phone is not null"),
                set_=set_,
            )
            .returning(Customer.id)
        )
        customer_id: uuid.UUID = (await self.session.execute(stmt)).scalar_one()
        return customer_id
