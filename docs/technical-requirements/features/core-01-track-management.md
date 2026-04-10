# core-01: Track Management

**Phase**: Core
**Status**: completed
**MCP Tools**: `list_tracks`, `get_track`, `manage_tracks`, `get_track_features`
**Services**: `TrackService`

## BR-TRK-001: Track Lifecycle

**Description**: Tracks are the fundamental entity — audio recordings with metadata, audio features, and external platform links.

**Rationale**: Every DJ workflow starts with tracks — they're referenced by playlists, sets, transitions, and audio analysis.

### User Stories

#### US-TRK-001: As an AI assistant, I want to list tracks with pagination and BPM filtering

**Acceptance Criteria:**
- [x] AC-TRK-001: Given a library with tracks, when `list_tracks(limit=20)` is called, then return paginated `TrackBrief` items with `next_cursor`
- [x] AC-TRK-002: Given tracks with audio features, when `list_tracks(bpm_min=124, bpm_max=128)` is called, then only tracks within BPM range are returned
- [x] AC-TRK-003: Given an empty library, when `list_tracks()` is called, then return `{items: [], total: 0, next_cursor: null}`

#### US-TRK-002: As an AI assistant, I want to retrieve full track details by ID or text search

**Acceptance Criteria:**
- [x] AC-TRK-004: Given a track ID, when `get_track(id=42)` is called, then return `TrackStandard` with artists, features, external IDs
- [x] AC-TRK-005: Given a text query, when `get_track(query="Amelie Lens")` is called, then resolve by title/artist fuzzy match
- [x] AC-TRK-006: Given a YM prefix, when `get_track(query="ym:135055088")` is called, then resolve via `track_external_ids` table

#### US-TRK-003: As an AI assistant, I want to create, update, and archive tracks

**Acceptance Criteria:**
- [x] AC-TRK-007: Given valid data, when `manage_tracks(action="create", data={...})` is called, then create track and return ID
- [x] AC-TRK-008: Given an existing track, when `manage_tracks(action="archive", data={id: 42})` is called, then set status=1 (archived)
- [x] AC-TRK-009: Given an archived track, when `manage_tracks(action="unarchive", data={id: 42})` is called, then set status=0 (active)

#### US-TRK-004: As an AI assistant, I want to view computed audio features for a track

**Acceptance Criteria:**
- [x] AC-TRK-010: Given analyzed track, when `get_track_features(id=42)` is called, then return 47 feature values grouped by category
- [x] AC-TRK-011: Given `include_sections=true`, when features are requested, then include structural sections (intro, drop, breakdown, etc.)
- [x] AC-TRK-012: Given unanalyzed track, when features are requested, then return summary with `analysis_level: 0`

## BR-TRK-002: Entity Resolution

**Description**: Tracks are addressable by numeric ID, text query, or YM-prefixed ID (`ym:12345`).

**Rationale**: AI assistants receive varied references from users — "that Amelie Lens track" or "track 42" or YM link.

### User Stories

#### US-TRK-005: As an AI assistant, I want flexible track references across all tools

**Acceptance Criteria:**
- [x] AC-TRK-013: Given `id=42`, resolution returns track by primary key
- [x] AC-TRK-014: Given `query="ym:135055088"`, resolution matches via `track_external_ids(provider=yandex_music)`
- [x] AC-TRK-015: Given ambiguous text query matching multiple tracks, return the best match with alternatives in `meta`
