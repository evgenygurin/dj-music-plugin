# Разбиение монолита на композицию MCP-серверов

**Дата:** 2026-07-07 · **Статус:** proposal (обсуждение) · **Автор среды:** research-сессия

Документ отвечает на задачу: превратить монолитный `dj-music-plugin` в
«микросервисную» топологию из отдельных MCP-серверов (Yandex / Beatport /
SoundCloud / …), объединяемых через FastMCP v3 в более крупные серверы и в
итоге в единый плагин Claude Code, возможно в нескольких репозиториях.

Основано на: чтении текущего кода (`app/`, `.claude-plugin/`, `.importlinter`),
живой схеме Supabase (`bowosphlnghhgaulcyfm`), документации FastMCP v3.4.x
(`gofastmcp.com`), официальной документации Claude Code Plugins/MCP
(`code.claude.com/docs`) и разборе плагина Superpowers (`obra/superpowers`).

---

## 0. TL;DR — что рекомендуется

1. **Настоящий шов проходит не по «провайдерам», а по оси «stateless catalog
   access ↔ stateful core (БД + модели + домен)».** Провайдеры у тебя уже тонкие
   адаптеры за единым `Provider`-протоколом. Это упрощает всё.

2. **Целевая раскладка — 4 класса серверов:**
   - *provider-серверы* (yandex, beatport, soundcloud, suno) — **stateless**, без
     БД, только обёртка внешнего API → canonical-словари;
   - *music-gateway* — FastMCP-сервер, который через `create_proxy()` + `mount(namespace=)`
     агрегирует provider-серверы и даёт кросс-провайдерные tools;
   - *core/db-сервер* — владелец Supabase + SQLAlchemy-моделей + репозиториев +
     handlers (persist, track_import), домена (transition/optimization) и prompts;
   - *domain-серверы* (позже) — audio-analysis, set-building — выносятся из core,
     когда это оправдано нагрузкой.

3. **Композиция — двухуровневая, оба механизма официальные:**
   - на уровне плагина Claude Code — несколько ключей в `mcpServers`
     (ты **уже** так делаешь: `mcp` + `db`);
   - на уровне FastMCP — `create_proxy(...)` + `mount(...)` для агрегации и
     кросс-серверных tools.

4. **Репозитории: начинай с монорепо + `uv` workspace, а не с распила на N
   репо.** Один marketplace-репозиторий-«зонтик» с источниками `git-subdir`
   даёт тебе внешне ту же «мульти-плагинную» витрину, что у Superpowers, но без
   операционных издержек мульти-репо. Выноси в отдельный репозиторий только тот
   сервер, у которого появляется независимый цикл релизов/потребители.

5. **Не переписывай curated-tools в OpenAPI-генерацию.** `from_openapi` хорош для
   бутстрапа стороннего REST (если у Beatport/SoundCloud есть спека), но авторы
   FastMCP прямо предупреждают: LLM работает заметно лучше с рукотворным surface.
   Это совпадает с твоим принципом «polymorphism over proliferation».

> **Мой главный тезис:** сначала зафиксируй **швы внутри одного репозитория**
> (провайдеры → stateless-пакеты со своими entrypoint'ами; core → отдельный
> entrypoint), докажи, что композиция через `create_proxy`/`mount` работает
> локально, и только потом (опционально) режь на репозитории. Обратный порядок
> — сразу N репозиториев — почти гарантированно даст боль синхронизации версий
> и общих схем.

---

## 1. Что уже есть (факты из кода)

**Монолит — один FastMCP-сервер**, собираемый в `app/server/app.py::build_mcp_server()`
из трёх `FileSystemProvider` (`app/tools`, `app/resources`, `app/prompts`) +
lifespan + middleware + sampling. Точка входа — `server.py` → `fastmcp.json`
(stdio).

**Плагин уже мульти-серверный.** `.claude-plugin/plugin.json` объявляет **два**
MCP-сервера:
- `mcp` — сам монолит (`uv run fastmcp run fastmcp.json`);
- `db` — сторонний `@supabase/mcp-server-supabase` в `--read-only` режиме.

