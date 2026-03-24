# DJ Techno Set Builder — Requirements Specification

> Pure requirements document. No implementation details, no code examples, no architecture suggestions.
> The system should be designed and implemented from scratch based solely on these requirements.

## 1. System Purpose

A server for managing a personal DJ techno music library, building optimized DJ sets, and integrating with the Yandex Music streaming platform. The server exposes all functionality exclusively through the Model Context Protocol (MCP), enabling AI assistants (Claude, etc.) to operate the system via tool calls.

There is no REST API, no CLI, no web UI. MCP is the sole interface.

---

## 2. Domain Model

### 2.1 Core Entities

**Track** — a music track in the local library.
- Title, sort title, duration (ms), status (active/archived), timestamps.
- A track can have multiple artists (primary, featured, remixer), genres, labels, and releases.
- A track can be linked to external platform IDs (Yandex Music, Spotify, Beatport, SoundCloud).

**Artist** — a music artist.
- Name, sort name.

**Genre** — a music genre with optional parent (hierarchical).

**Label** — a record label.

**Release** — an album/EP/single with label, date, and tracks.

### 2.2 Audio Features

**Computed Audio Features** — 47 numerical descriptors extracted from audio analysis.
- Tempo: BPM (20-300), confidence (0-1), stability (0-1), variable tempo flag.
- Loudness: integrated LUFS, short-term LUFS mean, momentary max, RMS dBFS, true peak dB, crest factor dB, loudness range (LU).
- Energy: mean/max/std, slope, 7-band breakdown (sub, low, lowmid, mid, highmid, high), ratios.
- Spectral: centroid Hz, rolloff 85%/95%, flatness, flux mean/std, slope dB/octave, contrast dB.
- Key: key code (0-23, mapping to 24 musical keys), confidence, atonality flag, chroma vector, HNR dB, chroma entropy.
- Rhythm: MFCC vector (13 coefficients), harmonic-to-percussive ratio (unbounded), onset rate, pulse clarity, kick prominence.

Each feature extraction is linked to a pipeline run (name, version, parameters, status, timestamps).

### 2.3 DJ Library

**Library Item** — a physical audio file on disk.
- File path/URI, hash, size, MIME type, bitrate, sample rate, channels, source app.

**Beatgrid** — BPM grid for a track.
- BPM, first downbeat position, grid offset, confidence, variable tempo flag, canonical flag.
- Can have change points (variable BPM).

**Cue Point** — a named position in a track.
- Position (ms), kind (8 types: cue, hot cue 1-7, memory), hotcue index (0-15), label, color, quantized flag, source app.

**Saved Loop** — a loop region in a track.
- In/out positions, length, hotcue index, label, active-on-load flag, color, source app.

### 2.4 Playlists

**Playlist** — an ordered collection of tracks.
- Name, parent playlist (hierarchical), source app.
- Source of truth: "local" or platform name.
- Platform IDs: JSON mapping platform names to external playlist IDs.
- Items: ordered (sort_index) track references with added_at timestamp.

### 2.5 DJ Sets

**DJ Set** — a planned DJ performance.
- Name, description, target duration (ms), target BPM range (min/max), target energy arc (JSON), template name, source playlist ID, linked YM playlist ID.

**Set Version** — a snapshot of a set's track ordering.
- Version label, generator run metadata (JSON), quality score, timestamp.
- Each version has ordered items (tracks with sort_index).

**Set Item** — a track in a set version.
- Sort index, track reference, transition reference, in/out section references, mix in/out points (ms), planned EQ (JSON), notes, pinned flag.

**Set Constraint** — a rule for set generation.
- Type and value (JSON).

**Set Feedback** — user/crowd rating of a set version or item.
- Rating (1-5), feedback type (manual, live crowd, A/B test), notes.

### 2.6 Transitions

**Transition** — scored quality of playing two tracks in sequence.
- From/to track, from/to section, overlap (ms).
- Scores: BPM distance, energy step, centroid gap Hz, low conflict, overlap, groove similarity, key distance weighted, overall quality.

**Transition Candidate** — a potential transition before full scoring.
- BPM distance, key distance, embedding similarity, energy delta, fully-scored flag.

### 2.7 Musical Key System

