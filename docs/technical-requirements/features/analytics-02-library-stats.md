# analytics-02: Library Statistics

**Phase**: Analytics
**Status**: completed
**MCP Tools**: `get_library_stats`
**Services**: `CurationService`

## BR-LIB-001: Library Health Dashboard

**Description**: Aggregate statistics — total tracks, active/archived, feature coverage, BPM/LUFS/mood/key distributions.

### User Stories

#### US-LIB-001: As a DJ, I want a library health overview

**Acceptance Criteria:**
- [x] AC-LIB-001: Return `tracks.total`, `tracks.with_features`, `tracks.feature_coverage` percentage
- [x] AC-LIB-002: Return `bpm_distribution` bucketed by 10-BPM ranges
- [x] AC-LIB-003: Return playlist and set counts
- [x] AC-LIB-004: Return `ym_linked_tracks` count for sync coverage awareness
