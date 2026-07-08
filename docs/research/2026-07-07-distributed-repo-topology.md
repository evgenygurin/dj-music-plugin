# Распределённая топология репозиториев MCP (строгая инкапсуляция)

**Дата:** 2026-07-07 · **Статус:** proposal (authoritative) ·
Заменяет monorepo-раскладку из
[2026-07-07-monorepo-structure.md](./2026-07-07-monorepo-structure.md).
Механику FastMCP берёт из
[2026-07-07-mcp-microservices-split.md](./2026-07-07-mcp-microservices-split.md).

## Требования (из постановки)

1. **Плагин-репозиторий не содержит кода реализации.** Только то, что относится
   к дистрибуции: манифесты плагинов Claude Code / Codex / прочих хостов + витрина.
2. **«Общий dj-music MCP» — отдельный репозиторий.** Он композитор, и **не
   содержит** конкретную реализацию более мелких MCP, из которых собран.
3. **Рекурсивно вниз:** каждый уровень только *ссылается* на нижний, не вендорит
   его исходники.
4. Цель системы в целом: **жёсткая инкапсуляция + жёсткое разделение**, при этом
   **гибкость взаимодействия «всего со всем»** и **настраиваемые ограничения и
   правила** этого взаимодействия.
5. Паттерн переиспользуемый — на нём будет расти бо́льшая система.

---

## 1. Ключевая идея: 4 архетипа репозиториев

Вся система строится из репозиториев **ровно четырёх типов**. Тип определяет, что
внутри, от чего зависит и как связывается с другими. Это и есть переиспользуемый
паттерн.

| Архетип | Что содержит | От чего зависит | Как отдаёт себя наверх |
|---|---|---|---|
| **Contract** (`*-contracts`) | только типы/протоколы/константы, pure Python | ничего (leaf) | как **опубликованный пакет** (semver) |
| **Leaf server** (`*-mcp-<x>`) | самодостаточная реализация одного MCP | только Contract(ы) | как **процесс/endpoint** (stdio-пакет или HTTP) |
| **Gateway** (`*-mcp`, `*-mcp-<group>`) | композиция + правила, **без реализации** | `fastmcp` + Contract(ы) + *ссылки* на детей | как процесс/endpoint |
| **Distribution** (`*-plugin`) | манифесты хостов (Claude Code/Codex/…) + витрина | *ссылка* на один Gateway | как устанавливаемый плагин |

**Единственная общая зависимость всех — Contract.** Это неизбежная «шина
совместимости»: чтобы «всё взаимодействовало со всем», нужен общий язык (протокол
Provider, canonical-схемы трека, коды ошибок). Contract версионируется как
артефакт и является *зависимостью*, а не вендорингом — инкапсуляция не нарушена.

### Механизм связывания «ссылается, но не содержит»

Родитель **никогда не импортирует исходники ребёнка**. Связь — по одному из двух
способов, оба — по протоколу MCP:

- **stdio-пакет:** ребёнок опубликован как пакет; родитель запускает его как
  отдельный процесс `uvx dj-music-mcp-yandex` (или container) и **проксирует** через
  `create_proxy(...)`. Исходников ребёнка в репо родителя нет — есть только имя
  пакета/версия в конфиге.
- **remote HTTP:** ребёнок задеплоен как сервис; родитель проксирует по `url`.

В обоих случаях в gateway-репо лежит только **конфиг детей** (имя пакета/URL +
namespace + правила), а не их код. Это и есть строгая инкапсуляция «по ссылке».

### Где живут «правила и ограничения взаимодействия»

Именно в **Gateway-слое**. Gateway — не просто прокси, а точка политики. Но важно:
в FastMCP v3 это **три разных механизма с разной зависимостью от транспорта**
(детали и транспортная матрица — [2026-07-07-fastmcp-v3-deep-dive.md](./2026-07-07-fastmcp-v3-deep-dive.md) §0):

- **Visibility** (`enable(tags=..., only=True)` / `disable(tags=...)`, рекурсивно на
  mounted, + per-session `ctx.enable_components`) — какие компоненты вообще видны.
  **Работает на любом транспорте (в т.ч. stdio).**
