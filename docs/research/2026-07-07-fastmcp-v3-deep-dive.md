# FastMCP v3 deep-dive: механизмы для распределённой системы MCP

**Дата:** 2026-07-07 · **Статус:** reference · Уточняет и исправляет
[2026-07-07-distributed-repo-topology.md](./2026-07-07-distributed-repo-topology.md)
после сплошного чтения docs (`gofastmcp.com`, v3.x).

Документ разбирает механизмы FastMCP v3, которые прямо обслуживают три твоих
требования — **строгая инкапсуляция**, **гибкость взаимодействия**,
**настраиваемые правила и ограничения** — и фиксирует, что из моего прошлого
описания было неточным.

---

## 0. Главная поправка: «правила взаимодействия» — это ТРИ разных механизма, и они работают на разных транспортах

В прошлом доке я свалил «правила» в один слой. На деле в v3 это три независимых
механизма с разной семантикой и, критично, **разной зависимостью от транспорта**:

| Механизм | Что делает | Гранулярность | Работает на stdio? | Работает на HTTP? |
|---|---|---|---|---|
| **Visibility** (`enable`/`disable`, `only=True`, `ctx.enable_components`) | какие компоненты вообще существуют/видны | сервер / провайдер / **сессия** | **да** | да |
| **Middleware** (`on_call_tool`, raise `ToolError`, фильтрация списков, rate-limit, cache, audit) | произвольная кросс-логика вокруг вызова | сервер (рекурсивно на mounted) | **да** | да |
| **Authorization** (`auth=` на компоненте + `AuthMiddleware`, `require_scopes`/`restrict_tag`/custom) | доступ **по личности вызывающего** (scopes/claims токена) | компонент / сервер | **НЕТ** (токена нет → проверки пропускаются) | да |

**Практический вывод для твоей системы:** пока серверы соединены по **stdio**
(локальный запуск как subprocess), правила ограничиваются структурой (Visibility)
и middleware — **правил «по вызывающему» (scopes/tenant/roles) нет**, потому что в
stdio нет OAuth-токена (`get_access_token()` → `None`, все `auth`-проверки молча
проходят). Настоящие per-caller/per-tenant ограничения между серверами
**требуют HTTP-транспорта + верификации токена**. Это меняет вывод предыдущего
дока: серьёзные точки принуждения правил должны быть **HTTP-gateway'ями с
токен-верификатором**, а не stdio-цепочкой. Референс — раздел 4 (sandboxed-agents).

### 0.1 Visibility — структурная экспозиция (любой транспорт)

Точная механика (`servers/visibility`, v3.0.0):
- `mcp.disable(tags={...})` / `mcp.enable(tags={...})`, по `keys={"tool:name"}` или
  `tags`. Компонент выключен, если совпал **хотя бы один** выключенный тег.
- `mcp.enable(tags={...}, only=True)` — **allowlist-режим**: всё, кроме указанного,
  выключено. Именно это — «экспонировать наверх только provider:read».
- Позже вызванный `enable`/`disable` **переопределяет** ранее вызванный → «широкое
  правило + точечные исключения».
- **Provider-level vs server-level:** провайдер может задать дефолтную видимость,
  но **сервер имеет финальное слово** (его transforms применяются после).
- **Per-session** (`ctx.enable_components(tags=...)` / `disable_components` /
  `reset_visibility`) — правила только для текущей сессии, шлёт `list_changed`.
  Паттерн «namespace activation»: держать домены выключенными глобально, а
  activation-tool включает их для сессии. (У тебя аналог — `unlock_namespace`.)
- Tag-фильтры родителя применяются **рекурсивно** к mounted-серверам.

### 0.2 Middleware — произвольная политика (любой транспорт)

`servers/middleware` (v2.9.0). Пайплайн вокруг операций; `call_next` продолжает,
не вызвать — остановить. Хуки от общего к частному: `on_message` → `on_request` →
`on_call_tool`/`on_read_resource`/`on_get_prompt`; плюс `on_list_tools` (фильтрация
списка перед выдачей). Отказ = **raise** `ToolError`/`ResourceError`/`PromptError`
(не возврат значения). Встроенные: Logging, Timing, **RateLimiting** (token-bucket
и sliding-window), **ResponseCaching** (TTL, storage backends), ErrorHandling/Retry,
Ping, **ResponseLimiting** (обрезка больших ответов). Композиция: **middleware
родителя выполняется для ВСЕХ запросов**, включая mounted; middleware ребёнка —
только для его запросов. **State не пересекает границу mount** (каждый FastMCP
владеет своим session-state-store; шарить через общий `session_state_store` или
`serializable=False`) — моё прошлое утверждение верно.

