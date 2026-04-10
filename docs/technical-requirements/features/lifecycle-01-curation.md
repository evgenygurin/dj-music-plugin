# lifecycle-01: Curation & Classification

**Phase**: Lifecycle
**Status**: completed
**MCP Tools**: `classify_mood`, `audit_playlist`, `review_set_quality`, `distribute_to_subgenres`, `get_library_stats` (hidden)
**Services**: `CurationService`
**Dependencies**: workflow-02

## BR-CUR-001: 15 Techno Subgenre Classification

**Description**: Every track is classifiable into one of 15 techno subgenres ordered by energy intensity: ambient_dub → dub_techno → minimal → detroit → melodic_deep → progressive → hypnotic → driving → tribal → breakbeat → peak_time → acid → raw → industrial → hard_techno.

**Rationale**: Subgenre classification drives template slot matching, playlist organization, and set variety scoring.

### User Stories

#### US-CUR-001: As a DJ, I want my library classified by subgenre

**Acceptance Criteria:**
- [x] AC-CUR-001: Given analyzed tracks, when `classify_mood(playlist_id=5)` is called, then assign mood + confidence to each track
- [x] AC-CUR-002: Given unanalyzed tracks, then auto-trigger L1+L2 analysis before classification
- [x] AC-CUR-003: Catch-all subgenres (driving, hypnotic) penalized by `settings.mood_catch_all_penalty`

#### US-CUR-002: As a DJ, I want to audit a playlist against techno quality criteria

**Acceptance Criteria:**
- [x] AC-CUR-004: Given a playlist, when `audit_playlist(playlist_id=5)` is called, then check each track against BPM/LUFS/energy/centroid criteria
- [x] AC-CUR-005: Return pass/fail per track with specific failing criteria

#### US-CUR-003: As a DJ, I want to distribute tracks to subgenre playlists

**Acceptance Criteria:**
- [x] AC-CUR-006: Given classified tracks, when `distribute_to_subgenres(source_playlist_id=5)` is called, then create/populate 15 subgenre playlists
- [x] AC-CUR-007: Given `sync_to_ym=true`, then push subgenre playlists to YM

## BR-CUR-002: Library Statistics

**Description**: Dashboard statistics — total tracks, feature coverage, BPM/LUFS/mood/key distributions.

### User Stories

#### US-CUR-004: As a DJ, I want library health overview

**Acceptance Criteria:**
- [x] AC-CUR-008: When `get_library_stats()` is called, then return counts, distributions, and coverage percentages
