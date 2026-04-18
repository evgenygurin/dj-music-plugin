# Промпты для фоновых агентов — доработка компонентов dj-music-plugin

> **HISTORICAL — pre-v1.0.0 snapshot (early April 2026).** Файл содержит батч
> промптов, составленных до v1 рефактора: ссылки на `app/controllers/tools/`,
> `app/services/`, `app/api/server.py`, «50 MCP tools», layered 5-band
> architecture — всё это не соответствует текущему коду (v1.0.1 — 13
> dispatchers + 27 resources + 6 prompts поверх flat `app/{tools,resources,
> prompts,handlers,registry,repositories,models,schemas,domain,audio,
> providers,server,rest,shared,config,db}/`). Живые пути и названия tools
> смотри в `docs/architecture.md`, `docs/tool-catalog.md`,
> `.claude/agents/panel-doctor.md` (секция «v1 tool names»).
>
> Оставлено как архив паттернов для batch-прогонов subagent'ов — сами
> инструкции можно переиспользовать, но подставить актуальные пути.
>
> Каждый промпт самодостаточный, не требует контекста родительского чата.
> Запускать через `Agent` tool с `subagent_type: general-purpose` (или
> указанным) и `run_in_background: true`. Все агенты должны открывать PR
> в ветку `dev`, не пушить в `main`.

---

## 1. HOOKS — аудит и доработка

**subagent_type**: `general-purpose`

```text
Ты дорабатываешь hooks плагина dj-music-plugin (cwd: /Users/laptop/dev/dj-music-plugin).

Контекст:
- Плагин определяет hooks в ДВУХ местах одновременно — это уже подозрительно:
  • hooks/hooks.json (plugin-level, поставляется вместе с плагином)
  • .claude/settings.json (project-level, локальная настройка проекта)
- В hooks/hooks.json есть SessionStart с двумя записями: первая — echo с additionalContext (50 MCP tools), вторая — bash scripts/start-services.sh со statusMessage "Starting DJ Music backend + panel...".
- В .claude/settings.json — отдельный SessionStart на .claude/hooks/start-servers.sh с timeout 60. Скрипта start-servers.sh может не существовать вообще.
- Backend MCP-сервер (fastmcp) и так стартует через mcpServers в .claude-plugin/plugin.json. Запуск через хук дублирует запуск.

Задачи:
1. Прочитай hooks/hooks.json, .claude/settings.json, .claude-plugin/plugin.json, scripts/start-services.sh (если есть), .claude/hooks/* (если есть).
2. Выясни: какой из двух SessionStart-хуков реально нужен, что делает каждый скрипт, есть ли дубли (mcpServers уже стартует backend).
3. Изучи официальную документацию Claude Code по hooks (события, exit codes, JSON output, matcher regex). Используй WebFetch для https://docs.claude.com/en/docs/claude-code/hooks.
4. Найди проблемы: дубли запуска, отсутствующие файлы, неправильные matcher-ы, отсутствующий timeout, hardcoded пути ($CLAUDE_PROJECT_DIR vs ${CLAUDE_PLUGIN_ROOT}), missing JSON output, exit codes.
5. Предложи минимальный набор хуков для плагина: SessionStart с additionalContext (контекст для модели), при необходимости PostToolUse для логирования вызовов dj-music tools, Stop для graceful shutdown panel/backend.
6. Реализуй изменения. Plugin-level hooks должны жить ТОЛЬКО в hooks/hooks.json (project-level .claude/settings.json не должен дублировать plugin hooks). Удали дубли.
7. Создай ветку fix/hooks-audit от dev, закоммить, открой PR с объяснением что дублировалось и почему.

Не трогай ничего вне hooks/, .claude/hooks/, .claude/settings.json, scripts/start-services.sh. Не меняй MCP servers. Отчёт ≤300 слов.
```

---

## 2. SKILLS — ревизия 5 skills плагина

**subagent_type**: `general-purpose`