То есть паттерн «несколько mcpServers в одном плагине» у тебя уже в проде — его
надо просто масштабировать.

**Провайдеры уже развязаны за протоколом.** `app/registry/provider.py`
определяет `Provider` (`read/write/search/download_audio/close`) и
`ProviderRegistry`. Под него уже написаны три адаптера:
`app/providers/{yandex,beatport,suno}/`. `soundcloud`/`spotify` существуют только
как мёртвые таблицы БД (0 строк), адаптеров нет.

**Слои жёстко зафиксированы import-linter'ом** (`.importlinter`): `audio` не
лезет в БД/провайдеры/tools; `prompts` — чистые текст-билдеры; `resources` не
импортят tools/handlers/providers; `domain.render` без IO; `shared` — leaf. Это
**огромный плюс** для распила: границы уже проведены и проверяются CI-эквивалентом
(`make arch`).

**Существующие модули (строки кода):**

| Слой | .py | ~строк | Роль при распиле |
|---|---:|---:|---|
| `app/audio` | 41 | 4466 | кандидат в отдельный **audio-analysis**-сервер |
| `app/domain` | 38 | 5542 | pure-compute → в **core** (transition/optimization/camelot) |
| `app/providers` | 19 | 3425 | → **provider-серверы** (по одному на площадку) |
| `app/tools` | 40 | 4187 | dispatchers → делятся между core и provider-серверами |
| `app/resources` | 17 | 2835 | read-only views → в основном в **core** |
| `app/prompts` | 34 | 2758 | workflow recipes → в **core** (или в orchestrator) |
| `app/repositories` | 15 | 1854 | UoW + repos → **core/db** |
| `app/schemas` `app/models` `app/handlers` `app/server` `app/registry` `app/shared` `app/config` `app/db` | | ~9.7k | инфраструктура ядра |

---

## 2. Ключевое наблюдение: где на самом деле швы

Твоя интуиция «отдельный сервер на Яндекс, отдельный на Beatport» — правильная,
но провайдеры — это **самая дешёвая** часть распила (тонкие httpx-обёртки). Вся
сложность в другом: **`tracks` — это хаб всей БД.**

Из FK-графа Supabase (полный граф — Приложение A) почти всё ссылается на `tracks`:
`track_audio_features_computed`, `dj_library_items`, `transitions`,
`track_sections`, `yandex_metadata`, `beatport_metadata`, `track_external_ids`,
`dj_set_items` → … → `dj_sets`. То есть данные **не** делятся чисто по площадкам
— они делятся на «каталог/идентичность трека» (центр) и «производные»
(фичи, переходы, сеты, library items).

**Отсюда два правила проектирования:**

- **A. Provider-серверы должны быть stateless.** Провайдер обёртывает внешний
  API и возвращает canonical dict — и **не** пишет в Supabase. Персистентностью
  (резолв `tracks.id`, запись `*_metadata`, `track_external_ids`) владеет
  **core/db**. Сейчас это смешано: `track_import` handler делает и обращение к
  Yandex, и запись в БД. При распиле handler остаётся в core и **вызывает
  provider-сервер как MCP-клиент**, а не импортирует его код.

- **B. Единый владелец `tracks` = один core/db-сервер.** Нельзя дать
  yandex-серверу и beatport-серверу писать в `tracks` независимо — получишь
  гонки на identity трека. Идентичность трека и её внешние маппинги
  (`track_external_ids`) централизуются в core.

Это и есть «микросервисный» канон: провайдеры = stateless integration services,
core = system of record. Не режь БД на «БД Яндекса» и «БД Beatport».

---

## 3. Целевая топология

