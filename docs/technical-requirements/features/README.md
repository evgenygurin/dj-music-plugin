# Feature Specifications — DJ Music Plugin

> **Note:** 6 specs (`core-01-track-management`, `core-04-deck-mixer-engines`,
> `workflow-01-set-building`, `workflow-02-audio-analysis`,
> `lifecycle-01-curation`, `integration-01-yandex-music`) describing
> the v0.x named-tool surface (`build_set`, `analyze_track`,
> `classify_mood`, `ym_search`, `mixer_*`, …) were removed in the
> Phase 7 cleanup — those tools no longer exist; the same functionality
> is now covered by the v1 generic dispatchers + handlers
> (`entity_*`, `provider_*`, `track_features_analyze`, …). See
> [docs/architecture.md](../../architecture.md) and
> [docs/tool-catalog.md](../../tool-catalog.md) for the current
> dependency graph and tool surface.

## Feature Index (current, v1)

| ID | Phase | Feature | Status | File |
|----|-------|---------|--------|------|
| core-02 | Core | Playlist Management | completed | [core-02-playlist-management.md](core-02-playlist-management.md) |
| core-03 | Core | Search & Filter | completed | [core-03-search-filter.md](core-03-search-filter.md) |
| workflow-03 | Workflow | Set Delivery & Export | completed | [workflow-03-set-delivery.md](workflow-03-set-delivery.md) |
| workflow-04 | Workflow | Import & Download | completed | [workflow-04-import-download.md](workflow-04-import-download.md) |
| workflow-05 | Workflow | Playlist Sync | completed | [workflow-05-playlist-sync.md](workflow-05-playlist-sync.md) |
| lifecycle-02 | Lifecycle | Set Reasoning | completed | [lifecycle-02-set-reasoning.md](lifecycle-02-set-reasoning.md) |
| analytics-01 | Analytics | Export Formats | completed | [analytics-01-export-formats.md](analytics-01-export-formats.md) |
| analytics-02 | Analytics | Library Statistics | completed | [analytics-02-library-stats.md](analytics-02-library-stats.md) |

## Domain Codes

| Code | Domain |
|------|--------|
| TRK | Tracks |
| PLS | Playlists |
| SET | DJ Sets |
| AUD | Audio Analysis |
| CUR | Curation |
| DLV | Delivery |
| IMP | Import/Download |
| SYN | Sync |
| YM | Yandex Music |
| RSN | Set Reasoning |
| DCK | Deck/Mixer |
| EXP | Export |
| LIB | Library Stats |
| SRC | Search |
