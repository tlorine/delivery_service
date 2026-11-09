# D1. Проверка `chokidar@4.0.3` перед исключением из trust policy

Дата: 2026-11-09. Причина: `trustPolicy: no-downgrade` блокирует любое изменение `pnpm-lock.yaml`, так как у `chokidar@4.0.3` нет provenance, а у более ранних `4.0.0`/`4.0.1` она есть. Пакет транзитивный (`@netlify/blobs@9.1.2` ← сборка Nuxt), уже залочен в upstream-lockfile NextOrders.

Все артефакты проверялись в изолированной папке, код пакета не выполнялся.

## Вывод
**Подозрительных признаков не найдено.** Отсутствие provenance объясняется ручной публикацией `npm publish` с машины автора (так же опубликована и `4.0.2`), а не сменой издателя. Опубликованный код побайтно совпадает со сборкой из подписанного тега. Применено точечное `trustPolicyExclude: ['chokidar@4.0.3']`, общая политика не ослаблена.

## Доказательства
| Проверка | Результат | Как проверено |
|---|---|---|
| Издатель | `_npmUser = paulmillr` у 3.6.0, 4.0.0, 4.0.1, 4.0.2, **4.0.3** — тот же единственный maintainer; с 5.0.0 публикует GitHub Actions (с provenance) | `registry.npmjs.org/chokidar` |
| Репозиторий | `git+https://github.com/paulmillr/chokidar.git`, совпадает у всех версий | метаданные registry |
| Provenance | нет у 4.0.2 и 4.0.3 (обе — ручные публикации в декабре 2024); есть у 4.0.0, 4.0.1, 5.0.0 | `dist.attestations` |
| История релизов | 4.0.2 — 2024-12-16, 4.0.3 — 2024-12-18, далее 5.0.0 — 2025-11-25; аномальных всплесков нет | `time` в registry |
| Тег и коммит | тег `4.0.3` → коммит `1182965a0d3d884f15db423009262778ddba0ac4` «Release 4.0.3.» (Paul Miller, 2024-12-18 22:20:06 UTC); **GitHub: verified = true, reason = valid**; объект тега подписан | GitHub API, `git cat-file` |
| Время публикации | npm: 22:21:34 UTC — через 88 с после коммита релиза | registry `time` |
| Целостность | sha512 скачанного tarball = `sha512-Qgzu8kfBvo+cA4962jnP…tnA==` = значение в `pnpm-lock.yaml` и в registry | `openssl dgst -sha512` |
| Подпись registry | ECDSA P-256 над `chokidar@4.0.3:<integrity>`: **Verified OK** ключом npm `SHA256:jl3bwswu80PjjokCgh0o2w5…` (действовал до 2025-01-29; подпись от 2024-12-18 — в периоде действия, затем плановая ротация ключей npm) | `/-/npm/v1/keys` + `openssl dgst -verify` |
| Соответствие исходникам | `src/` тега скомпилирован локальным TypeScript (без установки зависимостей пакета, без выполнения его кода) с опциями пресетов `@paulmillr/jsbt@0.2.1`: **`index.js`, `handler.js` (CJS и ESM) побайтно идентичны tarball**; `handler.d.ts` идентичен; в `index.d.ts` 1 строка отличается (`any` вместо `ReaddirpStream \| undefined` — в нашей сборке не было типов `readdirp`; на runtime не влияет); `package.json`, `README.md`, `LICENSE`, `esm/package.json` идентичны тегу | `tsc` 5.9.3 из нашего workspace, `cmp`/`diff` |
| Install scripts | нет `preinstall`/`install`/`postinstall`/`prepare`; scripts — только `build`, `lint`, `format`, `test` | `package.json` tarball |
| Состав tarball | 12 файлов: JS/`.d.ts` (CJS + ESM), README, LICENSE, package.json; нет бинарников и `bin` | `tar -t` |
| Опасные API | импорты только `fs`, `fs/promises`, `os`, `path`, `events`, `readdirp`; нет `child_process`, `eval`, `new Function`, сетевых модулей; URL — только в комментариях; env — документированные `CHOKIDAR_USEPOLLING`, `CHOKIDAR_INTERVAL` | `grep` по коду |
| Зависимость | `readdirp@^4.0.1` → в lockfile `readdirp@4.1.2`: издатель paulmillr, **provenance есть**, своих зависимостей и install scripts нет | registry, lockfile |
| Уязвимости | OSV: 0 для `chokidar@4.0.3`, 0 для `readdirp@4.1.2` | `api.osv.dev/v1/query` |

## Что не удалось проверить
- Полная воспроизводимая сборка штатным путём (`npm ci` + `npm run build` из lockfile пакета) заблокирована политикой среды — установка и запуск стороннего кода. Заменена компиляцией исходников тега доверенным компилятором; для JS результат побайтно совпал.
- Подпись тега локально не проверена (нет gpg); статус «verified» взят из GitHub API.

## Решение
`trustPolicyExclude` только для `chokidar@4.0.3` в `pnpm-workspace.yaml` со ссылкой на этот отчёт. При обновлении Nuxt/`@netlify/blobs`, когда зависимость уйдёт, исключение удаляется.