### 0.3 Authorization — по личности вызывающего (только HTTP)

`servers/authorization` (v3.0.0). Callable `AuthContext → bool`, AND-логика.
- `@mcp.tool(auth=require_scopes("admin"))` — компонент-уровень: управляет и
  видимостью (скрыт из списка), и доступом (not-found при вызове).
- `AuthMiddleware(auth=restrict_tag("admin", scopes=["admin"]))` — сервер-уровень,
  даёт явный `AuthorizationError`.
- `restrict_tag(tag, scopes=...)` — «если у компонента тег X, нужен scope Y».
- Custom-фабрики: `require_access_level(5)`, `require_premium_user`, async-проверки
  (читать server state / внешний сервис).
- **Оговорка (жирная):** в **stdio** OAuth-токена нет → `auth`-проверки
  **пропускаются**. Authorization имеет смысл только на HTTP-серверах с
  верификатором токена (раздел 3).

---

## 1. Provider-система — то, что я недоиспользовал

Каждый FastMCP-сервер — это набор **провайдеров** компонентов (`servers/providers`,
v3.0.0). Клиент спрашивает «какие tools?» — сервер опрашивает все провайдеры и
объединяет.

| Провайдер | Что | Как получить |
|---|---|---|
| `LocalProvider` | компоненты из декораторов `@mcp.tool` | по умолчанию, всегда **первый** |
| `FastMCPProvider` | обёртка другого FastMCP-сервера | `mcp.mount(server)` |
| `ProxyProvider` | подключение к другому MCP по сети/процессу | `create_proxy(client)` |
| `OpenAPIProvider` | генерация из OpenAPI-спеки | `FastMCP.from_openapi(...)` |
| `FileSystemProvider` | авто-дискавери из файлов | (твой текущий способ) |
| Custom | компоненты из БД/API/конфига динамически | subclass `Provider` |

**Порядок:** `LocalProvider` всегда первый; дальше — в порядке добавления; **первый
провайдер, у которого есть tool, обслуживает вызов**. (Нюанс vs composition-доки:
там «последний примонтированный побеждает» — это про конфликт имён в одном
namespace через Namespace-transform; на уровне провайдеров правило «первый
выигрывает». Практически: **всегда namespace'и mounted-серверы**, тогда конфликтов
нет и оба правила не важны.)

**Custom Provider** (`servers/providers/custom`) — override `_list_tools/_list_resources/
_list_prompts` + `lifespan()` для коннекта к БД. Возвращают готовые `Tool.from_function(...)`.
Для `dj-mcp-db` это опция, если часть tools хочется задавать динамически из
Supabase; для статичного surface достаточно декораторов/FileSystemProvider.
Важное разделение из доки: **Provider = откуда компоненты; Middleware/Visibility =
что с ними можно** — не смешивать.

---

## 2. `create_proxy` — детали, подтверждённые docs

- Принимает URL / путь к файлу / transport / **config-dict** (`mcpServers`) напрямую.
  Multi-server config → авто-namespacing (`weather_get_forecast`).
- **Ленивый мост:** upstream не трогается до `initialize` от клиента; статус прокси
  = статус upstream (недоступен/не MCP/auth не прошёл → init прокси падает).
- **Транспортный мост в обе стороны:** HTTP-бэкенд наружу по stdio (`proxy.run()`)
  или stdio-сервер наружу по HTTP (`proxy.run(transport="http")`).
- **Session isolation по умолчанию** (каждый запрос — своя upstream-сессия). Shared
  session — только single-threaded (context mixing). Для stateless HTTP — можно
  reuse (`FastMCPProxy(client_factory=lambda: shared)`) ради латентности.
- **Feature forwarding:** Roots/Sampling/Elicitation/Logging/Progress форвардятся
  авто; выключить точечно — `ProxyClient(sampling_handler=None, log_handler=None)`.
  → это тоже рычаг правил: например, запретить leaf'у инициировать sampling наверх.
- **Кэш списков компонентов** `ProxyProvider(cache_ttl=60)` (default 300s, `0`=off).
- **Mirrored components:** проксированные компоненты read-only; чтобы
  переименовать/выключить — `.copy()` локально.

---

## 3. Верификация токена — как серверы доверяют вызовам (микросервисный канон)

`servers/auth/token-verification`. Сервер = **resource server**: валидирует токены,
не занимается их выпуском. Это ключ к правилам между распределёнными серверами.

