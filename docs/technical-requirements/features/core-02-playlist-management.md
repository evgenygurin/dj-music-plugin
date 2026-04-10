# core-02: Playlist Management

**Phase**: Core
**Status**: completed
**MCP Tools**: `list_playlists`, `get_playlist`, `manage_playlist`
**Services**: `PlaylistService`

## BR-PLS-001: Playlist Operations

**Description**: Playlists are ordered collections of tracks with source-of-truth tracking (local vs platform).

**Rationale**: Playlists serve as input for set building, curation, and sync with Yandex Music.

### User Stories

#### US-PLS-001: As an AI assistant, I want to list and inspect playlists

**Acceptance Criteria:**
- [x] AC-PLS-001: Given playlists exist, when `list_playlists()` is called, then return paginated `PlaylistSummary` with track counts
- [x] AC-PLS-002: Given a playlist ID, when `get_playlist(id=5, include_tracks=true)` is called, then return tracks in sort_index order

#### US-PLS-002: As an AI assistant, I want to manage playlist contents

**Acceptance Criteria:**
- [x] AC-PLS-003: Given track refs, when `manage_playlist(action="add_tracks", track_refs=["42","ym:135"])` is called, then add tracks idempotently
- [x] AC-PLS-004: Given positions, when `manage_playlist(action="remove_tracks", positions=[3,5])` is called, then remove and reindex
- [x] AC-PLS-005: Given action "create", when called with name and optional source, then create playlist and return ID

## BR-PLS-002: Source of Truth

**Description**: Each playlist has a `source_of_truth` ("local" or platform name). Platform-sourced playlists sync bidirectionally.

**Rationale**: Prevents accidental overwrites when syncing with YM — local changes don't clobber platform state and vice versa.
