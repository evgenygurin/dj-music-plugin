# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс Музыкой. Включает Next.js панель для мониторинга.

**Текущая версия:** v1.2.17 (детальная история — [CHANGELOG.md](CHANGELOG.md)).

## Quick Start

```bash
export DJ_PLUGIN_DEV_PATH=/Users/laptop/dev/dj-music-plugin  # ← см. "Plugin cache" ниже
uv sync --all-extras                       # install deps (audio, stems, http, apps)
make check                                 # lint + typecheck + arch + test
uv run fastmcp run server.py --reload      # MCP dev server
uv run --extra http uvicorn app.rest.app:api --port 8000 --reload   # REST (для Panel)
cd panel && bun dev                        # Panel → http://localhost:3000
./start.sh                                 # backend + panel одной командой
```

## Документация

Загружай соответствующий doc при работе с областью:

- @docs/architecture.md — bounded-contexts, data flow, dependency rules
- @docs/tool-catalog.md — 20 dispatchers + 27 resources + 6 prompts
- @docs/domain-glossary.md — DJ терминология (BPM, Camelot, LUFS, subgenres)
- @docs/audio-pipeline.md — 18 анализаторов, tiered L1–L4, mood classifier
- @docs/audio-schema.md — `track_audio_features_computed` (47 features)
- @docs/transition-scoring.md — 6-компонентная формула, section-aware, recipe engine
- @docs/ym-api-guide.md — YM API quirks, rate limiting, diff format
- @docs/panel-guide.md — Panel архитектура, data flow, компоненты
- @docs/dev-mode.md — hot-reload: DJ_PLUGIN_DEV_PATH + hooks + /reload-plugins
- @docs/vm-deployment.md — batch анализ (`deploy_to_vm.sh` + `vm_analyze.py`)
- @docs/plugin-settings.md — per-project config (`.claude/dj-music.local.md`)
- @docs/structure.md — файловая карта репозитория

## Принципы v1

- **MCP — primary interface.** Tools / resources / prompts декларативны. Композиция через LLM (prompts, Tool Search), а не императивный service слой.
- **Polymorphism over proliferation.** 20 dispatchers = 6 entity CRUD + 3 provider + 2 compute + `playlist_sync` + 2 admin (`unlock_namespace`, `tool_invoke`) + 6 UI (Prefab Apps). Side-effects живут в **handlers**, привязанных к entity.
- **Anchor на DB entities.** Aggregate root → `models/<entity>.py` + `repositories/<entity>.py` + Pydantic family.
- **Unit of Work + BaseRepository[M].** Один UoW на tool call (`Depends(get_uow)`), Django-style lookups (`bpm__gte`, `mood__in`). DbSession middleware управляет commit/rollback.
- **Panel (Next.js)** читает напрямую из Supabase, мутации через **REST API** (`app/rest/`) — тонкая FastAPI-обёртка поверх MCP, без дублирования бизнес-логики.
- **FastMCP v3.x** с FileSystemProvider auto-discovery. Никакой ручной регистрации.
- **Никаких magic numbers** — `app/config/*.py` + `app/shared/constants.py`.
- **Время** — всегда через `app/shared/time.py` (`utc_now()`, `sa_now()`).
- Python 3.12+, async everywhere, mypy strict, pydantic v2.

## Архитектура

```text
app/
├── tools/          # 20 @tool — entity/provider/compute/sync/admin/ui
├── resources/      # 27 @resource — local://, schema://, session://, reference://
├── prompts/        # 6 workflow recipes
├── handlers/       # 6 side-effect handlers (track_import, audio_file_download, ...)
├── registry/       # EntityRegistry (11 entities) + ProviderRegistry
├── repositories/   # BaseRepository[M] + UnitOfWork
├── models/         # SQLAlchemy 2.0 — one file per aggregate root
├── schemas/        # Pydantic DTOs (View/Filter/Create/Update per entity)
├── domain/         # Pure compute: transition/ optimization/ camelot/ template/ audit/
├── audio/          # Tiered pipeline (analyzers, classification, level_config)
├── providers/      # yandex/ (adapter, client, rate_limiter)
├── server/         # FastMCP composition: app, lifespan, middleware/, transforms, visibility
├── rest/           # FastAPI proxy для Panel
├── shared/         # errors, constants, filters, ids, pagination, time (leaf)
└── config/         # 9 settings файлов split по доменам
```

**Dependency rule** (enforced by `import-linter` / `make arch`):

- `tools → handlers → repositories → models`
- `tools → domain` (pure compute OK)
- `domain` imports: только `models` + `shared`
- `audio` / `providers` — side-effect layers, импортируются только handlers
- `rest` оборачивает MCP через `mcp.call_tool()` — не дублирует логику
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

## FastMCP v3 правила

Перед любой работой с tools / resources / prompts / lifespan / visibility:
- @.claude/rules/tools.md — `@tool` шаблон, namespaces, annotations
- @.claude/rules/resources.md — URI schemes, return types
- FastMCP docs: <https://gofastmcp.com/llms.txt>

## DB состояние (drift)

Alembic-миграция `p2_drop_dead_tables` **не применена** к Supabase. 17 dead-таблиц (`spotify_*`, `beatport_metadata`, `soundcloud_metadata`, `embeddings`, `transition_candidates`, `dj_saved_loops`, `dj_cue_points`, `dj_beatgrid_change_points`, `dj_set_constraints`, `dj_set_feedback`, `labels`, `track_labels`, `app_exports`) живут в схеме с 0 rows. Всего **47 live tables**, после drop будет 31.

## Panel state (v1.0.7)

Panel actions переписаны под v1 dispatcher surface (commit `dbf5a10`): `entity_*`, `provider_*`, `transition_score_pool`, `sequence_optimize`, `playlist_sync`, `read_resource`. `bun run build` зелёный, все 15 routes собираются.

Остались 6 явных `TODO(v1.0-actions-rewrite)` маркеров для composer workflows:
1. `sync-actions.ts:distributeToSubgenres` — нужен composed `entity_list mood histogram + per-subgenre playlist_sync`
2. `sync-actions.ts:pushSetToYm` — нужен `provider_write(playlist, create) + add_tracks` chain
3. `set-actions.ts:scoreTransitions` — N×N matrix, consumers фильтруют до consecutive pairs
4. `set-actions.ts:deliverSet` — нужен server-side delivery handler
5. `set-actions.ts:exportSet` — JSON через `local://sets/{id}/full`; M3U8/Rekordbox writers — нужен tool
6. `transition-actions.ts:getTransitionStyle` — `recommended_style/bars` не expose'ит v1 transition resource

DEAD: `mixer-actions.ts` (set_eq/kill_eq/reset_eq/set_filter/mixer_state/mixer_crossfader) — DJ engine simulator удалён в Phase 7 cutover (Blueprint §13 D15). Экспорты бросают explicit error; UI-кнопки нужно отдельно disable.

Подробности: @docs/panel-guide.md.
