# FastMCP v3: полная карта возможностей + где я усложнял архитектуру

**Дата:** 2026-07-07 · **Статус:** reference (authoritative) · Итог сплошного
чтения документации `gofastmcp.com` (v3.x, ~50 страниц). Дополняет и местами
исправляет три предыдущих дока (topology / structure / deep-dive).

Ты был прав: я проектировал распределённую систему так, будто швы надо писать
руками, тогда как FastMCP даёт бо́льшую часть из коробки. Ниже — (1) что вы уже
используете правильно, (2) ранжированные упрощения, которые убирают ручной код на
швах, (3) пересмотренная **простая** архитектура, (4) компактный индекс всех
возможностей.

---

## 0. Что в монолите УЖЕ сделано правильно (не трогаем)

Проверено по коду (`app/server/transforms.py`, grep):
- `BM25SearchTransform` (встроенный) с `always_visible` — да.
- `PromptsAsTools`/`ResourcesAsTools` — да, через тонкие `JSONAware*`-сабклассы
  (обёртка ради stdio-квирка Claude Code, который стрингифицирует сложные
  аргументы). Это оправданная кастомизация, не переизобретение.
- `CodeMode` (experimental) — уже подключён за флагом `DJ_MCP_CODE_MODE`.
- `task=True` (Docket) на тяжёлых tools (`act_l5_set`, render_*), `Depends()`
  повсюду, `ProviderRegistry` через DI.

Вывод: внутренняя механика сервера — на уровне. Упущения — **на границах между
будущими серверами**, где я предлагал писать мосты/оркестраторы вручную.

---

## 1. Топ-упрощения: «было (мой план) → стало (встроенное)»

### 1.1 Gateway = конфиг, а не сервис с кодом ⭐️ главное

**Было:** я описывал gateway-репо с Python-кодом, `compose.*`, `policy/`, ручной
логикой mount.
**Стало:** `create_proxy(mcpServers-config)` строит агрегирующий gateway из
**чистого конфига**, с авто-namespacing. Плюс `fastmcp run <config>` умеет
запускать и `fastmcp.json`, и стандартный `mcpServers`-конфиг напрямую.

```python
# весь gateway — это буквально это:
from fastmcp.server import create_proxy
gateway = create_proxy({"mcpServers": {
    "yandex":   {"command": "uvx", "args": ["dj-music-mcp-yandex"]},
    "beatport": {"command": "uvx", "args": ["dj-music-mcp-beatport"]},
    "db":       {"url": "https://dj-db.internal/mcp", "transport": "http"},
}}, name="dj-music-mcp")
if __name__ == "__main__": gateway.run()
```

Gateway-репо ≈ один файл + `fastmcp.json`. Namespace, prefixing, lazy-connect,
session-isolation, feature-forwarding — бесплатно. «Реестр детей по ссылке» — это
и есть `mcpServers`-словарь.

### 1.2 Мосты между серверами = Tool Transformation, а не ручной MCP-клиент ⭐️

**Было:** я предлагал `providers_client.py` в core — рукописный MCP-клиент,
который зовёт провайдер-серверы, переименовывает, инжектит креды.
**Стало:** смонтируй/проксируй провайдер-сервер и переформуй его surface
**декларативно**:
- `ToolTransform({"old": ToolTransformConfig(name="new", description=...)})` —
  переименование/чистка без правки чужого репо.
- `ArgTransform(hide=True, default=...)` / `default_factory=...` — **инжект
  credentials / tenant-id / request-id**, скрытых от LLM.
- `transform_fn` + `forward()` — обернуть выполнение (валидация, пост-обработка)
  без «мостового» кода.
- `Depends()` — прятать `uow`/креды/коннекты из схемы (вы уже так делаете).

То есть adapter-слой между серверами — это transforms на границе, а не сервис.

### 1.3 Оркестрация кросс-сервер = Code Mode / prompts, а не сервис-оркестратор ⭐️

**Было:** я допускал отдельный `dj-music-mcp-orchestrator`-leaf для «read платформы →
write в db».
**Стало:** у вас **уже** есть `CodeMode` (за флагом). Он даёт LLM три meta-tool
(`search`/`get_schema`/`execute`) и sandbox, где LLM пишет Python, чейнящий
`call_tool(...)` по всем смонтированным серверам, и возвращает только результат.
«Импорт трека» = сгенерированный код `t = call_tool("yandex_provider_read", ...);
call_tool("db_entity_create", ...)`. Ноль серверного glue. Prompt-driven путь
(ваши 30 workflow) — второй вариант. Оркестратор-leaf не нужен.