```text
                         Claude Code plugin  (dj-music marketplace)
                                    │  stdio
              ┌─────────────────────┼───────────────────────────┐
              ▼                     ▼                             ▼
      ┌──────────────┐     ┌─────────────────┐          ┌─────────────────┐
      │  core/db     │     │  music-gateway  │          │  supabase (db)  │
      │  FastMCP     │◄────│  FastMCP proxy  │          │  сторонний MCP  │
      │              │call │                 │          │  (read-only)    │
      │ models,repos │     │  mount(ns=...)  │          └─────────────────┘
      │ handlers,    │     └───┬────┬────┬───┘
      │ domain,      │         │    │    │  create_proxy (stdio/http)
      │ prompts,     │         ▼    ▼    ▼
      │ resources    │      yandex beatport soundcloud   ← stateless provider-серверы
      └──────────────┘        │      │      │              (отдельные процессы/пакеты/репо)
             ▲                 └──────┴──────┘  suno (генерация ассетов)
             │ persist (track_import вызывает gateway как client)
             └───────────────────────────────────────────────┘
```

Позже из `core/db` отпочковываются **audio-analysis** (тяжёлый librosa/numba,
хочет VM/GPU и свой цикл) и **set-building/transition** (чистый compute).

**Почему две «крупные структуры», а не одна плоская пачка серверов:**
- *music-gateway* нужен, если хочешь **кросс-провайдерные** tools
  (`unified_search` по всем площадкам, дедупликация, единый `provider_read`) и
  чтобы core ходил в один endpoint, а не знал про N провайдеров. Это твоя
  «объединяющая музыкальная структура».
- если кросс-провайдерная логика не нужна, gateway можно **не делать** и просто
  объявить провайдеров как отдельные `mcpServers` в плагине (Claude Code сам
  сведёт их в один tool-неймспейс). Gateway — это оптимизация, а не обязательство
  (см. §5).

---

## 4. FastMCP v3: механизмы, которыми это собирается

Терминология v3 (важно — многое из v2 переименовано/deprecated):

| Задача | v3 API | Замечание |
|---|---|---|
| Живая композиция in-process | `parent.mount(child, namespace="x")` | live-link: tools ребёнка видны сразу |
| Статическая копия | ~~`import_server()`~~ | **deprecated в v3** → используй `mount` |
| Проксировать другой сервер (процесс/URL) | `from fastmcp.server import create_proxy` | ~~`FastMCP.as_proxy`~~ deprecated |
| Модуль прокси | `fastmcp.server.providers.proxy` | старый `fastmcp.server.proxy` deprecated |
| Namespacing | `namespace=` при mount / `Namespace` transform | tools: `x_tool`; resources: `data://x/...` |
| OpenAPI → MCP | `FastMCP.from_openapi(spec, client)` | curated лучше; см. §5.4 |
| FastAPI → MCP | `FastMCP.from_fastapi(app)` | operationId → имя компонента |

### 4.1 Gateway из независимых серверов — конфиг-словарь

Самый чистый способ для «gateway из отдельных серверов»:

```python
# music_gateway.py
from fastmcp.server import create_proxy

config = {
    "mcpServers": {
        # локальные stdio-процессы (пакеты в монорепо или отдельные репо)
        "yandex":     {"command": "uv", "args": ["run", "--project",
                        "servers/yandex", "fastmcp", "run", "server.py"]},
        "beatport":   {"command": "uv", "args": ["run", "--project",
                        "servers/beatport", "fastmcp", "run", "server.py"]},
        "soundcloud": {"command": "uv", "args": ["run", "--project",
                        "servers/soundcloud", "fastmcp", "run", "server.py"]},
        # или удалённый HTTP-деплой:
        # "yandex": {"url": "https://yandex-mcp.internal/mcp", "transport": "http"},
    }
}
# компоненты автоматически префиксуются: yandex_search, beatport_search, ...
music_gateway = create_proxy(config, name="MusicGateway")

if __name__ == "__main__":
    music_gateway.run()   # stdio по умолчанию → регистрируется в плагине
```

### 4.2 Gateway с собственными кросс-провайдерными tools

Если нужен `unified_search` и общий фасад:

```python
from fastmcp import FastMCP
from fastmcp.server import create_proxy

gateway = FastMCP("MusicGateway")
gateway.mount(create_proxy("servers/yandex/server.py"),     namespace="yandex")
gateway.mount(create_proxy("servers/beatport/server.py"),   namespace="beatport")
gateway.mount(create_proxy("servers/soundcloud/server.py"), namespace="soundcloud")

@gateway.tool
async def unified_search(query: str, limit: int = 20) -> dict:
    """Ищет во всех площадках и мёрджит/дедуплицирует результаты."""
    ...
```

### 4.3 Транспорт: stdio локально, HTTP для распределённого

- **stdio** — для локальной композиции (всё на одной машине, dev). Env **не**
  наследуется от шелла — токены (`DJ_YM_TOKEN`, `DJ_SUNO_*`) передавай явно через
  `mcpServers.env` или `StdioTransport(env=...)`.
- **Streamable HTTP** — для реально распределённого деплоя (провайдеры как
  отдельные сервисы на разных машинах). SSE — только legacy, `WSTransport` в v3
  удалён.
- **Гибрид (рекомендуемый):** gateway наружу stdio (для Claude Code), внутрь к
  провайдерам — HTTP. Прокси именно для этого моста stdio↔HTTP и создан.

### 4.4 Латентность прокси — не бесплатно

Проксированный вызов добавляет ~200–500 ms на операцию против ~1–2 ms локально;
`list_tools` через прокси — 300–400 ms × число бэкендов. Смягчения:
- `ProxyProvider(..., cache_ttl=60)` — кэш списков компонентов (default 300 s);
- session reuse **только** для доказанно stateless HTTP-бэкендов;
- **горячий путь (transition/optimization, reference-ресурсы) держи локально в
  core**, а не за прокси. Проксируй только то, что реально ходит во внешний мир
  (каталоги площадок).

---

## 5. Композиция на уровне плагина Claude Code

### 5.1 Несколько mcpServers в одном плагине — официально

`.claude-plugin/plugin.json` (inline) или `.mcp.json` (в корне плагина)
принимают объект `mcpServers` с **любым числом ключей**. Каждый ключ — отдельный
сервер (stdio `command`/`args`/`env` или remote `type:"http", url, headers`).
Именование tools: `mcp__plugin_<plugin>_<server>__<tool>` — учти в
permission-rules.

Полезное:
- `${CLAUDE_PLUGIN_ROOT}` — корень установленного плагина (пути только через него);
- `${CLAUDE_PLUGIN_DATA}` — **персистентный** каталог, переживает апдейты плагина
  → сюда скачанные MP3/кэши вместо `/tmp/dj_audio`;
- **Tool Search (deferred tools)** включён по умолчанию → «больше MCP-серверов ≈
  не раздувает контекст». То есть множество серверов в плагине — это ОК.

### 5.2 Два уровня — и когда какой

| Механизм | Даёт | Не даёт |
|---|---|---|
| **plugin `mcpServers`** (N ключей) | простую изоляцию процессов, независимый запуск, авто-неймспейсинг Claude Code | кросс-серверных tools, серверной агрегации, вызова провайдера из core |
| **FastMCP gateway** (`create_proxy`+`mount`) | кросс-провайдерные фасады, единый endpoint, мост stdio↔http, tag-visibility рекурсивно | «бесплатность» — добавляет прокси-латентность и ещё один процесс |

**Рекомендация:** начни с plugin-level (у тебя это уже `mcp`+`db`); добавь
gateway, **когда** появится первая настоящая кросс-провайдерная задача.

### 5.3 Marketplace-«зонтик» (паттерн Superpowers)

Superpowers = НЕ монорепо: крошечный `superpowers-marketplace` c одним
`marketplace.json` ссылается на N независимых репо (`source: url`), включая
чистые skills-плагины и чистые MCP-плагины (`private-journal-mcp`). Release-каналы
— через `ref` (stable vs `ref:"dev"`).

Для тебя это два варианта источников в `marketplace.json`:

```jsonc
// Вариант «монорепо» — sparse-clone подкаталога:
{ "name": "dj-yandex",
  "source": { "source": "git-subdir",
              "url": "https://github.com/evgenygurin/dj-music-plugin.git",
              "path": "servers/yandex" } }

// Вариант «мульти-репо» (как Superpowers):
{ "name": "dj-yandex",
  "source": { "source": "github", "repo": "evgenygurin/dj-yandex-mcp" } }
```

Версию пинуй **в одном месте** (либо `plugin.json`, либо marketplace-entry — не
в обоих: Claude Code молча берёт `plugin.json`).

### 5.4 OpenAPI — где уместно

Официальной «OpenAPI-фичи» в самом Claude Code нет; связка OpenAPI↔MCP делается
на уровне сервера (FastMCP `from_openapi`), который затем подключается обычным
`mcpServers`-энтри. Применяй точечно: если у Beatport/SoundCloud есть OpenAPI-спека
— можно быстро сгенерить черновой provider-сервер и потом заменить curated-tools.
Для основного surface (твои dispatchers) — не надо.

---

## 6. Репозитории: монорепо-first, мульти-репо потом

Ты склоняешься к «разным репозиториям сразу». Честный разбор для соло/малой
команды:

**Издержки мульти-репо, которые прилетят сразу:**
- общие контракты (`Provider`-протокол, canonical-схемы треков, DJ-константы,
  Camelot-таблицы) надо вынести в **опубликованный shared-пакет** и версионировать
  — иначе N репозиториев разъедутся;
- N × (CI-эквивалент `make check`, pre-push hook, релизный флоу, `.env`,
  зависимости, dependabot);
- атомарный рефактор через границу сервера (поменял протокол — правь N репо в N
  PR) вместо одного PR;
- у тебя **явно отключён GitHub Actions** (billing lock, см. CLAUDE.md) —
  значит на каждый репо ещё и ручной локальный гейт.

**Рекомендуемый путь — staged:**

1. **Монорепо + `uv` workspace.** Раздели `app/` на пакеты-члены workspace:
   `packages/dj-shared` (протокол, схемы, константы), `servers/yandex`,
   `servers/beatport`, `servers/soundcloud`, `servers/suno`, `servers/core`,
   `servers/music-gateway`. Каждый server — свой `pyproject.toml` +
   `server.py`/`fastmcp.json`, зависит от `dj-shared` как workspace-пакет. Швы
   становятся реальными (импорты через границу пакета ловятся), но всё в одном
   `git`, один релизный флоу.
2. **Marketplace-«зонтик»** с источниками `git-subdir` на подкаталоги —
   внешне выглядит как «много плагинов», внутри один репозиторий.
3. **Выноси в отдельный репозиторий только сервер, у которого появился
   независимый цикл** (например, `audio-analysis` уезжает на VM/GPU и релизится
   отдельно). Тогда — отдельный репо + published `dj-shared`.

Это даёт тебе почти всю ценность мульти-репо (изоляция, отдельные плагины в
витрине) без раннего налога на синхронизацию.

---

## 7. Поэтапный план миграции

Каждая фаза — самостоятельно ценна и оставляет проект рабочим.

**Фаза 0 — подготовка швов (внутри монолита, без нового процесса).**
- Ввести `uv` workspace; выделить `packages/dj-shared` (Provider-протокол из
  `app/registry/provider.py`, canonical track-схемы, `app/shared/constants`,
  Camelot из `reference`). Обновить import-linter контрактом «провайдеры зависят
  только от `dj-shared`, не друг от друга и не от core».
- Убедиться, что provider-адаптеры **не** импортят `app.db/repositories/handlers`
  (сейчас, по контрактам, они и так этого не делают — проверить `track_import`).

**Фаза 1 — первый provider-сервер + gateway (доказательство концепции).**
- Обернуть `app/providers/yandex` в самостоятельный FastMCP-сервер
  (`servers/yandex/server.py`) с tools `provider_read/write/search`,
  `download_audio` — **stateless**, возвращает canonical dict, без Supabase.
