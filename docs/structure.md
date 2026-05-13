# Project Structure & Database Schema

> Структура директорий, файлов и таблиц БД проекта DJ Music Plugin (v1.3.7).
> Обновлено: 2026-05-13.

## 1. Directory Tree

```text
dj-music-plugin/
├── CLAUDE.md                       # Главные инструкции для Claude
├── README.md
├── CHANGELOG.md
├── Makefile                        # make check / lint / test
├── Dockerfile
├── alembic.ini                     # Alembic config
├── pyproject.toml
├── start.sh                        # Dev environment setup (uv sync)
│
├── .claude/
│   ├── settings.json
│   ├── rules/                      # Правила по слоям (tools, resources, …)
│   └── worktrees/                  # git worktrees
│
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
│
├── agents/
│   └── dj-assistant.md
│
├── docs/                           # Архитектурная документация
│   ├── architecture.md             # Bounded contexts, data flow
│   ├── domain-glossary.md
│   ├── tool-catalog.md             # 20 tools + 27 resources + 6 prompts
│   ├── audio-pipeline.md
│   ├── ym-api-guide.md
│   ├── transition-scoring.md
│   ├── structure.md                # ← этот файл
│   ├── reports/
│   └── superpowers/specs/
│
├── app/                            # Backend (Python, FastMCP v3)
│   ├── __init__.py
│   │
│   ├── tools/                      # @tool — 20 dispatchers
│   │   ├── entity/                 # list, get, aggregate, create, update, delete
│   │   │   └── _fk_gate.py         # v1.3.7: validate_fk_constraints, auto-derived from table.foreign_keys
│   │   ├── provider/               # read, write, search
│   │   ├── compute/                # score_pool, sequence_optimize
│   │   ├── sync/                   # playlist_sync
│   │   ├── admin/                  # unlock_namespace, tool_invoke
│   │   └── ui/                     # 6 Prefab Apps (ui_set_view, ui_transition_score, ...)
│   │
│   ├── resources/                  # @resource — 27 URIs (16 local://, 4 schema://, 3 session://, 4 reference://)
│   │   ├── track.py, playlist.py, set.py, transition.py,
│   │   │  transition_history.py, session.py, schema.py
│   │   └── reference/              # camelot, subgenres, templates, audit_rules
│   │
│   ├── handlers/                   # 6 entity-scoped side-effect handlers
│   │   ├── _context_log.py         # v1.3.7: safe_info / safe_report_progress wrappers (ctx may be None in headless/tests)
│   │   └── track_import.py, track_features_{analyze,reanalyze}.py, audio_file_download.py, set_version_build.py, transition_persist.py
│   │
│   ├── prompts/                    # @prompt — 6 workflow recipes
│   │   ├── dj_expert_session.py
│   │   ├── build_set_workflow.py
│   │   ├── deliver_set_workflow.py
│   │   ├── expand_playlist_workflow.py
│   │   ├── full_pipeline.py
│   │   └── quick_mix_check.py
│   │
│   ├── handlers/                   # entity-specific side-effects
│   │   ├── track_import.py
│   │   ├── track_features_analyze.py
│   │   ├── track_features_reanalyze.py
│   │   ├── audio_file_download.py
│   │   ├── set_version_build.py
│   │   └── transition_persist.py
│   │
│   ├── registry/                   # EntityRegistry + ProviderRegistry
│   │   ├── entity.py
│   │   ├── provider.py
│   │   └── defaults.py
│   │
│   ├── repositories/               # BaseRepository[M] + UnitOfWork
│   │   ├── base.py                 # BaseRepository[M] with Django lookups
│   │   ├── unit_of_work.py
│   │   ├── track.py, track_features.py, audio_file.py,
│   │   │  playlist.py, set.py, transition.py,
│   │   │  transition_history.py, track_affinity.py,
│   │   │  track_feedback.py, scoring_profile.py,
│   │   │  key.py, provider_metadata.py
│   │   └── …
│   │
│   ├── models/                     # SQLAlchemy 2.0 ORM
│   │   ├── base.py
│   │   └── <one file per aggregate root>
│   │
│   ├── schemas/                    # Pydantic DTOs
│   │   ├── common.py
│   │   ├── tool_responses.py
│   │   └── <one family per entity>
│   │
│   ├── domain/                     # Pure compute (no IO)
│   │   ├── transition/             # 6-component scoring, hard_constraints, recipe engine
│   │   ├── optimization/           # GA, greedy, fitness, protocol
│   │   ├── camelot/                # Camelot wheel
│   │   ├── template/               # Set templates registry
│   │   └── audit/                  # Techno audit rules
│   │
│   ├── audio/                      # Tiered L1-L4 pipeline
│   │   ├── pipeline.py
│   │   ├── level_config.py
│   │   ├── temp_download.py
│   │   ├── timeseries.py
│   │   ├── core/                   # AudioSignal, AnalysisContext, clip helpers
│   │   ├── analyzers/              # 18 analyzers
│   │   └── classification/         # mood classifier (15 subgenres)
│   │
│   ├── providers/                  # External platforms
│   │   └── yandex/                 # YandexMusicClient
│   │
│   ├── server/                     # FastMCP composition
│   │   ├── app.py                  # FastMCP server entry
│   │   ├── lifespan.py
│   │   ├── di.py                   # get_uow, get_entity_registry, …
│   │   ├── middleware/             # log, timing, rate limit, session, errors
│   │   ├── transforms.py           # resources↔tools, prompts↔tools
│   │   ├── visibility.py           # namespace activation
│   │   ├── observability.py        # Sentry / OTEL
│   │   ├── sampling.py             # LLM sampling fallback
│   │   ├── session_store.py
│   │   └── prefetch.py
│   │
│   ├── shared/                     # Leaf module
│   │   ├── errors.py               # NotFoundError, ValidationError, …
│   │   ├── constants.py
│   │   ├── filters.py              # Django-style lookup DSL
│   │   ├── ids.py
│   │   ├── pagination.py
│   │   └── time.py                 # utc_now, utc_timestamp_iso, sa_now
│   │
│   ├── config/                     # Settings split by concern
│   │   ├── database.py, audio.py, yandex.py, mcp.py,
│   │   │  audit.py, delivery.py, discovery.py,
│   │   │  optimization.py, transition.py
│   │
│   └── db/                         # DB bootstrap, migrations
│       ├── session.py              # async_session_factory
│       ├── migrations/             # Alembic
│       └── seed.py                 # 24 keys + providers
│
├── tests/                          # pytest + in-memory SQLite
├── scripts/                        # Dev / ops scripts (smoke_test_all_tools, verify_audio_pipeline, prefab_previews, …)
└── hooks/                          # git pre-push
```

