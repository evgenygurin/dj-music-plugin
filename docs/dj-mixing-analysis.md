# DJ Mixing Analysis Contracts

## BPM, beatgrid, and phrase alignment

**BPM** is a scalar tempo estimate. It is useful for cheap candidate filtering,
but equal BPM does not imply that two decks are phase-locked.

**Beatgrid** adds beat positions, first-downbeat phase, bars, and local tempo
information. It is the timing contract used by the pure mixing domain for
phase and accumulated-drift scoring.

**Phrase alignment** operates at bar/phrase boundaries. It answers whether a
transition lands at a musically useful structural point rather than merely on
a mathematically valid beat.

## Staged analysis

The candidate pipeline is intentionally cheap → deep:

1. Filter by basic availability, hard constraints, BPM, and energy.
2. Compute deterministic DJ alignment for the surviving shortlist.
3. Run the existing stem-aware `TransitionScorer` only for the shortlist.
4. Present the legacy transition score together with the DJ-aware alignment.

This keeps expensive analysis out of the broad candidate scan and avoids
requiring full Demucs inference for recommendation or regression tests.

## Transition contracts

Transition durations are constrained to 4, 8, 16, 32, or 64 bars. Cue
candidates are represented by track, role, bar index, duration, position, and
a deterministic quality/reason field. Missing timing data produces a neutral
alignment score instead of a hard failure; callers requiring precise timing
must validate the underlying beatgrid.
