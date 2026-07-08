# Структура монорепо: директории, файлы, маппинг модулей

> ⚠️ **SUPERSEDED (2026-07-07).** Выбор изменён на распределённую многорепо-топологию
> со строгой инкапсуляцией — см.
> [2026-07-07-distributed-repo-topology.md](./2026-07-07-distributed-repo-topology.md).
> Этот документ сохранён для истории: маппинг модулей `app/* → сервер` и внутренняя
> раскладка каждого сервера остаются в силе, меняется только упаковка (не один
> workspace, а отдельные репозитории по архетипам).

**Дата:** 2026-07-07 · **Статус:** superseded · Дополняет
[2026-07-07-mcp-microservices-split.md](./2026-07-07-mcp-microservices-split.md).

Принятые решения: **монорепо + `uv` workspace**; провайдеры как **плоские
`mcpServers`** сейчас, `music-gateway` — отдельный сервер позже (структура уже
заложена, встанет без переделок).

Документ описывает: (1) корневое дерево workspace, (2) внутреннюю раскладку
каждого сервера, (3) назначение каждого файла, (4) куда переезжает каждый
текущий `app/*` модуль.

---

## 1. Корневое дерево workspace

```text
dj-music-plugin/                      # корень репо = корень uv workspace
├── pyproject.toml                    # [tool.uv.workspace] members = ["packages/*", "servers/*"]
├── uv.lock                           # ОДИН lock на весь workspace
├── Makefile                          # make check/test/arch — на весь workspace + per-server
├── .importlinter                     # межпакетные контракты (расширяем существующие)
├── .env / .env.example               # общий dev-env (токены всех серверов)
├── README.md · CHANGELOG.md · CLAUDE.md · AGENTS.md · LICENSE
│
├── .claude-plugin/
│   ├── plugin.json                   # ОДИН плагин, N ключей в mcpServers (см. §5)
│   └── marketplace.json              # витрина (позже git-subdir на servers/*)
│
├── packages/
│   └── dj-shared/                    # общий пакет-контракт (см. §2)
│
├── servers/
│   ├── core/                         # stateful ядро: БД, модели, домен (см. §3)
│   ├── yandex/                       # stateless provider (см. §4)
│   ├── beatport/                     # stateless provider
│   ├── soundcloud/                   # stateless provider (адаптер писать с нуля)
│   ├── suno/                         # stateless generation provider
│   └── music-gateway/                # ПОЗЖЕ: агрегатор провайдеров (§4.4)
│
├── migrations/                       # Alembic (владелец схемы — core, но миграции общие)
├── docs/ · scripts/ · tests/         # общие; per-server тесты внутри серверов
└── hooks/pre-push                    # существующий локальный гейт (make check)
```

**Ключевой принцип:** каждый `servers/*` и `packages/*` — самостоятельный
Python-пакет со своим `pyproject.toml`. Они видят друг друга как
workspace-зависимости (`dj-shared = { workspace = true }`), но собираются и
запускаются независимо. Один `uv.lock` гарантирует единые версии внешних
зависимостей во всём репо.

---

## 2. `packages/dj-shared/` — общий контракт

Всё, что **обязано** совпадать между серверами: протоколы, canonical-схемы
треков, DJ-константы, ошибки, утилиты. Провайдеры и core зависят от `dj-shared`,
но **не** друг от друга.

```text
packages/dj-shared/
├── pyproject.toml                    # name = "dj-shared", без тяжёлых зависимостей
└── src/dj_shared/
    ├── __init__.py
    ├── provider.py                   # ← app/registry/provider.py (Provider Protocol, ProviderRegistry)
    ├── canonical/                    # canonical DTO обмена «провайдер → core»
    │   ├── track.py                  # CanonicalTrack, CanonicalArtist, CanonicalAlbum
    │   ├── search.py                 # SearchResult, SearchType
    │   └── external_id.py            # ExternalId (provider, external_id, url)
    ├── constants.py                  # ← app/shared/constants.py (BPM/Camelot/LUFS enums)
    ├── camelot.py                    # ← Camelot-таблицы (из reference), pure
    ├── errors.py                     # ← app/shared/errors.py (NotFoundError, ValidationError, AuthFailedError…)
    ├── time.py                       # ← app/shared/time.py (utc_now, sa_now)
    ├── ids.py · filters.py · pagination.py   # ← app/shared/* (leaf-утилиты)
    ├── ratelimit.py                  # общий TokenBucketRateLimiter (сейчас дублируется в каждом провайдере)
    └── config_base.py                # базовый pydantic-settings класс (env_prefix helper)
```

