# MCP Tool Catalog

Quick reference for all 44 tools. Full details in design spec §4.

## Core Tools (always visible)

### CRUD (10 tools, tag: `core`)

| Tool | Params | Returns | RO |
|------|--------|---------|-----|
| `list_tracks` | playlist_id?, mood?, bpm_min/max?, key?, status?, sort_by, detail, cursor, limit | PaginatedResult[TrackBrief] | yes |
| `get_track` | id?, query?, ym_id?, view, include_transitions? | TrackFull | yes |
| `manage_tracks` | action(create\|update\|archive\|unarchive), data? | TrackStandard | no |
| `list_playlists` | source?, parent_id?, cursor, limit | PaginatedResult[PlaylistSummary] | yes |
| `get_playlist` | id?, query?, include_tracks?, view | PlaylistDetail | yes |
| `manage_playlist` | action(create\|update\|delete\|add_tracks\|remove_tracks\|reorder), data?, track_refs?, positions? | PlaylistSummary | no |
| `list_sets` | template?, cursor, limit | PaginatedResult[SetSummary] | yes |
| `get_set` | id?, query?, version?, view(summary\|tracks\|transitions\|full) | SetView | yes |
| `manage_set` | action(create\|update\|delete\|add_constraint\|remove_constraint\|add_feedback), data? | SetSummary | no |
| `get_track_features` | id?, query?, include_sections?, include_timeseries? | AudioFeaturesSummary | yes |

### Search (2 tools, tag: `core`)

| Tool | Params | Returns | RO |
|------|--------|---------|-----|
| `search` | query, entity(tracks\|artists\|playlists\|sets\|all), limit | SearchResults | yes |
| `filter_tracks` | bpm_min/max?, key?, key_compatible?, energy_min/max?, mood?, centroid_min/max?, has_features?, exclude_set_id?, sort_by, limit, cursor | PaginatedResult[TrackStandard] | yes |

### Set Building (4 tools, tag: `sets`)

| Tool | Params | Returns | RO |
|------|--------|---------|-----|
| `build_set` | playlist_id?, playlist_query?, name, template?, target_duration_min?, bpm_min/max?, algorithm, pinned_tracks?, excluded_tracks?, dry_run? | SetBuildResult | no |
| `rebuild_set` | set_id, pin_tracks?, unpin_tracks?, exclude_tracks?, include_tracks?, swap?, algorithm, version_label? | SetBuildResult | no |
| `score_transitions` | mode(set\|pair\|track_candidates), set_id?, from_track_id?, to_track_id?, track_id?, top_n? | varies by mode | yes |
| `get_set_cheat_sheet` | set_id, version? | str (formatted text) | yes |

### Set Reasoning (5 tools, tag: `sets`)

| Tool | Params | Returns | RO |
|------|--------|---------|-----|
| `suggest_next_track` | set_id, after_position, pool?, count?, prefer_mood?, energy_direction? | list[NextTrackSuggestion] | yes |
| `explain_transition` | from_track_id, to_track_id | TransitionExplanation | yes |
| `find_replacement` | set_id, position, pool?, count?, constraints? | list[ReplacementCandidate] | yes |
| `compare_set_versions` | set_id, version_a?, version_b? | VersionComparison | yes |
| `quick_set_review` | set_id, version? | QuickSetReview | yes |

### Admin (2 tools, tag: `admin`)

| Tool | Params | Returns | RO |
|------|--------|---------|-----|
| `unlock_tools` | action(unlock\|lock\|status), category? | VisibilityStatus | no |
| `list_platforms` | — | list[Platform] | yes |

## Extended Tools (unlock per category)

### Delivery & Export (2 tools, tag: `delivery`)

| Tool | Params | Returns | Timeout |
|------|--------|---------|---------|
| `deliver_set` | set_id, version?, output_dir?, copy_files?, sync_to_ym?, formats?, dry_run? | DeliveryResult | 300s |
| `export_set` | set_id, format, output_path?, rekordbox_options? | ExportResult | — |

### Discovery & Download (3 tools, tag: `discovery`)

| Tool | Params | Returns | Timeout |
|------|--------|---------|---------|
| `find_similar_tracks` | track_id, strategy?, limit?, bpm_tolerance?, key_compatible? | list[SimilarTrack] | — |
| `import_tracks` | track_refs, playlist_id?, auto_analyze? | ImportResult | — |
| `download_tracks` | track_refs, target_dir?, skip_existing? | DownloadResult | 300s |

### Curation (5 tools, tag: `curation`)

| Tool | Params | Returns | RO |
|------|--------|---------|-----|
| `classify_mood` | track_ids?\|playlist_id?, reclassify? | ClassificationResult | yes |
| `audit_playlist` | playlist_id?, playlist_query?, check?, template? | AuditReport | yes |
| `review_set_quality` | set_id, version? | SetQualityReport | yes |
| `distribute_to_subgenres` | source_playlist_id?, mode?, sync_to_ym?, dry_run? | DistributionResult | no |
| `get_library_stats` | — | LibraryStats | yes |

### Sync (2 tools, tag: `sync`)

| Tool | Params | Returns | RO |
|------|--------|---------|-----|
| `sync_playlist` | playlist_id, direction?, conflict_strategy?, dry_run? | SyncResult | no |
| `push_set_to_ym` | set_id, ym_playlist_name?, mode? | PushResult | no |

### YM API (6 tools, tag: `ym`)

| Tool | Params | Returns | RO |
|------|--------|---------|-----|
| `ym_search` | query, type?, limit? | YMSearchResults | yes |
| `ym_get_tracks` | track_ids | list[YMTrack] | yes |
| `ym_get_album` | album_id, include_tracks? | YMAlbum | yes |
| `ym_artist_tracks` | artist_id, page?, sort_by? | YMArtistTracks | yes |
| `ym_playlists` | action(get\|list\|create\|rename\|delete\|add_tracks\|remove_tracks), params... | varies | varies |
| `ym_likes` | action(get_liked\|add\|remove), track_ids? | varies | varies |

## Hidden Tools (explicit unlock required)

### Audio Analysis (3 tools, tag: `audio`)

| Tool | Params | Returns | Timeout |
|------|--------|---------|---------|
| `analyze_track` | track_id?, track_query?, analyzers?, force? | AnalysisResult | 120s |
| `analyze_batch` | track_ids?\|playlist_id?, analyzers?, priority? | BatchAnalysisResult | 600s |
| `separate_stems` | track_id?, track_query?, stems? | StemResult | 300s |

## Legend

- **RO**: readOnlyHint annotation (yes = no side effects)
- **?**: optional parameter
- **\|**: alternative (enum values)
