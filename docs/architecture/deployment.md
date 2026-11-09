# Развёртывание

## Компоненты
| Сервис | Образ | Процесс |
|---|---|---|
| `api` | `backend` | `uvicorn app.main:app` |
| `worker` | `backend` | `python -m app.worker` |
| `migrate` | `backend` | `alembic upgrade head` (one-shot перед `api`) |
| `web` | `web-app` | Nuxt SSR (`node .output/server/index.mjs`) |
| `admin` | `admin` | статика SPA за прокси |
| `postgres` | `postgres:17` | — |
| `proxy` | `caddy:2` | TLS (в т.ч. on-demand для собственных доменов), маршрутизация `/v1` → api, остальное → web |

Маршрутизация: `*.<platform-domain>` и собственные домены → прокси → `/v1/*` на api (тот же origin — без CORS и с корректным Host для определения тенанта), остальное → web. Админка — `admin.<platform-domain>`.

## Образы и CI
| Workflow | Когда | Что |
|---|---|---|
| `ci.yml` | push в `main`, PR в `main` | lint, typecheck, unit, сборка, E2E (витрина, админка, мобильная SPA-сборка) против backend + PostgreSQL 17 |
| `backend.yml` | push/PR с изменениями `backend/**` | ruff, mypy, актуальность OpenAPI, миграции без дрейфа, pytest, сборка образа |
| `images.yml` | push в `main` (код/Dockerfile) или вручную | образы `ghcr.io/<repo>/backend`, `…/web-app`, `…/admin` с тегами `main` и SHA коммита |

Dockerfile: `backend/Dockerfile`, `docker/web-app/Dockerfile`, `docker/admin/Dockerfile` (контекст — весь workspace, установка `--frozen-lockfile` с фильтром приложения; `.dockerignore` исключает backend, документацию, нативные проекты). Workflow-ы NextOrders (публикация `@nextorders/food-schema` в npm, деплой их демо в Kubernetes, образы essence/selector) удалены.

## Окружения и секреты
Backend: `TRUST_FORWARDED_HOST=true` за прокси/витриной (тенант по `X-Forwarded-Host`), `GEOCODER=dadata` + `DADATA_API_KEY` для доставки. Мобильное приложение: хост API в `PLATFORM_API_HOSTS`, `CORS_ORIGINS` = `["https://localhost","capacitor://localhost"]` (mobile.md). Витрина: `NUXT_API_INTERNAL_URL` (адрес API для SSR), `NUXT_PROXY_API=false`, если `/v1` маршрутизирует reverse proxy.

Конфигурация — переменные окружения (pydantic-settings), шаблон `backend/.env.example`. Секреты: `DATABASE_URL`, `MIGRATOR_DATABASE_URL`, `APP_ENCRYPTION_KEY`, `SESSION_SECRET`. В production — файлы Docker secrets или переменные из хранилища секретов облака, не в git.

## Локальная разработка
`docker compose up` — postgres, api, worker, web. Без Docker: `backend/` через `uv`, PostgreSQL локально (см. backend/README.md).

## Production (первый этап)
Одна VM в российском ДЦ (2 vCPU / 4 GB достаточно для десятков кафе), Docker Compose. Без Kubernetes: один инстанс api + worker. Масштабирование: managed PostgreSQL → несколько инстансов api за прокси (rate limit переносится в прокси/Redis, ADR-0006).

## Резервное копирование
- Managed PostgreSQL провайдера с PITR — предпочтительно.
- Иначе: ежедневный `pg_dump -Fc` (сервис `backup` в compose) в S3-совместимое хранилище в РФ, хранение 30 дней, WAL-архивация (wal-g) для PITR. Ежемесячная проверка восстановления — пункт регламента.

## Логи PostgreSQL
При ошибках PostgreSQL пишет в свой лог текст запроса (`log_min_error_statement = error` по умолчанию); при `log_statement`/`log_min_duration_statement` — и параметры. Запросы к `orders`/`customers` содержат ПДн, поэтому в production: `log_min_error_statement = panic`, `log_statement = none`, `log_parameter_max_length_on_error = 0`, срок хранения логов СУБД ограничен.

## Наблюдаемость
JSON-логи в stdout; `request_id` сквозной (`X-Request-Id`). `/health/live`, `/health/ready`. Метрики Prometheus и Sentry (self-hosted или российская альтернатива) — этап стабилизации.