**Что переезжает сюда из `app/`:**
- `app/registry/provider.py` → `provider.py` (протокол — сердце развязки);
- `app/shared/{constants,errors,time,ids,filters,pagination}.py` → соответствующие файлы;
- Camelot-логика из `app/resources/reference` + `app/domain/camelot` (pure-часть) → `camelot.py`;
- три копии `rate_limiter.py` (yandex/beatport/suno) → один `ratelimit.py`.

**Правило import-linter:** `dj_shared` — leaf. Не импортит ни core, ни провайдеров,
ни `fastmcp`, ни `sqlalchemy`, ни `librosa`. Только stdlib + pydantic.

---

## 3. `servers/core/` — stateful ядро (БД + домен)

Это «MCP-сервер для работы с БД» из твоего описания + весь compute. Владелец
Supabase, identity трека (`tracks`), домена и workflow-prompt'ов. Сюда переезжает
бо́льшая часть текущего `app/`.

```text
servers/core/
├── pyproject.toml                    # name = "dj-core"; deps: fastmcp, sqlalchemy, dj-shared, (audio опц.)
├── fastmcp.json                      # entrypoint = mcp, transport stdio
├── server.py                         # from dj_core.server.app import build_mcp_server; mcp = build_mcp_server()
└── src/dj_core/
    ├── server/                       # ← app/server/*  (composition root, middleware, lifespan, di, transforms…)
    ├── models/                       # ← app/models/*   (SQLAlchemy 2.0, one file per aggregate root)
    ├── repositories/                 # ← app/repositories/*  (BaseRepository[M], UnitOfWork)
    ├── handlers/                     # ← app/handlers/*  (track_import и пр. — см. §3.1)
    ├── domain/                       # ← app/domain/*    (transition/optimization/camelot/template/audit/render)
    ├── registry/                     # ← app/registry/*  БЕЗ provider.py (он в dj-shared) — только EntityRegistry
    ├── schemas/                      # ← app/schemas/*   (entity View/Filter/Create/Update DTO)
    ├── db/                           # ← app/db/*        (session, engine, PRAGMA FK)
    ├── config/                       # ← app/config/*    (per-domain settings; base — из dj-shared)
    ├── tools/
    │   ├── entity/                   # ← app/tools/entity/*   (entity_list/get/create/update/delete/aggregate)
    │   ├── compute/                  # ← app/tools/compute/*  (transition, sequence_optimize)
    │   ├── sync/                     # ← app/tools/sync/*     (playlist_sync)
    │   ├── admin/                    # ← app/tools/admin/*    (unlock_namespace, tool_invoke)
    │   ├── ui/                       # ← app/tools/ui/*       (6 Prefab Apps)
    │   └── provider/                 # provider_read/write/search — ТОНКИЕ (см. §3.1)
    ├── resources/                    # ← app/resources/*  (local://, schema://, session://, reference://)
    └── prompts/                      # ← app/prompts/*    (30 workflow recipes)
```

### 3.1 Ключевое изменение: как core общается с провайдерами

Сейчас `track_import` handler **импортирует** yandex-клиент напрямую. После
распила провайдер — отдельный процесс, поэтому:

- `servers/core/src/dj_core/providers_client.py` (новый) — тонкий MCP-клиент,
  который вызывает provider-серверы (yandex/beatport/…) по их именам как MCP-tools
  (`fastmcp.Client`). Это единственная точка, где core «знает» о существовании
  провайдер-серверов.
- `provider_read/write/search` tools в core становятся **прокси-обёртками**: они
  форвардят вызов в нужный provider-сервер через `providers_client` и (для write-
  операций импорта) сохраняют результат в Supabase.
- `track_import` handler: `providers_client.read("yandex", "track", id)` → получил
  `CanonicalTrack` → резолвит/создаёт `tracks.id` + пишет `track_external_ids` +
  `yandex_metadata`. Вся persist-логика остаётся в core.

> Альтернатива без клиента: если позже поднимешь `music-gateway`, core вызывает
> **один** gateway вместо N провайдеров. `providers_client` меняет только адрес.

### 3.2 Что НЕ переезжает сразу

`app/audio/` (4466 строк, librosa/numba) остаётся физически внутри `core` как
пакет `src/dj_core/audio/` **на Фазе 1–3**, но с прицелом на вынос в
`servers/audio-analysis/` (Фаза 4). Держи его уже сейчас за чистой границей
(import-linter уже это делает), чтобы вынос был механическим.

---

## 4. `servers/<provider>/` — stateless провайдеры

