-- Enable Row Level Security (RLS) on all public schema tables.
--
-- Context:  All application data access goes through the DJ Music MCP server
-- (backend with service-role key) and PostgREST is used only as a read-only
-- data source.  This migration enables RLS everywhere and adds a single
-- explicit-allow policy for the `full_access` service‑role so the backend
-- can continue to SELECT / INSERT / UPDATE / DELETE without using the
-- bypass‑rls key pattern.
--
-- IMPORTANT:  Supabase MCP `db` server already runs with `--read-only`, so
-- the only way to mutate the DB is through the `mcp` server (service‑role).
-- The policy below makes that boundary explicit rather than relying on a
-- special key.

--------------------------------------------------------------------------
-- 1. Enable RLS on every public table
--------------------------------------------------------------------------
ALTER TABLE public.alembic_version               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.app_exports                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artists                         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.beatport_metadata               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_beatgrid_change_points       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_beatgrids                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_cue_points                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_library_items                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_playlist_items               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_playlists                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_saved_loops                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_set_constraints              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_set_feedback                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_set_items                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_set_versions                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dj_sets                         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.embeddings                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feature_extraction_runs         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.genres                          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.key_edges                       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.keys                            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.labels                          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.providers                       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raw_provider_responses          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.releases                        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scoring_profiles                ENABLE ROW LEVEL SECURITY;  -- was already enabled, idempotent
ALTER TABLE public.soundcloud_metadata             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spotify_album_metadata          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spotify_artist_metadata         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spotify_audio_features          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spotify_metadata                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spotify_playlist_metadata       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.timeseries_references           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.track_affinity                  ENABLE ROW LEVEL SECURITY;  -- was already enabled, idempotent
ALTER TABLE public.track_artists                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.track_audio_features_computed   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.track_external_ids              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.track_feedback                  ENABLE ROW LEVEL SECURITY;  -- was already enabled, idempotent
ALTER TABLE public.track_genres                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.track_labels                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.track_releases                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.track_sections                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tracks                          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transition_candidates           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transition_history              ENABLE ROW LEVEL SECURITY;  -- was already enabled, idempotent
ALTER TABLE public.transitions                     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yandex_metadata                 ENABLE ROW LEVEL SECURITY;

--------------------------------------------------------------------------
-- 2. Create a single service-role policy per table
--
-- Supabase gives the `anon` and `authenticated` roles to PostgREST;
-- the `service_role` key used by the MCP server is the only role that
-- should perform mutations.  We drop any stale policies first, then
-- create a new one.
--------------------------------------------------------------------------
DO $$
DECLARE
    v_tbl text;
    v_pol text;
BEGIN
    FOR v_tbl IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename NOT LIKE 'pg_%'
    LOOP
        v_pol := 'service_role_all_' || v_tbl;
        -- best-effort: drop stale policy if exists
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON public.%I',
            v_pol, v_tbl
        );
        EXECUTE format(
            'CREATE POLICY %I ON public.%I
             FOR ALL
             TO service_role
             USING (true)
             WITH CHECK (true)',
            v_pol, v_tbl
        );
    END LOOP;
END $$;
