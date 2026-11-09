#!/bin/sh
# Fresh database, migrations, 24/7 demo cafe, then the API. Used by playwright.config.ts.
# Needs PostgreSQL with roles `delivery` (owner) and `delivery_app` (see backend/README.md).
set -eu
PG_HOST="${E2E_PG_HOST:-localhost}"
PG_PORT="${E2E_PG_PORT:-5432}"
DB="${E2E_DB:-delivery_e2e}"
cd "$(dirname "$0")/../backend"
PGPASSWORD="${E2E_PG_OWNER_PASSWORD:-delivery}" psql -h "$PG_HOST" -p "$PG_PORT" -U delivery -d postgres -qc "DROP DATABASE IF EXISTS $DB" -c "CREATE DATABASE $DB"
export MIGRATOR_DATABASE_URL="postgresql+asyncpg://delivery:delivery@$PG_HOST:$PG_PORT/$DB"
export DATABASE_URL="postgresql+asyncpg://delivery_app:delivery_app@$PG_HOST:$PG_PORT/$DB"
export GEOCODER=demo TRUST_FORWARDED_HOST=true ORDER_RATE_LIMIT_PER_MINUTE=1000 LOGIN_RATE_LIMIT_PER_MINUTE=1000 PLATFORM_API_HOSTS='["api.localhost"]' CORS_ORIGINS='["http://localhost:3080"]' LOG_LEVEL=WARNING
uv run alembic upgrade head
DEMO_OWNER_PASSWORD=e2e-owner-pass uv run python -m app.cli seed-demo --always-open >/dev/null
# Second cafe: the mobile app must keep carts and data separate per cafe.
DEMO_OWNER_PASSWORD=e2e-owner-pass uv run python -m app.cli seed-demo --always-open --slug second --host second.localhost --owner-email owner@second.local --name "Кофейня «Второе»" >/dev/null
STAFF_PASSWORD=e2e-staff-pass uv run python -m app.cli create-staff demo operator@demo.local "Оператор" --role operator
STAFF_PASSWORD=e2e-staff-pass uv run python -m app.cli create-staff demo manager@demo.local "Менеджер" --role manager
# Bot for Mini App tests: initData in tests is signed with this token (no real Telegram involved).
TELEGRAM_BOT_TOKEN="${E2E_BOT_TOKEN:-123456:E2E-TOKEN}" uv run python -m app.cli set-telegram-bot demo demo_bot >/dev/null
exec uv run uvicorn app.main:app_factory --factory --port "${E2E_API_PORT:-8078}"
