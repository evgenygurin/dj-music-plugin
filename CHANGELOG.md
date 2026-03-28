# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- `app/audio/core/` — Layer 1: DSP primitives with zero app dependencies
  - `types.py` — `FrameParams`, `AudioSignal`, `AnalyzerResult` frozen dataclasses
  - `framing.py` — `compute_frame_energies()`, `compute_energy_slope()` (single source of truth)
  - `spectral.py` — `compute_stft()`, `band_energies()`, `spectral_centroid()`, etc.
  - `loader.py` — `AudioLoader` with fallback chain (soundfile → librosa → wave)
  - `context.py` — `AnalysisContext` with eager STFT/magnitude precompute (thread-safe)
- `app/audio/analyzers/base.py` — `BaseAnalyzer` ABC (Template Method), `@register_analyzer` decorator, `AnalyzerRegistry` with `pkgutil` auto-discovery
- `app/audio/classification/` — Layer 2b: mood/subgenre classification
  - `profiles.py` — 15 frozen `SubgenreProfile` dataclasses with `FeatureTarget`
  - `classifier.py` — `MoodClassifier` with Strategy pattern, injectable profiles, `MoodResult.top_matches`
- `scripts/verify_audio_pipeline.py` — E2E verification script with per-stage timing, parallel speedup measurement, and sanity checks

### Changed
- `TrackFeatures.from_db(row)` classmethod replaces 5 copies of manual field mapping
- `FeatureRepository.get_scoring_features()` + `get_scoring_features_batch()` — batch loading (N SQL → 1)
- Tools (`sets.py`, `reasoning.py`, `curation.py`) use shared helpers instead of inline queries
- Refactored `app/audio/` into layered architecture: `core/` → `analyzers/` → `classification/` → `pipeline.py`
- 8 analyzers migrated to sync `_extract(ctx)` Template Method (was async `analyze(signal)`)
- Pipeline rewritten: `AudioLoader` DI + eager `AnalysisContext` + `asyncio.to_thread()` parallelism (~1.5x speedup)
- `MoodClassifier` refactored to Strategy pattern with injectable `SubgenreProfile` dataclasses
- `scripts/benchmark_audio.py` updated to use new `AnalysisContext` + `analyzer.run(ctx)` API

### Removed
- `_features_to_dataclass()` from `background_tasks.py` (replaced by `TrackFeatures.from_db()`)
- `_load_features()` from `sets.py` (replaced by `FeatureRepository.get_scoring_features()`)
- `_load_track_features()` from `curation.py` (replaced by `FeatureRepository.get_features()`)
- `app/audio/registry.py` (split into `core/types.py` + `analyzers/base.py`)
- `app/audio/mood.py` (split into `classification/classifier.py` + `classification/profiles.py`)
- Duplicated frame energy computation (was in energy.py + structure.py)
- Duplicated FFT/windowing (was in spectral.py, energy.py, key.py)
- 8 copies of empty signal guard (now single check in `BaseAnalyzer.run()`)
- Hardcoded frame_length/hop_length (now `FrameParams` dataclass)

### Fixed
- `reasoning.py` `suggest_next_track` was missing `spectral_flatness` and `chroma_entropy` fields when constructing `TrackFeatures` — now uses `from_db()` with all 10 fields

## [0.3.0] — 2026-03-25

### Added
- Background tasks via FastMCP Docket for long-running tools (expand, analyze, deliver)
- Error masking + retry middleware for production safety
- Real MP3 download from Yandex Music API with iCloud stub detection
- BPM, Key, Beat, MFCC analyzers (librosa) + MP3 input support
- Transition scoring: compute + persist via `TransitionScorer`
- GA/Greedy optimizer wired to `build_set` tool
- `suggest_next_track` wired to `TransitionScorer`
- Structured output: tracks tools return Pydantic models
- Session state cache, LLM sampling, elicitation utilities
- Progress reporting, `ToolResult.meta`, `catalog://stats` resource
- `deliver_set`: `key_camelot`, `mood`, `file_path` + real file copy
- Full lifespan context in test client fixture

### Changed
- Plugin bumped to v0.3.0 (51 tools: 47 visible + 4 atomic hidden)
- `crud.py` split into `tracks.py` + `playlists.py` with `Depends()` DI
- `discovery.py` split, `import_download.py` extracted
- Server switched to FileSystemProvider, circular imports eliminated
- Shared helpers extracted to `core/schemas.py`

## [0.2.0] — 2026-03-24

### Added
- Hidden atomic tools layer + mood persist in DB
- Composable tools for playlist expansion and YM sync
- YM tools connected to real `YandexMusicClient` via DI
- `list_page_size` increased to 100 for Claude Code tool visibility

### Fixed
- Plugin spec alignment: `.mcp.json`, hooks format, marketplace.json
- `manage_set`: serialize `constraint_value` dict, fix `add_feedback` ordering
- Double-import bug and runtime errors across MCP tools

## [0.1.0] — 2026-03-24

### Added
- Project requirements specification (REQUIREMENTS.md)
- Architecture design specification
- Claude Code plugin with 5 DJ workflow skills (build-set, expand-playlist, deliver-set, curate-library, ym-sync)
- 44 MCP tools across 10 categories
- 44 SQLAlchemy models (10 track, 5 audio, 5 library, 2 playlist, 5 set, 2 transition, 8 platform, 3 ingestion, 1 export, 2 key, 1 feature extraction)
- BaseRepository + 6 domain repositories with cursor pagination
- TrackService, PlaylistService with DI factories
- Yandex Music async client with rate limiter + exponential backoff
- Audio pipeline: AnalyzerRegistry + 3 core analyzers (loudness, energy, spectral)
- MoodClassifier for 15 techno subgenres (Gaussian scoring, catch-all penalty)
- TransitionScorer: 5-component formula with hard constraints
- GA optimizer + greedy chain builder + 8 DJ set templates
- Export: M3U8 (#EXTDJ-* tags), Rekordbox XML, JSON guide, cheat sheet
- FastMCP v3.1 server with db_lifespan, visibility system, DI
- Project scaffolding: pyproject.toml, Makefile, .env.example, Alembic migration
- Claude Code rules (.claude/rules/) for all layers
