# workflow-04: Import & Download

**Phase**: Workflow
**Status**: completed
**MCP Tools**: `import_tracks`, `download_tracks` (hidden)
**Services**: `ImportService`, `ImportTracksWorkflow`
**Dependencies**: integration-01

## BR-IMP-001: Track Import from YM

**Description**: Import tracks from Yandex Music into local library — create Track entities, link external IDs, enrich metadata, optionally add to playlist and trigger analysis.

**Rationale**: Library building starts with import from streaming platform. Metadata enrichment (artists, genres, labels) happens automatically.

### User Stories

#### US-IMP-001: As a DJ, I want to import tracks from YM into my library

**Acceptance Criteria:**
- [x] AC-IMP-001: Given YM track IDs, when `import_tracks(track_refs=["135055088"])` is called, then create Track + YandexMetadata + external ID link
- [x] AC-IMP-002: Given `playlist_id=5`, then also add imported tracks to the playlist (idempotent)
- [x] AC-IMP-003: Given `auto_analyze=true`, then trigger `TieredPipeline.ensure_level(L3)` on imported tracks
- [x] AC-IMP-004: Given track already exists (by YM ID), then skip creation but still return in `id_mapping`

## BR-IMP-002: MP3 Download

**Description**: Download MP3 files from YM to local iCloud library path, creating DjLibraryItem records automatically.

### User Stories

#### US-IMP-002: As a DJ, I want to download MP3 files for my tracks

**Acceptance Criteria:**
- [x] AC-IMP-005: Given YM track IDs, when `download_tracks(track_refs=["135055088"])` is called, then download MP3 and create DjLibraryItem
- [x] AC-IMP-006: Given `skip_existing=true` and file exists, then skip download
- [x] AC-IMP-007: Numbers < 100000 treated as local IDs, >= 100000 as YM IDs
