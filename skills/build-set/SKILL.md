---
name: build-set
description: "This skill should be used when the user asks to build a DJ set, create a set from playlist, optimize track order, rebuild set, reorder tracks, or make a set. Covers playlist audit, GA/greedy optimization, review and iteration."
version: 1.0.1
---

# Build DJ Set Workflow

Guide the user through building an optimized DJ set from a playlist using the v1 polymorphic dispatcher surface (**20 tools** = 14 core dispatchers + 6 UI Prefab Apps — см. @docs/tool-catalog.md).

## Steps

1. **Identify source playlist**
   - List playlists: `entity_list(entity="playlist", fields="summary")`
   - Resolve by name: `entity_list(entity="playlist", filters={"name__icontains": "..."})`
   - Get detail: `entity_get(entity="playlist", id=<id>, include_relations=["tracks"])`

2. **Choose template and parameters**
   - 8 templates: `warm_up_30`, `classic_60`, `peak_hour_60`, `roller_90`,
     `progressive_120`, `wave_120`, `closing_60`, `full_library`
   - Static reference: read `reference://templates`
   - Ask for BPM range / target duration if the template default doesn't fit

3. **Audit source playlist first**
   - Read `local://playlists/{id}/audit` — coverage, BPM/key distribution, gaps
   - If coverage < ~80% on features, pre-warm:
     `entity_create(entity="track_features", data={"track_ids": [...], "level": 2})`
     (handler `track_features_analyze` runs L1+L2 tiered pipeline → mood lands in features automatically)

4. **Build the set — two-step (optimize → persist)**
   - Create a set container if missing:
     `entity_create(entity="set", data={"name": "...", "template_name": "peak_hour_60"})`
   - **Step A — optimize ordering** (pure compute, no persist):
     `sequence_optimize(track_ids=[...], algorithm="ga", template="peak_hour_60", pinned=[...], excluded=[...])`
     → returns `{track_order, quality_score, algorithm, generations}`.
     - `algorithm`: `"auto"` (default — greedy for pools ≥200, GA otherwise), `"ga"` (~30s for 100 tracks), or `"greedy"` (fast).
     - `pinned` / `excluded` reject ids not in the pool with a typed `ValidationError` (v1.3.7 gate).
   - **Step B — persist as a SetVersion** (handler `set_version_build` writes items + scores transitions):
     `entity_create(entity="set_version", data={"set_id": <id>, "label": "v1", "track_order": [<...from Step A>]})`
     - Schema is strict (`extra="forbid"`): only `set_id`, `label`, `track_order`, `quality_score?`, `generator_run_meta?` are accepted.
     - FK gate (v1.3.7) rejects unknown `track_id`s in `track_order` before insert with a typed error listing the missing ids.

5. **Review the result**
   - Read `local://sets/{id}/review` — quality overview (score, hard conflicts, weakest transitions, energy arc deviation)
   - Read `local://sets/{id}/summary` or `local://sets/{id}/full`
   - **Visual review (Prefab UI)**: `ui_set_view(set_id=<id>)` renders heading + energy LineChart + DataTable + transition badges + cheatsheet card; fallback is a structured JSON payload for non-Prefab clients
   - **Pairwise heatmap**: `ui_score_pool_matrix(track_ids=[...])` for N×N visual mix-affinity
   - Score a pool of candidates without persisting:
     `transition_score_pool(track_ids=[...], intent=<optional>)` — rejects duplicate ids (v1.3.7 gate)

6. **Iterate**
   - Suggest next track: `local://tracks/{id}/suggest_next?limit=5&energy_direction=up`
   - Replacement for a weak slot: `local://tracks/{track_id}/suggest_replacement/{set_id}/{position}`
   - New version with pins/exclusions: repeat step 4 with different pinned/excluded — creates a new `set_version`, previous versions untouched
   - Compare versions: read `local://sets/{id}/versions/compare/{a}/{b}`

7. **Finalize**
   - Cheat sheet: read `local://sets/{id}/cheatsheet?version=<latest>`
   - Narrative: read `local://sets/{id}/narrative`
   - Suggest `/deliver-set` when happy

## Key Parameters

- **algorithm**: `"auto"` (default), `"ga"`, or `"greedy"` — passed to `sequence_optimize`. Without features on candidate tracks, optimizer falls back to `playlist_order`.
- **Pin / exclude**: `pinned` / `excluded` on `sequence_optimize` (NOT on `entity_create(set_version)` — that handler accepts only `track_order`). Each `entity_create(set_version)` produces a new immutable `SetVersion`.
- **view**: resources `local://sets/{id}/{summary|tracks|transitions|full}`; UI: `ui_set_view(set_id=...)`.

Auto-analysis: set build triggers L3 analysis for any candidate with `analysis_level < 3` — no manual reanalyze needed (see @docs/reports/tiered-analysis-design-2026-03-27.md).

## Tips

- Audit before building — missing audio features force `playlist_order` fallback
- GA with 100+ tracks can take 30–120 seconds (tool timeout: 120s)
- Energy arc comes from the template — tracks are placed to match the target curve
- Tool reference: @docs/tool-catalog.md (all 20 tools = 14 core dispatchers + 6 UI Prefab); resources catalog lists all 27 URIs
