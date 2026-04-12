# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.7.1] — 2026-04-12

### Added
- `title` on all 88 `@tool()` decorators — Claude Code shows human-readable names instead of "Run Tool"
- 7 semantic annotation presets: `ANNOTATIONS_READ_ONLY`, `WRITE_IDEMPOTENT`, `WRITE_DESTRUCTIVE`, `WRITE_OPEN_WORLD`, `WRITE_DESTRUCTIVE_OPEN`, `READ_ONLY_OPEN_WORLD`, `WRITE`
- 16 SVG icon sets per tool category (tracks, sets, playlists, audio, ym, admin, etc.)
- `TOOL_META` / `RESOURCE_META` dicts on all tools and resources (`version`, `author`)
- `title`, `icons`, `meta` on all 9 `@resource()` decorators
- Neural Mix stem-aware scoring layer (cherry-picked from main #88)
- Speculative prefetch service for next-track preparation (#89)
- `PrefetchService` + DI factory + 3 test files
- `TransitionHistoryService` DI wiring via `Depends()` (was broken `= None`)
- GitHub Actions CI workflow (ruff + mypy + lint-imports + pytest)
- PR template (`.github/pull_request_template.md`)
- Branch strategy doc (`.github/BRANCH_STRATEGY.md`)
- Pre-push hook blocking direct pushes to main
- `.claude/rules/git.md` — project-specific git workflow rules

### Changed
- **Removed `BM25SearchTransform`** — was proxying all tool calls through `run_tool`, causing "Run Tool" display in Claude Code. Replaced with native `mcp.disable(tags=...)` tag-based visibility
- Visibility policy: extended categories (delivery, discovery, curation, sync, ym) disabled at startup, unlockable via `unlock_tools`
- Repo settings: squash-only merges (merge commits disabled), auto-delete branches enabled
- Main and dev branches synced (were 50 vs 14 commits diverged)

### Fixed
- `track_affinity.refresh_from_history()` — `func.cast(..., type_=None)` produced `NullType` DDL error, replaced with `func.count().filter()`
- Duplicate alembic revision `a1b2c3d4e5f6` — renamed `add_first_downbeat_ms` to `f4a1b2c3d5e6`
- Missing imports for `ICON_*`, `TOOL_META`, annotation constants in 34 tool/resource files

### Removed
- 4 backward-compatibility shims: `services/export.py`, `optimizer.py`, `templates.py`, `transition.py`
- `services/background_tasks.py` (dead code)
- Stale git branches (claude/keen-bardeen, docs/sync-markdown-with-project, fix/tool-title-display)

## [0.7.0] — 2026-04-11

### Added
- Transition Recipe Engine — 12 djay Pro AI transition types with stem-level instructions
- Beatgrid migration (23,755 tracks)
- Auto-DJ with smart track selection (BPM ±3, Camelot ≤2)
- Preload next track, echo-out LPF, click fix, transition logging
- Phase 1 — Transition History (model, repo, service, 4 MCP tools, migration)
- Phase 2 — Track Affinity Matrix (model, repo, service, 3 MCP tools)
- Phase 3 — Persistent Track Feedback (like/ban/rate, 6 MCP tools)
- Phase 4 — Adaptive Energy Arc (trend analysis, 3 MCP tools)
- Phase 5 — Set Narrative Engine (phase analysis + suggestions)
- Phase 6 — Personal Scoring Weights (profiles, 3 MCP tools)
- DJ Panel: 4-deck layout, waveforms, EQ faders, cue points, mixer, iOS PWA
- Mixer MCP tools: set_eq, kill_eq, reset_eq, set_filter
- Selectel VM deployment with systemd-run pattern

### Changed
- Scoring weights rebalanced: spectral 0.20 (was 0.15), groove 0.15 (was 0.10), harmonic 0.12 (was 0.20)
- Section-aware scoring with drum-only harmonic floor

## [0.6.0] — 2026-04-10

### Added
- Modular architecture: bootstrap/, api/, DI, workflows
- REST API wrapper (FastAPI) with Swagger docs
- Panel (Next.js) with Supabase direct reads + MCP mutations
- FileSystemProvider auto-discovery for tools/resources/prompts
- Visibility system with `unlock_tools` per-session toggle

### Changed
- Refactored from monolithic server to 5-band architecture
- Split controllers/dependencies into db, repos, services, audio, external, uow

## [0.5.0] — 2026-04-08

### Added
- Transition system redesign: 6-component scoring (+ timbral)
- Section-aware scoring with SectionContext
- Context-aware TransitionIntent with per-template phase tables
- Style recommendation + TransitionRecipeEngine design

## [0.4.0] — 2026-04-06

### Added
- P1 analyzers: danceability, tempogram, dissonance, dynamic_complexity, tonnetz, beats_loudness
- P2 analyzers: spectral_complexity, pitch_salience, bpm_histogram, phrase
- Two-phase pipeline: independent → dependent analyzers
- Audio core layer: AnalysisContext, AudioLoader, FrameParams
- Per-analyzer clip duration (60s stitched multi-window)
- Shared onset envelope cache

### Changed
- Audio module refactored to layered architecture: core/ → analyzers/ → classification/ → pipeline
- MoodClassifier refactored to Strategy pattern with SubgenreProfile dataclasses

## [0.3.0] — 2026-03-25

### Added
- Background tasks via FastMCP Docket for long-running tools
- Error masking + retry middleware for production safety
- Real MP3 download from Yandex Music API with iCloud stub detection
- BPM, Key, Beat, MFCC analyzers (librosa) + MP3 input support
- Transition scoring: compute + persist via TransitionScorer
- GA/Greedy optimizer wired to build_set tool
- Structured output: tracks tools return Pydantic models

### Changed
- Plugin bumped to v0.3.0 (51 tools: 47 visible + 4 atomic hidden)
- Server switched to FileSystemProvider

## [0.2.0] — 2026-03-24

### Added
- Hidden atomic tools layer + mood persist in DB
- Composable tools for playlist expansion and YM sync
- YM tools connected to real YandexMusicClient via DI

### Fixed
- Plugin spec alignment: .mcp.json, hooks format, marketplace.json

## [0.1.0] — 2026-03-24

### Added
- Project requirements specification (REQUIREMENTS.md)
- Architecture design specification
- Claude Code plugin with 5 DJ workflow skills
- 44 MCP tools across 10 categories
- 44 SQLAlchemy models
- Yandex Music async client with rate limiter
- Audio pipeline: 3 core analyzers (loudness, energy, spectral)
- MoodClassifier for 15 techno subgenres
- TransitionScorer: 5-component formula
- GA optimizer + greedy chain builder + 8 DJ set templates
- Export: M3U8, Rekordbox XML, JSON guide, cheat sheet
- FastMCP v3.1 server with db_lifespan, visibility system, DI