- **Middleware** (auth-политика, rate-limit, audit-log, маскирование ошибок,
  бюджеты; отказ = raise `ToolError`). **Любой транспорт.**
- **Authorization** (`auth=require_scopes(...)`/`restrict_tag(...)` + `AuthMiddleware`)
  — доступ **по личности вызывающего** (scopes/claims токена). **ТОЛЬКО HTTP** —
  в stdio токена нет, проверки молча пропускаются.
- **feature-forwarding** — через `ProxyClient(sampling_handler=None, ...)` выключить
  проброс sampling/logging от ребёнка (leaf не инициирует LLM-вызовы наверх).
- **контрактные ограничения** — `operations_supported` в Contract фиксирует легальные
  операции провайдера (compile-time граница).

⚠️ **Ключевое:** per-caller/per-tenant правила (scopes, роли) требуют **HTTP-транспорта
+ верификации токена** (`JWTVerifier`). Пока серверы соединены по stdio, правила =
только Visibility + Middleware. Референс-архитектура для «capabilities, not
credentials» — sandboxed-agents (см. deep-dive §4): секреты держит gateway, потребитель
ходит с коротким scoped-токеном по HTTP, tools проектируются как узкие капабилити.

«Гибкость всего со всем» получается потому, что все говорят на MCP: любой gateway
может подключить любой сервер/gateway, топология переописывается **конфигом**, не
трогая leaf-репозитории. Новый потребитель (другой плагин, Codex, внешний агент)
просто указывает на нужный gateway или прямо на leaf — по тем же правилам.

### Правила зависимостей (жёсткое разделение — инвариант системы)

```text
Distribution → (ровно один) Gateway
Gateway      → Contract(s) + ссылки на детей (Gateway/Leaf) по конфигу
Leaf         → Contract(s)   ТОЛЬКО
Contract     → ничего (leaf)

Запрещено:  Leaf → Leaf,  Leaf → Gateway,  Distribution → Leaf,
            любой импорт исходников ребёнка родителем.
```

Эти правила — не пожелание, а проверяемый инвариант: у Contract и Leaf в
`pyproject.toml` физически нет зависимостей на соседей; gateway зависит от
`fastmcp` и Contract, а детей знает только как строки конфига. Нарушить = добавить
запрещённую зависимость, что видно в ревью/линте.

---

## 2. Инстанцирование для DJ-music (конкретные репозитории)

```text
                    ┌────────────────────────────┐
   Distribution     │  dj-music-plugin           │  манифесты Claude Code/Codex/Cursor,
                    │  (только манифесты)         │  marketplace.json → ссылка на dj-music-mcp
                    └──────────────┬─────────────┘
                                   │ references (package/url)
                    ┌──────────────▼─────────────┐
   Gateway (top)    │  dj-music-mcp  «общий DJ music»  │  композиция + ПРАВИЛА, без реализации;
                    │  config + rules + prompts   │  кросс-доменные workflow-prompts (pure text)
                    └───┬───────┬───────┬────────┘
        references      │       │       │
        ┌───────────────┘       │       └──────────────┐
        ▼                       ▼                       ▼
 ┌───────────────┐     ┌────────────────┐      ┌────────────────┐
 │ dj-music-mcp-       │     │  dj-music-mcp-db     │      │  dj-music-mcp-audio  │   (+ dj-music-mcp-setbuilder)
 │ platforms     │     │  (Leaf: SoR)   │      │  (Leaf)        │
 │ (Gateway)     │     │  Supabase,     │      │  librosa/numba │
 │ config+rules  │     │  identity      │      └────────────────┘
 └──┬──┬──┬──┬───┘     └────────────────┘
    │  │  │  │ references
    ▼  ▼  ▼  ▼
  yandex beatport soundcloud suno         ← dj-music-mcp-<x>  (Leaf: stateless integrations)

  ВСЕ зависят от:  dj-music-contracts (Contract, published)
```

### 2.1 Реестр репозиториев

