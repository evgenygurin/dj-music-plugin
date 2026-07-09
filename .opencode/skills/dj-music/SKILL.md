---
name: dj-music
description: >
  Use when managing DJ techno music library, building DJ sets, analyzing
  audio/transitions, or working with Yandex Music/Beatport/Suno providers.
  Triggers on keywords: dj, set, mix, track, bpm, camelot, transition,
  playlist, library, techno, suno, yandex music, beatport. Use ONLY when
  the task involves DJ-specific domain (library management, set building,
  audio analysis, provider sync). Do NOT use for general programming.
---

# DJ Music Plugin — MCP Tools Guide

This project exposes **24 MCP tools**, **33 resources**, **31 prompts**, and
**6 side-effect handlers** for DJ techno music library management.

## MCP Servers

| Server | Purpose | Tool prefix |
|--------|---------|-------------|
| `dj` | Main DJ plugin (FastMCP v3) | `dj_entity_*`, `dj_provider_*`, `dj_sequence_optimize`, `dj_transition_score_pool`, `dj_playlist_sync`, `dj_ui_*`, `dj_render_*` |
| `supabase` | Supabase Management API (read-only) | `supabase_execute_sql`, `supabase_list_tables`, `supabase_apply_migration`, `supabase_get_schema` |

## Quick Reference

### Entity CRUD (6 tools)

`dj_entity_list`, `dj_entity_get`, `dj_entity_aggregate`, `dj_entity_create`, `dj_entity_update`, `dj_entity_delete`

Supported entities: `track`, `track_features`, `audio_file`, `playlist`, `set`, `set_version`, `transition`, `transition_history`, `track_affinity`, `track_feedback`, `scoring_profile`.

Filters use Django-style lookups: `bpm__gte=120`, `mood__in=peak_time,driving`.

### Provider Tools (3)

- `dj_provider_read` — fetch from Yandex/Beatport/Suno
- `dj_provider_search` — search provider catalog
- `dj_provider_write` — mutate provider (playlist sync, likes, generation)

### Compute Tools (2)

- `dj_sequence_optimize` — find optimal track ordering (GA/greedy)
- `dj_transition_score_pool` — compute NxN pair scores

### Sync Tool (1)

- `dj_playlist_sync` — pull/push/diff with Yandex Music

### UI Prefabs (6)

`dj_ui_library_dashboard`, `dj_ui_library_audit`, `dj_ui_camelot_wheel`, `dj_ui_set_view`, `dj_ui_control_center`, `dj_ui_render_studio`, `dj_ui_transition_score`, `dj_ui_score_pool_matrix`

### Render Pipeline (3)

- `dj_render_beatgrid` — kick-phase detect + sub-beat refine
- `dj_render_mixdown` — continuous beatmatched mix (rubberband + EQ)
- `dj_render_diagnose` — defect sweep (level jumps, dropouts, bass-thin)

### Admin (2)

- `dj_unlock_namespace` — per-session enable destructive/write tools
- `dj_tool_invoke` — invoke tools by name (for clients with stale lists)

## Architecture Rules

- **MCP is primary interface** — tools/resources/prompts are declarative
- **Prompts > manual tool chains** — for multi-step DJ workflow, use prompts first
- **DB access**: locally → `dj_entity_*` (asyncpg); cloud → Supabase MCP (HTTPS)
- **Dependency rule**: `tools → handlers → repositories → models`

## When to Use What

| Task | Tool/Prompt |
|------|-------------|
| List/search library | `dj_entity_list(track)` |
| Build a set from playlist | Prompt: `build_set_workflow` |
| Check transition A→B | `dj_transition_score_pool` or `dj_ui_transition_score` |
| Sync with Yandex Music | `dj_playlist_sync` |
| Audit library quality | `dj_ui_library_audit` |
| Generate Suno assets | `suno_set_asset_workflow` prompt |
| Render mix | `dj_render_mixdown` |
