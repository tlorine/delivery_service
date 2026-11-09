# Модель данных

PostgreSQL 16+. Первичные ключи — UUID v7-совместимые (генерируются приложением, сортируемы по времени). Время — `timestamptz` (UTC); локальное время заведения вычисляется по `branches.timezone` (IANA, напр. `Europe/Moscow`). Деньги — `bigint` в копейках (ADR-0008).

Обозначения: 🔒 — тенантная таблица с RLS (ADR-0002).

```mermaid
erDiagram
  tenants ||--o{ tenant_domains : "host →"
  tenants ||--o| telegram_bots : has
  tenants ||--o{ memberships : ""
  staff_users ||--o{ memberships : ""
  staff_users ||--o{ staff_sessions : ""
  tenants ||--o{ branches : ""
  branches ||--o{ branch_hours : ""
  branches ||--o{ delivery_zones : ""
  branches ||--o{ stoplist_entries : ""
  tenants ||--o{ categories : ""
  categories ||--o{ products : ""
  products ||--o{ product_variants : ""
  products ||--o{ product_modifier_groups : ""
  modifier_groups ||--o{ product_modifier_groups : ""
  modifier_groups ||--o{ modifiers : ""
  tenants ||--o{ customers : ""
  tenants ||--o{ carts : ""
  carts ||--o{ cart_items : ""
  carts ||--o| orders : "checked out as"
  branches ||--o{ orders : ""
  customers ||--o{ orders : ""
  orders ||--o{ order_items : ""
  order_items ||--o{ order_item_modifiers : ""
  orders ||--o{ order_status_changes : ""
  tenants ||--o{ audit_log : ""
  tenants ||--o{ outbox_events : ""

  tenants { uuid id PK; text slug UK; text name; text status; char3 currency; text locale; text timezone; jsonb branding; jsonb settings }
  tenant_domains { uuid id PK; uuid tenant_id FK; text host UK; bool is_primary }
  telegram_bots { uuid id PK; uuid tenant_id UK; bigint bot_id UK; text username; bytea token_encrypted; text webhook_secret; bigint notify_chat_id; bool is_active }
  staff_users { uuid id PK; text email UK; text password_hash; text name; bool is_active }
  staff_sessions { uuid id PK; uuid user_id FK; bytea token_hash UK; timestamptz expires_at; timestamptz revoked_at }
  memberships { uuid tenant_id PK; uuid user_id PK; text role }
  branches { uuid id PK; uuid tenant_id; text name; text address; float lat; float lon; text timezone; bool is_active; bool delivery_enabled; bool pickup_enabled; int prep_time_min; int delivery_time_min; text_arr payment_methods }
  branch_hours { uuid id PK; uuid tenant_id; uuid branch_id; smallint weekday; time opens_at; time closes_at }
  delivery_zones { uuid id PK; uuid tenant_id; uuid branch_id; text name; jsonb polygon; bigint fee_minor; bigint min_order_minor; bigint free_from_minor; int priority; bool is_active }
  categories { uuid id PK; uuid tenant_id; text slug; text name; int sort; bool is_active }
  products { uuid id PK; uuid tenant_id; uuid category_id; text slug; text name; text description; text image_url; int sort; bool is_active }
  product_variants { uuid id PK; uuid tenant_id; uuid product_id; text name; bigint price_minor; int weight_value; text weight_unit; int sort; bool is_active }
  modifier_groups { uuid id PK; uuid tenant_id; text name; int min_selected; int max_selected; int sort }
  modifiers { uuid id PK; uuid tenant_id; uuid group_id; text name; bigint price_minor; int max_quantity; int sort; bool is_active }
  product_modifier_groups { uuid tenant_id; uuid product_id PK; uuid group_id PK; int sort }
  stoplist_entries { uuid id PK; uuid tenant_id; uuid branch_id; uuid variant_id; uuid modifier_id }
  customers { uuid id PK; uuid tenant_id; text phone; text name; bigint telegram_user_id }
  carts { uuid id PK; uuid tenant_id; bytea token_hash UK; text status; timestamptz expires_at }
  cart_items { uuid id PK; uuid tenant_id; uuid cart_id; uuid variant_id; int quantity; jsonb modifiers; text line_key }
  orders { uuid id PK; uuid tenant_id; int number; uuid branch_id; uuid cart_id UK; uuid customer_id; text status; text fulfillment; text payment_method; text payment_status; text channel; bigint subtotal_minor; bigint delivery_fee_minor; bigint total_minor; text idempotency_key; bytea request_hash; bytea public_token_hash UK; timestamptz promised_at; timestamptz pd_consent_at }
  order_items { uuid id PK; uuid tenant_id; uuid order_id; uuid variant_id; text product_name; text variant_name; bigint unit_price_minor; int quantity; bigint line_total_minor }
  order_item_modifiers { uuid id PK; uuid tenant_id; uuid order_item_id; uuid modifier_id; text name; bigint unit_price_minor; int quantity }
  order_status_changes { uuid id PK; uuid tenant_id; uuid order_id; text from_status; text to_status; text actor_type; uuid actor_id; text reason }
  audit_log { uuid id PK; uuid tenant_id; text actor_type; uuid actor_id; text action; text entity_type; uuid entity_id; jsonb data }
  outbox_events { bigint id PK; uuid tenant_id; text type; jsonb payload; text status; int attempts; timestamptz available_at; text last_error }
```

## Ключевые ограничения
| Ограничение | Зачем |
|---|---|
| `UNIQUE (tenant_id, slug)` в `categories`, `products` | одинаковые slug у разных кафе допустимы |
| `UNIQUE tenant_domains.host` (в нижнем регистре) | однозначное определение тенанта |
| `UNIQUE (tenant_id, idempotency_key)` в `orders` | идемпотентность оформления |
| `UNIQUE orders.cart_id` | корзина оформляется один раз |
| `UNIQUE (tenant_id, number)` в `orders` | номер заказа для людей, счётчик на тенанта (`tenant_counters`, `UPDATE … RETURNING`) |
| `UNIQUE (tenant_id, phone)` в `customers` (частичный, phone not null) | один покупатель на телефон в рамках кафе |
| Составные FK `(tenant_id, id)` для ссылок внутри тенанта | невозможно сослаться на филиал/товар чужого тенанта даже ошибкой кода |
| CHECK `price_minor >= 0`, `quantity > 0`, `min_selected <= max_selected` | инварианты на уровне БД |

## Снимки заказа
`order_items` и `order_item_modifiers` хранят названия и цены на момент оформления. Изменение меню не меняет историю. Ссылки `variant_id`/`modifier_id` сохраняются для аналитики (`ON DELETE RESTRICT`: товар, по которому были заказы, архивируется — `is_active = false` — а не удаляется).

## ПДн
Персональные данные: `customers.phone/name/telegram_user_id`, в `orders` — имя, телефон, адрес, комментарий. Хранение — см. security.md §5 (сроки, обезличивание).
