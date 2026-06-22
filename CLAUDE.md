# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс Музыкой.

**Текущая версия:** v1.5.0 (детальная история — [CHANGELOG.md](CHANGELOG.md)).

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
- @docs/tool-catalog.md — 20 dispatchers + 27 resources + 26 prompts
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
├── prompts/        # 26 workflow recipes
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
- @.claude/rules/prompts.md — 26 workflow prompts + content-correctness контракт (filter/data/op-имена пинятся тестами)
- FastMCP docs: <https://gofastmcp.com/llms.txt>

## DB состояние (drift)

Alembic-миграция `p2_drop_dead_tables` **не применена** к Supabase. 17 dead-таблиц (`spotify_*`, `beatport_metadata`, `soundcloud_metadata`, `embeddings`, `transition_candidates`, `dj_saved_loops`, `dj_cue_points`, `dj_beatgrid_change_points`, `dj_set_constraints`, `dj_set_feedback`, `labels`, `track_labels`, `app_exports`) живут в схеме с 0 rows. Всего **47 live tables**, после drop будет 31.
