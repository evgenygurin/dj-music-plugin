# workflow-05: Playlist Sync

**Phase**: Workflow
**Status**: completed
**MCP Tools**: `sync_playlist`, `push_set_to_ym` (hidden)
**Services**: `SyncService`, `SyncPlaylistWorkflow`
**Dependencies**: core-02, integration-01

## BR-SYN-001: Bidirectional Playlist Sync

**Description**: Synchronize local playlists with YM playlists — pull (YM→local), push (local→YM), or diff (show differences).

**Rationale**: DJ's library spans local DB and YM. Keeping them in sync prevents track loss and stale playlists.

### User Stories

#### US-SYN-001: As a DJ, I want to sync a playlist with Yandex Music

**Acceptance Criteria:**
- [x] AC-SYN-001: Given `direction="pull"`, when syncing, then import new YM tracks into local playlist
- [x] AC-SYN-002: Given `direction="push"`, when syncing, then add local-only tracks to YM playlist
- [x] AC-SYN-003: Given `direction="diff"`, when syncing, then return additions/deletions without modifying either side
- [x] AC-SYN-004: Given `dry_run=true` (default), then show changes without applying

#### US-SYN-002: As a DJ, I want to push a completed set to YM as a playlist

**Acceptance Criteria:**
- [x] AC-SYN-005: Given a set with YM-linked tracks, when `push_set_to_ym(set_id=6)` is called, then create/update YM playlist with set track order