| Репозиторий | Архетип | Содержимое | Ссылается на |
|---|---|---|---|
| `dj-music-contracts` | Contract | Provider-протокол, canonical track/search DTO, константы, Camelot, errors, ratelimit | — |
| `dj-music-mcp-yandex` | Leaf | yandex client+adapter+tools, stateless | dj-music-contracts |
| `dj-music-mcp-beatport` | Leaf | beatport client+adapter+tools | dj-music-contracts |
| `dj-music-mcp-soundcloud` | Leaf | soundcloud (адаптер писать с нуля) | dj-music-contracts |
| `dj-music-mcp-suno` | Leaf | suno generation, stateless | dj-music-contracts |
| `dj-music-mcp-db` | Leaf | Supabase system-of-record: `tracks` identity, features, sets, transitions persist; models, repos, handlers | dj-music-contracts |
| `dj-music-mcp-audio` | Leaf | audio-анализ (Фаза 2) | dj-music-contracts |
| `dj-music-mcp-setbuilder` | Leaf | transition scoring + optimization (Фаза 2) | dj-music-contracts |
| `dj-music-mcp-platforms` | Gateway | агрегатор 4 платформ, `unified_search`, дедуп по external_id | dj-music-contracts + 4 leaf по ссылке |
| `dj-music-mcp` | Gateway (top) | «общий DJ music», композиция platforms+db+audio+setbuilder, правила, кросс-доменные prompts | dj-music-contracts + дети по ссылке |
| `dj-music-plugin` | Distribution | `.claude-plugin/*`, `.codex-plugin/*`, marketplace, host-адаптеры | dj-music-mcp по ссылке |

> `dj-music-plugin` (текущий репо) **худеет** до Distribution: из него уезжает
> весь `app/`, остаются манифесты + витрина + host-адаптеры (`.codex`, `.agents`,
> и т.п., которые уже есть).

---

## 3. Что лежит в каждом типе репо (скелеты)

### 3.1 Contract — `dj-music-contracts`

```text
dj-music-contracts/
├── pyproject.toml                 # name="dj-music-contracts"; deps: pydantic ТОЛЬКО; semver-релизы
├── CHANGELOG.md                   # контракт версионируется строго (ломающие → major)
└── src/dj_contracts/
    ├── provider.py                # Provider Protocol, ProviderRegistry, operations_supported
    ├── canonical/                 # CanonicalTrack, SearchResult, ExternalId
    ├── constants.py · camelot.py  # BPM/Camelot/LUFS enums, Camelot-таблицы (pure)
    ├── errors.py · time.py · ids.py · filters.py · pagination.py
    └── ratelimit.py               # общий TokenBucketRateLimiter
```

Правило: без `fastmcp`, `sqlalchemy`, `httpx`, `librosa`. Меняется редко и
осознанно — это шина совместимости всей системы.

### 3.2 Leaf — `dj-music-mcp-yandex` (шаблон для всех платформ)

```text
dj-music-mcp-yandex/
├── pyproject.toml                 # deps: fastmcp, httpx, dj-music-contracts (^X.Y)
├── fastmcp.json · server.py       # stdio entrypoint
├── Dockerfile                     # опц.: для HTTP-деплоя
├── Makefile · hooks/pre-push      # СВОЙ локальный гейт (make check)
├── .env.example                   # только DJ_YM_*
├── tests/                         # СВОИ тесты (in-memory MCP client)
└── src/dj_yandex/
    ├── server.py                  # FastMCP("dj-yandex")
    ├── config.py                  # YandexSettings(env_prefix="DJ_YM_")
    ├── client.py · adapter.py · filters.py
    └── tools/{read,write,search,download}.py   # тонкие обёртки над adapter
```

Инвариант leaf: **stateless** (кроме `dj-music-mcp-db`), зависит только от
`dj-music-contracts`, запускается и тестируется в одиночку. Никаких ссылок на соседей.

### 3.3 Leaf (особый) — `dj-music-mcp-db` (system-of-record)

Единственный stateful leaf: владелец Supabase и identity трека (`tracks` — хаб
всей схемы, его нельзя дробить по площадкам). Сюда переезжают
`app/{models,repositories,db,handlers,schemas,domain}` + entity/compute/sync tools
+ resources. Персист внешних маппингов (`track_external_ids`, `*_metadata`) — тут.

