# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс Музыкой.

**Текущая версия:** v1.6.1 (детальная история — [CHANGELOG.md](CHANGELOG.md)).

## ⛔ НЕ создавать CI (GitHub Actions)

**Никогда не добавляй CI-workflow'ы** (`.github/workflows/*.yml`, GitHub
Actions и любые внешние CI). GitHub Actions для этого репозитория
недоступны на уровне аккаунта (billing lock) — каждый run падает за 2–8
секунд без назначения раннера, создавая ложный «красный» статус на каждом
PR. `.github/workflows/ci.yml` удалён намеренно.

Качество гарантируется **локально**, без зависимости от внешнего CI:

- `make check` (lint + typecheck + arch + test) — основной гейт;
- pre-push хук (`hooks/pre-push`) гоняет тот же `make check` перед каждым
  push (bypass: `DJ_SKIP_CHECK=1 git push ...`).

Если просят «починить CI» — не воссоздавай workflow; зелёного статуса
можно добиться только восстановлением Actions на уровне аккаунта, что вне
кодовой базы.

## Quick Start

```bash
export DJ_PLUGIN_DEV_PATH=/Users/laptop/dev/dj-music-plugin  # ← см. "Plugin cache" ниже
uv sync --all-extras                       # install deps (audio, stems, apps)
make check                                 # lint + typecheck + arch + test
uv run fastmcp run server.py --reload      # MCP dev server
```

## Документация

Загружай соответствующий doc при работе с областью:

- @docs/architecture.md — bounded-contexts, data flow, dependency rules
- @docs/tool-catalog.md — 20 dispatchers + 27 resources + 30 prompts
- @docs/domain-glossary.md — DJ терминология (BPM, Camelot, LUFS, subgenres)
- @docs/audio-pipeline.md — 18 анализаторов, tiered L1–L4, mood classifier
- @docs/audio-schema.md — `track_audio_features_computed` (47 features)
- @docs/transition-scoring.md — 6-компонентная формула, section-aware, recipe engine
- @docs/ym-api-guide.md — YM API quirks, rate limiting, diff format
- @docs/dev-mode.md — hot-reload: DJ_PLUGIN_DEV_PATH + hooks + /reload-plugins
- @docs/plugin-settings.md — per-project config (`.claude/dj-music.local.md`)
- @docs/structure.md — файловая карта репозитория

## Принципы v1

- **MCP — primary interface.** Tools / resources / prompts декларативны. Композиция через LLM (prompts, Tool Search), а не императивный service слой.
- **Polymorphism over proliferation.** 20 dispatchers = 6 entity CRUD + 3 provider + 2 compute + `playlist_sync` + 2 admin (`unlock_namespace`, `tool_invoke`) + 6 UI (Prefab Apps). Side-effects живут в **handlers**, привязанных к entity.
- **Anchor на DB entities.** Aggregate root → `models/<entity>.py` + `repositories/<entity>.py` + Pydantic family.
- **Unit of Work + BaseRepository[M].** Один UoW на tool call (`Depends(get_uow)`), Django-style lookups (`bpm__gte`, `mood__in`). DbSession middleware управляет commit/rollback.
- **FastMCP v3.x** с FileSystemProvider auto-discovery. Никакой ручной регистрации.
- **Никаких magic numbers** — `app/config/*.py` + `app/shared/constants.py`.
- **Время** — всегда через `app/shared/time.py` (`utc_now()`, `sa_now()`).
- Python 3.12+, async everywhere, mypy strict, pydantic v2.

## Архитектура