```python
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier

# JWKS (ротация ключей автоматически) — для внешних/prod
auth = JWTVerifier(jwks_uri="https://auth.you/.well-known/jwks.json",
                   issuer="https://auth.you", audience="dj-mcp")
# HMAC (общий секрет) — для внутренних микросервисов (проще, быстрее)
auth = JWTVerifier(public_key="shared-secret-32+chars", issuer="internal",
                   audience="dj-internal", algorithm="HS256")
mcp = FastMCP("dj-mcp", auth=auth)
```

Варианты: `JWTVerifier` (JWKS / статический ключ / HMAC), `IntrospectionTokenVerifier`
(opaque-токены через RFC 7662 introspection — мгновенный revoke ценой сетевого
хопа), `StaticTokenVerifier`/`DebugTokenVerifier` (dev). Микросервисный паттерн из
доки: центральный auth-сервис выпускает токены → **каждый сервер валидирует
независимо** (общий JWKS или HMAC-секрет). Это и есть механизм «правил
взаимодействия между серверами», который работает **по HTTP**.

---

## 4. Sandboxed-agents = референс-архитектура ровно под твою систему

`deployment/sandboxed-agents` описывает то, что ты формулируешь как «жёсткая
инкапсуляция + правила», почти дословно. Принцип: **«давай возможности, а не
credentials»** (*capabilities, not credentials*).

- Привилегированные ключи (Supabase, YM-токен, Suno-cookie) держит **сервер
  (gateway)**, а не потребитель/leaf.
- Потребитель (Claude Code, Codex, sandbox-агент, другой сервис) получает
  **короткоживущий scoped-токен** и ходит по **HTTP**.
- Сервер: верифицирует токен → авторизует по scopes/claims → **экспонирует только
  нужные tools** → сам ходит в привилегированные upstream (БД, API, другие MCP).
- **Инструменты — узкие капабилити, не сырой доступ:** `write_summary`,
  `publish_review_comment` — да; `run_sql`, `call_internal_api` — нет (толкает
  привилегию и политику в потребителя, где их не проконтролировать).
- **Проксируй более привилегированный upstream** через gateway, не форвардь секреты
  вниз. Ревокация и аудит — на границе сервера.

Прямое отображение на dj-music: `dj-mcp` (top-gateway, HTTP) держит все секреты,
верифицирует токен потребителя, авторизует, проксирует leaf'ы с сильными
credentials. Leaf'ы (`dj-mcp-db`, провайдеры) — за gateway, не выставлены наружу.
Это и есть «жёсткое разделение + гибкость + правила» в терминах FastMCP.

> Следствие: для локального dev достаточно stdio-цепочки (правила = visibility +
> middleware). Для «большой системы» с multi-tenant/внешними потребителями —
> gateway'и деплоятся как **HTTP** с токен-верификацией, и правила становятся
> полноценными (per-caller). Проектируй tools как узкие капабилити с самого начала
> — это единственный слой, который одинаково работает на обоих транспортах.

---

## 5. Эволюция контракта: versioning + tool fingerprinting (anti-drift для растущей системы)

Твоя система будет расти → контракты будут меняться. В v3 два штатных инструмента,
которые я раньше свёл к «semver пакета»:

**Component versioning** (`servers/versioning`, v3.0.0):
```python
@components.tool(version="1.0")
def calculate(x, y): ...
@components.tool(version="2.0")
def calculate(x, y, z=0): ...
api_v1 = FastMCP(providers=[components]); api_v1.add_transform(VersionFilter(version_lt="2.0"))
api_v2 = FastMCP(providers=[components]); api_v2.add_transform(VersionFilter(version_gte="2.0"))
```
- Клиент по умолчанию видит **высшую** версию; можно запросить конкретную
  (`call_tool(..., version="1.0")` или `_meta.fastmcp.version`).
- `meta.fastmcp.versions` — дискавери всех версий.
- `VersionFilter` на родителе применяется **и к mounted-серверам** (после
  namespacing) → единая версионная политика на всю иерархию.
- Нельзя мешать versioned и unversioned компоненты с одним именем.

**Tool fingerprinting** (`servers/tool-fingerprinting`, v3.0.0): собери стабильный
хеш контракта из `tool.key` (`tool:name@version`) + `tool.to_mcp_tool()` (input
schema), опционально description/outputSchema/annotations. Генерь manifest в CI и
сравнивай между деплоями → **детект дрейфа схемы**. Для multi-repo это backbone:
каждый leaf публикует fingerprint-manifest; gateway/CI ловит несовместимые
изменения контракта до релиза. Сильнее, чем просто «bump версии пакета».

