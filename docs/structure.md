# Project Structure & Database Schema

> Структура директорий, файлов и таблиц БД проекта DJ Music Plugin.
> Сгенерировано: 2026-04-07.

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
├── app/api/server.py                   # FastAPI REST wrapper над MCP
│
├── .claude/
│   ├── settings.json
│   ├── rules/                      # Правила по слоям (audio, models, tools, ...)
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
│   ├── __init__.py
│   ├── server.py                   # MCP server entry
│   ├── config.py                   # Settings (env DJ_*)
│   ├── telemetry.py                # Sentry / OTEL
│   │
│   ├── core/                       # Shared (no external deps)
│   │   ├── constants.py
│   │   ├── errors.py               # NotFoundError, ValidationError, ConflictError
│   │   ├── camelot.py              # Camelot wheel math
│   │   ├── cache.py
│   │   ├── elicitation.py
│   │   ├── entity_resolver.py
│   │   ├── pagination.py
│   │   ├── parsing.py
│   │   ├── seed.py
│   │   ├── storage.py
│   │   ├── track_features.py       # TrackFeatures dataclass + from_db()
│   │   ├── transition_intent.py
│   │   ├── ym_filters.py
│   │   └── schemas/                # Pydantic models
│   │       ├── common.py
│   │       ├── track.py
│   │       ├── playlist.py
│   │       ├── set.py
│   │       └── yandex.py
│   │
│   ├── utils/
│   │   ├── time.py                 # utc_now(), sa_now()
│   │   └── files.py
│   │
│   ├── models/                     # SQLAlchemy 2.0 модели
│   │   ├── base.py                 # Base + TimestampMixin
│   │   ├── track.py
│   │   ├── audio.py                # features, sections, embeddings, runs
│   │   ├── library.py              # DJ library items, beatgrids, cues, loops
│   │   ├── playlist.py
│   │   ├── set.py
│   │   ├── transition.py
│   │   ├── platform.py             # YM/Spotify/Beatport/SoundCloud metadata
│   │   ├── ingestion.py            # providers, raw responses
│   │   ├── export.py
│   │   └── key.py                  # 24 keys + camelot edges
│   │
│   ├── repositories/               # Data access (flush, никогда commit)
│   │   ├── base.py                 # BaseRepository + cursor pagination
│   │   ├── track/
│   │   │   ├── core.py
│   │   │   ├── filtering.py
│   │   │   ├── library.py
│   │   │   ├── external_ids.py
│   │   │   └── stats.py
│   │   ├── playlist.py
│   │   ├── set.py
│   │   ├── feature.py
│   │   ├── transition.py
│   │   ├── candidate.py
│   │   ├── embedding.py
│   │   ├── audio.py
│   │   ├── metadata.py
│   │   ├── ingestion.py
│   │   └── export.py
│   │
│   ├── services/                   # Business logic (framework-agnostic)
│   │   ├── track_service.py
│   │   ├── playlist_service.py
│   │   ├── set/
│   │   │   ├── facade.py
│   │   │   ├── builder.py
│   │   │   ├── scoring.py
│   │   │   ├── crud.py
│   │   │   └── cheatsheet.py
│   │   ├── set_service.py
│   │   ├── transition.py
│   │   ├── transition_cache.py
│   │   ├── optimizer.py
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
│   │   ├── export.py
│   │   ├── templates.py
│   │   ├── background_tasks.py
│   │   ├── curation_service.py
│   │   └── curation/
│   │       ├── facade.py
│   │       ├── audit.py
│   │       ├── mood.py
│   │       └── distribution.py
│   │
│   ├── domain/                     # Pure domain logic
│   │   ├── transition/
│   │   │   ├── scorer.py           # 6-component formula
│   │   │   └── math_helpers.py
│   │   ├── optimization/
│   │   │   ├── genetic.py          # GA optimizer
│   │   │   ├── greedy.py
│   │   │   ├── fitness.py
│   │   │   ├── protocol.py
│   │   │   └── result.py
│   │   ├── audit/rules.py
│   │   ├── templates/
│   │   │   ├── models.py
│   │   │   └── registry.py         # 8 set templates
│   │   └── export/
│   │       ├── m3u8_writer.py      # Extended M3U8
│   │       ├── rekordbox_writer.py
│   │       ├── json_writer.py
│   │       ├── cheatsheet_writer.py
│   │       └── models.py
│   │
│   ├── audio/                      # Audio analysis pipeline
│   │   ├── pipeline.py             # AnalysisPipeline orchestrator
│   │   ├── temp_download.py
│   │   ├── timeseries.py
│   │   ├── level_config.py         # L1-L4 tiered config
│   │   ├── core/
│   │   │   ├── loader.py
│   │   │   ├── context.py          # AnalysisContext + shared STFT
│   │   │   ├── framing.py
│   │   │   ├── spectral.py
│   │   │   └── types.py
│   │   ├── analyzers/              # 18 анализаторов
│   │   │   ├── base.py             # BaseAnalyzer
│   │   │   ├── loudness.py         # core
│   │   │   ├── energy.py           # core
│   │   │   ├── spectral.py         # core
│   │   │   ├── bpm.py              # librosa
│   │   │   ├── key.py              # librosa
│   │   │   ├── beat.py             # librosa
│   │   │   ├── mfcc.py             # librosa
│   │   │   ├── tonnetz.py          # librosa
│   │   │   ├── tempogram.py        # librosa
│   │   │   ├── structure.py        # librosa
│   │   │   ├── danceability.py     # essentia
│   │   │   ├── dissonance.py       # essentia
│   │   │   ├── dynamic_complexity.py
│   │   │   ├── beats_loudness.py
│   │   │   ├── spectral_complexity.py
│   │   │   ├── pitch_salience.py
│   │   │   ├── bpm_histogram.py
│   │   │   └── phrase.py
│   │   └── classification/
│   │       ├── classifier.py       # Mood classifier (15 subgenres)
│   │       └── profiles.py
│   │
│   ├── ym/                         # Yandex Music client
│   │   ├── client.py               # YandexMusicClient (httpx async)
│   │   ├── rate_limiter.py
│   │   └── models.py
│   │
│   ├── infrastructure/
│   │   ├── seed.py
│   │   └── storage.py
│   │
│   ├── mcp/                        # MCP server layer
│   │   ├── dependencies.py         # DI factories (Depends)
│   │   ├── middleware.py           # logging, timing, rate limit, retry
│   │   ├── elicitation.py
│   │   ├── tools/                  # 50 MCP tools (auto-discovered)
│   │   │   ├── _shared/
│   │   │   │   ├── taxonomy.py     # ToolCategory, annotations, timeouts
│   │   │   │   ├── resolvers.py    # resolve_track_id, resolve_entity
│   │   │   │   ├── context.py      # ToolContext wrapper
│   │   │   │   ├── dispatch.py     # ActionDispatcher
│   │   │   │   └── errors.py
│   │   │   ├── tracks.py           # CRUD tracks
│   │   │   ├── playlists.py
│   │   │   ├── crud.py             # Sets CRUD
│   │   │   ├── search.py
│   │   │   ├── sets.py             # build_set, rebuild_set, score_transitions
│   │   │   ├── reasoning.py        # suggest_next, explain, replace, compare
│   │   │   ├── delivery.py
│   │   │   ├── discovery.py
│   │   │   ├── import_download.py
│   │   │   ├── curation.py         # mood, audit, distribute
│   │   │   ├── sync.py
│   │   │   ├── audio.py            # analyze_track / batch / stems
│   │   │   ├── audio_atomic.py     # 4 hidden atomic tools
│   │   │   ├── admin.py            # unlock_tools, list_platforms
│   │   │   ├── run_tool.py
│   │   │   └── yandex/             # YM tools
│   │   │       ├── search.py
│   │   │       ├── tracks.py
│   │   │       ├── albums.py
│   │   │       ├── playlists.py
│   │   │       ├── likes.py
│   │   │       └── _constants.py
│   │   ├── resources/              # MCP resources (read-only)
│   │   │   ├── status.py
│   │   │   ├── templates.py
│   │   │   └── reference.py
│   │   ├── prompts/
│   │   │   └── workflows.py        # 5 workflow prompts
│   │   └── schemas/
│   │       └── sampling.py
│   │
│   └── migrations/                 # Alembic
│       ├── env.py
│       └── versions/               # 12 migration files
│
├── tests/                          # Pytest (in-memory SQLite)
│   ├── test_models/
│   ├── test_repositories/
│   ├── test_services/
│   ├── test_tools/
│   ├── test_mcp/
│   ├── test_mcp_tools_shared/
│   ├── test_resources/
│   ├── test_prompts/
│   ├── test_core/
│   ├── test_audio/
│   └── test_ym/
│
└── panel/                          # Frontend (Next.js 16, Bun)
    ├── package.json
    ├── components.json             # shadcn config
    ├── app/                        # App router (SSR)
    │   ├── layout.tsx
    │   ├── page.tsx                # Dashboard
    │   ├── library/
    │   │   ├── page.tsx
    │   │   ├── library-table.tsx
    │   │   └── [id]/
    │   │       ├── page.tsx
    │   │       └── track-actions-menu.tsx
    │   ├── playlists/[id]/page.tsx
    │   ├── sets/[id]/page.tsx
    │   ├── discover/
    │   │   ├── page.tsx
    │   │   ├── ym-search.tsx
    │   │   └── discover-actions.tsx
    │   ├── tools/[name]/
    │   │   ├── page.tsx
    │   │   └── tool-runner.tsx
    │   ├── curation/page.tsx
    │   ├── audio/page.tsx
    │   ├── delivery/page.tsx
    │   └── admin/page.tsx
    │
    ├── actions/                    # Server actions → MCP via REST
    │   ├── analysis-actions.ts
    │   ├── discovery-actions.ts
    │   ├── set-actions.ts
    │   ├── sync-actions.ts
    │   ├── playlist-actions.ts
    │   ├── track-actions.ts
    │   └── tool-actions.ts
    │
    ├── lib/
    │   ├── mcp-client.ts           # HTTP wrapper
    │   ├── constants.ts            # subgenre colors / labels
    │   ├── utils.ts
    │   ├── supabase/server.ts
    │   └── queries/                # Direct Supabase queries
    │       ├── dashboard.ts
    │       ├── tracks.ts
    │       ├── playlists.ts
    │       └── sets.ts
    │
    ├── components/
    │   ├── ui/                     # 25+ shadcn components
    │   ├── charts/                 # Recharts (cyberpunk neon)
    │   │   ├── bpm-distribution.tsx
    │   │   ├── lufs-range.tsx
    │   │   ├── mood-distribution.tsx
    │   │   ├── camelot-wheel.tsx
    │   │   ├── energy-arc.tsx
    │   │   ├── hp-ratio-distribution.tsx
    │   │   ├── phrase-distribution.tsx
    │   │   └── danceability-distribution.tsx
    │   ├── data-table.tsx
    │   ├── track-features.tsx
    │   ├── section-cards.tsx
    │   ├── sections-timeline.tsx
    │   ├── transition-table.tsx
    │   ├── set-actions-panel.tsx
    │   ├── playlist-actions-bar.tsx
    │   ├── cheat-sheet-tab.tsx
    │   ├── command-palette.tsx
    │   ├── mood-badge.tsx
    │   ├── tool-form.tsx
    │   ├── tool-runner.tsx (в app/tools)
    │   ├── tool-result.tsx
    │   ├── tool-action-card.tsx
    │   ├── app-sidebar.tsx
    │   └── site-header.tsx
    │
    └── hooks/use-mobile.ts
```

---

## 2. Database Schema (44 tables)

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
