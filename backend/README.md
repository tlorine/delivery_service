# Backend

FastAPI modular monolith: one image, processes `api` and `worker`. Architecture: [../docs/README.md](../docs/README.md).

## Layout
```
src/app/
  core/            config, DB + tenant guard (RLS), errors (RFC 9457), security, logging, rate limit
  modules/
    tenancy/       tenants, domains, branches, opening hours, tenant resolution, /v1/storefront
    identity/      staff, roles, sessions, /v1/admin/auth
    catalog/       categories, products, variants, modifiers, stop-list, /v1/storefront/menu
    pricing/       pure price + modifier rules (no I/O)
    cart/          server-side cart, /v1/cart
    delivery/      zones, point-in-polygon, DeliveryProvider port
    payments/      PaymentProvider port; cash / card on delivery
    customers/     buyers per tenant
    ordering/      checkout, order state machine, read model, /v1/orders, /v1/admin/orders
    notifications/ transactional outbox, worker, Telegram staff notifier
    telegram/      Bot API client, initData verification
    audit/         append-only audit log
  di.py            Dishka container (API, worker, CLI share it)
  main.py          FastAPI app factory
  worker.py        outbox worker entrypoint
  cli.py, seed.py  platform operations (owner role)
migrations/        Alembic (schema + RLS policies + grants)
tests/unit         pure logic
tests/integration  real PostgreSQL, app role under RLS
```

## Run locally without Docker
Requirements: Python 3.13+, [uv](https://docs.astral.sh/uv/), PostgreSQL 14+.
```sh
# once: roles and databases (owner `delivery`, application role `delivery_app`)
psql -U postgres -c "CREATE ROLE delivery LOGIN CREATEDB PASSWORD 'delivery'" \
  -c "CREATE ROLE delivery_app LOGIN PASSWORD 'delivery_app' NOBYPASSRLS" \
  -c "CREATE DATABASE delivery OWNER delivery" -c "CREATE DATABASE delivery_test OWNER delivery"
cp .env.example .env            # adjust URLs/ports
uv sync
uv run alembic upgrade head
uv run python -m app.cli seed-demo          # prints the owner login
uv run uvicorn app.main:app_factory --factory --reload    # http://localhost:8000/docs
uv run python -m app.worker                 # second terminal
```
With Docker: `docker compose up --build` in the repository root (see `docker-compose.yml`).

## Storefront E2E
```sh
pnpm --filter @nextorders/web-app build && pnpm --filter @delivery/admin build
E2E_PG_PORT=5432 pnpm test:e2e     # recreates the `delivery_e2e` DB (owner role needs CREATEDB), seeds a 24/7 demo cafe
```

## Checks
```sh
uv run pytest                     # TEST_DATABASE_URL / TEST_MIGRATOR_DATABASE_URL, defaults: localhost:54329
uv run ruff check src tests && uv run mypy
uv run python scripts/export_openapi.py          # after API changes; CI runs it with --check
uv run alembic revision --autogenerate -m "..."  # new migration; review it, add RLS for new tenant tables
```

## Rules of the codebase
- A request's tenant is set only in `di.TenantProvider`; services read it from `TenantContext`. Never accept `tenant_id` from a client.
- New tenant table: `TenantMixin` + `UniqueConstraint("tenant_id", "id")` + `tenant_fk(...)` for references + add it to RLS in the migration.
- Money: `int` minor units (`*_minor`). Never float.
- Status changes only through `OrderService` and `state_machine.check_transition`.
- Side effects outside the DB (Telegram, payments) go through the outbox, never inside the request transaction.
- Do not log personal data: phones, names, addresses, comments, tokens.

## Platform CLI
```sh
uv run python -m app.cli create-tenant <slug> "<Name>" --host <slug>.example.ru
STAFF_PASSWORD=... uv run python -m app.cli create-staff <slug> owner@cafe.ru "Имя" --role owner
TELEGRAM_BOT_TOKEN=... uv run python -m app.cli set-telegram-bot <slug> <bot_username> --chat-id <staff chat id>
```