```text
dj-music-mcp-db/
├── pyproject.toml                 # deps: fastmcp, sqlalchemy, dj-music-contracts
├── migrations/                    # Alembic — владелец схемы Supabase
└── src/dj_db/
    ├── server.py · config/ · db/
    ├── models/ · repositories/ · schemas/
    ├── handlers/                  # persist-логика (без сетевых вызовов провайдеров!)
    ├── domain/                    # если setbuilder не вынесен — пока здесь
    ├── tools/{entity,compute,sync,admin,ui}/
    └── resources/                 # local://, schema://, session://, reference://
```

### 3.4 Gateway — `dj-music-mcp-platforms` и `dj-music-mcp` (композиция + правила, без impl)

```text
dj-music-mcp/
├── pyproject.toml                 # deps: fastmcp, dj-music-contracts  (НЕ зависит от детей-пакетов!)
├── fastmcp.json · server.py
├── compose.toml (или .yaml)       # РЕЕСТР ДЕТЕЙ: имя пакета/URL + namespace + теги + правила
└── src/dj_mcp/
    ├── server.py                  # читает compose.*, create_proxy(child) + mount(namespace=)
    ├── policy/                    # ПРАВИЛА: middleware (auth/ratelimit/audit), tag-visibility
    ├── clients.py                 # ProxyClient-настройки (feature forwarding on/off)
    └── prompts/                   # кросс-доменные workflow (pure text) — единственный «контент»
```

Пример `compose.toml` (дети — по ссылке, не по коду):

```toml
[children.platforms]
package   = "dj-music-mcp-platforms"      # uvx dj-music-mcp-platforms  (или url = "https://.../mcp")
namespace = "platforms"
expose_tags = ["provider:read", "provider:search"]   # write наверх не пробрасываем

[children.db]
package   = "dj-music-mcp-db"
namespace = "db"

[children.audio]
package   = "dj-music-mcp-audio"
namespace = "audio"
enabled   = false                    # включим в Фазе 2
```

`dj-music-mcp` **не импортирует** `dj_mcp_platforms` как Python-модуль — он запускает его
как процесс и проксирует. Отсюда «не содержит реализацию».

### 3.5 Distribution — `dj-music-plugin` (только манифесты)

```text
dj-music-plugin/
├── .claude-plugin/
│   ├── plugin.json                # mcpServers: { "dj-music-mcp": { command: "uvx dj-music-mcp ..." } }
│   └── marketplace.json           # витрина
├── .codex-plugin/ · .agents/ · .cursor-plugin/   # адаптеры других хостов (как в Superpowers)
├── README.md
└── (никакого app/, никакого src/ реализации)
```

`plugin.json` ссылается на **один** gateway (`dj-music-mcp`), запускаемый как пакет:

```jsonc
{ "name": "dj-music", "version": "2.0.0",
  "mcpServers": {
    "dj-music-mcp": { "command": "uvx", "args": ["dj-music-mcp@2", "run"],
                "env": { "DJ_YM_TOKEN": "${DJ_YM_TOKEN}", "DJ_DATABASE_URL": "${DJ_DATABASE_URL}", "…": "…" } }
  } }
```

---

## 4. Оркестрация кросс-серверных операций (важный нюанс)

«Импорт трека» = прочитать из платформы + записать в БД — затрагивает два leaf'а.
Кто исполняет, если gateway «без реализации»?

**Рекомендация: prompt-driven на уровне `dj-music-mcp`.** Gateway видит tools обоих
детей (`platforms.provider_read`, `db.entity_create`), поэтому кросс-доменный
сценарий — это **workflow-prompt** (чистый текст, не реализация): LLM выполняет
шаги через реальные MCP-tools. Это ровно текущая философия проекта («MCP —
primary interface, композиция через prompts, а не императивный service-слой») и
она сохраняет чистоту gateway.

Если понадобится **атомарная** серверная склейка (транзакция через границу) —
это отдельный **Leaf** `dj-music-mcp-orchestrator` (импортирует только `dj-music-contracts`,
внутри — MCP-клиент к platforms и db), а не код в gateway. Так правило «gateway
без impl» не нарушается. По умолчанию — не заводим, начинаем с prompt-driven.

