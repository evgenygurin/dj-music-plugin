# Project Structure & Database Schema

> Структура директорий, файлов и таблиц БД проекта DJ Music Plugin.
> Обновлено: 2026-04-16.

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
│   └── rules/                      # Правила по слоям (audio, models, tools, ...)
│
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
│
├── agents/
│   └── dj-assistant.md
│
├── docs/                           # Архитектурная документация
│   ├── architecture.md
│   ├── domain-glossary.md
│   ├── tool-catalog.md
│   ├── audio-pipeline.md
│   ├── ym-api-guide.md
│   ├── transition-scoring.md
│   ├── panel-guide.md
│   ├── structure.md                # ← этот файл
│   ├── reports/
│   └── superpowers/specs/
│
├── app/                            # Backend (Python, FastMCP)
│   ├── server.py                   # MCP server entry → bootstrap/server_builder.py
│   ├── config.py                   # Settings (env DJ_*)
│   ├── telemetry.py                # Sentry / OTEL
│   ├── _version.py
│   │
│   ├── core/                       # Core — cross-cutting (no external deps)
│   │   ├── constants.py
│   │   ├── errors.py               # NotFoundError, ValidationError, ConflictError
│   │   └── utils/
│   │       ├── cache.py            # TransitionCache (in-memory LRU)
│   │       ├── files.py
│   │       ├── pagination.py
│   │       ├── parsing.py
│   │       └── time.py             # utc_now(), sa_now()
│   │
│   ├── controllers/                # Interface — MCP entry (tools, prompts, resources)
│   │   ├── elicitation.py
│   │   ├── middleware.py           # logging, timing, rate limit
│   │   ├── tools/                  # MCP tools (auto-discovered by FSProvider)
│   │   │   ├── _shared/
│   │   │   │   ├── taxonomy.py     # ToolCategory, annotations, timeouts, meta
│   │   │   │   ├── resolvers.py
│   │   │   │   ├── entity_resolver.py
│   │   │   │   ├── context.py      # ToolContext wrapper
│   │   │   │   ├── dispatch.py     # ActionDispatcher
│   │   │   │   └── errors.py
│   │   │   ├── tracks.py
│   │   │   ├── playlists.py
│   │   │   ├── crud.py             # Sets CRUD
│   │   │   ├── search.py
│   │   │   ├── sets.py             # build_set, rebuild_set, score_transitions
│   │   │   ├── sets_meta.py
│   │   │   ├── reasoning.py        # suggest_next, explain, replace, compare
│   │   │   ├── delivery.py
│   │   │   ├── discovery.py
│   │   │   ├── importing.py
│   │   │   ├── curation.py         # mood, audit, distribute
│   │   │   ├── sync.py
│   │   │   ├── audio.py            # analyze_track / batch / stems (stub)
│   │   │   ├── audio_atomic.py     # hidden atomic tools
│   │   │   ├── admin.py            # unlock_tools, list_platforms
│   │   │   ├── adaptive_arc.py
│   │   │   ├── scoring_profile.py
│   │   │   ├── set_narrative.py
│   │   │   ├── track_affinity.py
│   │   │   ├── track_feedback.py
│   │   │   ├── transition_history.py
│   │   │   └── yandex/             # YM API tools
│   │   │       ├── _constants.py
│   │   │       ├── search.py
│   │   │       ├── tracks.py
│   │   │       ├── albums.py
│   │   │       ├── playlists.py
│   │   │       └── likes.py
│   │   ├── prompts/workflows/      # 8 workflow prompts (→ PromptResult)
│   │   │   ├── build_set.py
│   │   │   ├── deliver_set.py
│   │   │   ├── dj_expert_session.py
│   │   │   ├── expand_playlist.py
│   │   │   ├── full_pipeline.py
│   │   │   ├── improve_set.py
│   │   │   ├── llm_discovery.py
│   │   │   ├── quick_mix_check.py  # ← NEW: pair compatibility check
│   │   │   └── taste_analysis.py   # ← NEW: taste profile from likes
│   │   ├── resources/              # MCP resources (read-only, → dict[str,Any])
│   │   │   ├── session_draft.py    # session://set-draft
│   │   │   ├── session_history.py  # ← NEW: session://tool-history
│   │   │   ├── snapshot.py         # library://snapshot
│   │   │   ├── status.py           # status://library, status://platforms
│   │   │   ├── templates.py        # track://{id}/features, set://{id}/summary, etc.
│   │   │   ├── transition_score.py # ← NEW: transition://{from_id}/{to_id}/score
│   │   │   └── reference/
│   │   │       ├── camelot.py
│   │   │       ├── subgenres.py
│   │   │       └── templates.py
│   │   └── dependencies/           # Depends() factories
│   │       ├── db.py
│   │       ├── repos.py
│   │       ├── services.py
│   │       ├── audio.py
│   │       ├── external.py
│   │       └── uow.py
│   │
│   ├── bootstrap/                  # MCP composition root
│   │   ├── server_builder.py       # build_mcp_server()
│   │   ├── lifespans.py            # db | ym | analyzer | cache | audio
│   │   ├── middleware.py
│   │   ├── observability.py
│   │   ├── sampling.py
│   │   ├── transforms.py
│   │   └── visibility.py
│   │
│   ├── api/                        # Interface — FastAPI REST wrapper
│   │   ├── server.py
│   │   ├── lifespan.py
│   │   ├── state.py
│   │   ├── openapi.py
│   │   ├── schemas.py
│   │   ├── routes/
│   │   │   ├── audio.py
│   │   │   ├── discovery.py
│   │   │   ├── execution.py
│   │   │   └── health.py
│   │   ├── audio_proxy.py          # AudioStreamProxy (provider-agnostic)
│   │   ├── signed_url_cache.py     # Signed URL TTL cache
│   │   └── tool_registry.py        # Static MCP tool metadata
│   │
│   ├── schemas/                    # Interface — Pydantic DTOs
│   │   ├── common.py
│   │   ├── track.py
│   │   ├── playlist.py
│   │   ├── set.py
│   │   ├── yandex.py
│   │   ├── track_affinity.py
│   │   ├── track_feedback.py
│   │   ├── transition_history.py
│   │   └── tool_responses.py       # ← NEW: SetVersionResult, TransitionScoreResult, etc.
│   │
│   ├── services/                   # Application — request-scoped use cases
│   │   ├── track_service.py
│   │   ├── playlist_service.py
│   │   ├── audio_service.py
│   │   ├── tiered_pipeline.py
│   │   ├── delivery_service.py
│   │   ├── discovery_service.py
│   │   ├── import_service.py
│   │   ├── candidate_service.py
│   │   ├── reasoning_service.py
│   │   ├── search_service.py
│   │   ├── sync_service.py
│   │   ├── metadata_service.py
│   │   ├── embedding_service.py
│   │   ├── prefetch_service.py
│   │   ├── mix_point_service.py
│   │   ├── adaptive_arc.py
│   │   ├── set_narrative.py
│   │   ├── track_affinity.py
│   │   ├── transition_history.py
│   │   ├── set/
│   │   │   ├── facade.py
│   │   │   ├── builder.py
│   │   │   ├── scoring.py
│   │   │   ├── crud.py
│   │   │   └── cheatsheet.py
│   │   ├── curation/
│   │   │   ├── facade.py
│   │   │   ├── audit.py
│   │   │   ├── mood.py
│   │   │   └── distribution.py
│   │   └── workflows/
│   │       ├── _helpers.py
│   │       ├── analyze_track_workflow.py
│   │       ├── build_set_workflow.py
│   │       ├── deliver_set_workflow.py
│   │       ├── import_tracks_workflow.py
│   │       └── sync_playlist_workflow.py
│   │
│   ├── entities/                   # Domain — pure dataclass domain
│   │   └── audio/
│   │       └── features.py         # TrackFeatures dataclass + from_db()
│   │
│   ├── transition/                 # Domain — 6-component scoring + intent
│   │   ├── scorer.py               # TransitionScorer
│   │   ├── score.py                # TransitionScore dataclass
│   │   ├── hard_constraints.py
│   │   ├── intent.py
│   │   ├── math_helpers.py
│   │   ├── neural_mix.py           # NeuralMixScorer
│   │   ├── recipe.py
│   │   ├── recipe_engine.py        # 12 djay Pro AI transition types
│   │   ├── section_context.py
│   │   ├── style.py
│   │   ├── subgenre_rules.py
│   │   ├── weights.py
│   │   └── components/             # Scoring components
│   │       ├── bpm.py
│   │       ├── energy.py
│   │       ├── groove.py
│   │       ├── harmonic.py
│   │       ├── spectral.py
│   │       └── timbral.py
│   │
│   ├── optimization/               # Domain — GA, greedy, fitness
│   │   ├── genetic.py
│   │   ├── greedy.py
│   │   ├── fitness.py
│   │   ├── protocol.py
│   │   └── result.py
│   │
│   ├── templates/                  # Domain — set templates registry
│   │   ├── models.py
│   │   └── registry.py             # 8 set templates
│   │
│   ├── audit/                      # Domain — techno audit specs
│   │   └── rules.py
│   │
│   ├── export/                     # Domain — export writers
│   │   ├── models.py
│   │   ├── m3u8_writer.py
│   │   ├── rekordbox_writer.py
│   │   ├── json_writer.py
│   │   └── cheatsheet_writer.py
│   │
│   ├── camelot/                    # Domain — Camelot wheel math
│   │   └── wheel.py
│   │
│   ├── audio/                      # External — analysis pipeline
│   │   ├── pipeline.py             # AnalysisPipeline orchestrator
│   │   ├── temp_download.py
│   │   ├── timeseries.py
│   │   ├── level_config.py         # L1-L4 tiered config
│   │   ├── core/
│   │   │   ├── loader.py
│   │   │   ├── context.py          # AnalysisContext + shared STFT
│   │   │   ├── framing.py
│   │   │   ├── rhythm.py
│   │   │   ├── spectral.py
│   │   │   ├── tonal.py
│   │   │   └── types.py
│   │   ├── analyzers/
│   │   │   ├── base.py
│   │   │   ├── loudness.py, energy.py, spectral.py          # core (numpy)
│   │   │   ├── bpm.py, key.py, beat.py, mfcc.py             # librosa
│   │   │   ├── tonnetz.py, tempogram.py, structure.py        # librosa
│   │   │   ├── danceability.py, dissonance.py                # essentia
│   │   │   ├── dynamic_complexity.py, beats_loudness.py      # essentia
│   │   │   ├── spectral_complexity.py, pitch_salience.py     # essentia
│   │   │   ├── bpm_histogram.py
│   │   │   └── phrase.py
│   │   └── classification/
│   │       ├── classifier.py       # Mood classifier (15 subgenres)
│   │       └── profiles.py
│   │
│   ├── providers/                   # Music provider abstraction layer
│   │   ├── protocol.py             # MusicProvider protocol (universal interface)
│   │   ├── models.py               # ProviderTrack, ProviderAlbum, etc.
│   │   └── registry.py             # ProviderRegistry (runtime container)
│   │
│   ├── clients/                     # External — platform-specific clients
│   │   └── ym/                     # Yandex Music client
│   │       ├── client.py           # YandexMusicClient (httpx async)
│   │       ├── adapter.py          # YandexMusicAdapter (→ MusicProvider)
│   │       ├── rate_limiter.py
│   │       ├── factory.py          # build_ym_client() — shared factory
│   │       ├── filters.py
│   │       └── models.py
│   │
│   └── db/                         # Persistence
│       ├── seed.py                 # static reference data (24 keys, 4 providers)
│       ├── session.py              # async_session_factory
│       ├── models/                 # SQLAlchemy 2.0 ORM
│       │   ├── base.py             # Base + TimestampMixin
│       │   ├── track.py
│       │   ├── audio.py            # features, sections, embeddings, runs
│       │   ├── library.py          # DJ library items, beatgrids, cues, loops
│       │   ├── playlist.py
│       │   ├── set.py
│       │   ├── transition.py
│       │   ├── transition_history.py
│       │   ├── platform.py         # YM/Spotify/Beatport/SoundCloud metadata
│       │   ├── ingestion.py        # providers, raw responses
│       │   ├── export.py
│       │   ├── key.py              # 24 keys + camelot edges
│       │   ├── scoring_profile.py
│       │   ├── track_affinity.py
│       │   └── track_feedback.py
│       ├── repositories/           # Data access (flush, никогда commit)
│       │   ├── base.py             # BaseRepository + cursor pagination
│       │   ├── unit_of_work.py
│       │   ├── track/
│       │   │   ├── core.py
│       │   │   ├── filtering.py
│       │   │   ├── library.py
│       │   │   ├── external_ids.py
│       │   │   └── stats.py
│       │   ├── playlist.py
│       │   ├── set.py
│       │   ├── feature.py
│       │   ├── transition.py
│       │   ├── transition_history.py
│       │   ├── candidate.py
│       │   ├── embedding.py
│       │   ├── audio.py
│       │   ├── metadata.py
│       │   ├── ingestion.py
│       │   ├── export.py
│       │   ├── track_affinity.py
│       │   └── track_feedback.py
│       └── migrations/             # Alembic
│           ├── env.py
│           └── versions/
│
├── tests/                          # Pytest (in-memory SQLite)
│   ├── acceptance/                 # Live end-to-end tests (real MCP client)
│   ├── test_models/
│   ├── test_repositories/
│   ├── test_services/
│   ├── test_tools/
│   ├── test_domain/
│   ├── test_transition/
│   ├── test_resources/
│   ├── test_prompts/
│   ├── test_core/
│   ├── test_audio/
│   └── test_ym/                    # → tests/test_ym/ (tests for clients/ym)
│
└── panel/                          # Frontend (Next.js 16, Bun)
    ├── package.json
    ├── components.json             # shadcn config
    ├── app/                        # App router (SSR)
    │   ├── layout.tsx
    │   ├── page.tsx                # Dashboard
    │   ├── library/
    │   ├── playlists/
    │   ├── sets/
    │   ├── discover/
    │   ├── tools/
    │   ├── curation/
    │   ├── audio/
    │   ├── delivery/
    │   └── admin/
    ├── actions/                    # Server actions → MCP via REST
    ├── lib/
    │   ├── mcp-client.ts
    │   ├── constants.ts
    │   ├── supabase/server.ts
    │   └── queries/
    ├── components/
    │   ├── ui/                     # shadcn components
    │   └── charts/                 # Recharts (cyberpunk neon)
    └── hooks/