```text
Ты ревизируешь 5 skills плагина dj-music-plugin (cwd: /Users/laptop/dev/dj-music-plugin):
skills/build-set, skills/curate-library, skills/deliver-set, skills/expand-playlist, skills/ym-sync.

Контекст skills:
- Каждый skill = SKILL.md с frontmatter (name, description) + опционально supporting files.
- description ≤250 chars, должен начинаться с "Use when..." или "This skill should be used when..." и содержать триггер-ключевые слова — Claude использует description чтобы решить когда auto-invoke.
- Skill не должен дублировать содержимое CLAUDE.md или docs/*.md — должен ссылаться на них через @import или просто упоминать пути.
- Каждому skill соответствует slash-command в commands/<name>.md — они НЕ должны дублировать друг друга. Команда вызывает skill, skill содержит логику.

Задачи:
1. Прочитай все 5 SKILL.md, все 5 commands/<name>.md, и docs/tool-catalog.md (50 tools).
2. Изучи официальную доку https://docs.claude.com/en/docs/claude-code/skills (frontmatter, progressive disclosure, best practices).
3. Для каждого skill оцени:
   - description: длина, наличие триггеров, формулировка "Use when..."
   - корректность списка MCP tools (актуально к docs/tool-catalog.md, нет упоминаний удалённых tools)
   - дублирование с command-файлом
   - дублирование с CLAUDE.md/docs
   - наличие конкретных примеров вызовов tools
   - structure: пошаговый workflow, не свалка фактов
4. Для каждого skill выпиши конкретные fix-ы (не более 5 штук на skill), затем реализуй их.
5. Ветка: fix/skills-audit от dev. Один коммит на skill (5 коммитов). PR в dev.

Отчёт: таблица "skill → найдено проблем → исправлено" + список самых крупных правок. ≤400 слов.
```

---

## 3. PLUGIN MANIFEST + MARKETPLACE — валидация

**subagent_type**: `plugin-dev:plugin-validator`

```text
Провалидируй структуру плагина dj-music-plugin (cwd: /Users/laptop/dev/dj-music-plugin) и исправь найденные проблемы.

Что проверить:
1. .claude-plugin/plugin.json:
   - все обязательные поля (name, version, description)
   - семантическая версия (0.5.0 — она в актуальном состоянии? сверь с CHANGELOG.md)
   - keywords релевантны
   - mcpServers оба корректны (mcp + db), env-переменные документированы в .env.example
2. .claude-plugin/marketplace.json:
   - валидна, содержит правильную ссылку на этот плагин
3. .claude-plugin/CLAUDE.md — нужен ли он там, или должен быть в корне
4. plugin.json НЕ должен содержать ничего что должно быть в hooks/, agents/, skills/, commands/ — только manifest
5. Все 5 skills, 6 commands (build-set, curate-library, deliver-set, expand-playlist, panel, ym-sync), agents/dj-assistant.md, hooks/hooks.json — все ли подхватываются плагином автоматически (FileSystemProvider + plugin discovery)?
6. Конфликт имён: skill build-set и command build-set имеют одинаковое имя — проверь что это работает корректно (skill auto-namespaced как dj-music:build-set).
7. ${CLAUDE_PLUGIN_ROOT} используется правильно во всех путях.

Изучи https://docs.claude.com/en/docs/claude-code/plugins для точных требований.

Запусти plugin-validator agent если можешь, иначе валидируй вручную через чтение файлов.

Отчёт: список нарушений с severity (error/warning/info) и предложенными фиксами. Если нашёл критические ошибки — исправь и открой PR fix/plugin-manifest в dev. ≤300 слов.
```

---

## 4. MCP SERVERS — security и UX

**subagent_type**: `general-purpose`

```text
Аудит двух MCP серверов плагина dj-music-plugin (cwd: /Users/laptop/dev/dj-music-plugin).

Контекст:
- В .claude-plugin/plugin.json два mcpServers:
  1. "mcp" — локальный fastmcp с 50 DJ tools, запускается через `bash -c "cd ... && source .env && uv run fastmcp run fastmcp.json --reload --reload-dir app --no-banner"`
  2. "db" — Supabase MCP read-only, scoped к project-ref bowosphlnghhgaulcyfm, использует DJ_DB_ACCESS_TOKEN из .env
- См. memory: 1100-1103 — было решено: DJ_DB_ACCESS_TOKEN из env, project-ref hardcoded, --read-only обязателен.

Задачи:
1. Прочитай plugin.json mcpServers секцию и .env.example.
2. Изучи https://docs.claude.com/en/docs/claude-code/mcp и https://github.com/supabase-community/supabase-mcp.
3. Проверь:
   - Обе записи используют bash wrapper с source .env — это работает кроссплатформенно? (macOS/Linux да, Windows нет — задокументировать ограничение)
   - --reload в production включён — должен быть только в dev. Раздели dev/prod конфиги или убери.
   - "db" сервер: --read-only стоит, project-ref правильный, нет ли утечки токена в args (он в env, OK)
   - .env.example содержит DJ_DB_ACCESS_TOKEN с пояснением где взять
   - Документация в README.md и CLAUDE.md соответствует актуальному состоянию (имена серверов "mcp" и "db", не "supabase")
4. Проверь что fastmcp.json существует и корректно описывает 50 tools.
5. Если найдёшь проблемы — исправь, ветка fix/mcp-audit от dev, PR.

НЕ трогай токены, НЕ коммить .env. Отчёт ≤300 слов.
```