**Key** — one of 24 musical keys.
- Key code (0-23), pitch class (0-11), mode (minor=0, major=1), name, Camelot notation ("1A"-"12B").

**Key Edge** — compatibility between two keys.
- Distance, weight, rule name.
- The 24 keys form a compatibility graph (Camelot wheel).

### 2.8 Embeddings & Timeseries

**Embedding** — vector representation of a track.
- Type (name, dimensions, model), vector data.

**Timeseries Reference** — pointer to frame-level feature data stored on disk.
- Feature set name, storage URI, frame count, hop length, sample rate, data type, shape.

### 2.9 Platform Metadata

Per-platform enrichment for each track:

**Yandex Music** — yandex_track_id, album info (ID, title, type, genre, year), label, release date, duration, cover URI, explicit flag, extra JSON.

**Spotify** — spotify_track_id, album reference, explicit, popularity, duration, preview URL, release date, extra JSON. Plus separate models for album metadata, artist metadata, playlist metadata, audio features (danceability, energy, etc.).

**SoundCloud** — 20+ fields: playback/favorites/reposts/comment counts, downloadable/streamable flags, permalink, artwork, etc.

**Beatport** — beatport_track_id, BPM, key, length, label, genre/subgenre, release date, preview/image URLs, extra JSON.

### 2.10 Ingestion

**Provider** — one of 4 supported sources: Spotify, SoundCloud, Beatport, Yandex Music.

**Provider Track ID** — mapping between local track_id and external provider_track_id.

**Raw Provider Response** — cached raw API response from a provider for a track.

### 2.11 Export

**App Export** — a record of exporting data to a DJ app.
- Target app (Traktor, Rekordbox, djay), export format, playlist reference, file path, size.

---

## 3. Audio Analysis Pipeline

### 3.1 Individual Analyzers

The system must provide the following independent audio analysis capabilities. Each takes an audio signal and produces a structured result:

- **BPM Detection** — tempo with confidence and stability scores.
- **Key Detection** — musical key (one of 24) with confidence and atonality assessment.
- **Loudness Measurement** — integrated LUFS, short-term/momentary statistics, RMS, true peak, crest factor, loudness range.
- **Energy Computation** — mean/max/std energy, slope, 7-band frequency breakdown, inter-band ratios.
- **Spectral Analysis** — centroid, bandwidth, rolloff points, flatness, flux, slope, contrast, HNR.
- **Beat Detection** — beat positions, onset rate, pulse clarity, kick prominence, harmonic-to-percussive ratio. (Requires specialized audio library.)
- **Groove Analysis** — rhythmic complexity and swing metrics.
- **Structure Segmentation** — section boundaries (intro, attack, build, pre-drop, drop, peak, breakdown, outro, rise, valley, sustain) with energy and confidence per section.
- **MFCC Extraction** — 13-coefficient Mel-Frequency Cepstral Coefficients. (Requires specialized audio library.)
- **Stem Separation** — separate vocals, drums, bass, other. (Requires ML model.)

### 3.2 Pipeline Orchestration

A combined pipeline that runs all applicable analyzers on a track and persists results. Some analyzers are optional (depend on additional libraries). The pipeline must handle partial failures gracefully — known errors bubble up, unexpected errors are wrapped.

### 3.3 Mood Classification

A rule-based classifier that assigns each track to one of **15 techno subgenres** based on audio features:

1. ambient_dub, 2. dub_techno, 3. minimal, 4. detroit, 5. melodic_deep, 6. progressive, 7. hypnotic, 8. driving, 9. tribal, 10. breakbeat, 11. peak_time, 12. acid, 13. raw, 14. industrial, 15. hard_techno

Ordered by energy intensity (ambient_dub = lowest, hard_techno = highest).

Each subgenre has a weighted scoring function using 6-8 audio features. A track is scored against all 15 subgenres; the highest score wins. The classifier returns: mood, confidence, full scores dict, and reasoning text.

Key discriminating features: harmonic-to-percussive ratio, spectral centroid, energy mean, kick prominence, loudness range, spectral flux std.

"Catch-all" subgenres (driving, hypnotic) must be penalized to prevent dominating the distribution.

---

## 4. Transition Scoring

### 4.1 Scoring Formula