```text
app/
├── tools/          # 20 @tool — entity/provider/compute/sync/admin/ui
├── resources/      # 27 @resource — local://, schema://, session://, reference://
├── prompts/        # 30 workflow recipes
├── handlers/       # 6 side-effect handlers (track_import, audio_file_download, ...)
├── registry/       # EntityRegistry (11 entities) + ProviderRegistry
├── repositories/   # BaseRepository[M] + UnitOfWork
├── models/         # SQLAlchemy 2.0 — one file per aggregate root
├── schemas/        # Pydantic DTOs (View/Filter/Create/Update per entity)
├── domain/         # Pure compute: transition/ optimization/ camelot/ template/ audit/
├── audio/          # Tiered pipeline (analyzers, classification, level_config)
├── providers/      # yandex/ (adapter, client, rate_limiter)
├── server/         # FastMCP composition: app, lifespan, middleware/, transforms, visibility
├── shared/         # errors, constants, filters, ids, pagination, time (leaf)
└── config/         # 9 settings файлов split по доменам
```

**Dependency rule** (enforced by `import-linter` / `make arch`):

- `tools → handlers → repositories → models`
- `tools → domain` (pure compute OK)
- `domain` imports: только `models` + `shared`
- `audio` / `providers` — side-effect layers, импортируются только handlers
- `shared` — leaf, нет обратных импортов

Детали + диаграмма потока: @docs/architecture.md.

## ⚠️ Plugin cache ≠ working dir

Claude Code грузит плагин в `~/.claude/plugins/cache/dj-music-plugin/` — **отдельная копия** кода и `.env`. Правки в working dir видны только если выставлена `DJ_PLUGIN_DEV_PATH`:

```json
// ~/.claude/settings.json — один раз на машину
{ "env": { "DJ_PLUGIN_DEV_PATH": "/Users/laptop/dev/dj-music-plugin" } }
```

Симптомы когда забыли: правки в `app/` не применяются; `no such table: dj_*` (cache без `.env` → default SQLite вместо Supabase). **Никогда** не копируй/симлинкай файлы в cache руками.

Dev-режим целиком (4 слоя hot-reload + `/reload-plugins`) — @docs/dev-mode.md.

После plugin update (bump version, symlink в cache, sync `installed_plugins.json`) — `Skill(dj-music:reload-plugin)`: чистит bytecode/pyc/mypy/ruff/pytest caches и убивает MCP stdio → Claude Code respawn'ит сервер с свежим кодом. Альтернатива `/reload-plugins` для полного rescan plugin-wide.

## FastMCP v3 правила

Перед любой работой с tools / resources / prompts / lifespan / visibility:
- @.claude/rules/tools.md — `@tool` шаблон, namespaces, annotations
- @.claude/rules/resources.md — URI schemes, return types
- @.claude/rules/prompts.md — 30 workflow prompts + content-correctness контракт (filter/data/op-имена пинятся тестами)
- FastMCP docs: <https://gofastmcp.com/llms.txt>

## Когда использовать MCP prompts

Prompts — основной способ запускать DJ workflow. Если пользователь просит
не просто прочитать одну сущность, а выполнить музыкальную задачу из
нескольких шагов (анализ → отбор → оптимизация → ревью → экспорт), сначала
подбери prompt из `app/prompts/` / `docs/tool-catalog.md`, а не собирай
цепочку `entity_*` / `provider_*` / `compute_*` вручную.

Перед использованием или редактированием prompt обязательно загрузи
@.claude/rules/prompts.md. В prompt body нельзя придумывать entity names,
filter keys, field presets, provider operations, template names или cross-prompt
references: все имена должны соответствовать runtime surface и тестам
`tests/prompts/test_prompt_content_correctness.py`.

Практическая маршрутизация:

| Пользовательское намерение | Prompt |
|---|---|
| Нужен общий DJ-контекст перед сложной сессией | `dj_expert_session` |
| Построить сет из плейлиста | `build_set_workflow` |
| Расширить плейлист через discovery/import/analyze | `expand_playlist_workflow` |
| Сделать полный проход expand → build → deliver | `full_pipeline` |
| Экспортировать сет, подготовить deliverables или синкнуть в YM | `deliver_set_workflow` |
| Быстро проверить переход A → B | `quick_mix_check` |
| Проверить здоровье библиотеки или плейлиста | `library_health_workflow` |
| Дозаполнить/поднять уровень audio analysis | `analyze_library_workflow` |
| Подготовить один трек к миксу | `track_prep_workflow` |
| Спроектировать сет по тональности Camelot | `harmonic_journey_workflow` |
| Спроектировать energy/subgenre arc | `subgenre_journey_workflow` |
| Спроектировать BPM ramp | `tempo_journey_workflow` |
| Собрать warmup/peak/closing/roller/wave/progressive сценарий | `scenario_set_workflow` |
| Собрать сет в стиле DJ/persona | `dj_persona_workflow` |
| Собрать mono-style / subgenre-locked сет | `style_lock_set_workflow` |
| Найти плотный кластер совместимых треков | `mix_cluster_workflow` |
| Подготовить слот лайнапа с handoff BPM | `lineup_handoff_workflow` |
| Спланировать B2B из двух crates | `b2b_planning_workflow` |
| Удлинить существующий сет | `extend_set_workflow` |
| Отревьюить существующий сет | `set_review_workflow` |
| Спасти сет с множеством hard/weak transitions | `rescue_set_workflow` |
| Починить один слабый переход | `fix_transition_workflow` |
| Заменить слабый слот в сете | `replace_track_workflow` |
| Сделать performance cue sheet | `set_cheatsheet_workflow` |
| Подогнать сет под точный таймслот | `set_duration_fit_workflow` |
| Выбрать следующий трек в live-ситуации | `live_next_track_workflow` |
| Digging по seed/артисту/треку и импорт находок | `crate_digging_workflow` |
| Зафиксировать вкус: likes/bans/ratings/affinity | `taste_profile_workflow` |
| Pull/push/diff локального плейлиста с Yandex Music | `playlist_sync_workflow` |
| Найти hygiene-проблемы и план чистки библиотеки | `library_cleanup_workflow` |

Ручные tools/resources используй напрямую, когда запрос точечный:
прочитать конкретный объект, показать UI view, выполнить один CRUD/action,
проверить одну пару или сделать ad-hoc диагностику. Для пользовательских
workflow с музыкальным результатом предпочитай prompt, затем выполняй его
инструкции через реальные MCP tools/resources.

## Взаимодействие с БД — через Supabase MCP

**Любое прямое чтение/запись live-БД делай через Supabase MCP**
(`mcp__Supabase__execute_sql`, `mcp__Supabase__list_tables`,
`mcp__Supabase__apply_migration`, ... — project_id
`bowosphlnghhgaulcyfm`). Он ходит в Supabase Management API по HTTPS
(:443) и работает во всех окружениях, включая облачную песочницу
claude.ai/code, где сырой Postgres (asyncpg :6543/:5432) заблокирован
egress-прокси.

- **Не** полагайся на asyncpg `entity_*` для ad-hoc запросов к проду из
  песочницы — порты 5432/6543 закрыты (timeout). Это свойство
  egress-прокси, не чинится конфигом (детали — @docs/dev-mode.md
  «Доступ к БД по окружениям»).
- `entity_*` (ORM-слой через asyncpg) работают напрямую только
  **локально** и под `claude --teleport`.
- Канон по окружениям: **облако → Supabase MCP** (live read/write по
  HTTPS) или teleport; **локаль/teleport → asyncpg `entity_*`** напрямую.

## DB состояние (drift)

Alembic-миграция `p2_drop_dead_tables` **не применена** к Supabase. 17 dead-таблиц (`spotify_*`, `beatport_metadata`, `soundcloud_metadata`, `embeddings`, `transition_candidates`, `dj_saved_loops`, `dj_cue_points`, `dj_beatgrid_change_points`, `dj_set_constraints`, `dj_set_feedback`, `labels`, `track_labels`, `app_exports`) живут в схеме с 0 rows. Всего **47 live tables**, после drop будет 31.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **dj-music-plugin** (9521 symbols, 15882 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/dj-music-plugin/context` | Codebase overview, check index freshness |
| `gitnexus://repo/dj-music-plugin/clusters` | All functional areas |
| `gitnexus://repo/dj-music-plugin/processes` | All execution flows |
| `gitnexus://repo/dj-music-plugin/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
