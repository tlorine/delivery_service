"""Russian-language messages for the cafe staff chat. Amounts are integers in minor units (ADR-0008)."""

from html import escape
from zoneinfo import ZoneInfo

from app.modules.ordering.schemas import OrderOut

STATUS_RU = {
    "pending": "Новый",
    "confirmed": "Подтверждён",
    "preparing": "Готовится",
    "ready": "Готов",
    "delivering": "В пути",
    "completed": "Выполнен",
    "cancelled": "Отменён",
    "rejected": "Отклонён",
}
PAYMENT_RU = {"cash": "наличные", "card_on_delivery": "картой при получении", "online": "онлайн"}


def money(minor: int, currency: str = "RUB") -> str:
    rub, kop = divmod(minor, 100)
    whole = f"{rub:,}".replace(",", " ")
    sign = "₽" if currency == "RUB" else currency
    return f"{whole}{',' + f'{kop:02d}' if kop else ''} {sign}"


def new_order_message(order: OrderOut, tz: str, admin_url: str | None) -> str:
    local = order.created_at.astimezone(ZoneInfo(tz))
    lines = [f"🆕 <b>Заказ №{order.number}</b> · {local:%H:%M}"]
    lines.append("🚗 Доставка" if order.fulfillment == "delivery" else "🏃 Самовывоз")
    if order.requested_at:
        lines.append(f"⏰ Ко времени: {order.requested_at.astimezone(ZoneInfo(tz)):%d.%m %H:%M}")
    lines.append("")
    for item in order.items:
        name = (
            item.product_name
            if item.variant_name in {"", item.product_name}
            else f"{item.product_name} ({item.variant_name})"
        )
        lines.append(f"• {escape(name)} × {item.quantity} — {money(item.line_total_minor, order.currency)}")
        for m in item.modifiers:
            qty = f" ×{m.quantity}" if m.quantity > 1 else ""
            lines.append(f"   + {escape(m.name)}{qty}")
    lines.append("")
    if order.delivery_fee_minor:
        lines.append(f"Доставка: {money(order.delivery_fee_minor, order.currency)}")
    lines.append(
        f"<b>Итого: {money(order.total_minor, order.currency)}</b> · {PAYMENT_RU.get(order.payment_method, '')}"
    )
    if order.change_from_minor:
        lines.append(f"Сдача с {money(order.change_from_minor, order.currency)}")
    lines.append("")
    lines.append(f"👤 {escape(order.customer_name)} · {order.customer_phone}")
    if order.address:
        a = order.address
        extra = ", ".join(
            p
            for p in [
                f"кв. {a.flat}" if a.flat else "",
                f"подъезд {a.entrance}" if a.entrance else "",
                f"этаж {a.floor}" if a.floor else "",
                f"домофон {a.intercom}" if a.intercom else "",
            ]
            if p
        )
        lines.append(f"📍 {escape(a.street)}{', ' + escape(extra) if extra else ''}")
        if a.comment:
            lines.append(f"   {escape(a.comment)}")
    if order.comment:
        lines.append(f"💬 {escape(order.comment)}")
    if admin_url:
        lines.append(f'\n<a href="{escape(admin_url)}">Открыть в панели</a>')
    return "\n".join(lines)


def status_message(order: OrderOut) -> str:
    return f"Заказ №{order.number}: {STATUS_RU.get(order.status, order.status)}"