---

## 5. Версионирование и совместимость (клей системы)

- **`dj-music-contracts` — semver, single source of truth совместимости.** Ломающее
  изменение протокола → major; leaf/gateway пинят `dj-music-contracts ^X`. Пока major
  один, «всё взаимодействует со всем».
- **Leaf/Gateway** релизятся независимо (свой тег, свой CHANGELOG). Gateway пинит
  версии детей в `compose.*` (`dj-music-mcp-yandex@1`).
- **Distribution** пинит версию gateway в `plugin.json`. Обновление доезжает до
  пользователя только при bump (совпадает с текущим release-flow в
  `.claude/rules/git.md`).
- **Витрина/marketplace** может отдавать несколько плагинов (release-каналы через
  `ref`), как у Superpowers.

---

## 6. Трейд-оффы этой топологии (честно)

- **Латентность прокси складывается по уровням.** Цепочка
  `dj-music-plugin → dj-music-mcp → dj-music-mcp-platforms → dj-music-mcp-yandex` — это 3 stdio-хопа,
  ~200–500 ms каждый на вызов + инициализация N процессов. Смягчение: (а) кэш
  списков компонентов (`ProxyProvider cache_ttl`); (б) **не углублять рантайм без
  нужды** — репо-иерархия может быть глубокой, а *рантайм-топология* — плоской:
  `dj-music-mcp` может проксировать листья **напрямую** по `compose.*`, а `dj-music-mcp-platforms`
  существовать как отдельно-запускаемый gateway для других потребителей. Реко:
  ≤ 2 прокси-хопа в проде; горячий compute (transition/optimization) держать
  ближе к БД, не за лишними хопами.
- **Операционные издержки × N репозиториев:** у каждого свой `make check`,
  pre-push, `.env`, релиз. У тебя отключён GitHub Actions (billing lock) → гейт
  ручной в каждом репо. Это цена жёсткой инкапсуляции — закладывай шаблон репо
  (cookiecutter) и общий Makefile-фрагмент, чтобы не плодить расхождения.
- **`dj-music-contracts` — единая точка сопряжения и единая точка боли.** Держи его
  маленьким и стабильным; любое изменение — осознанный релиз.

---

## 7. Порядок разворачивания (первый заход)

1. **`dj-music-contracts`** — вынести протокол + shared-утилиты, опубликовать `0.1`
   (внутренний индекс/git-пакет). Все дальнейшие репо пинят его.
2. **`dj-music-mcp-yandex`** — первый leaf из `app/providers/yandex`; запустить и
   протестировать standalone (`fastmcp run`, in-memory client).
3. **`dj-music-mcp-db`** — вынести `models/repositories/db/handlers/…`; standalone.
4. **`dj-music-mcp`** — top-gateway: `compose.*` с двумя детьми (yandex+db, напрямую,
   плоский рантайм), кросс-доменный prompt «track import» (read→write). Проверить
   end-to-end.
5. **`dj-music-plugin`** — вычистить `app/`, оставить манифесты; `plugin.json`
   ссылается на `dj-music-mcp`. Проверить в Claude Code.
6. Добавлять leaf'ы (beatport/suno/soundcloud) и `dj-music-mcp-platforms` как под-gateway;
   позже — audio/setbuilder. Каждый — по шаблону п.2.

Текущий монолит остаётся рабочим, пока не собран п.4–5 (веди в параллельных
репозиториях, монолит замораживается и выпиливается последним).

---

## Приложение. Переиспользование паттерна для будущей системы

Чтобы «растить большую систему» — заведи два шаблона репозитория (cookiecutter):
`template-mcp-leaf` и `template-mcp-gateway`, плюс правило: **новый функционал =
новый Leaf**, **новая группировка = новый Gateway с `compose.*`**, **новый способ
доставки = новый Distribution**. Contract расширяется только когда появляется
новый общий тип обмена. Инварианты зависимостей из §1 — единый закон системы,
одинаковый на любом уровне вложенности.
```