---

## 5. AGENT (dj-assistant) — улучшение

**subagent_type**: `general-purpose`

```bash
Ты дорабатываешь единственный subagent плагина dj-music-plugin: agents/dj-assistant.md (cwd: /Users/laptop/dev/dj-music-plugin).

Контекст:
- Это специализированный агент для DJ-задач (track selection, set optimization, audio analysis, library management).
- Frontmatter должен содержать: name, description (с конкретными triggers и examples), tools (whitelist), model (опционально).
- Agents изолированы — не видят родительский контекст. Поэтому description и tools должны быть достаточны для standalone работы.

Задачи:
1. Прочитай agents/dj-assistant.md, agents/CLAUDE.md (если есть), docs/tool-catalog.md.
2. Изучи https://docs.claude.com/en/docs/claude-code/sub-agents.
3. Оцени текущий dj-assistant:
   - description: содержит ли 2-3 example блока (как в built-in agents)?
   - tools: ограничены ли только нужными (Read, Write, Bash, Glob, Grep, mcp__plugin_dj-music_mcp__*)? Не давай ему доступ к Web/Linear/Sentry — это узкоспециализированный агент.
   - Содержит ли инструкции как использовать MCP tools (через mcp__plugin_dj-music_mcp__run_tool)?
   - Знает ли про hidden tools (audio, atomic) и unlock_tools?
   - Знает ли про subgenres, Camelot wheel, transition scoring (ссылка на @docs/domain-glossary.md и @docs/transition-scoring.md)?
4. Перепиши агента с учётом найденных пробелов. Должен быть один файл, ≤200 строк.
5. Ветка: fix/dj-assistant-agent от dev, PR.

Отчёт: что было плохо, что стало. ≤250 слов.
```

---

## 6. SLASH COMMANDS — sync с skills

**subagent_type**: `general-purpose`

```text
Ты ревизируешь 6 slash commands плагина dj-music-plugin (cwd: /Users/laptop/dev/dj-music-plugin):
commands/build-set.md, commands/curate-library.md, commands/deliver-set.md, commands/expand-playlist.md, commands/panel.md, commands/ym-sync.md.

Контекст:
- 5 из 6 commands имеют одноимённый skill в skills/. Шестая (panel) не имеет skill.
- Command — это просто markdown с инструкциями, без frontmatter (или с минимальным).
- Skill — это инструкции + supporting files + frontmatter.
- Распространённая ошибка: command дублирует содержимое skill вместо того чтобы его вызывать.

Задачи:
1. Прочитай все 6 commands/*.md и сравни с соответствующими skills/*/SKILL.md.
2. Изучи https://docs.claude.com/en/docs/claude-code/slash-commands (frontmatter, $ARGUMENTS, file references).
3. Для каждой команды реши:
   - Делает ли она что-то отличное от skill, или просто дубль?
   - Если дубль — превратить в тонкий wrapper, который ссылается на skill ("Run the dj-music:<name> skill with these args: $ARGUMENTS")
   - Если уникальная (panel) — оставить, но проверить корректность
4. Добавь frontmatter где нужно (description, argument-hint).
5. Удали дублирующее содержимое.
6. Проверь $ARGUMENTS и file references работают.
7. Ветка: fix/commands-sync от dev. PR в dev.

Отчёт: таблица command → skill → action (kept/wrapped/uniq) + diff stats. ≤250 слов.
```

---

## 7. SETTINGS + CLAUDE.md — иерархия и контекст

