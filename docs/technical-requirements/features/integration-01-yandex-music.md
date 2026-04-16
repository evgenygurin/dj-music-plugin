# integration-01: Yandex Music API

**Phase**: Integration
**Status**: completed
**MCP Tools**: `search_platform`, `get_platform_tracks`, `get_platform_artist_tracks`, `get_platform_album`, `platform_playlists`, `platform_liked_tracks` (hidden)
**Services**: `YandexMusicClient`

## BR-YM-001: Yandex Music API Integration

**Description**: Async HTTP client wrapping YM REST API with OAuth auth, rate limiting (1.5s + exponential backoff), and retry logic.

**Rationale**: YM is the primary streaming platform. All track discovery, import, download, and sync flows depend on this client.

### User Stories

#### US-YM-001: As a DJ, I want to search YM for tracks

**Acceptance Criteria:**
- [x] AC-YM-001: Given a query, when `search_platform(query="Amelie Lens", type="tracks")` is called, then return platform track metadata
- [x] AC-YM-002: Rate limiting enforced — 1.5s between requests, exponential backoff on 429

#### US-YM-002: As a DJ, I want to manage YM playlists

**Acceptance Criteria:**
- [x] AC-YM-003: Given `action="get_tracks"`, when called with playlist kind, then return tracks with pagination (limit/offset)
- [x] AC-YM-004: Given `action="add_tracks"`, then use JSON diff format with auto-resolved albumId
- [x] AC-YM-005: Given `action="remove_tracks"`, then remove by track_id (not by index)
- [x] AC-YM-006: After every modification, re-fetch playlist for fresh revision

#### US-YM-003: As a DJ, I want to manage YM likes

**Acceptance Criteria:**
- [x] AC-YM-007: Given `action="get_liked"`, then return liked track IDs
- [x] AC-YM-008: Given `action="add"` with track_ids, then like tracks on YM

## BR-YM-002: Known API Quirks

- Artist brief-info: 403 Antirobot — use artist tracks/albums instead
- Lyrics: 400 requires HMAC — skip gracefully
- Playlist diff format: JSON array with `op`/`at`/`tracks` (not object)
- Delete uses inclusive/exclusive index ranges (`from` inclusive, `to` exclusive)
