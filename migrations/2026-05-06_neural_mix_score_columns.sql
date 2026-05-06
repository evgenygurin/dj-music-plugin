-- v1.3.1 — Neural Mix score-column rename
--
-- Renames four score columns in `transitions` and `transition_history` and
-- four weight columns in `scoring_profiles` to match the Neural Mix stem
-- vocabulary established in v1.3.0:
--
--   harmonic_score  -> harmonics_score   (HARMONICS stem)
--   spectral_score  -> bass_score        (BASS stem)
--   groove_score    -> drums_score       (DRUMS stem)
--   timbral_score   -> vocals_score      (VOCALS stem)
--
-- The rename is purely cosmetic — column data types, defaults, indexes, and
-- check constraints are preserved. Application code in v1.3.1+ writes the
-- new column names exclusively; rolling back to v1.3.0 requires reversing
-- this migration with the obvious symmetric ALTER TABLE statements.
--
-- Apply against the production Supabase project once and only once.
-- No corresponding Alembic version is generated — this repo manages
-- transition-domain DDL via direct SQL because Supabase is the source of
-- truth for the schema.

BEGIN;

-- transitions ────────────────────────────────────────────────────────────
ALTER TABLE transitions RENAME COLUMN harmonic_score TO harmonics_score;
ALTER TABLE transitions RENAME COLUMN spectral_score TO bass_score;
ALTER TABLE transitions RENAME COLUMN groove_score   TO drums_score;
ALTER TABLE transitions RENAME COLUMN timbral_score  TO vocals_score;

-- transition_history ─────────────────────────────────────────────────────
ALTER TABLE transition_history RENAME COLUMN harmonic_score TO harmonics_score;
ALTER TABLE transition_history RENAME COLUMN spectral_score TO bass_score;
ALTER TABLE transition_history RENAME COLUMN groove_score   TO drums_score;
ALTER TABLE transition_history RENAME COLUMN timbral_score  TO vocals_score;

-- scoring_profiles ───────────────────────────────────────────────────────
ALTER TABLE scoring_profiles RENAME COLUMN harmonic_weight TO harmonics_weight;
ALTER TABLE scoring_profiles RENAME COLUMN spectral_weight TO bass_weight;
ALTER TABLE scoring_profiles RENAME COLUMN groove_weight   TO drums_weight;
ALTER TABLE scoring_profiles RENAME COLUMN timbral_weight  TO vocals_weight;

-- Update the per-row CheckConstraint names to keep psql introspection sane.
ALTER TABLE scoring_profiles RENAME CONSTRAINT ck_profile_harm     TO ck_profile_harmonics;
ALTER TABLE scoring_profiles RENAME CONSTRAINT ck_profile_spectral TO ck_profile_bass;
ALTER TABLE scoring_profiles RENAME CONSTRAINT ck_profile_groove   TO ck_profile_drums;
ALTER TABLE scoring_profiles RENAME CONSTRAINT ck_profile_timbral  TO ck_profile_vocals;

COMMIT;