```

---

## 2. Database Schema

> Production: Supabase PostgreSQL 16. Tests: in-memory SQLite (aiosqlite).
> Все таблицы (кроме join-table и `keys`/`key_edges`) имеют `created_at`, `updated_at`.

### 2.1 Core Catalog

#### `tracks`
| Column | Type | Constraints |
|---|---|---|
| id | int | PK |
| title | varchar(500) | NOT NULL |
| sort_title | varchar(500) | nullable |
| duration_ms | int | nullable |
| status | int | default 0, index (0=active, 1=archived) |
| created_at, updated_at | timestamptz | |

#### `artists`
| Column | Type | Constraints |
|---|---|---|
| id | int | PK |
| name | varchar(300) | UNIQUE |
| sort_name | varchar(300) | nullable |

#### `genres`
| id | int | PK |
| name | varchar(200) | NOT NULL |
| parent_id | int | FK genres.id, nullable |

#### `labels`
| id | int | PK |
| name | varchar(300) | UNIQUE |

#### `releases`
| id | int | PK |
| title | varchar(500) |
| label_id | int | FK labels.id, nullable |
| release_date | date | nullable |
| release_type | varchar(50) | nullable |

### 2.2 Track Joins

#### `track_artists` (join)
| track_id | int | FK tracks.id CASCADE, PK |
| artist_id | int | FK artists.id CASCADE, PK |
| role | varchar(50) | PK ('primary'/'featured'/'remixer') |

#### `track_genres`
| track_id | int | FK CASCADE, PK |
| genre_id | int | FK CASCADE, PK |

#### `track_labels`
| track_id | int | FK CASCADE, PK |
| label_id | int | FK CASCADE, PK |

#### `track_releases`
| track_id | int | FK CASCADE, PK |
| release_id | int | FK CASCADE, PK |
| track_number | int | nullable |

#### `track_external_ids`
| id | int | PK |
| track_id | int | FK tracks.id CASCADE |
| platform | varchar(50) | yandex/spotify/beatport/soundcloud |
| external_id | varchar(200) | |

### 2.3 Audio Features

#### `feature_extraction_runs`
| id | int | PK |
| track_id | int | FK tracks.id CASCADE, index |
| pipeline_name | varchar(100) | |
| pipeline_version | varchar(50) | |
| parameters | text | nullable (JSON) |
| status | varchar(20) | default 'pending' |
| error_message | text | nullable |

#### `track_audio_features_computed` (главная таблица фич)
| Column | Type | Notes |
|---|---|---|
| track_id | int | PK, FK tracks.id CASCADE |
| pipeline_run_id | int | FK feature_extraction_runs.id |
| analysis_level | int | 1-4 (L1-L4 tiered) |
| **Tempo** | | |
| bpm | float | index, 20-300 |
| bpm_confidence | float | 0-1 |
| bpm_stability | float | 0-1 |
| variable_tempo | bool | |
| **Loudness** | | |
| integrated_lufs | float | index |
| short_term_lufs_mean | float | |
| momentary_max | float | |
| rms_dbfs | float | |
| true_peak_db | float | |
| crest_factor_db | float | |
| loudness_range_lu | float | |
| **Energy (mean/max/std/slope + 7 bands + 6 ratios)** | | |
| energy_mean, energy_max, energy_std, energy_slope | float | |
| energy_sub, energy_low, energy_lowmid, energy_mid, energy_highmid, energy_high | float | |
| energy_sub_ratio … energy_high_ratio | float | |
| **Spectral** | | |
| spectral_centroid_hz | float | |
| spectral_rolloff_85, spectral_rolloff_95 | float | |
| spectral_flatness | float | |
| spectral_flux_mean, spectral_flux_std | float | |
| spectral_slope, spectral_contrast | float | |
| **Key** | | |
| key_code | int | 0-23, index |
| key_confidence | float | |
| atonality | bool | |
| hnr_db | float | |
| chroma_entropy | float | |
| **Rhythm** | | |
| mfcc_vector | varchar(500) | JSON 13 коэф. |
| hp_ratio | float | |
| onset_rate | float | |
| pulse_clarity | float | |
| kick_prominence | float | |
| **P1 Analyzers** | | |
| danceability | float | essentia DFA |
| dynamic_complexity | float | |
| dissonance_mean | float | 0-1 |
| tonnetz_vector | varchar(500) | JSON |
| tempogram_ratio_vector | varchar(500) | JSON |
| beat_loudness_band_ratio | varchar(500) | JSON |
| **P2 Analyzers** | | |
| spectral_complexity_mean | float | |
| pitch_salience_mean | float | |
| bpm_histogram_first_peak_weight | float | |
| bpm_histogram_second_peak_bpm | float | |
| bpm_histogram_second_peak_weight | float | |
| phrase_boundaries_ms | varchar(2000) | JSON |
| dominant_phrase_bars | smallint | |
| **Mood** | | |
| mood | varchar(30) | index, 1 of 15 subgenres |
| mood_confidence | float | 0-1 |

#### `track_sections`
| id | int | PK |
| track_id | int | FK tracks.id CASCADE, index |
| section_type | int | 0-11 (intro/drop/breakdown/...) |
| start_ms, end_ms | int | |
| energy | float | nullable |
| confidence | float | nullable |

#### `embeddings`
| id | int | PK |
| track_id | int | FK CASCADE, index |
| embedding_type | varchar(50) | |
| dimensions | int | |
| vector_data | bytea | |

#### `timeseries_references`
| id | int | PK |
| track_id | int | FK CASCADE |
| feature_set_name | varchar(100) | |
| storage_uri | varchar(1000) | NPZ path |
| frame_count, hop_length, sample_rate | int | |
| data_type | varchar(20) | |
| shape | varchar(100) | JSON |

### 2.4 DJ Library (Files / Cues)

#### `dj_library_items`
| id | int | PK |
| track_id | int | FK tracks.id CASCADE, index |
| file_path | varchar(1000) | |
| file_uri | varchar(1000) | nullable |
| file_hash | varchar(128) | |
| file_size | int | |
| mime_type | varchar(100) | |
| bitrate, sample_rate, channels | int | nullable |
| source_app | varchar(50) | nullable |

#### `dj_beatgrids`
| id | int | PK |
| library_item_id | int | FK |
| bpm | float | |
| first_downbeat_ms, grid_offset_ms | float | |
| confidence | float | |
| variable_tempo | bool | default false |
| canonical | bool | default false |

#### `dj_beatgrid_change_points`
| id | int | PK |
| beatgrid_id | int | FK |
| position_ms, bpm | float | |

#### `dj_cue_points`
| id | int | PK |
| library_item_id | int | FK |
| position_ms | float | |
| kind | int | 0-7 |
| hotcue_index | int | 0-15 |
| label, color | varchar | |
| quantized | bool | |
| source_app | varchar(50) | |

#### `dj_saved_loops`
| id | int | PK |
| library_item_id | int | FK |
| in_position_ms, out_position_ms, length_ms | float | |
| hotcue_index | int | nullable |
| label, color | varchar | |
| active_on_load | bool | |
| source_app | varchar(50) | |

### 2.5 Playlists

#### `dj_playlists`
| id | int | PK |
| name | varchar(500) | |
| parent_id | int | FK self, nullable |
| source_app | varchar(200) | nullable |
| source_of_truth | varchar | 'local' or platform |
| platform_ids | text | JSON map |

#### `dj_playlist_items`
| id | int | PK |
| playlist_id | int | FK CASCADE |
| track_id | int | FK tracks.id CASCADE, index |
| sort_index | int | |
| added_at | timestamptz | nullable |

### 2.6 DJ Sets

#### `dj_sets`
| id | int | PK |
| name | varchar(500) | |
| description | text | |
| target_duration_ms | int | |
| target_bpm_min, target_bpm_max | float | |
| target_energy_arc | text | JSON |
| template_name | varchar(200) | |
| source_playlist_id | int | FK dj_playlists.id |
| ym_playlist_id | varchar(200) | |

#### `dj_set_versions`
| id | int | PK |
| set_id | int | FK dj_sets.id CASCADE, index |
| label | varchar(200) | |
| generator_run_meta | text | JSON |
| quality_score | float | |

#### `dj_set_items`
| id | int | PK |
| version_id | int | FK dj_set_versions.id |
| track_id | int | FK tracks.id CASCADE |
| sort_index | int | |
| transition_id | int | FK transitions.id, nullable |
| in_section_id, out_section_id | int | nullable |
| mix_in_point_ms, mix_out_point_ms | int | nullable |
| planned_eq | text | JSON |
| notes | text | |
| pinned | bool | default false |

#### `dj_set_constraints`
| id | int | PK |
| set_id | int | FK CASCADE |
| constraint_type | varchar(200) | |
| constraint_value | text | JSON |

#### `dj_set_feedback`
| id | int | PK |
| version_id | int | FK |
| set_item_id | int | nullable |
| rating | int | 1-5 |
| feedback_type | varchar(100) | manual/live/ab_test |
| notes | text | |

### 2.7 Transitions

#### `transitions`
| id | int | PK |
| from_track_id, to_track_id | int | FK tracks.id |
| from_section_id, to_section_id | int | nullable |
| overlap_ms | int | |
| bpm_score, energy_score, harmonic_score, spectral_score, groove_score, timbral_score | float | 6-component formula |
| hard_reject | bool | |
| reject_reason | varchar | |
| key_distance_weighted, low_conflict_score | float | |
| overall_quality | float | финальный score |

#### `transition_candidates`
| id | int | PK |
| from_track_id, to_track_id | int | FK |
| bpm_distance, embedding_similarity, energy_delta | float | |
| key_distance | int | |
| fully_scored | bool | default false |

### 2.8 Platform Metadata

#### `yandex_metadata`
| id | int | PK |
| track_id | int | FK CASCADE, UNIQUE |
| yandex_track_id | varchar(100) | |
| album_id, album_title, album_type, album_genre | varchar | |
| album_year | int | |
| label, release_date | varchar | |
| duration_ms | int | |
| cover_uri | varchar(1000) | |
| explicit | bool | |
| extra | text | JSON |

#### `spotify_metadata`
| id | PK |
| track_id | FK UNIQUE |
| spotify_track_id, album_id | varchar(100) |
| explicit | bool |
| popularity, duration_ms | int |
| preview_url | varchar(1000) |
| release_date | varchar(50) |
| extra | text |

#### `spotify_album_metadata`
| id | PK |
| spotify_album_id | varchar(100) UNIQUE |
| title, album_type, total_tracks, release_date, image_url, label | various |

#### `spotify_artist_metadata`
| id | PK |
| spotify_artist_id | UNIQUE |
| name, genres, popularity, image_url | |

#### `spotify_playlist_metadata`
| id | PK |
| spotify_playlist_id | UNIQUE |
| name, description, owner_id, total_tracks, image_url | |

#### `spotify_audio_features`
| id | PK |
| track_id | FK UNIQUE |
| spotify_track_id | |
| danceability, energy, loudness, speechiness, acousticness, instrumentalness, liveness, valence, tempo | float |
| key, mode, duration_ms, time_signature | int |

#### `beatport_metadata`
| id | PK |
| track_id | FK UNIQUE |
| beatport_track_id | varchar(100) |
| bpm | float |
| key, length, label, genre, subgenre, release_date, preview_url, image_url | varchar |
| extra | text |

#### `soundcloud_metadata`
| id | PK |
| track_id | FK UNIQUE |
| soundcloud_track_id | varchar(100) |
| playback_count, favoritings_count, reposts_count, comment_count, duration_ms | int |
| downloadable, streamable | bool |
| permalink_url, artwork_url | varchar(1000) |
| genre, tag_list, license, created_at_sc | varchar |
| description, extra | text |

### 2.9 Ingestion

#### `providers`
| id | int | PK |
| name | varchar(100) | UNIQUE (spotify/soundcloud/beatport/yandex) |

#### `raw_provider_responses`
| id | int | PK |
| track_id | int | FK |
| provider_id | int | FK providers.id |
| raw_data | text | JSON |
| fetched_at | timestamptz | |

### 2.10 Export

#### `app_exports`
| id | int | PK |
| target_app | varchar(50) | traktor/rekordbox/djay |
| export_format | varchar(50) | m3u8/xml/json |
| playlist_id | int | FK dj_playlists.id, nullable |
| file_path | varchar(1000) | |
| file_size | int | |

### 2.11 Musical Key System

#### `keys` (static, 24 rows)
| key_code | int | PK 0-23 |
| pitch_class | int | 0-11 |
| mode | int | 0=minor, 1=major |
| name | varchar(30) | |
| camelot | varchar(3) | "1A".."12B" |

#### `key_edges` (Camelot graph)
| id | int | PK |
| from_key_code | int | FK keys.key_code |
| to_key_code | int | FK keys.key_code |
| distance | int | 0-6 |
| weight | float | |
| rule_name | varchar(50) | |

---

## 3. Constraint Reference (домен)

| Параметр | Диапазон |
|---|---|
| BPM | 20-300 (techno: 120-155) |
| confidence (любой) | 0-1 |
| key_code | 0-23 |
| section_type | 0-11 |
| cue kind | 0-7 |
| hotcue_index | 0-15 |
| status (track) | 0=active, 1=archived |
| analysis_level | 1-4 (L1=triage, L2=placement, L3=scoring, L4=transition) |
| LUFS (techno) | -20…-4 |
| rating (feedback) | 1-5 |

---

## 4. Approximate Volumes

| Table | Rows |
|---|---|
| tracks | ~3,000 |
| track_audio_features_computed | ~2,800 |
| track_sections | ~108,000 |
| dj_library_items | ~2,750 |
| dj_playlist_items | ~3,900 |
| dj_playlists | ~25 |
| dj_sets | ~43 |
| dj_set_versions | ~55 |
| dj_set_items | ~2,200 |
| yandex_metadata | ~2,600 |
| feature_extraction_runs | ~2,900 |
| keys | 24 (static) |
| providers | 4 (static) |