**subagent_type**: `claude-md-management:claude-md-improver`

```text
Аудит и улучшение CLAUDE.md иерархии в dj-music-plugin (cwd: /Users/laptop/dev/dj-music-plugin).

Контекст:
- Корневой CLAUDE.md (~250 строк, ссылается на @docs/architecture.md, @docs/tool-catalog.md, @docs/audio-pipeline.md, и т.д.) — это главный entry point.
- Дополнительные CLAUDE.md есть в: agents/CLAUDE.md, commands/CLAUDE.md, hooks/CLAUDE.md, .claude-plugin/CLAUDE.md.
- .claude/rules/*.md — модульные правила (audio.md, models.md, services.md, tools.md, ym.md, panel.md, gotchas.md, и т.д.).
- .claude/settings.json — extraKnownMarketplaces, hooks, enabledPlugins.
- .claude/settings.local.json — gitignored, локальные оверрайды.

Задачи:
1. Запусти claude-md-improver агент на этом проекте.
2. Дополнительно проверь:
   - Дублирует ли какой-нибудь подкаталоговый CLAUDE.md содержимое корневого
   - Корректны ли все @import-ы (ссылки на существующие файлы)
   - Соответствует ли список tools в docs/tool-catalog.md актуальному коду (Glob app/controllers/tools/**/*.py и сравни)
   - Есть ли упоминания удалённых фич (например supabase MCP server vs db MCP server — переименование)
   - .claude/rules/ файлы все ли актуальны, нет ли мёртвых
3. Settings.json: проверь что enabledPlugins не содержит несуществующих, hooks не дублируют plugin hooks.
4. Исправь найденные проблемы. Ветка: fix/claude-md-audit от dev. PR.

Отчёт от claude-md-improver + твои дополнения. ≤400 слов.
```

---

## 8. END-TO-END TEST — все компоненты вместе

**subagent_type**: `general-purpose`

```text
Smoke-тест плагина dj-music-plugin как целого (cwd: /Users/laptop/dev/dj-music-plugin).

Контекст:
- Плагин содержит: 2 MCP server (mcp + db), 5 skills, 6 commands, 1 subagent, 2 hook events, 50 MCP tools, panel (Next.js), backend (FastMCP).
- Цель: убедиться что всё работает вместе и нет разваленных ссылок.

Задачи (только READ-ONLY проверки, ничего не менять):
1. Запусти `make check` (lint + typecheck + test). Зафиксируй результат.
2. Прочитай plugin.json, marketplace.json, hooks.json, settings.json, все SKILL.md, все commands/*.md, agents/dj-assistant.md.
3. Построй карту зависимостей:
   - какие skills ссылаются на какие docs
   - какие commands вызывают какие skills
   - какие skills упоминают какие MCP tools
   - какие docs ссылаются на какие файлы
4. Проверь broken references:
   - все @import пути существуют
   - все MCP tool имена в skills/commands соответствуют реальным tools (grep по app/controllers/tools/**/*.py)
   - все упоминания scripts/* и .claude/hooks/* указывают на существующие файлы
   - все ссылки в README.md и CHANGELOG.md живые
5. Проверь .env.example содержит ВСЕ переменные, которые упоминаются в коде/конфигах (DJ_*, SUPABASE_*, NEXT_PUBLIC_*).
6. Запусти `uv run pytest tests/test_mcp -q` если есть — фиксируй сколько tools покрыто.

НЕ создавай PR. Не меняй файлы. Только отчёт.

Формат отчёта:
- ✅ что работает
- ⚠️ что подозрительно (с file:line)
- ❌ что сломано (с file:line и предложенным фиксом)
- 📊 stats: tools coverage, broken refs count, lint errors
≤600 слов.
```

---

## 9. ERROR MESSAGES — грамотные ошибки вместо `Error calling tool 'X'`

**subagent_type**: `general-purpose`

