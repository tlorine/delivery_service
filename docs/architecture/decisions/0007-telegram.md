# ADR-0007. Telegram: Mini App = storefront с адаптером, бот на тенанта

Статус: принято · 2026-11-09

## Решение
- **Mini App** — тот же `apps/web-app`, открываемый по URL домена тенанта с `?tgWebApp…`. Платформа определяется по наличию `window.Telegram.WebApp.initData`. Адаптер `packages/core/app/platform/telegram`: `ready/expand`, тема → CSS-переменные, BackButton ↔ роутер, MainButton для «Оформить», haptics, safe area/viewport, `close()` после заказа. Бизнес-логика и компоненты общие.
- **Бот на тенанта.** Таблица `telegram_bots`: токен (зашифрован ключом приложения), `webhook_secret`, чат уведомлений кафе. Webhook: `POST /v1/telegram/webhook/{bot_id}` с проверкой `X-Telegram-Bot-Api-Secret-Token`.
- **Идентичность покупателя (реализовано, пересмотрено 2026-11-09).** Отдельной сессии и таблицы нет: при оформлении Mini App передаёт сырую строку `initData` в заголовке `X-Telegram-Init-Data`. Сервер: тенант определён по Host → бот *этого* тенанта → HMAC-SHA256 с ключом `HMAC("WebAppData", bot_token)` → `auth_date` не старше 24 ч и не из будущего → `customers.telegram_user_id`, `orders.channel = telegram`. Подпись бота другого кафе, подделка или просроченные данные → `401 invalid_init_data`. `initDataUnsafe` используется только для отображения (подстановка имени).
  - Почему не сессия: в MVP Telegram-личность нужна только в момент заказа (привязка для уведомлений о статусе); 24 ч жизни `initData` покрывают сценарий без хранения токенов. Сессия понадобится для «моих заказов» и бонусов — тогда добавим `POST /v1/telegram/session` поверх той же проверки.
- **Бот.** Webhook `POST /v1/telegram/webhook/{bot_id}` проверяет `X-Telegram-Bot-Api-Secret-Token`. Команды: `/start` — приветствие и кнопка Mini App; `/link <код>` в чате сотрудников — подключает уведомления (код — HMAC от секрета приложения, без хранения). Ответ отдаётся телом webhook-а, без дополнительных вызовов API. Настройка: `python -m app.cli telegram-setup <tenant> --public-url https://…` (webhook + кнопка меню).
- **Уведомления покупателю** о создании и смене статуса заказа — через бота кафе, если заказ сделан из Mini App.
- **Фронтенд:** скрипт `telegram-web-app.js` загружается только при открытии внутри Telegram (по `#tgWebAppData`) — обычные посетители сайта не обращаются к telegram.org.

## Почему не отдельное Telegram-приложение
Отдельная SPA дублировала бы каталог, корзину, checkout. Отличия Telegram — навигация, кнопки, тема — укладываются в адаптер и пару условных компонентов.
