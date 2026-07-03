# Production Set Scoring Alignment

## Goal

Make the order optimizer, persisted transitions, set items, and booth
cheatsheet describe the same transition decisions.

## Source Of Truth

`track_audio_features_computed` remains the canonical feature row.
High-confidence Beatport metadata owns canonical BPM/key/mood while the
audio-derived values remain available in the `audio_*` fields. Transition
scoring consumes the canonical values and uses `key_source`, `atonality`, and
confidence fields to explain how much the key should influence the result.

## Pair Context

Every ordered pair gets one context built from:

- position in the set;
- LUFS delta;
- selected template;
- outgoing track's preferred mix-out section;
- incoming track's preferred mix-in section.

The same context is used by optimization, persisted scoring, and recipe
selection. If section data is missing, scoring falls back to the existing
generic behavior.

## Structural Data

`TrackFeaturesRepository.get_scoring_features_batch` enriches the scoring DTO
with preferred mix-in/mix-out section metadata and parsed phrase boundaries.
No new database columns are required.

When a set version is created, the handler writes:

- transition section ids and overlap duration to `transitions`;
- transition id, section ids, and mix points to `dj_set_items`;
- the effective template and scoring policy into `generator_run_meta`.

## Optimizer

Both GA and greedy paths use intent-aware, section-aware pair scoring. Mood is
passed from the canonical feature rows instead of being forced to `None`.
The GA cache includes the effective section class so cached values cannot be
reused under a different scoring context.

## Cheatsheet

The cheatsheet remains backward compatible while adding:

- canonical Camelot key and source;
- audio key and confidence;
- Beatport key, Camelot value, and match confidence;
- explicit key agreement flag;
- canonical/audio/Beatport BPM values and source;
- mix-in/mix-out section and point;
- next transition score, recipe, and bar count.

This makes provider metadata, audio analysis, and the actual transition plan
visually distinguishable.

## Failure Handling

Missing sections or phrase boundaries degrade to generic scoring and null mix
points. Missing transitions do not prevent set creation. Database writes stay
inside the existing Unit of Work and roll back together on persistence errors.

## Verification

Add focused tests for pair-context construction, repository enrichment,
optimizer wiring, set-version persistence, and cheatsheet provenance. Run the
targeted suites followed by the repository's local quality gate.
