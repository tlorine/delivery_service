# Интеграции

Все внешние системы — за портами (Python `Protocol`) в доменном модуле; реализации — в `infrastructure` модуля. Ядро заказов не импортирует SDK.

## Платежи — `PaymentProvider`
```python
class PaymentProvider(Protocol):
    code: str
    async def create_payment(self, order: OrderPaymentRequest) -> PaymentInitResult  # redirect_url / qr
    async def get_payment(self, external_id: str) -> PaymentState
    async def refund(self, external_id: str, amount_minor: int, idempotency_key: str) -> RefundResult
    def parse_webhook(self, headers: Mapping[str, str], body: bytes) -> PaymentWebhookEvent  # проверяет подлинность
```
| Реализация | Статус |
|---|---|
| `cash_on_delivery` / `card_on_delivery` | MVP — без внешних вызовов, `payment_status = not_required` |
| `yookassa` (карты, SberPay, СБП) | после пилота. Подлинность webhook: IP-allowlist ЮKassa + повторный `GET /payments/{id}` (у ЮKassa нет HMAC-подписи); идемпотентность — `Idempotence-Key` в запросах и уникальный `(provider, external_event_id)` |
| СБП через Тинькофф/Т-Банк эквайринг или ЮKassa | после пилота |

Платёжные ключи — на тенанта (деньги идут кафе напрямую), хранятся зашифрованными.

## Доставка — `DeliveryProvider`
```python
class DeliveryProvider(Protocol):
    code: str
    async def quote(self, branch: BranchRef, destination: GeoPoint, order_total_minor: int) -> DeliveryQuote | None
    async def dispatch(self, order: OrderRef) -> DispatchResult      # курьер своего кафе: no-op
    async def cancel(self, dispatch_id: str) -> None
```
MVP: `OwnCourierProvider` — расчёт по зонам доставки филиала (полигоны, стоимость, минимальная сумма, бесплатно от суммы), назначение курьера вручную в админке. Яндекс Доставка — отдельная реализация без изменения `ordering`.

## Геокодирование — `Geocoder`
`GET /v1/address/suggest` → `Geocoder.suggest(query, near=филиалы, limit)`. Реализации (`GEOCODER`):
- `dadata` — DaData Suggestions (ФИАС, координаты для домов), поиск ограничен радиусом 30 км вокруг филиалов; ключ `DADATA_API_KEY`. При ошибке провайдера возвращается пустой список (адрес можно ввести позже), оформление не падает.
- `demo` — фиксированные адреса Сочи для разработки и E2E; запрещён в production.
- `none` — подсказок нет; витрина предлагает только самовывоз (без координат доставку не рассчитать).

Координаты в заказ присылает клиент (из выбранной подсказки). Риск подмены принят: заказ подтверждает человек, адрес виден целиком. **Техдолг:** серверное геокодирование выбранного адреса перед расчётом доставки. Яндекс Геосаджест / 2ГИС — новые реализации порта.

## Уведомления — `Notifier`
Доменные события (`order.created`, `order.status_changed`) пишутся в outbox (ADR-0006). Воркер маршрутизирует событие по каналам тенанта:
- `TelegramNotifier` — сообщение в чат кафе через бота тенанта, с inline-кнопками «Подтвердить/Отклонить» (после MVP — обработка нажатий через webhook).
- `TelegramCustomerNotifier` — покупателю: «заказ принят» и каждая смена статуса, если заказ создан из Mini App (подтверждённый `telegram_user_id`). Заблокированный бот (403) не повторяется.
- Доставка «как минимум один раз» на событие: если один канал упал, событие повторяется целиком и другой канал может получить дубль сообщения. Для MVP приемлемо (дубль лучше потери); при росте — учёт доставки по паре (событие, канал).
- Расширение: e-mail, SMS, web-push — новые реализации `Notifier`.

Telegram API вызывается через `httpx` напрямую (Bot API — простой HTTPS), без тяжёлого SDK: нужны `sendMessage`, `setWebhook`, `answerCallbackQuery`.

## Фискализация — `FiscalProvider`
См. security.md §7. Не нужен для пилота (оплата при получении).