### 1.4 Правила взаимодействия = три встроенных механизма, а не свой «policy-слой»

**Было:** абстрактный «слой правил» в gateway.
**Стало:** конкретика (транспортная матрица — deep-dive §0):
- **Visibility** (`enable/disable`, `only=True`, per-session `ctx.enable_components`)
  — экспозиция, любой транспорт.
- **Authorization** (`@tool(auth=require_scopes(...))`, `AuthMiddleware`,
  `restrict_tag`) — по вызывающему, **только HTTP**.
- **Middleware** (rate-limit/audit/cache/деньги/ошибки, отказ = `raise ToolError`)
  — любой транспорт.
- **`MultiAuth(server=OAuthProxy(...), verifiers=[JWTVerifier(...)])`** — на одном
  gateway: внешние потребители через OAuth, внутренние leaf'ы через M2M-JWT.

### 1.5 Инкапсуляция+доверие сервер-к-серверу = JWT, а не своя схема ⭐️

**Было:** «контрактные ограничения» на словах.
**Стало:** канонический M2M-паттерн: на каждом сервере
`FastMCP(auth=JWTVerifier(jwks_uri=..., issuer=..., audience=<per-server>))`,
вызывающий шлёт Bearer-JWT (`Client(url, auth="<jwt>")`). Уникальный `audience`
на сервер = токен нельзя переиспользовать между сервисами. Централизованный
издатель + общий JWKS = ротация ключей без раздачи секретов. Это и есть «жёсткие
правила взаимодействия» — по HTTP, без кастома. Референс всей модели —
**sandboxed-agents** («capabilities, not credentials»): секреты на gateway,
потребитель с коротким scoped-токеном, tools как узкие капабилити.

### 1.6 Распределённое состояние и фоновые задачи — флагом

- `FastMCP(session_state_store=RedisStore(...))` — session-state между
  рестартами/инстансами без своей инфры (`serializable` контролирует scope).
- `@tool(task=True)` + `FASTMCP_DOCKET_URL=redis://...` + `fastmcp tasks worker` —
  дистрибутивные фоновые задачи. **Прямо заменяет ваш ручной обход 120s-таймаута**
  для batch MP3-download / L5-reanalyze (сейчас — батчами по 3–5 под лимит; с
  Docket/Redis — просто background task + polling).

### 1.7 Общий код между серверами = standalone `LocalProvider`, а не только пакет

Помимо `dj-music-contracts` (типы), общие **готовые компоненты** можно держать в
standalone `LocalProvider` и подключать к нескольким серверам
(`FastMCP(providers=[shared])`) — без дублирования и с precedence (локальный
override поверх общего).

### 1.8 Дистрибуция — CLI, а не ручные скрипты

- `fastmcp.json` (source/environment/deployment) на каждый репо; `fastmcp project
  prepare` → детерминированный `.venv`+lock.
- `uvx fastmcp-remote <https-url>` — мост HTTP-gateway → stdio для Claude Code.
- `fastmcp install {claude-code,cursor,mcp-json,stdio}` — генерация конфигов.
- `fastmcp run <URL>` — локальный proxy-мост к удалённому серверу.
- `fastmcp generate-cli <server>` — typed CLI + `SKILL.md` из любого сервера.

---

## 2. Возможно, самое большое упрощение: Prefect Horizon

Ты строишь руками ровно то, что уже есть как управляемая платформа от команды
FastMCP (**free personal tier**):