- Поднять `servers/music-gateway` через `create_proxy` над yandex (stdio).
- В core оставить `track_import`, но переключить его: вместо прямого импорта
  yandex-клиента — вызов gateway/yandex как MCP-клиента; core пишет в Supabase.
- Зарегистрировать gateway в плагине как ещё один `mcpServers`-ключ рядом с `mcp`.
- Гейт готовности: `build_set_workflow` end-to-end проходит через новую развязку.

**Фаза 2 — остальные провайдеры.**
- Перенести beatport, suno в `servers/*` по тому же шаблону; добавить soundcloud
  (сейчас только dead-таблицы — реализовать адаптер или отложить).
- Ввести кросс-провайдерные tools в gateway (`unified_search`, дедупликация по
  `track_external_ids`).

**Фаза 3 — выделить core/db как явный сервер.**
- `servers/core` = models + repositories + handlers + domain + prompts +
  resources + entity/compute/sync tools. Это и есть «MCP-сервер для работы с БД»
  из твоего описания — владелец Supabase и identity трека.
- Оставить сторонний `db` (supabase read-only MCP) для ad-hoc SQL/диагностики —
  он ортогонален и уже работает.

**Фаза 4 — отпочковать domain-серверы (по потребности).**
- `audio-analysis` (librosa/numba, тяжёлый — кандидат на HTTP/VM, `task=True` для
  длинных прогонов). Помни про numba/JIT warmup и 120s MCP-таймаут из
  `.claude/rules/audio.md`.
- `set-building/transition` — чистый compute, легко выносится, но и дёшево
  держать в core; выноси только если понадобится независимый релиз.

**Фаза 5 — витрина.**
- Marketplace-«зонтик» с `git-subdir`-источниками; при необходимости — вынос
  «созревших» серверов в отдельные репозитории + published `dj-shared`.

---

## 8. Открытые решения (нужен твой выбор)

1. **Монорепо-first или сразу мульти-репо?** Рекомендую монорепо + workspace,
   мульти-репо по мере созревания. Если принципиально мульти-репо сразу — первым
   делом надо опубликовать `dj-shared` и завести версионирование контрактов.
2. **Нужен ли gateway с кросс-провайдерными tools сейчас, или достаточно
   плоских `mcpServers` в плагине?** От этого зависит, появляется ли
   `music-gateway`-процесс в Фазе 1 или позже.
3. **Provider-серверы строго stateless (рекомендую) — ок?** Это значит: вся
   запись в Supabase остаётся в core; провайдеры ничего не персистят.
4. **Транспорт между серверами:** всё локально по stdio (проще) или сразу
   закладываем HTTP-деплой части серверов (audio на VM)?
5. **SoundCloud/Spotify:** реализуем адаптеры (сейчас их нет — только пустые
   таблицы) или откладываем и режем только существующее (yandex/beatport/suno)?

---

## 9. Риски и анти-паттерны (чего не делать)

- **Не** резать `tracks`/БД по площадкам — identity трека централизована, иначе
  гонки. Один владелец `tracks`.
- **Не** давать provider-серверам писать в Supabase — они stateless.
- **Не** строить на `import_server`/`as_proxy` — deprecated в v3 (`mount`/`create_proxy`).
- **Не** проксировать горячий compute (transition/optimization) — держи локально
  в core, проксируй только внешние каталоги.
- **Не** дублировать `version` в `plugin.json` и marketplace-entry.
- **Не** полагаться на env шелла в stdio-бэкендах — токены передавай явно.
- **Не** массово конвертировать в OpenAPI-tools основной surface — curated лучше.
- Помни про уже существующие ограничения проекта: нет CI (billing lock) →
  каждый новый сервер увеличивает ручной гейт; в облачной песочнице сырой
  Postgres закрыт → работа с БД через Supabase MCP (это как раз ложится на
  отдельный `db`-сервер).

