# API-контракт

- База: `/v1`. Источник истины — OpenAPI, генерируемый FastAPI (`/v1/openapi.json`, файл `backend/openapi.json` в репозитории). TS-клиент — `packages/api-client` (`pnpm gen:api`).
- JSON, `snake_case`. Деньги — `*_minor: int` + `currency`. Время — ISO 8601 с зоной.

## Определение тенанта
| Поверхность | Механизм |
|---|---|
| Storefront (web, Telegram) | `Host` (через прокси — `X-Forwarded-Host` только от доверенного прокси) |
| Mobile / dev | `X-Tenant: <slug>` (используется, если Host — домен API платформы) |
| Admin | сессия сотрудника + `X-Tenant-Id` среди его членств (проверяется) |
| Telegram webhook | `bot_id` в пути + секрет в заголовке |

Тело запроса никогда не содержит `tenant_id`.

## Эндпоинты (MVP)
### Storefront — публичные
| Метод | Путь | Описание |
|---|---|---|
| GET | `/v1/storefront` | Конфиг витрины: название, брендинг, локаль, валюта, филиалы, способы получения/оплаты, статус «открыто» |
| GET | `/v1/storefront/time-slots?branch_id=&fulfillment=` | Доступное время для заказа ко времени (шаг 30 мин, сегодня и завтра) |
| GET | `/v1/address/suggest?q=&limit=` | Подсказки адреса с координатами вокруг филиалов кафе (`Geocoder`: DaData / demo / none). Без подсказок `storefront.address_suggest_enabled = false` и витрина предлагает только самовывоз |
| GET | `/v1/storefront/menu?branch_id=` | Категории → товары → варианты, группы модификаторов, доступность в филиале |
| POST | `/v1/carts` | Создать корзину → `{cart_token, cart}` |
| GET | `/v1/cart` | Корзина по `X-Cart-Token` с актуальным расчётом |
| POST | `/v1/cart/items` | `{variant_id, quantity, modifiers:[{modifier_id, quantity}]}` |
| PATCH / DELETE | `/v1/cart/items/{item_id}` | Изменить количество / удалить |
| POST | `/v1/checkout/quote` | Предрасчёт: способ получения, адрес → доставка, итог, ошибки валидации |
| POST | `/v1/orders` | Оформление. Заголовки `X-Cart-Token`, `Idempotency-Key`. → `201 {order, order_token}` |
| GET | `/v1/orders/{order_token}` | Статус и состав заказа для покупателя |
| POST | `/v1/orders/{order_token}/cancel` | Отмена покупателем (только из `pending`) |
| — | заголовок `X-Telegram-Init-Data` у `POST /v1/orders` | Подписанные данные Mini App; сервер проверяет ботом кафе и привязывает заказ к Telegram-пользователю (ADR-0007) |

### Admin — `/v1/admin/*`, сессия сотрудника
**Реализовано:** `auth/login`, `auth/logout`, `auth/me`; `orders` (список с фильтром по статусу/филиалу и курсором `before`, карточка с `next_statuses`, `POST orders/{id}/transitions {to_status, reason}`).

**Управление (этап 5, реализовано):**

| Роль ≥ | Эндпоинты |
|---|---|
| operator | `GET catalog`; `GET branches`; `GET/PUT branches/{id}/stoplist/(variants\|modifiers)/{id}`; заказы |
| manager | `POST/PATCH/DELETE categories`, `products`, `products/{id}/variants`, `variants/{id}`, `modifier-groups`, `modifier-groups/{id}/modifiers`, `modifiers/{id}`; `PUT products/{id}/modifier-groups`; `PATCH branches/{id}`; `PUT branches/{id}/hours`; `GET/POST branches/{id}/delivery-zones`, `PATCH/DELETE delivery-zones/{id}`; `GET analytics/summary?days=` |
| owner | `GET/PATCH settings` (название; брендинг: `logo_url`, `description`, `copyright`, `accent_color` — строго `#RRGGBB`, нормализуется к верхнему регистру, `cover_url` — только `https://`; статус Telegram и команда `/link`); `GET/POST staff`, `PATCH/DELETE staff/{user_id}` |

Удаление того, что уже есть в заказах, — `409 *_has_orders` (скрыть через `is_active: false`). Деньги во входных схемах — строго JSON-целые (`"100"` и `1.0` отклоняются).

### Служебные
`GET /health/live`, `GET /health/ready` (проверка БД); `POST /v1/telegram/webhook/{bot_id}` (секрет в `X-Telegram-Bot-Api-Secret-Token`; не в OpenAPI); `POST /v1/payments/webhook/{provider}` (после MVP).

## Ошибки — RFC 9457 `application/problem+json`
```json
{
  "type": "about:blank",
  "title": "Conflict",
  "status": 409,
  "code": "price_changed",
  "detail": "prices have changed",
  "extra": { "quote": { "total_minor": 141000, "...": "..." } }
}
```
Ошибки валидации схемы: `code: "validation_error"` + `errors: [{loc, code, message}]`. Нарушения бизнес-правил при оформлении: `422` + `extra.problems: [{code, detail, item_id}]` (все найденные проблемы, а не только первая).
`code` — стабильный машинный идентификатор; клиенты локализуют по нему. Полный список кодов MVP:

| HTTP | Коды |
|---|---|
| 401/403 | `unauthorized`, `invalid_credentials`, `session_expired`, `forbidden`, `insufficient_role`, `tenant_access_denied`, `csrf_check_failed`, `tenant_suspended`, `invalid_init_data` |
| 404 | `tenant_not_found`, `not_found`, `cart_not_found`, `cart_item_not_found`, `product_not_found`, `branch_not_found`, `order_not_found` |
| 409 | `price_changed`, `cart_already_checked_out`, `invalid_status_transition`, `reason_required`, `product_has_orders`, `variant_has_orders`, `modifier_has_orders`, `group_has_orders`, `category_not_empty`, `slug_taken` |
| 422 | `validation_error`, `cart_empty`, `cart_too_large`, `item_unavailable`, `invalid_modifiers`, `branch_required`, `address_required`, `branch_closed`, `invalid_requested_time`, `fulfillment_unavailable`, `outside_delivery_zone`, `below_min_order`, `payment_method_unavailable`, `invalid_change`, `invalid_phone`, `idempotency_key_reused`, `last_variant`, `invalid_bounds`, `invalid_polygon`, `invalid_hours`, `no_fulfillment`, `last_owner`, `cannot_remove_self`, `password_required`, `already_member` |
| 429 | `rate_limited` |

## Версионирование и совместимость
- Внутри `/v1` — только аддитивные изменения: новые эндпоинты, новые необязательные поля запроса, новые поля ответа. Клиенты игнорируют неизвестные поля и значения enum (показывают общий вид).
- Breaking → `/v2`, `/v1` поддерживается не менее 6 месяцев (мобильные сборки). Мобильный клиент шлёт `X-Client: mobile/<version>`; сервер может ответить `426` с `min_version` для принудительного обновления.
- CI: `openapi.json` перегенерируется и сравнивается; удаление поля/эндпоинта в `/v1` — ошибка ревью (oasdiff — в план).