---

## 6. Запуск и деплой каждого репо

**`fastmcp.json`** (`deployment/server-configuration`, v2.12.0) — канонический
декларативный конфиг: `source` (WHERE, `path`+`entrypoint`), `environment` (WHAT,
`type:uv`, `python`, `dependencies`/`requirements`/`project`/**`editable`**),
`deployment` (HOW, `transport`, `host`/`port`/`path`, `env` с `${VAR}`-интерполяцией,
`cwd`, `args`). CLI переопределяет поля. `fastmcp project prepare` отделяет
медленный build env от быстрого run.
- **`editable: [".", "../dj-music-contracts"]`** — важно: даёт editable-инстал общего
  пакета даже при разработке нескольких репо рядом (мост между «репо изолированы» и
  «удобно править контракт локально»).

**HTTP-деплой** (`deployment/http`):
- `mcp.run(transport="http", host="0.0.0.0", port=...)` или ASGI `app = mcp.http_app()`
  под uvicorn/gunicorn.
- **Горизонтальное масштабирование → `stateless_http=True`** (sticky sessions с MCP
  не работают: клиенты Cursor/Claude Code на `fetch()` не форвардят cookie).
- `@mcp.custom_route("/health")` — health-check (никогда не под auth).
- Долгие операции за LB → `EventStore` + `ctx.close_sse_stream()` (SSE polling);
  nginx: `proxy_buffering off`, `proxy_read_timeout 300s`.

**Distribution → gateway (важное дополнение):** если gateway задеплоен как **HTTP**,
плагин Claude Code ссылается на него через **`uvx fastmcp-remote <url>`**
(`clients/fastmcp-remote`) — stdio↔remote мост для хостов, которые умеют только
запускать локальную команду:
```json
{ "mcpServers": {
    "dj-mcp": { "command": "uvx",
      "args": ["fastmcp-remote", "https://dj-mcp.you/mcp",
               "--header", "Authorization: Bearer ${DJ_TOKEN}"] } } }
```
OAuth включается авто для HTTPS; токены кэшируются в `~/.fastmcp/remote`. Это чище,
чем `uvx <package>`-запуск локально, когда gateway живёт как сервис. Для локального
gateway остаётся `uvx <package> run` (stdio).

---

## 7. Что уточнить в топологии (правки к предыдущему доку)

1. **«Слой правил» = три механизма, не один.** Visibility (структура, любой
   транспорт) + Middleware (политика, любой транспорт) + Authorization (по
   вызывающему, **только HTTP**). Впиши в gateway policy/ явно.
2. **Транспорт определяет силу правил.** stdio-цепочка = только структура+middleware.
   Per-caller/tenant правила ⇒ gateway на **HTTP** + `JWTVerifier`. Референс —
   sandboxed-agents.
3. **Секреты — на gateway, не в leaf/потребителе** («capabilities, not credentials»).
   Провайдеры-leaf за gateway, наружу выставлен только gateway.
4. **Tools = узкие капабилити** с самого начала (единственный слой правил,
   работающий и на stdio, и на HTTP).
5. **Anti-drift = versioning + fingerprinting**, а не только semver пакета
   `dj-music-contracts`. Каждый leaf/gateway публикует fingerprint-manifest в своём гейте.
6. **Feature-forwarding как правило:** `ProxyClient(sampling_handler=None, ...)` —
   ограничить, что leaf может инициировать наверх.
7. **Distribution-связка:** `uvx fastmcp-remote <https-url>` для HTTP-gateway;
   `uvx <package> run` для локального stdio-gateway. Оба валидны, выбор по деплою.
8. **`editable` в fastmcp.json** снимает часть боли мультирепо при локальной
   правке `dj-music-contracts`.

---

## Источники (прочитано целиком)

- Providers overview / proxy / custom: gofastmcp.com/servers/providers/{overview,proxy,custom}.md
- Composition: /servers/composition.md · Visibility: /servers/visibility.md
- **Authorization**: /servers/authorization.md · Middleware: /servers/middleware.md
- **Token verification**: /servers/auth/token-verification.md
- **Sandboxed agents**: /deployment/sandboxed-agents.md
- Versioning: /servers/versioning.md · Tool fingerprinting: /servers/tool-fingerprinting.md
- HTTP deployment: /deployment/http.md · fastmcp.json: /deployment/server-configuration.md
- fastmcp-remote (stdio↔remote): /clients/fastmcp-remote.md
- Индекс: /llms.txt