**Отдельно — безопасность БД (не блокер распила, но всплыло):** Supabase advisory
сообщает, что во всех 43 таблицах `public` **отключён RLS** — с anon-ключом они
полностью читаемы/записываемы. При формализации доступа к БД как отдельного
сервера это стоит закрыть (включить RLS + политики). SQL-ремедиацию не применял —
включение RLS без политик заблокирует доступ; решай отдельно.

---

## Приложение A. FK-граф Supabase (хаб = `tracks`)

Родитель → дети (FK). Показывает, почему БД централизована вокруг `tracks`.

```text
tracks ──┬─ track_audio_features_computed (23815)   ← фичи (audio-домен)
         ├─ dj_library_items (675) ─┬─ dj_beatgrids ─ dj_beatgrid_change_points
         │                          ├─ dj_cue_points
         │                          └─ dj_saved_loops
         ├─ transitions (1577) ── dj_set_items
         ├─ transition_history / transition_candidates
         ├─ track_sections / track_external_ids (18)
         ├─ track_artists ─ artists       ├─ track_genres ─ genres
         ├─ track_labels ─ labels ─ releases ─ track_releases
         ├─ yandex_metadata (18) / beatport_metadata / soundcloud_metadata
         ├─ spotify_metadata / spotify_audio_features / …
         ├─ track_affinity / track_feedback (15) / embeddings
         ├─ feature_extraction_runs ─ (pipeline_run_id ← features)
         └─ raw_provider_responses ─ providers
dj_playlists ─┬─ dj_playlist_items      dj_sets ─ dj_set_versions ─ dj_set_items
              ├─ dj_sets (source)                              └─ dj_set_feedback
              └─ app_exports
keys ─ key_edges
```

Живые таблицы с данными: `tracks` 24005, `track_audio_features_computed` 23815,
`dj_set_items` 4268, `transitions` 1577, `dj_library_items` 675,
`dj_set_versions` 144, `dj_sets` 34, `yandex_metadata`/`track_external_ids` 18,
`track_feedback` 15. Остальное — 0 (в т.ч. `spotify_*`, `soundcloud_metadata`,
`beatport_metadata`, `genres`, `artists`, `labels`, dead-таблицы из
`p2_drop_dead_tables`).

## Приложение B. Целевая раскладка пакетов (монорепо + uv workspace)

```text
dj-music-plugin/
├── .claude-plugin/{plugin.json, marketplace.json}   # витрина + mcpServers
├── packages/
│   └── dj-shared/         # Provider-протокол, canonical schemas, константы, Camelot
├── servers/
│   ├── yandex/            # stateless FastMCP (server.py + fastmcp.json)
│   ├── beatport/
│   ├── soundcloud/
│   ├── suno/
│   ├── music-gateway/     # create_proxy + mount(namespace) + cross-provider tools
│   └── core/              # models, repos, handlers, domain, prompts, resources, БД
│       └── (позже отпочковываются audio-analysis, set-building)
└── uv.lock                # один lock на workspace
```

## Приложение C. Источники

- FastMCP composition: https://gofastmcp.com/servers/composition.md
- FastMCP proxy provider: https://gofastmcp.com/servers/providers/proxy.md
- FastMCP namespace transform: https://gofastmcp.com/servers/transforms/namespace.md
- FastMCP OpenAPI / FastAPI: https://gofastmcp.com/integrations/openapi.md · /integrations/fastapi.md
- FastMCP transports: https://gofastmcp.com/clients/transports.md
- FastMCP Claude Code: https://gofastmcp.com/integrations/claude-code.md
- FastMCP v2→v3 upgrade (deprecations): https://gofastmcp.com/getting-started/upgrading/from-fastmcp-2.md
- Claude Code plugins: https://code.claude.com/docs/en/plugins · /plugins-reference · /plugin-marketplaces · /mcp
- Superpowers: https://github.com/obra/superpowers · https://github.com/obra/superpowers-marketplace
- Внутренние: `app/server/app.py`, `app/registry/provider.py`, `.importlinter`,
  `.claude-plugin/plugin.json`, `docs/architecture.md`, `.claude/rules/*`
```
