-- Preserve source-specific values while making verified Beatport metadata
-- authoritative for the canonical BPM, key and internal subgenre fields.
ALTER TABLE track_audio_features_computed
    ADD COLUMN IF NOT EXISTS audio_bpm double precision,
    ADD COLUMN IF NOT EXISTS audio_bpm_confidence double precision,
    ADD COLUMN IF NOT EXISTS audio_key_code integer,
    ADD COLUMN IF NOT EXISTS audio_key_confidence double precision,
    ADD COLUMN IF NOT EXISTS audio_mood varchar(30),
    ADD COLUMN IF NOT EXISTS audio_mood_confidence double precision,
    ADD COLUMN IF NOT EXISTS bpm_source varchar(16),
    ADD COLUMN IF NOT EXISTS key_source varchar(16),
    ADD COLUMN IF NOT EXISTS mood_source varchar(16),
    ADD COLUMN IF NOT EXISTS beatport_bpm double precision,
    ADD COLUMN IF NOT EXISTS beatport_key varchar(64),
    ADD COLUMN IF NOT EXISTS beatport_camelot varchar(3),
    ADD COLUMN IF NOT EXISTS beatport_duration_ms integer,
    ADD COLUMN IF NOT EXISTS beatport_isrc varchar(32),
    ADD COLUMN IF NOT EXISTS beatport_release varchar(500),
    ADD COLUMN IF NOT EXISTS beatport_label varchar(300);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_features_audio_key_code') THEN
        ALTER TABLE track_audio_features_computed
            ADD CONSTRAINT ck_features_audio_key_code
            CHECK (audio_key_code IS NULL OR audio_key_code BETWEEN 0 AND 23);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_features_bpm_source') THEN
        ALTER TABLE track_audio_features_computed
            ADD CONSTRAINT ck_features_bpm_source
            CHECK (bpm_source IS NULL OR bpm_source IN ('audio', 'beatport'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_features_key_source') THEN
        ALTER TABLE track_audio_features_computed
            ADD CONSTRAINT ck_features_key_source
            CHECK (key_source IS NULL OR key_source IN ('audio', 'beatport'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_features_mood_source') THEN
        ALTER TABLE track_audio_features_computed
            ADD CONSTRAINT ck_features_mood_source
            CHECK (mood_source IS NULL OR mood_source IN ('audio', 'beatport'));
    END IF;
END
$$;

UPDATE track_audio_features_computed
SET audio_bpm = COALESCE(audio_bpm, bpm),
    audio_bpm_confidence = COALESCE(audio_bpm_confidence, bpm_confidence),
    audio_key_code = COALESCE(audio_key_code, key_code),
    audio_key_confidence = COALESCE(audio_key_confidence, key_confidence),
    audio_mood = COALESCE(audio_mood, mood),
    audio_mood_confidence = COALESCE(audio_mood_confidence, mood_confidence),
    bpm_source = COALESCE(bpm_source, CASE WHEN bpm IS NOT NULL THEN 'audio' END),
    key_source = COALESCE(key_source, CASE WHEN key_code IS NOT NULL THEN 'audio' END),
    mood_source = COALESCE(mood_source, CASE WHEN mood IS NOT NULL THEN 'audio' END);

CREATE INDEX IF NOT EXISTS ix_features_mood_source
    ON track_audio_features_computed (mood_source);
CREATE INDEX IF NOT EXISTS ix_features_beatport_isrc
    ON track_audio_features_computed (beatport_isrc)
    WHERE beatport_isrc IS NOT NULL;
