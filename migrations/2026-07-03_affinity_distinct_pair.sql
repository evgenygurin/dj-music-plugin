-- Forbid degenerate self-pairs in track_affinity at the DB level.
-- A track's affinity with itself carries no pair history; the pydantic
-- gate on TrackAffinityCreate (audit iter 54) already rejects it at the
-- tool boundary, but a raw insert bypassed it and one legacy row
-- (id=1, track 146 ↔ 146, created 2026-04-12 pre-gate) survived.
--
-- Delete any surviving self-pairs first so the CHECK can be added, then
-- add the constraint idempotently.

DELETE FROM track_affinity WHERE track_a_id = track_b_id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_affinity_distinct_pair'
    ) THEN
        ALTER TABLE track_affinity
            ADD CONSTRAINT ck_affinity_distinct_pair
            CHECK (track_a_id <> track_b_id);
    END IF;
END $$;