```text
Ты исправляешь систему ошибок MCP tools плагина dj-music-plugin (cwd: /Users/laptop/dev/dj-music-plugin).

Проблема:
- Сейчас клиент часто видит бесполезные сообщения вида `Error calling tool 'get_track'` без причины, без поля, без подсказки.
- Это происходит когда FastMCP с `mask_error_details=True` оборачивает любое неизвестное исключение в generic ToolError.
- В app/controllers/tools/_shared/errors.py уже есть слой трансляции domain → MCP errors (NotFoundError → fastmcp.NotFoundError, ValidationError → ValueError, ConflictError → ToolError "Conflict:"), но применяется не везде через @map_domain_errors / domain_errors_as_tool_error.
- Также многие tools кидают сырые exceptions из app.core.errors без перевода, либо ловят и возвращают error-dict вместо raise.

Цель:
Сделать так, чтобы пользователь ВСЕГДА видел осмысленную ошибку:
- какой ресурс не найден (entity type + identifier)
- какое поле невалидно + почему + ожидаемое значение
- какой конфликт + как его разрешить
- для unexpected errors — короткое описание + request_id для логов (не stack trace в prod)

Задачи:
1. Прочитай:
   - app/core/errors.py (типы доменных ошибок)
   - app/controllers/tools/_shared/errors.py (текущий маппинг)
   - 5-7 представительных tools: app/controllers/tools/tracks.py, playlists.py, sets/crud.py, search.py, sets/sets.py, run_tool.py, yandex/playlists.py
   - app/server.py / fastmcp.json (mask_error_details setting)
2. Изучи как правильно писать ошибки:
   - Официальная FastMCP дока: https://gofastmcp.com/servers/tools — раздел Error Handling. Используй WebFetch.
   - JSON-RPC 2.0 error codes: -32600 invalid request, -32601 method not found, -32602 invalid params, -32603 internal error, -32001 (FastMCP) not found
   - Best practices: actionable messages, no stack traces в user-facing, structured error data, локализация не нужна (англ ОК)
3. Аудит:
   - найди ВСЕ места где tools кидают ошибки или ловят их
   - выпиши паттерны: raw raise, try/except → return dict, missing decorator, hardcoded "Error: ..." строки
   - построй таблицу: tool → как сейчас → как должно быть
4. Спроектируй унифицированную систему:
   - все tools оборачиваются @map_domain_errors (или явный domain_errors_as_tool_error context manager)
   - NotFoundError всегда содержит entity type + identifier ("Track 'local:42' not found", "Playlist matching query 'techno peak' not found")
   - ValidationError содержит field + value + constraint ("bpm_min=300 invalid: must be between 20 and 300")
   - ConflictError содержит сущность + причину + suggestion ("Set version 5 already exists; use force=True to overwrite or version_label='5b'")
   - Unexpected exceptions: log full trace + raise ToolError с короткой версией + request_id
5. Реализация:
   - Расширь app/controllers/tools/_shared/errors.py: добавь helper-функции `not_found(entity, ref)`, `invalid_param(field, value, expected)`, `conflict(entity, reason, suggestion=None)` чтобы единообразно формировать сообщения
   - Применить @map_domain_errors ко всем tools где его нет
   - Заменить hardcoded строки ошибок на helpers
   - Доменные сервисы (app/services/*) — убедись что они raise с осмысленным message, не сырое `raise NotFoundError()`
   - Repositories — flush errors превращать в ConflictError с понятным контекстом
6. Тесты:
   - Добавь tests/test_mcp_errors.py с проверками: что get_track с несуществующим id возвращает понятную ошибку, что filter_tracks с bpm_min=999 говорит про диапазон, что manage_set с дублирующимся именем говорит про конфликт.
   - Проверь что mask_error_details=True (production) НЕ скрывает наши осмысленные сообщения (они идут через ToolError, не через wrapping)
7. Документация:
   - Обнови .claude/rules/tools.md секцию error handling с паттернами
   - Добавь в docs/architecture.md короткую секцию "Error contract"

Granularity:
- Минимум 3 коммита: (1) errors.py helpers + tests, (2) применение к tools, (3) docs.
- Ветка: fix/error-messages от dev. PR в dev.

Запрещено:
- НЕ менять JSON-RPC коды наугад — сверяйся со спекой
- НЕ выкидывать stack traces клиенту в production
- НЕ ловить Exception голым except (catching domain errors → ok, catching all → no)
- НЕ ломать существующие тесты — если ломаются, исправь их корректно (новый текст ошибки), а не суппресни

Отчёт:
- Таблица "tool → было → стало" (топ-10 самых криничных)
- Список новых helpers
- Coverage: сколько tools теперь под @map_domain_errors из общего числа
- Примеры ДО/ПОСЛЕ для 3 типичных кейсов (not_found, validation, conflict)
≤500 слов.
```