A 5-component weighted formula for evaluating how well two tracks transition:

| Component | Purpose |
|-----------|---------|
| BPM | Tempo compatibility — Gaussian similarity with double/half-time awareness |
| Harmonic | Key compatibility — Camelot wheel distance weighted by chroma entropy and HNR |
| Energy | Energy flow — sigmoid function on LUFS difference |
| Spectral | Timbral similarity — MFCC cosine + centroid proximity + frequency band balance |
| Groove | Rhythmic compatibility — onset density + kick prominence matching |

### 4.2 Hard Constraints

If any of these are violated, score = 0.0 (hard reject):
- BPM difference > 10
- Camelot distance >= 5
- Energy gap > 6 LUFS

### 4.3 Camelot Wheel

24 keys arranged in a wheel where adjacent keys are harmonically compatible. The system needs:
- Key code ↔ Camelot notation conversion ("8A", "11B", etc.)
- Distance calculation between any two keys (0-6)
- Compatibility check (boolean)

---

## 5. Set Generation

### 5.1 Genetic Algorithm Optimizer

Given a pool of tracks, find the optimal playing order that maximizes:
- Transition quality scores between consecutive tracks
- Adherence to a target energy arc
- BPM smoothness across the set
- Subgenre variety
- Template slot fitness (when template is active)

The optimizer must support:
- **Pinned tracks** — tracks that must remain in the set (cannot be removed by mutations).
- **Excluded tracks** — tracks banned from the set.
- **2-opt local search** — post-GA refinement.
- **Template-aware fitness** — when a template is active, compare each track's mood, energy, BPM against its assigned template slot.

### 5.2 Greedy Chain Builder

A fast alternative to GA — builds a chain by greedily selecting the best next transition at each step.

### 5.3 Set Templates

8 pre-defined DJ set templates with slot-based energy arcs:

| Template | Duration | Description |
|----------|----------|-------------|
| warm_up_30 | 30 min | Low-energy opener |
| classic_60 | 60 min | Standard build-peak-release |
| peak_hour_60 | 60 min | High-energy throughout |
| roller_90 | 90 min | Sustained driving energy |
| progressive_120 | 120 min | Gradual build over 2 hours |
| wave_120 | 120 min | Multiple energy waves |
| closing_60 | 60 min | Energy wind-down |
| full_library | variable | Use all available tracks |

Each template defines a sequence of slots with: position (0.0-1.0), target mood, energy target (LUFS), BPM range, target duration, flexibility score.

---

## 6. Yandex Music Integration

### 6.1 API Client

An async HTTP client for the Yandex Music REST API with:
- OAuth token authentication
- Rate limiting (1.5s delay + exponential backoff)
- Retry logic for transient errors

### 6.2 Required API Operations

**Search**: search by query (tracks, albums, artists, playlists, all), list genres.

**Tracks**: batch fetch by IDs, batch metadata, find similar tracks, get track supplement (lyrics/videos), resolve download URL, download MP3 file.

**Albums**: get album info, get album with tracks, batch fetch albums.

**Artists**: get artist's tracks (paginated), get artist's albums (paginated, sortable), get popular tracks.

**Playlists**: get playlist, get playlist tracks, list user playlists, batch fetch playlists, get recommendations, create/rename/delete playlist, set visibility, add tracks (diff insert format), remove tracks (index range).

**Likes**: get liked/disliked track IDs, add/remove likes.

### 6.3 Known API Constraints

- Playlist modifications use a JSON diff array format (not object).
- Delete operations use inclusive/exclusive index ranges.
- Rate limiting applies to reads too (HTTP 429).
- After every modification, re-fetch the playlist for fresh revision/indices.
- Some endpoints are broken: artist brief-info (403 Antirobot), lyrics (400 requires HMAC).

---

## 7. MCP Server Requirements

### 7.1 Server Architecture

- Standalone MCP server (no web framework wrapping).
- Single gateway that composes DJ workflow tools and Yandex Music tools under separate namespaces.
- Transforms for tool-only clients: prompts exposed as tools, resources exposed as tools.
- DB lifecycle management via MCP lifespan.
- Optional LLM sampling fallback for tools that need AI assistance (e.g., similar track discovery).

