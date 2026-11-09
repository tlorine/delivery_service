# Технический индекс

Платформа прямых заказов для кафе (SaaS / white-label) на основе NextOrders. Один backend — много заведений; клиенты: Web, Telegram Mini App, Mobile; отдельно — админка.

| Хочу понять… | Документ |
|---|---|
| Что сейчас работает | [implementation/STATUS.md](implementation/STATUS.md) |
| План работ | [implementation/ROADMAP.md](implementation/ROADMAP.md) |
| Исходное состояние NextOrders | [audit/00-nextorders-audit.md](audit/00-nextorders-audit.md) |
| Общую схему, границы пакетов | [architecture/overview.md](architecture/overview.md) |
| Модули, сущности, машину состояний заказа | [architecture/domain-model.md](architecture/domain-model.md) |
| Таблицы и ER-диаграмму | [architecture/data-model.md](architecture/data-model.md) |
| API, ошибки, версионирование | [architecture/api-contract.md](architecture/api-contract.md) |
| Изоляцию тенантов, 152-ФЗ, 54-ФЗ | [architecture/security.md](architecture/security.md) |
| Платежи, доставку, уведомления | [architecture/integrations.md](architecture/integrations.md) |
| Деплой, бэкапы | [architecture/deployment.md](architecture/deployment.md) |
| Мобильное приложение: сборка, ссылки, публикация | [architecture/mobile.md](architecture/mobile.md) |
| Редизайн витрины | [design/storefront-redesign.md](design/storefront-redesign.md) |
| Почему так решили | [architecture/decisions/](architecture/decisions/) |
| Как запустить backend | [../backend/README.md](../backend/README.md) |

## Карта репозитория
```
backend/                FastAPI модульный монолит (Python), openapi.json — контракт
apps/web-app            Nuxt 4 витрина (Web + Telegram Mini App; SPA-сборка для Mobile)
apps/admin              Nuxt 4 SPA — панель заведения (ADR-0010)
apps/mobile             Capacitor 8 (Android, iOS) — оболочка SPA-сборки витрины
apps/essence            демо-бэкенд NextOrders (не используется, удаляется при обновлении lockfile)
apps/web-app-selector   выбор канала NextOrders (исключён из workspace, маркетплейс-паттерн)
packages/api-client     TS-типы из OpenAPI + типизированный fetch, formatMoney
packages/food-schema    view-model витрины (Zod)
packages/core           Nuxt layer: сторы, адаптер API→view, /v1 proxy, платформа
packages/ui             Nuxt layer: тема, i18n (ru по умолчанию)
e2e/                    Playwright: storefront/ и admin/ против реального backend + PostgreSQL
docker-compose.yml      локальная разработка: postgres, migrate, api, worker
docs/                   эта документация
```
