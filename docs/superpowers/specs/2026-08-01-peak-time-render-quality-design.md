# Peak-time render quality: phrase-alignment, energy micro-arc, soft Camelot

Date: 2026-08-01
Status: Approved
Related: `docs/superpowers/specs/2026-07-21-render-refactor-design.md`,
`docs/superpowers/specs/2026-07-23-render-analysis-agent-design.md`

## Goal

Make peak_time_techno renders sound "right" per techno DJ best practices:

1. **Phrase-aligned track entry** — every incoming track enters on a musical
   phrase boundary (not mid-phrase), without breaking the kick grid.
2. **Energy micro-arc in track order** — the set's density ramps toward a peak
   (~70-80%) then eases off, instead of the flat 32/32-bar block.
3. **Soft Camelot in peak_time** — a Camelot distance >= hard-reject threshold
   no longer kills the transition in peak_time; it becomes a warning. Strict
   mode (the default) is byte-for-byte unchanged.

Scope is additive: the render engine and `SubgenreRenderPreset` values are NOT
modified. Only new parameters, a pure helper, and threading of flags.

## Background

Best-practice sources reviewed (mixgraph.io, vibesdj.io, techno mixing guides):

- Transitions should start/end on phrase boundaries (16/32 bars) — techno
  listeners read phrases, not individual bars.
- In peak-time the "blocky" uniform 32-bar body sounds monotonous; even a
  relentless set needs micro-variation: open ~60-70% peak, plateau, final push.
- Bass is binary: one kick at a time, swap on a single beat.
- In percussive techno, groove/energy/timing outrank harmonic neatness —
  especially when ~99% of this library is atonal (low key-confidence), a hard
  Camelot reject kills transitions that should live by energy.

## Feature 1 — Phrase-aligned track entry

### Data

Already stored per track in `track_features`:

- `phrase_boundaries_ms` (`String(2000)`, JSON list of ms timestamps).
- `dominant_phrase_bars` (`SmallInteger`, typically 8 or 16 for techno).
- `first_downbeat_ms` (sparse; most rows fall back to 0).

### Changes

1. **`app/domain/render/models.py`** — add to `TrackInput`:
   - `phrase_boundaries_ms: list[int] | None = None`
   - `dominant_phrase_bars: int | None = None`

2. **`app/repositories/set.py`** — `get_render_inputs`: select the two columns
   from `TrackAudioFeaturesComputed` (columns already exist on the model at
   `track_features.py:130`) and populate the new `TrackInput` fields.
   Parse `phrase_boundaries_ms` JSON string -> `list[int]` (or None).

3. **New file `app/domain/render/phrase_align.py`** — pure helper:

   ```python
   def snap_trim_to_phrase(
       trim_s: float,
       phrase_boundaries_ms: list[int] | None,
       source_bpm: float,
       *,
       window_bars: int = 4,
   ) -> float:
   ```

   - `bar_s_source = 4 * 60 / source_bpm` (source-file bar length).
   - Find the boundary nearest to `trim_s * 1000`.
   - Accept the shift `delta_ms = boundary_ms - trim_s * 1000` ONLY if
     `abs(delta_ms) / bar_s_source` is within ±0.05 of an integer (a whole-bar
     shift) AND the shift is <= `window_bars` bars.
   - Whole-bar shift keeps every kick on the beat grid (phase intact).
   - Return the adjusted `trim_s`, or the original when no boundary qualifies.

4. **`app/domain/render/timeline.py`** — `place_segments`: after reading
   `g.effective_trim`, when `inputs[i].phrase_boundaries_ms` is non-empty and
   the track's `bpm` is known, apply `snap_trim_to_phrase`. The geometry's
   `trim_start_s` then reflects the phrase-snapped value.

5. **`app/handlers/_orchestrator/render_executor.py`** — `_persist_plan`: add
   `"phrase_align": true` when any segment had its trim adjusted (plan payload).

6. **`app/tools/render/render_diagnose.py`** — structural flow section: report
   how many tracks were phrase-aligned (from `render_plan.json`).

### Acceptance

- Whole-bar shift lands the entry on a phrase boundary.
- Non-whole-bar candidate shifts are rejected (grid safety).
- No boundaries / out-of-window -> trim unchanged.
- Kick phase alignment (beatgrid) is preserved.

## Feature 2 — Energy micro-arc in track order (peak_time)

### Background

- `ArcShape.PEAK_ONLY` enum exists (`energy_arc.py:31`) but there is NO
  `ARC_PRESETS` factory for it (only roller/journey/warehouse/festival).
- `fit_tracks_to_arc` (`energy_arc.py:153`) is fully written and currently
  UNUSED — a ready greedy track-to-slot assignment (weights: bpm 0.4, energy
  0.3, key 0.3).
- Optimizers (GA/greedy/constructive) all hold `self.scorer` and expose
  `optimize(tracks, track_ids, ...)`; `sequence_optimize` tool is the entry.

### Changes

1. **`app/domain/performance/energy_arc.py`** — add a `peak_only_arc` factory
   and register it in `ARC_PRESETS`:

   ```python
   def peak_only_arc(num_tracks: int = 12) -> EnergyArc:
       return EnergyArc(
           shape=ArcShape.PEAK_ONLY,
           num_tracks=num_tracks,
           target_bpm_start=130.0,
           target_bpm_peak=130.0,
           target_bpm_end=130.0,
           name=f"PeakOnly-{num_tracks}",
       )
   ```

   `build_slots()` already handles `ArcShape.PEAK_ONLY` (flat BPM at
   `target_bpm_peak`). Adjust the flat `energy_curve = np.full(n, 0.65)` to a
   subtle peak-time micro-arc: rise to a peak near 75% then ease off:

   ```python
   energy_curve = 0.50 + 0.25 * np.exp(-((x - 0.75) ** 2) / 0.05)
   energy_curve = np.clip(energy_curve, 0.45, 0.80)
   ```

