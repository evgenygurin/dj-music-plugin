# core-03: Search & Filter

**Phase**: Core
**Status**: completed
**MCP Tools**: `search`, `filter_tracks`
**Services**: `SearchService`

## BR-SRC-001: Cross-Entity Search

**Description**: Full-text search across tracks, artists, playlists, and sets from a single tool.

### User Stories

#### US-SRC-001: As an AI assistant, I want universal search

**Acceptance Criteria:**
- [x] AC-SRC-001: Given `entity="all"`, when searching, then return matches across all entity types
- [x] AC-SRC-002: Given `entity="tracks"`, then search only tracks by title/artist

## BR-SRC-002: Parametric Track Filtering

**Description**: Filter tracks by audio features — BPM range, key, energy, compatible keys, excluding tracks already in a set.

### User Stories

#### US-SRC-002: As a DJ, I want to find tracks matching specific criteria

**Acceptance Criteria:**
- [x] AC-SRC-003: Given `bpm_min=124, bpm_max=128, key="8A"`, when filtering, then return tracks matching all criteria
- [x] AC-SRC-004: Given `key_compatible=true`, then also include Camelot-adjacent keys (distance ≤ 1)
- [x] AC-SRC-005: Given `exclude_set_id=6`, then omit tracks already in that set
- [x] AC-SRC-006: Given `sort_by="energy_desc"`, then sort by energy mean descending
