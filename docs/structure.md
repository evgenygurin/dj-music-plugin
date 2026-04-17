# Project Structure & Database Schema

> Структура директорий, файлов и таблиц БД проекта DJ Music Plugin (v1.0.0).
> Обновлено: 2026-04-17 (Phase 7 refactor).

## 1. Directory Tree

```text
dj-music-plugin/
├── CLAUDE.md                       # Главные инструкции для Claude
├── REQUIREMENTS.md                 # Спецификация требований
├── README.md
├── CHANGELOG.md
├── Makefile                        # make check / lint / test
├── Dockerfile
├── alembic.ini                     # Alembic config
├── pyproject.toml
├── start.sh                        # Backend + Panel dev runner
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
│   ├── tool-catalog.md             # 13 tools + 20 resources + 6 prompts
│   ├── audio-pipeline.md
│   ├── ym-api-guide.md
│   ├── transition-scoring.md
│   ├── panel-guide.md
│   ├── structure.md                # ← этот файл
│   ├── vm-deployment.md
│   ├── reports/
│   └── superpowers/specs/
│
├── app/                            # Backend (Python, FastMCP v3)
│   ├── __init__.py
│   │
│   ├── tools/                      # @tool — 13 generic dispatchers
│   │   ├── entity/                 # list, get, aggregate, create, update, delete
│   │   ├── provider/               # read, write, search
│   │   ├── compute/                # score_pool, sequence_optimize
│   │   ├── sync/                   # playlist_sync
│   │   └── admin/                  # unlock_namespace
│   │
│   ├── resources/                  # @resource — 20 URIs
│   │   ├── track.py, playlist.py, set.py, transition.py,
│   │   │  transition_history.py, session.py, schema.py
│   │   └── reference/              # camelot, subgenres, templates, audit_rules
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
│   ├── rest/                       # FastAPI wrapper over MCP (Panel)
│   │   ├── app.py                  # REST entry
│   │   ├── lifespan.py
│   │   ├── state.py
│   │   ├── schemas.py
│   │   └── routes/
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
├── scripts/                        # Dev / ops scripts (vm_import_and_analyze, …)
├── panel/                          # Next.js dashboard (Bun, shadcn, Supabase)
└── hooks/                          # git pre-push
```

## 2. DB Schema — ~31 tables

Dead tables удалены в Phase 4: spotify_\* (×5), beatport_metadata,
soundcloud_metadata, embeddings, transition_candidates, dj_saved_loops,
dj_cue_points, dj_beatgrid_change_points, dj_set_constraints,
dj_set_feedback, labels, track_labels, app_exports. Подробный список
актуальных таблиц — в `app/models/` (one file per aggregate root) и
Alembic history (`uv run alembic history`).

Core aggregate roots:
- `tracks`, `track_audio_features_computed`, `track_sections`,
  `track_external_ids`, `feature_extraction_runs`
- `dj_library_items` (audio_file), `dj_playlists`, `dj_playlist_items`
- `dj_sets`, `dj_set_versions`, `dj_set_items`, `transitions`
- `transition_history`, `track_affinity`, `track_feedback`,
  `scoring_profiles`
- `keys` (24 static), `providers` (static), `yandex_metadata`,
  `raw_provider_responses`
