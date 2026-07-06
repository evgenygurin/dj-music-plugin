# Set Design-Data Dump — Design Spec

Date: 2026-07-07
Status: approved (design phase)

## Purpose

We need a way to hand a design agent (working on a future visual dashboard
for building/managing DJ sets) a complete, self-describing snapshot of
everything the database knows about one set/version — tracks, full audio
features, transitions, render/beatgrid state — so it can decide how to
group and lay out a real dashboard without guessing at what data exists.

This is explicitly a **throwaway data-exposure tool**, not the final
dashboard architecture. Once the design agent proposes a layout, we will
revisit what belongs in proper `tools/` vs `resources/` vs UI components
(per `.claude/rules/tools.md` / `.claude/rules/resources.md`). Right now the
only goal is: get every relevant field out, human-labeled, in one JSON
payload.

## Scope

One resource, one read path: given a `set_id` (+ optional `version_id`,
defaulting to latest), return a single JSON document containing:

1. **Set** (`dj_sets`) — name, description, target_duration_ms,
   target_bpm_min/max, target_energy_arc, template_name,
   source_playlist_id, ym_playlist_id.
2. **Version** (`dj_set_versions`) — label, quality_score,
   generator_run_meta.
3. **Tracks** — one entry per `dj_set_items` row in the version:
   position (sort_index), mix_in_point_ms, mix_out_point_ms, planned_eq,
   pinned, notes, plus the **full** `TrackAudioFeaturesComputed` row (all
   ~70 columns) for that track, grouped into semantic blocks:
   Tempo, Loudness, Energy, Spectral, Key, Rhythm, P1 (essentia),
   P2 (essentia), Classification/Mood, Beatport ground-truth.
4. **Transitions** — for each adjacent track pair in the version: all
   score components (bpm/energy/drums/bass/harmonics/vocals),
   overall_quality, hard_reject/reject_reason, fx_type, transition_bars,
   transition_recipe_json.
5. **Render/beatgrid** — beatgrid rows, job status, timeline, diagnostics
   for this version, if present (reuse `gather_render_studio`).

Out of scope: whole-library aggregates (already covered by
`ui_library_dashboard` / `ui_camelot_wheel`), multi-set comparison,
write/mutation paths, Prefab UI rendering.

## Field descriptions — the "not bare numbers" requirement

Every leaf metric is returned as an object, not a bare scalar:

```json
{
  "value": 0.82,
  "label": "Kick prominence",
  "description": "0-1 proxy for how dominant the kick drum is in the mix. High values (>0.6) suggest driving/peak-time material; low values suggest minimal/ambient."
}
```

Descriptions live in a static lookup table keyed by column name — one
entry per `TrackAudioFeaturesComputed` column and one per `Transition`
score column — not generated at request time. This keeps the resource
pure-read and avoids any LLM-in-the-loop cost.

Null values still return the `label`/`description` (so the design agent
knows the field *exists* and what it *would* mean), with `value: null`.

## Implementation shape

- New resource file: `app/resources/set_design_data.py`, URI
  `local://sets/{id}/design_data{?version}`.
- New static catalog: `app/resources/_feature_catalog.py` — dict mapping
  each `TrackAudioFeaturesComputed` / `Transition` column name to
  `{group, label, description}`. Hand-written, one-time cost, ~90 entries
  total (70 feature columns + ~15 transition columns + a handful of
  set/version/set_item columns).
- Reuse existing batch-read helpers — no new repository methods:
  - `uow.track_features.get_scoring_features_batch(track_ids)`
  - `uow.tracks.get_many(track_ids)`
  - `uow.transitions.get_pairs_batch(pair_keys)`
  - `gather_render_studio(...)` (already used by `ui_render_studio`)
- Version resolution: `version` query param optional; when omitted, use
  the most recently created `dj_set_versions` row for the set (mirrors
  existing `local://sets/{id}/review{?version}` convention).
- Pure JSON resource (no Prefab UI, no `meta={"ui": True}`) — the design
  agent reads `read_resource` output directly. `mime_type="application/json"`.
- Not registered as a tool; not added to `ALWAYS_VISIBLE_TOOLS`. It is a
  resource like the rest of `local://`.

## Error handling

- Unknown `set_id` → typed `NotFoundError` (existing `DomainErrorMiddleware`
  convention, consistent with other `local://sets/{id}/...` resources).
- Set with no versions → typed error, not an empty/degenerate payload.
- Missing render/beatgrid data for the version → `render` section present
  with all sub-fields `null`/empty, not omitted (design agent needs to see
  the shape even when empty).

## Non-goals / explicit deferrals

- No decision yet on whether this becomes a permanent resource, gets
  folded into `ui_control_center`, or is deleted once the design phase
  ends. That call happens after the design agent's proposal comes back.
- No Prefab UI component for this data — it is agent-to-agent data
  exchange, not a human-facing screen.
- No aggregation/statistics beyond what's already stored per row (e.g. no
  new derived metrics).