### 7.2 Tool Categories

The server must provide tools in these categories:

**CRUD** (tracks, playlists, sets, features) — standard list/get/create/update/delete with:
- Cursor-based pagination
- Flexible entity references (numeric ID, "local:N", text search)
- Structured Pydantic return types for `structuredContent`

**Search & Filter** — universal search across all entity types; parametric filter by audio features (BPM range, key, energy, spectral).

**Set Building** — build set from playlist, rebuild with pinned/excluded tracks, score transitions, score specific track pairs.

**Delivery** — multi-stage pipeline (score → export files → optional YM sync) with visible progress stages and conflict elicitation checkpoints.

**Export** — M3U8 playlist, JSON DJ guide, Rekordbox XML.

**Download** — download MP3 files from YM to local iCloud library.

**Discovery** — find similar tracks via LLM-assisted strategy and YM recommendations.

**Curation** — classify tracks by 15 moods, analyze library gaps vs template, review set quality, audit playlist against techno criteria, distribute tracks to subgenre playlists.

**Sync** — bidirectional sync between local playlists and platform playlists, source-of-truth management, push/pull DJ sets to/from YM.

**Admin** — visibility control for heavy tools (hidden by default, unlockable on demand), platform listing.

**Yandex Music** — consolidated tools wrapping all YM API operations (search, tracks, albums, artists, playlists, likes).

### 7.3 Tool Design Principles

- Read-only tools must be annotated as such.
- Tools that can fail on invalid input must raise proper MCP errors (not return error dicts).
- All tools must return typed Pydantic models for structured output.
- Long-running tools must report progress via visible stages and `ctx.info()` messages.
- Tools requiring user decisions must use elicitation (not assumptions).
- Heavy/expensive tools (audio analysis, GA optimization) must be hidden by default and require explicit activation.
- Parameterized consolidation for API wrappers: group related operations under a single tool with an `action` parameter to reduce schema token overhead.

### 7.4 Resource Endpoints

The server must expose read-only resources:
- Playlist status (track count)
- Catalog statistics (total tracks)
- Set summary (version count)
- Track audio features summary (BPM, key, energy, spectral highlights)
- Set latest version (ID, score, label)
- Library health (total tracks, feature coverage percentage)

### 7.5 Workflow Prompts

Pre-defined multi-step workflow recipes that guide AI through complex operations:
- Expand a playlist with similar tracks
- Build a set from scratch (search → import → optimize)
- Improve an existing set (score → identify weak points → rebuild)
- Deliver a set (score → export → YM sync)
- Full playlist expansion pipeline (audit → discover → import → download → analyze → re-audit → classify)

### 7.6 Dependency Injection

All services and repositories must be injected via the MCP framework's DI system. A single DB session is shared across all services within one tool call, with automatic commit on success and rollback on failure.

---

## 8. Set Delivery Workflow

When delivering a completed DJ set, the system must:

1. **Score all transitions** — evaluate every consecutive pair and produce a summary (total, hard conflicts, weak transitions, average/minimum score).

2. **Handle conflicts** — if hard conflicts exist (score = 0.0), ask the user whether to continue or abort (elicitation).

3. **Write files** to an output directory (`generated-sets/{sanitized_set_name}/`):
   - Numbered MP3 copies: `01. Track Title.mp3`, `02. Track Title.mp3`, etc.
   - M3U8 playlist with standard + custom DJ extension tags (BPM, key, energy, cue points, loops, sections, EQ, transition info, notes).
   - JSON guide with full per-track and per-transition details + set-level analytics.
   - Text cheat sheet with human-readable transition info (BPM, key, type, score, flagged problems).

4. **Handle iCloud stubs** — if a file hasn't been downloaded from iCloud yet (blocks < 90% of size), skip copying but reference the original path in M3U.

5. **Optional YM sync** — push the set as a YM playlist.

---

## 9. Export Formats

### 9.1 Extended M3U8