---

## 10. PANEL REFACTOR — БД + FastAPI/FastMCP интеграция

**subagent_type**: `general-purpose`

```sql
Ты делаешь полный рефакторинг панели dj-music-plugin (cwd: /Users/laptop/dev/dj-music-plugin/panel) и настраиваешь её взаимодействие с БД и с MCP-сервером через REST API.

Контекст архитектуры:
- Panel: Next.js 16 + Bun + shadcn/ui (Base UI + Tailwind v4) + Recharts + TanStack Table + @tabler/icons-react. Cyberpunk dark theme.
- Два независимых канала данных:
  1. READ path: Page (server component) → lib/queries/*.ts → Supabase PostgreSQL (direct SQL, no ORM, anon key, RLS disabled)
  2. WRITE/MUTATION path: User action → Server action (actions/*.ts) → lib/mcp-client.ts → HTTP POST на REST API (app/api/server.py:8000) → mcp.call_tool() → FastMCP server → DB
- REST API: app/api/server.py — тонкая FastAPI обёртка, НЕ дублирует business logic, только проксирует mcp.call_tool(). Endpoints: /api/health, /api/tools, /api/tools/{name}, /api/tools/{name}/schema, /api/tools/{name}/call, /mcp (native StreamableHTTP).
- MCP: 50 tools (46 visible + 4 atomic hidden), namespace через FastMCP, FileSystemProvider auto-discovery.
- Env vars: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, MCP_HTTP_URL (default http://localhost:8000).
- Pages: /, /library, /library/[id], /playlists, /playlists/[id], /sets, /sets/[id], /discover.
- Server actions: analysis-actions.ts, discovery-actions.ts, set-actions.ts, sync-actions.ts.

Цели рефакторинга:
1. **Типобезопасность end-to-end**: Supabase queries → typed interfaces, MCP tool calls → typed по их JSON Schema (генерация типов из /api/tools/{name}/schema), Server Actions → typed input/output.
2. **Единая точка для MCP вызовов**: lib/mcp-client.ts должен быть тонким, типобезопасным, с error handling, retry, timeout. Никаких прямых fetch в actions.
3. **Единая точка для Supabase**: lib/supabase/server.ts (SSR client) + lib/queries/* — каждая query функция документирована, типизирована, имеет error handling (не throw в UI, возвращать Result type или fallback).
4. **Корректная инвалидация кэша**: после mutation через MCP — revalidatePath/revalidateTag для затронутых страниц.
5. **Loading + Error states**: каждая страница имеет loading.tsx и error.tsx, каждый async компонент в Suspense с skeleton.
6. **Optimistic UI** где имеет смысл (классификация треков, добавление в плейлист).
7. **Real-time обновления** (опционально): Supabase Realtime для обновления статуса анализа треков.

Задачи (по фазам):

### Фаза 0: Аудит (только чтение)
1. Прочитай: panel/package.json, panel/next.config.ts, panel/tsconfig.json, panel/tailwind.config.ts, panel/components.json, .env.example, app/api/server.py, app/server.py, app/controllers/tools/_shared/dispatch.py.
2. Изучи структуру: panel/app/, panel/lib/, panel/components/, panel/actions/.
3. Изучи https://nextjs.org/docs/app/building-your-application/data-fetching (Server Components, Server Actions, revalidation), https://supabase.com/docs/guides/auth/server-side/nextjs, https://gofastmcp.com/clients/python (MCP HTTP client).
4. Построй карту: страница → query → таблицы Supabase | страница → action → MCP tool.
5. Найди проблемы: дубли fetch-логики, untyped responses, missing error handling, missing loading states, hardcoded URLs, SSR/CSR mismatches, неправильные использования "use client" / "use server", прямые SQL в страницах, обходы lib/queries.

### Фаза 1: Инфраструктура (lib/)
1. **lib/mcp-client.ts** — переписать как типобезопасный клиент:
   - `mcpCall<TArgs, TResult>(toolName: string, args: TArgs): Promise<Result<TResult, MCPError>>`
   - timeout (30s default, override per call), retry (1 раз на 5xx, не на 4xx), structured error parsing (использовать error contract из агента #9)
   - Никаких throw — возвращать Result type
   - Парсинг structuredContent из MCP response, не raw text
2. **lib/mcp-types.ts** — генерация типов из /api/tools (опционально через openapi-typescript или вручную для топ-10 tools)
3. **lib/supabase/server.ts** — убедиться SSR-compatible, cookies handling корректно
4. **lib/supabase/types.ts** — типы для всех таблиц (можно сгенерить через `supabase gen types typescript --project-id bowosphlnghhgaulcyfm` если есть CLI, иначе вручную для топ-10 таблиц используемых в panel)
5. **lib/queries/** — каждая функция: типизирована, документирована, returns `Promise<Result<T, QueryError>>`, использует select только нужных полей (не SELECT *)
6. **lib/result.ts** — Result<T, E> type + helpers (ok, err, isOk, isErr, unwrap, mapResult)

### Фаза 2: Server Actions
1. Каждый action — typed input (Zod схема) + typed output (Result)
2. Использует только новый mcpClient, не raw fetch
3. После mutation — revalidatePath() для затронутых страниц
4. Обработка ошибок: возвращать структурированный ответ {success, data?, error?}, не throw
5. Audit-log: console.info/error на сервере, не в клиент

### Фаза 3: Страницы и компоненты
1. Каждая async страница оборачивает data fetching в try/catch и рендерит ErrorBoundary fallback
2. Добавить loading.tsx на каждый route segment
3. Добавить error.tsx на каждый route segment
4. Suspense + skeletons для streaming
5. Типизация props через interfaces, не any
6. Удалить дублирующуюся логику в компонентах (DRY)

### Фаза 4: UX улучшения
1. Optimistic updates через useOptimistic для классификации треков
2. Toast notifications для mutation results (использовать sonner — уже в shadcn ecosystem)
3. Form validation через react-hook-form + zod (consistent across panel)
4. Pagination state в URL (?page=2&sort=bpm) для shareable links

### Фаза 5: Тесты и качество
1. `cd panel && bun run lint` — должен проходить чисто
2. `bun run build` — должен билдиться без warnings
3. Если есть тесты — все зелёные. Если нет — добавить минимум smoke-test для критичных страниц через playwright или vitest.
4. Проверить что dev server запускается: `bun dev` + ручная проверка / и /library через curl или playwright.

Granularity:
- 5 PR-ов (по фазе) ИЛИ один большой PR с 5 коммитами. Предпочтительно второе для атомарности.
- Ветка: refactor/panel от dev.

Запрещено:
- НЕ дублировать business logic в panel (всё через MCP tools)
- НЕ писать SQL в страницах напрямую (только через lib/queries)
- НЕ хардкодить URLs (только через env vars)
- НЕ ломать существующие routes — все page paths остаются такими же
- НЕ менять схему Supabase — только читаешь
- НЕ устанавливать heavy deps без необходимости (проверь что уже есть в package.json)
- НЕ трогать backend (app/*, app/api/server.py) — только если найдёшь баг в REST API, открой отдельный issue

Зависимости от других агентов:
- Лучше запускать ПОСЛЕ агента #9 (errors) — тогда mcp-client сможет парсить осмысленные ошибки
- Не зависит от других

Отчёт:
- Карта "page → data sources" до и после
- Список новых файлов в lib/
- Coverage: сколько queries/actions типизированы из общего числа
- Lint/build/test results
- Скриншоты или curl-проверки 5 ключевых страниц (опционально)
- Список найденных но не исправленных issues (для будущих PR)
≤700 слов.
```

---

## Запуск всех агентов

Все 8 промптов независимы — можно запустить параллельно одним сообщением (8 `Agent` tool calls с `run_in_background: true`). Каждый агент откроет свой PR в `dev` (кроме #8, который только репортит).

Рекомендуемый порядок если последовательно:
1. **#8** (smoke test) — baseline что вообще работает
2. **#3** (manifest) — основа плагина
3. **#1** (hooks) и **#4** (mcp) — параллельно, инфраструктура
4. **#2** (skills) и **#6** (commands) — параллельно, user-facing
5. **#5** (agent) и **#7** (CLAUDE.md) — параллельно, контекст
6. **#8** (smoke test) повторно — убедиться что всё ещё зелёное