Единый шаблон для yandex / beatport / soundcloud / suno. Провайдер = обёртка
внешнего API, возвращает `CanonicalTrack`/`SearchResult` из `dj-shared`, **ничего
не пишет в Supabase**.

### 4.1 Шаблон (на примере yandex)

```text
servers/yandex/
├── pyproject.toml                    # name = "dj-yandex"; deps: fastmcp, httpx, dj-shared
├── fastmcp.json                      # entrypoint = mcp, stdio
├── server.py                         # mcp = build_yandex_server()
├── README.md                         # что за сервер, какие env нужны
└── src/dj_yandex/
    ├── __init__.py
    ├── server.py                     # FastMCP("dj-yandex"), регистрация tools
    ├── config.py                     # YandexSettings(env_prefix="DJ_YM_")  ← app/config/yandex.py
    ├── client.py                     # ← app/providers/yandex/client.py  (raw httpx)
    ├── adapter.py                    # ← app/providers/yandex/adapter.py (Provider protocol impl)
    ├── filters.py                    # ← app/providers/yandex/filters.py
    └── tools/
        ├── read.py                   # @tool provider_read  (track, album, artist_tracks, playlist, likes…)
        ├── write.py                  # @tool provider_write (playlist create/add/remove, likes add/remove)
        ├── search.py                 # @tool provider_search (tracks/albums/artists/playlists)
        └── download.py               # @tool download_audio → возвращает путь/URL (без записи в БД)
```

Внутри `tools/*.py` — тонкие FastMCP-обёртки над `adapter.py`. Никакого UoW, БД,
`Depends(get_uow)` здесь нет — сервер stateless.

### 4.2 Раскладка провайдеров и источник кода

| Сервер | Из чего | Статус |
|---|---|---|
| `servers/yandex` | `app/providers/yandex/*` + `app/config/yandex.py` | код есть, переносим |
| `servers/beatport` | `app/providers/beatport/*` (client, adapter, canonical, matcher, rate_limiter) | код есть |
| `servers/suno` | `app/providers/suno/*` (client, adapter, endpoints, endpoints_web, session_auth) | код есть, opt-in |
| `servers/soundcloud` | адаптера нет — только dead-таблица `soundcloud_metadata` | писать с нуля или отложить |

### 4.3 Env-переменные провайдеров (передавать явно через plugin `mcpServers.env`)

stdio-серверы **не** наследуют env шелла. Каждому провайдеру — свой набор:
`DJ_YM_TOKEN`/`DJ_YM_USER_ID` (yandex), `DJ_BEATPORT_*` (beatport),
`DJ_SUNO_*` (suno). Секреты живут в общем `.env`, но каждому серверу
пробрасываются нужные ключи (см. §5).

### 4.4 `servers/music-gateway/` — позже, структура заложена

```text
servers/music-gateway/
├── pyproject.toml                    # deps: fastmcp, dj-shared
├── fastmcp.json
├── server.py
└── src/dj_gateway/
    ├── server.py                     # create_proxy(config) ИЛИ mount(create_proxy(...), namespace=)
    ├── config.py                     # адреса провайдер-серверов (stdio команды / http url)
    └── tools/
        └── unified.py                # @tool unified_search — кросс-провайдерный поиск + дедуп по external_id
```

Появляется, когда нужен единый фасад. До этого core ходит в провайдеров напрямую
через `providers_client` (§3.1).

---

## 5. Манифест плагина: N серверов в одном плагине

`.claude-plugin/plugin.json` — один плагин `dj-music`, в `mcpServers` по ключу на
сервер. Пути — через `${CLAUDE_PLUGIN_ROOT}`, состояние — `${CLAUDE_PLUGIN_DATA}`.

```jsonc
{
  "name": "dj-music",
  "version": "2.0.0",
  "mcpServers": {
    "core": {
      "command": "bash",
      "args": ["-c",
        "cd \"${DJ_PLUGIN_DEV_PATH:-${CLAUDE_PLUGIN_ROOT}}/servers/core\" && set -a && source ../../.env 2>/dev/null && set +a && exec uv run fastmcp run fastmcp.json --no-banner"]
    },
    "yandex": {
      "command": "bash",
      "args": ["-c",
        "cd \"${DJ_PLUGIN_DEV_PATH:-${CLAUDE_PLUGIN_ROOT}}/servers/yandex\" && exec uv run fastmcp run fastmcp.json --no-banner"],
      "env": { "DJ_YM_TOKEN": "${DJ_YM_TOKEN}", "DJ_YM_USER_ID": "${DJ_YM_USER_ID}" }
    },
    "beatport": { "command": "bash", "args": ["-c", "cd .../servers/beatport && exec uv run fastmcp run fastmcp.json"] },
    "suno":     { "command": "bash", "args": ["-c", "cd .../servers/suno && exec uv run fastmcp run fastmcp.json"] },
    "db": {  // существующий сторонний supabase MCP — оставляем как есть
      "command": "bash",
      "args": ["-c", "... npx -y @supabase/mcp-server-supabase@0.7.0 --read-only --project-ref=... "]
    }
  }
}
```