| Ты хочешь построить | Horizon даёт |
|---|---|
| Distribution/деплой каждого репо | **Deploy** — из GitHub-репо в живой URL за ~60s, авто-редеплой на push, preview на каждый PR |
| Marketplace-«зонтик» / реестр серверов | **Registry** — каталог MCP-серверов (свои/сторонние/**curated remix из нескольких источников**) |
| Слой правил (RBAC, кто что видит) | **Gateway** — role-based access control, auth, audit-логи, **на уровне tool** |
| Композиция нескольких серверов для потребителя | **Agents** — чат поверх одного/нескольких MCP-серверов (композиция капабилити) |

«Curated remix servers composed from multiple sources» = твоя агрегация
platforms+db+audio. «Gateway с tool-level RBAC» = твой слой правил. То есть
распределённую композицию + реестр + правила можно **не писать**, а взять.
Проверка совместимости репо: `fastmcp inspect server.py:mcp`.

Это не значит «обязательно Horizon» — но это референс и реальный shortcut. Если
хочется своё/on-prem — п.1 показывает, что даже своими силами это в основном
конфиг+transforms+JWT, а не сервисы.

---

## 3. Пересмотренная (простая) распределённая архитектура

Архетипы из topology-дока остаются, но **стоимость реализации схлопывается**:

| Слой | Было (мой план) | Стало (встроенное FastMCP) |
|---|---|---|
| **Leaf** (yandex/beatport/db/…) | FastMCP-сервер + tools | без изменений — `fastmcp.json` + `@tool`; auth=`JWTVerifier` если HTTP |
| **Gateway** (platforms / dj-music-mcp) | Python-сервис + `compose.*` + policy + providers_client | `create_proxy(mcpServers-config)` + transforms-файл; правила = visibility+`MultiAuth`+middleware |
| **Мост core↔провайдеры** | рукописный MCP-клиент | mount/proxy + `ArgTransform(hide=True)` для credentials |
| **Кросс-сервер оркестрация** | orchestrator-leaf | Code Mode (уже есть) или prompt |
| **Rules** | абстрактный policy-слой | Visibility + Authorization(HTTP) + Middleware + JWT audience |
| **State/queue** | своя инфра | `session_state_store=Redis` + `task=True`/Docket |
| **Distribution** | ручные bash | `fastmcp.json` + `fastmcp-remote` + `install` |
| **Реестр/RBAC/деплой** | marketplace-репо + свой gateway | опц. Prefect Horizon (Registry+Gateway+Deploy) |

**Итог:** «жёсткая инкапсуляция + гибкость + правила» достигается конфигом
(`mcpServers`), декларативными transforms и JWT-audience — не сервисным кодом на
каждом шве. Отдельные репо остаются (инкапсуляция), но каждый gateway — тонкий.

**Один нюанс, который НЕ упрощается:** per-caller правила (scopes/tenant) требуют
**HTTP + токен** — на stdio они пропускаются. Значит серьёзные точки принуждения
(gateway) деплой как HTTP с `JWTVerifier`/`MultiAuth`; локальный dev — stdio с
visibility+middleware. Это не сложность FastMCP, а природа модели.

---

## 4. Компактный индекс возможностей (для справки — «что вообще есть»)

**Провайдеры** (`servers/providers/*`): `LocalProvider` (декораторы, всегда
первый), `FastMCPProvider` (`mount`), `ProxyProvider` (`create_proxy`, cache_ttl,
session-reuse, mirrored `.copy()`), `OpenAPIProvider` (`from_openapi`/`from_fastapi`,
RouteMap), `FileSystemProvider` (auto-discovery, `reload`), `SkillsDirectoryProvider`
(`skill://`, vendor-провайдеры, `sync_skills`), Custom (`_list_tools` + `lifespan`,
DB-backed).

**Transforms** (`servers/transforms/*`): `Namespace`, `ToolTransform`/`Tool.from_tool`
+`ArgTransform` (rename/hide/inject/`transform_fn`+`forward`), `Visibility`,
`VersionFilter`, `PromptsAsTools`/`ResourcesAsTools`, **Tool Search**
(`BM25SearchTransform`/`RegexSearchTransform`, `always_visible`, `max_results`),
**Code Mode** (`search`/`get_schema`/`execute`, sandbox limits, discovery patterns),
custom `Transform` (list=pure / get=middleware).

**Правила/доступ:** Visibility (`enable/disable`, `only=True`, keys/tags, per-session
`ctx.*`), Authorization (`auth=` + `AuthMiddleware`, `require_scopes`/`restrict_tag`/
custom, **HTTP-only**), Middleware (hooks `on_*`, built-in: Logging/Timing/
**RateLimiting**/**ResponseCaching**/ErrorHandling/Retry/Ping/**ResponseLimiting**).

**Auth** (`servers/auth/*`): `TokenVerifier` (`JWTVerifier` JWKS/HMAC/static,
`IntrospectionTokenVerifier`, `StaticTokenVerifier`/`DebugTokenVerifier`),
`RemoteAuthProvider` (DCR: WorkOS/Descope, `AuthKitProvider`), `OAuthProxy`/`OIDCProxy`
(не-DCR: GitHub/Google/Auth0/Azure, token-factory, consent), `MultiAuth`
(server+verifiers), `OAuthProvider` (full, избегать). Storage: `RedisStore`/
`FileTreeStore`+`FernetEncryptionWrapper` для distributed OAuth-state. CIMD (v3).
Клиент: `auth="<jwt>"`/`BearerAuth`, `auth="oauth"`/`OAuth(...)`.

**Композиция:** `mount(server, namespace=)`, `create_proxy(url|path|transport|config)`,
conflict-resolution, recursive tag-filter, composable `lifespan` (`|`), state НЕ
пересекает mount (общий `session_state_store` или `serializable=False`).

**Ядро/примитивы:** `@tool`(`timeout`,`version`,`annotations`,`meta`,`output_schema`,
`ToolResult`), `@resource`+templates (RFC6570 `{?query}`,`{path*}`,`ResourceResult`),
`@prompt`(`Message`,`PromptResult`), `Context` (state async, elicit, sample,
progress, transport, session-visibility), DI (`Depends`, `Current*`, `get_*`,
per-request cache, param-hiding), lifespan, **tasks** (`task=True`, Docket/Redis,
`fastmcp tasks worker`, Progress), elicitation (accept/decline/cancel, defaults,
multi-select), sampling (`ctx.sample`, tools/structured/`sample_step`, fallback
handlers).

**Apps/Prefab UI** (`apps/*`, `fastmcp[apps]`, пинить `prefab-ui` точно): Prefab
(`@tool(app=True)`, `PrefabApp`, `Rx`/`ForEach`/`If`, state), `FastMCPApp`
(`@app.ui`/`@app.tool`, `CallTool(fn)` переживает namespacing, Actions, `Form.from_model`),
GenerativeUI (LLM пишет UI в Pyodide-sandbox). Вы уже используете 6 UI-tools.

**Deploy/CLI:** `fastmcp.json` (source/env/deployment, `editable`, `${VAR}`),
`fastmcp run|dev|install|inspect|list|call|discover|generate-cli|project prepare|
auth cimd`, HTTP (`http_app`, `stateless_http` для scale, custom_route health,
EventStore/SSE-polling, nginx `proxy_buffering off`), `fastmcp-remote`, **Prefect
Horizon** (managed Deploy/Registry/Gateway/Agents).

**Settings (`FASTMCP_*`):** `MASK_ERROR_DETAILS`, `STATELESS_HTTP`, `STRICT_INPUT_VALIDATION`,
`DOCKET_URL`/`DOCKET_CONCURRENCY` (tasks), `LOG_LEVEL`, `HOST/PORT/PATH`, `HOME`,
`ENV_FILE`.

**v2→v3 (пин `>=3.0,<4`):** конструктор без transport-kwargs (→`run()`);
`import_server`→`mount`; `as_proxy`→`create_proxy`; `fastmcp.server.proxy`→
`.providers.proxy`; `get_tools()`→`list_tools()` (списки); `ctx.*_state` async;
`Message`/`PromptResult`/`ResourceResult`/`ToolResult`; `WSTransport` удалён;
декораторы возвращают функцию; repo `PrefectHQ/fastmcp`.

---

## 5. Практические правки к моим прошлым докам

1. topology §3.4/§4: gateway-репо — **не** Python-сервис, а `create_proxy(config)`
   + опц. transforms-файл. Убрать `providers_client`; core↔провайдеры — mount+
   ArgTransform.
2. topology §4: оркестрацию кросс-сервер вести Code Mode (уже интегрирован) или
   prompt; `dj-music-mcp-orchestrator`-leaf не заводить.
3. deep-dive §7: добавить `MultiAuth` (внешний OAuth + внутренний M2M-JWT на одном
   gateway) и `session_state_store=Redis` / `task=True` как замену ручным обходам.
4. Рассмотреть **Prefect Horizon** как альтернативу ручным marketplace+gateway+RBAC
   (free personal tier, deploy-from-GitHub, tool-level RBAC, Agents-композиция).
5. Долгие jobs (L5/download) на новых серверах — сразу `task=True`+Docket/Redis, а
   не батчи под 120s-таймаут.

---

## Источники
Полный список прочитанных страниц (≈50) — в предыдущих доках + этой сессии:
providers/{overview,proxy,custom,filesystem,local,skills}, transforms/{transforms,
tool-transformation,namespace,prompts-as-tools,resources-as-tools,tool-search,
code-mode}, {authorization,middleware,visibility,versioning,tool-fingerprinting},
auth/{authentication,token-verification,oauth-proxy,oidc-proxy,remote-oauth,
multi-auth,full-oauth-server}, storage-backends, {server,tools,resources,prompts,
context,lifespan,tasks,elicitation,sampling,dependency-injection}, apps/{overview,
prefab,fastmcp-app,generative}, deployment/{http,server-configuration,sandboxed-agents,
prefect-horizon}, cli/{overview,running,install-mcp,inspecting,generate-cli,client,auth},
clients/{transports,fastmcp-remote,auth/bearer,auth/oauth}, integrations/{openapi,
fastapi,mcp-json-configuration}, getting-started/upgrading/from-fastmcp-2, more/settings,
patterns/contrib.
