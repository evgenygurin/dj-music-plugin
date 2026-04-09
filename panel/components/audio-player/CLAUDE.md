# Audio Player Context

Single-file Web Audio engine (`audio-player-context.tsx`, ~1800 LOC). Handles dual-deck crossfade, LUFS normalization, bass-kick kill, and 6-style transition dispatch.

## Deck signal chain

`source → preGain → (dryGain ‖ hp1 → hp2 → wetGain) → sum → mid → high → gain → masterLimiter → destination`

- `preGain` — LUFS-normalization offset (attenuate-only, set at fade start)
- `dryGain` / `wetGain` — bass-kick kill crossfader (LR4 HP @ 150 Hz default)
- `gain` — per-deck equal-power fade envelope
- `masterLimiter` — shared `DynamicsCompressorNode`, last safety before `ctx.destination`

## `RuntimeStyle` is duplicated in 3 places

Extending the transition-style set requires editing ALL three or TypeScript happily passes:

1. `AudioPlayerApi.lastResolvedStyle` (interface field, ~line 166)
2. `useState<...>` for `lastResolvedStyle` (~line 261)
3. `type RuntimeStyle = ...` inside `startCrossfade` (~line 866)

## Per-style cleanup pattern

Styles that build transient Web Audio nodes (e.g. ECHO_OUT's DelayNode / feedback graph) or mutate deck state (e.g. FILTER_SWEEP's HP cutoff automation) **must** push a disposer into `extraCleanup: Array<() => void>` declared near the gain-envelope dispatch. The fade finaliser `setTimeout` drains it before freeing the deck.

## Style → backend recommendation mapping

Dispatcher in `startCrossfade` maps the 6 backend styles to 6 runtime styles 1:1:

- `cut` → `cut`
- `bass_swap_short` / `bass_swap_long` → `swap`
- `echo_out` → `echo_out`
- `filter_sweep` → `filter_sweep`
- `long_blend` → `harmonic`
- fallback → `fade`

Manual override chip group (MediumPlayerBar) only exposes `cut`/`swap`/`harmonic`/`fade` — `echo_out` and `filter_sweep` arrive ONLY from the backend scorer. `manualStyleRef.current` wins over the scorer at dispatch time (read from ref, not state, because `startCrossfade` runs inside a `.then()`).

## ECHO_OUT bypasses the master limiter

Its feedback loop routes `echoDelay → echoWet → ctx.destination` directly (not through the shared `masterLimiter`). Safety depends on `feedback ≤ 0.55` and `wetCeiling ≤ 0.7 * vol`. Do not raise these without adding a dedicated limiter on the wet branch.

## Fast Refresh

This module exports components AND hooks — mixing type exports in would trigger full-reload. Types live in sibling `audio-player-types.ts` — import `PlayerTrackMeta` / `ManualTransitionStyle` from there, never re-export them through this file.

## `manualStyle` persistence

Persisted to `localStorage['dj.player.manualStyle']`. Initialised to `'auto'` on mount (SSR-safe), hydrated in a mount effect with `isValidManualStyle` type-guard. `setManualStyle` writes through. Both sides wrapped in try/catch for private-mode / quota errors. Both `manualStyle` and `setManualStyle` must stay in the `useMemo` deps of the `api` object.