Имена tools в Claude Code станут:
`mcp__plugin_dj-music_core__entity_list`, `mcp__plugin_dj-music_yandex__provider_search`
и т.д. — учесть в permission-rules / `allowed-tools`.

`marketplace.json` пока оставляем `source: "./"` (один плагин). При выносе
серверов в отдельные плагины — переключаем источники на `git-subdir`
(`path: "servers/yandex"`).

---

## 6. Маппинг «текущий `app/*` → целевой сервер» (сводка)

| Текущий модуль | Куда | Примечание |
|---|---|---|
| `app/registry/provider.py` | `packages/dj-shared` | протокол — общий контракт |
| `app/registry/` (EntityRegistry, defaults) | `servers/core` | БД-сущности |
| `app/shared/{constants,errors,time,ids,filters,pagination}` | `packages/dj-shared` | leaf-утилиты |
| `app/providers/yandex` | `servers/yandex` | + tools-обёртки |
| `app/providers/beatport` | `servers/beatport` | + tools-обёртки |
| `app/providers/suno` | `servers/suno` | + tools-обёртки |
| (soundcloud) | `servers/soundcloud` | адаптер с нуля / отложить |
| `app/models` `app/repositories` `app/db` | `servers/core` | владелец БД |
| `app/handlers` | `servers/core` | track_import → зовёт провайдеров через `providers_client` |
| `app/domain` | `servers/core` | pure compute (transition/optimization/…) |
| `app/schemas` | `servers/core` (+ canonical в `dj-shared`) | entity DTO в core, обменные — в shared |
| `app/resources` `app/prompts` | `servers/core` | views + workflow |
| `app/tools/entity,compute,sync,admin,ui` | `servers/core` | |
| `app/tools/provider` | `servers/core` (прокси) + логика в `servers/<provider>` | тонкий прокси в core |
| `app/server` | `servers/core/server` | composition root ядра |
| `app/config/*` | делится: base → `dj-shared`, per-domain → соответствующий сервер | yandex.py→yandex, suno.py→suno |
| `app/audio` | `servers/core/audio` сейчас → `servers/audio-analysis` (Фаза 4) | тяжёлый, выносим позже |

---

## 7. import-linter: новые межпакетные контракты

Расширить существующий `.importlinter` (он уже держит слои внутри `app/`):

- `dj_shared` — leaf: не импортит `dj_core`, ни один `dj_<provider>`, ни
  `fastmcp`/`sqlalchemy`/`librosa`/`httpx`.
- `dj_<provider>` — зависит только от `dj_shared`: запрещены `dj_core`, другие
  `dj_<provider>`, `sqlalchemy`.
- `dj_core` — не импортит внутренности провайдеров (`dj_yandex.client` и т.п.),
  только `dj_shared` + свой MCP-клиент `providers_client`.
- `dj_gateway` (позже) — только `dj_shared` + `fastmcp` (прокси), без `dj_core`.

Это делает «микросервисные» границы такими же проверяемыми, как сейчас проверяются
слои внутри монолита.

---

## 8. Порядок работ (первый заход)

1. Завести workspace: корневой `pyproject.toml` с `[tool.uv.workspace]`, создать
   пустые `packages/dj-shared`, `servers/core`, `servers/yandex` с их `pyproject.toml`.
2. Перенести `dj-shared` (протокол + shared-утилиты + один rate limiter),
   прогнать `make arch`.
3. Собрать `servers/yandex` из `app/providers/yandex` + tools-обёртки; поднять
   как отдельный stdio-сервер, проверить `fastmcp run`.
4. В `servers/core` добавить `providers_client` и переключить `track_import` на
   вызов yandex-сервера; убедиться, что `build_set_workflow` проходит.
5. Обновить `plugin.json` (ключи `core` + `yandex`), проверить в Claude Code.
6. Повторить для beatport/suno; soundcloud — по решению.

Монолит остаётся рабочим до шага 5 (можно вести в ветке `refactor/workspace`).
```