Standard M3U8 plus custom `#EXTDJ-*` tags:
- `#EXTDJ-BPM:` — track BPM
- `#EXTDJ-KEY:` — Camelot key notation
- `#EXTDJ-ENERGY:` — LUFS level
- `#EXTDJ-CUE:` — cue points with time, type, name, color
- `#EXTDJ-LOOP:` — loops with in/out/name
- `#EXTDJ-SECTION:` — structural sections with type, start, end, energy
- `#EXTDJ-EQ:` — planned EQ settings
- `#EXTDJ-TRANSITION:` — transition to next track with type, score, confidence, deltas, reason
- `#EXTDJ-NOTE:` — DJ notes

### 9.2 Rekordbox XML

Export set as Rekordbox-compatible XML with configurable inclusion of: cue points, saved loops, beatgrid, sections.

### 9.3 JSON Guide

Structured JSON with set metadata, per-track details, per-transition recommendations, and set-level analytics.

---

## 10. Database Requirements

### 10.1 Dual Database Support

- Development: SQLite (via async driver)
- Production: PostgreSQL 16+ (with async driver, pgvector extension for embeddings)

### 10.2 Schema

44 tables total. See domain model (section 2) for complete entity definitions.

Key constraints:
- All BPM values: 20-300
- All confidence values: 0-1
- All energy values: 0-1
- Track status: 0 (active), 1 (archived)
- Key codes: 0-23
- Section types: 0-11
- Cue kinds: 0-7
- Hotcue indices: 0-15

### 10.3 Data Volumes (reference)

| Table | Approximate rows |
|-------|-----------------|
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

---

## 11. Subgenre Playlists

15 Yandex Music playlists (one per subgenre) + 15 corresponding local DB playlists.

Source playlist: "TECHNO FOR DJ SETS" (~680 tracks).

The system must be able to:
- Classify all tracks by mood/subgenre
- Distribute tracks to the appropriate subgenre playlists
- Clean and redistribute when re-classifying
- Report distribution statistics

---

## 12. Techno Audio Quality Criteria

Tracks must meet these criteria to be considered valid techno:

| Parameter | Min | Max |
|-----------|-----|-----|
| BPM | 120 | 155 |
| LUFS | -20 | -4 |
| Energy mean | 0.05 | — |
| Onset rate | 1.0 | — |
| Kick prominence | 0.05 | — |
| Pulse clarity | 0.02 | — |
| HP ratio | — | 8.0 |
| Centroid | 300 Hz | 10,000 Hz |
| Flatness | — | 0.5 |
| Tempo confidence | 0.3 | — |
| BPM stability | 0.3 | — |
| Crest factor | — | 30 dB |
| LRA | — | 25 LU |
| HNR | -30 dB | — |

---

## 13. Testing Requirements

### 13.1 Coverage

- All domain models must have constraint validation tests
- All services must have unit tests with real DB (in-memory SQLite)
- All audio utility functions must have tests with synthetic audio
- All MCP tools must have:
  - Metadata tests (registration, tags, annotations, namespacing)
  - Client integration tests (in-memory tool invocation with structured output validation)
  - DB-dependent tools must have tests with seeded data

### 13.2 Test Infrastructure

- In-memory SQLite for all tests (fast, no cleanup)
- Synthetic audio fixtures (generated WAV files with known frequencies)
- MCP test fixtures for each server variant (with/without DB, with/without gateway namespacing)

---

## 14. Configuration

All configuration via environment variables with sensible defaults:

| Category | Variables |
|----------|----------|
| Database | Connection URL (SQLite default) |
| Yandex Music | OAuth token, user ID, base URL, library path |
| Observability | Sentry DSN, OTEL endpoint, trace sampling |
| MCP | Cache dir/TTL, retry config, pagination size, payload logging |
| LLM Sampling | API key, model name, max tokens |

---

## 15. Non-Functional Requirements

- **Language**: Python 3.12+
- **Async**: All DB and HTTP operations must be async
- **Type Safety**: Strict mypy checking with Pydantic plugin
- **Linting**: Line length 99, standard rules (E/F/W/I/N/UP/B/SIM/RUF)
- **Audio Dependencies**: Optional extras (audio analysis, ML stem separation)
- **Pagination**: Cursor-based for all list operations
- **Error Handling**: Typed error hierarchy (NotFound, Validation, Conflict)
- **Transactions**: Commit at tool boundary, not in services/repositories (repositories flush only)
- **Observability**: Structured logging, optional Sentry, optional OpenTelemetry tracing