2. **`app/tools/compute/sequence_optimize.py`** — add parameter
   `energy_arc: Literal["none", "peak_time"] | None = None`:
   - `"none"`/None -> existing GA/greedy/constructive path unchanged.
   - `"peak_time"` -> load features for the pool, build `TrackCandidate`s
     (track_id, bpm, energy_mean, key_code, integrated_lufs), call
     `fit_tracks_to_arc(...)` with the `peak_only` arc sized to the pool, and
     return its order as `track_order`. The arc is authoritative for order.
   - Requires a `get_by_track_ids`-style features loader on the UoW (reuse the
     existing `track_features` repository or the already-fetched feature set).

3. **`app/tools/compute/_tool_descriptions` / MCP surface** — mirror the new
   parameter via the `dj_sequence_optimize` tool so the client can pass it.

### Acceptance

- `peak_time` arc energy rises, peaks near 75%, eases off at the end.
- `sequence_optimize(energy_arc="peak_time")` returns an order whose density
  follows that curve (energy_mean of positioned tracks roughly matches slots).
- Default path (`energy_arc` unset) is unchanged.

## Feature 3 — Soft Camelot in peak_time (scorer)

### Background

- `CamelotDistanceSpec.check` (`constraints/specs/camelot_distance.py`)
  rejects when `key_dist >= settings.hard_reject_camelot_dist` (default 5) and
  both keys are reliable (`key_reliable`, confidence floor 0.5).
- Hard reject is threaded via `check_hard_constraints`
  (`hard_constraints.py`) into: `TransitionScorer.score`,
  `score_all_intents`, `score_with_candidates`; GA
  `_precompute_reject_mask` (static); and the vectorised
  `bulk_scorer.hard_reject_mask_bulk`.
- `TransitionScore` (`score.py`) has no warnings field today.

### Changes

1. **`app/domain/transition/score.py`** — add to `TransitionScore`:
   `warnings: tuple[str, ...] = ()` (additive; existing constructions intact).

2. **`app/domain/transition/constraints/specs/camelot_distance.py`** —
   `check(..., *, soft: bool = False)`. Return type becomes
   `tuple[str | None, str | None]` = `(reason, warning)`:
   - hard mode (default): as today — `(reason, None)` on violation.
   - soft mode: `(None, "Camelot distance X >= Y (soft)")` on violation.

3. **`app/domain/transition/constraints/chain.py`** — `check(..., *,
   soft_camelot: bool = False)`: collect warnings; when a spec returns a
   `(None, warning)` pair, do NOT hard-reject; surface the accumulated warnings
   on a passing `TransitionScore` (or return a dedicated lightweight
   `TransitionScore(warnings=...)` when no other component scored — caller
   decides). Keep hard-reject semantics identical when `soft_camelot=False`.

4. **`app/domain/transition/hard_constraints.py`** — `check_hard_constraints(
   ..., *, soft_camelot: bool = False)` forwards the flag.

5. **`app/domain/transition/scorer.py`** — `score`, `score_all_intents`,
   `score_with_candidates` accept `soft_camelot: bool = False`, forward it,
   and merge spec warnings into the returned `TransitionScore.warnings`.

6. **`app/domain/optimization/genetic.py`** — `_precompute_reject_mask(
   ..., *, soft_camelot: bool = False)`: skip the Camelot hard-check when soft
   (BPM/energy hard checks still apply).

7. **`app/domain/transition/bulk_scorer.py`** —
   `hard_reject_mask_bulk(..., *, soft_camelot: bool = False)`: when soft,
   drop `key_violates` from the mask.

8. **Optimizer constructors** — `GeneticAlgorithm`, `GreedyOptimizer`,
   `ConstructiveOptimizer` accept `soft_camelot: bool = False` and forward to
   scorer calls / precompute.

9. **`app/tools/compute/sequence_optimize.py`** — add parameter
   `camelot_mode: Literal["strict", "soft"] = "strict"`; forward
   `soft_camelot = camelot_mode == "soft"` into the optimizer.

10. **MCP surface** — mirror `camelot_mode` on `dj_sequence_optimize`.

### Acceptance

- `strict` (default): identical behaviour to today (byte-for-byte).
- `soft`: a Camelot dist>=5 pair scores normally, carries a warning in
  `TransitionScore.warnings`, and the GA reject-mask no longer drops it.
- BPM/energy hard rejects remain active in soft mode.

## Testing

- `snap_trim_to_phrase`: in-window whole-bar shift applied; non-whole-bar
  rejected; out-of-window rejected; no-boundaries no-op; 1/2/4-bar cases.
- `PEAK_ONLY` / `peak_only_arc`: energy monotonic rise to 75% then fall;
  registered in `ARC_PRESETS`.
- `fit_tracks_to_arc` with a peak_time pool: order follows the energy curve.
- Camelot soft at spec / chain / scorer level: soft -> no hard_reject +
  warnings; strict -> unchanged.
- GA + bulk in soft: reject mask omits camelot, keeps bpm/energy.
- `sequence_optimize` integration: `energy_arc="peak_time"` +
  `camelot_mode="soft"`.
- `place_segments` phrase-aligned geometry: kick phase preserved.
- Full gate: `make check` (ruff + mypy strict + pytest + import-linter).

## Out of scope

- No change to `SubgenreRenderPreset` values or the render engine DSP.
- No change to classic (`stem=False`) pipeline behaviour beyond the shared
  `place_segments` phrase snapping (which is opt-in per-track data).
- No change to `render_mixdown` tool signature (features 1-2 are additive via
  track data / a separate tool parameter; feature 3 lives on
  `sequence_optimize`).