## 2. DB Schema — 47 live tables (30 live + 17 drop-pending)

Blueprint §13.2 пометил 17 legacy-таблиц на удаление, но миграция
`p2_drop_dead_tables` пока **не применена** к Supabase — пустые схемы
существуют (`app_exports` с 2 устаревшими rows, остальные 0). v1-код
их не трогает.

Drop-pending: spotify_\* (×5), beatport_metadata, soundcloud_metadata,
embeddings, transition_candidates, dj_saved_loops, dj_cue_points,
dj_beatgrid_change_points, dj_set_constraints, dj_set_feedback,
labels, track_labels, app_exports.

Подробный список актуальных таблиц — в `app/models/` (one file per aggregate root) и Alembic history (`uv run alembic history`). Текущие row counts — `mcp__plugin_dj-music_db__list_tables` или `entity_aggregate(entity="...", operation="count")`.

Core aggregate roots:
- `tracks`, `track_audio_features_computed`, `track_sections`,
  `track_external_ids`, `feature_extraction_runs`
- `dj_library_items` (audio_file), `dj_playlists`, `dj_playlist_items`
- `dj_sets`, `dj_set_versions`, `dj_set_items`, `transitions`
- `transition_history`, `track_affinity`, `track_feedback`,
  `scoring_profiles`
- `keys` (24 static), `providers` (static), `yandex_metadata`,
  `raw_provider_responses`
