-- Cell 17 — BeatGrid metadata persistence.
--
-- Cheap scalar metadata for the new audio.core.tempo.BeatGrid was already
-- present on track_audio_features_computed: bpm / bpm_confidence /
-- bpm_stability / variable_tempo / first_downbeat_ms /
-- phrase_boundaries_ms / dominant_phrase_bars. The *large* beatgrid
-- arrays (beat_times, downbeat_times, bar_times, tempo_curve,
-- hypotheses) are stored on disk as a single NPZ file and referenced by
-- URI — mirroring the existing ``timeseries_references`` pattern
-- (audio/timeseries.py) instead of bloating the relational row with
-- multi-KB JSON blobs. A handful of scalar columns are added so callers
-- can introspect a beatgrid row without loading the NPZ.
--
-- Idempotent: every ALTER uses IF NOT EXISTS so re-runs against
-- Supabase are safe.

ALTER TABLE track_audio_features_computed
    ADD COLUMN IF NOT EXISTS beatgrid_storage_uri varchar(500),
    ADD COLUMN IF NOT EXISTS beatgrid_frame_count integer,
    ADD COLUMN IF NOT EXISTS beatgrid_hop_length integer,
    ADD COLUMN IF NOT EXISTS beatgrid_sample_rate integer,
    ADD COLUMN IF NOT EXISTS dominant_hypothesis_bpm double precision,
    ADD COLUMN IF NOT EXISTS dominant_hypothesis_octave_preference double precision;
