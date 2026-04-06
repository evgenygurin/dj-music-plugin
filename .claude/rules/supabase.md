---
description: Supabase query patterns for panel
globs: panel/lib/supabase/**/*.ts, panel/lib/queries/**/*.ts
---

# Supabase Queries

- Direct SQL queries via `@supabase/supabase-js` — no ORM, no Prisma
- SSR client: `createClient()` from `lib/supabase/server.ts` (uses Next.js cookies for auth)
- **RLS disabled** on all tables — queries run with anon key, no row-level filtering
- Connection via env vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Query Patterns

- Queries live in `lib/queries/` organized by domain: `dashboard.ts`, `tracks.ts`, `playlists.ts`, `sets.ts`
- Each query function creates its own Supabase client: `const supabase = await createClient()`
- Use Supabase query builder: `.from('table').select('columns').eq('col', val)`
- For joins use select with relations: `.select('*, artists:track_artists(artist:artists(name))')`
- Return typed results — define interfaces in the same query file
- Handle errors: check `error` field, throw or return empty defaults
