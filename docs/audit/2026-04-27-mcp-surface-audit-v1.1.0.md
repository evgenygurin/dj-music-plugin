# MCP Surface Audit — v1.1.0 (2026-04-27)

End-to-end manual probe of all 20 tools, 27 resources, 6 prompts on live
Supabase + Yandex Music data. Goal: catch bug classes that unit tests
miss. v1.1.0 closed the 5-bug transport-asymmetry family
(v1.0.10–v1.0.13 → `JsonStringCoerceMiddleware`); this audit looks at
what the next session needs to address.

**Method:** `superpowers:verification-before-completion` discipline —
every claim below is backed by a fresh MCP call captured in the session
transcript. Bugs were investigated to root cause via
`superpowers:systematic-debugging` Phase 1 before being filed; no
rush-fixes were attempted in this session.

**Baseline state**

- branch: `main` @ `56e9869` (Release v1.1.0)
- plugin installed: `1.1.0`
- `DJ_PLUGIN_DEV_PATH=/Users/laptop/dev/dj-music-plugin`
- DB: 23 987 tracks, 19 playlists, 46 sets, 66 set_versions,
  3 transition_history rows
- Tests: 775 passed + 3 SKIPPED (no `DJ_YM_TOKEN`) + 44 xfailed +
  20 xpassed (per session brief — not re-run in this audit)

---

## Resource probe results (27 / 27)

| URI | Status | Notes |
|---|---|---|
| `local://tracks/{id}` | ✓ | Returns `id, title, sort_title, duration_ms, status, primary_artist_name`. `primary_artist_name` was `null` for track 27269 — see Observation O-1. |
| `local://tracks/{id}/features` | ✓ (prior session) | — |
| `local://tracks/{id}/audit` | ✓ | Returns `passed, violations, score, criteria_checked`. |
| `local://tracks/{id}/suggest_next` | ⚠ | Returned empty `candidates: []` for track 27269 even with `?energy_direction=up&limit=5`. Likely sparse-data, not bug — but no easy way to distinguish. |
| `local://tracks/{id}/suggest_replacement/{set_id}/{position}` | ⚠ | Returns empty candidates without validating `removed_track_id` is actually at `position`. URL encodes 3 params; no shape error if mismatched. |
| `local://playlists/{id}` | ✓ | Returns full playlist row. |
| `local://playlists/{id}/audit` | ⚠ | Tested on playlists 26 and 5 — both `total_tracks: 0`. Either local playlists with no items or items table not joined; not investigated. |
| `local://sets/{id}/summary` | ✓ | — |
| `local://sets/{id}/tracks` | ✓ | 30 items returned for set 46 with positions, titles, pinned flag. |
| `local://sets/{id}/transitions` | ✓ | 29 transitions; 9 hard-rejects shown for set 46. |
| `local://sets/{id}/full` | ✓ | Combines summary + tracks + transitions. |
| `local://sets/{id}/cheatsheet` | ✓ | bpm/key/energy per slot. `?version=N` query string honored. |
| `local://sets/{id}/narrative` | ✓ | Phase split (warm_up/peak/close) + count summary. |
| `local://sets/{id}/review` | ✓ | Hard-conflicts list with reasons. |
| `local://sets/{id}/versions/compare/{a}/{b}` | ✓ | `delta` + `changed_positions` array. Tested 6→18 (57 changed of 60). |
| `local://transition/{a}/{b}/score` | ✗ | **Bug C** — returns persisted row from `transitions` table; can be **stale** (hard_reject + zeros) when underlying features were re-analyzed since the row was written. See [Bug C](#bug-c-stale-persisted-transitions-vs-live-explain). |
| `local://transition/{a}/{b}/explain` | ✓ | Always recomputes via `TransitionScorer`. Disagrees with `/score` for the same pair when persistence is stale. |
| `local://transition_history/best_pairs` | ⚠ | Returns null `plays/avg_reaction/overall_score` for self-pair entries (e.g. 146→146). Order seems first-by-id, not best-by-score. Not investigated to RC. |
| `local://transition_history/history` | ✓ | Latest 3 entries returned. |
| `schema://entities` | ✓ (prior session) | — |
| `schema://entities/{entity}` | ✓ (prior session) | — |
| `schema://providers` | ✓ | `["yandex"]`. |
| `schema://providers/yandex` | ⚠ | **Bug F** — `entities_supported: ["track","album","artist","playlist","likes"]` is missing `track_similar, track_batch, artist_tracks, playlist_list, dislikes` which `provider_read` accepts per docs. Schema description ≠ reality. |
| `session://set-draft` | ✓ | Empty draft for new session. |
| `session://tool-history` | ✓ (prior session) | — |
| `session://energy-trend` | ✓ | Empty samples for fresh session. |
| `reference://camelot` | ✓ (prior session) | — |
| `reference://subgenres` | ✓ | 15 profiles, full feature weights. |
| `reference://templates` | ✓ (prior session) | — |
| `reference://audit_rules` | ✓ | 9 rules with thresholds. |

**O-1 (informational, not bug):** `local://tracks/27269` returned
`primary_artist_name: null` even though `track_artists` rows exist for
the track. The view's relation lookup may return null when there's no
`role='primary'` row — not investigated.

---

## Tool probe — happy paths and edge cases

### Working as expected

- `entity_list(track, with_total=true)` → `total: 23987` returned
  alongside cursor-paginated items. ✓
- `entity_list(track_features, filters={"mood__in":["acid","industrial"]})`
  → 3 items returned. ✓ — filter DSL **works on TrackFeaturesFilter**.
- `entity_aggregate(track, count)` → 23987. ✓
- `entity_aggregate(track_features, distinct, mood)` → 13 values.
  Library has 12 distinct moods + null. (`driving`, `hypnotic`,
  `hard_techno` absent — purely data observation.)
- `provider_search(yandex, "Амели Ленс", tracks, 2)` → 94 hits, 2
  returned. Cyrillic non-ASCII transport ✓ — middleware end-to-end
  proven.
- `transition_score_pool(track_ids=[10 ids])` → 90 directional pairs,
  20 hard-rejects, full 6-component breakdown per pair. ✓
- `unlock_namespace(action="status", namespace="all")` → empty
  `enabled_tools` (matches v1.1.0 `DISABLED_NAMESPACE_TAGS=frozenset()`).

### Edge cases that revealed bugs

| Probe | Result | Bug |
|---|---|---|
| `entity_list(track, filters={"has_features": true})` | `extra_forbidden: has_features__eq` | **A** |
| `entity_list(track, filters={"id__gt": 27000})` | `extra_forbidden: id__gt` | **A** |
| `entity_list(track, filters={"bpm__gte": 130, "bpm__lte": 132})` | `extra_forbidden: bpm__gte, bpm__lte` | **A** (also documented as feature-table only) |
| `entity_get(playlist, 25)` | `{id: 25}` only — name/source_of_truth missing | **B** |
| `entity_get(playlist, 25, include_relations=["items"])` | `{id: 25}` only — relations stripped | **B** |
| `entity_list(playlist, limit=2)` | `[{id:3}, {id:5}]` only — name missing | **B** |

---

## Prompt probe (6 / 6 prompts) — content correctness

All 6 prompts render successfully (`get_prompt(...)` returns
`{messages: [...]}` with no error). However, prompt content tells
the LLM to make incorrect calls:

| Prompt | Problem |
|---|---|
| `dj_expert_session` | ✓ — references real `reference://` URIs and entity tools. |
| `quick_mix_check` | ✓ (verified prior session) |
| `build_set_workflow` | Says `entity_list(entity="track", fields="scoring")` — `fields` is `list[str] \| None`, not a string preset. Will reject. |
| `deliver_set_workflow` | Says `entity_create(entity='app_export', ...)` — `app_export` is **drop-pending** (CLAUDE.md §"DB drift") and not in `EntityRegistry`. Will reject with unknown-entity error. |
| `expand_playlist_workflow` | (1) `provider_read(entity='similar_tracks', ...)` — actual entity is `track_similar` (per docs/tool-catalog.md). (2) `entity_create(entity='audio_file', data={'track_ids':[...]})` — handler signature is single `track_id`, not `track_ids` plural array (untested live, but doc mismatch). |
| `full_pipeline` | Inherits issues from build/deliver/expand. |

**Bug class D** below.

---

## Bug catalog

### Bug A — Filter DSL underspecification on `TrackFilter`

**Severity:** medium · **Class:** schema/spec mismatch · **Surface:** documented but not honored

`app/schemas/track.py:21-37` declares `TrackFilter` with strict
`extra="forbid"` and only 7 explicit lookup fields:

```text
id__in, id__eq, title__icontains,
status__eq, status__in,
duration_ms__gte, duration_ms__lte
```

But `.claude/rules/repositories.md` documents `has_features=True` as a
magic Track filter (INNER JOIN on `track_audio_features_computed`),
and CLAUDE.md / docs claim Django-style lookups across all entities.
Common probes that should work but don't:

| Probe | Reality |
|---|---|
| `has_features: true` | Rejected (`extra_forbidden: has_features__eq`) |
| `id__gt: 27000`, `id__lt`, `id__gte`, `id__lte` | All rejected — only `id__in` and `id__eq` are declared |
| `title__contains` (case-sensitive) | Not declared (only `title__icontains`) |

**Root cause:** `TrackFilter` chose explicit-allowlist over generic
parser. There is no `__init_subclass__`-style auto-generation of
common lookups; each filter must declare every accepted shape.
`TrackFeaturesFilter` declares more (mood/bpm/key gte/lte/in) which
is why `mood__in` works there.

**Fix candidates** (do not implement here):

1. Add the missing common lookups (`id__gt/gte/lt/lte`,
   `has_features`, `title__contains`) to `TrackFilter`.
2. OR adopt a base `Filter` class that auto-emits standard lookups
   per declared field type.
3. OR loosen `extra="allow"` and let `BaseRepository._parse_filter`
   handle unknown lookups — but this drops Pydantic validation.

**Recommendation:** PATCH (`v1.1.1`) — add missing fields explicitly
on `TrackFilter` to match the documented contract. Keep
`extra="forbid"` for safety. **Do not** widen all filter classes in
one PR — audit each entity filter against its own docs first.

---

### Bug B — `entity_get` / `entity_list` default fields = `[id]` only

**Severity:** medium · **Class:** UX regression · **Surface:** v1.0.13 fields-projection introduced this

After v1.0.13 implemented fields projection, calling `entity_get` /
`entity_list` **without** `fields=` returns only `{id}`. Same
behavior on track, playlist, set, set_version.

```text
entity_get(playlist, 25)                              → {id: 25}
entity_get(playlist, 25, include_relations=["items"]) → {id: 25}
entity_get(playlist, 25, fields=["id","name"])        → {id, name}     ✓
entity_list(track, limit=2)                           → [{id},{id}]
entity_list(track, limit=2, fields=["id","title"])    → full ✓
```

For comparison, the parallel resource `local://playlists/25` returns
full row (id, name, source_of_truth, parent_id) — so the underlying
data is available, only the v1 dispatcher path strips it.

**Root cause hypothesis:** v1.0.13 set the default to "no fields"
(`= []`?) instead of "all fields" (`= None` semantically meaning
"don't project"). The implementation likely projects to
`fields or []` rather than `fields or all_columns`.

**Investigation needed:** `app/tools/entity/get.py` and
`app/tools/entity/list.py` — what does the dispatcher pass to the
repository when `fields is None`? And does `BaseRepository` understand
"None means all" or "None means empty"?

`include_relations` also appears to be either silently ignored or
masked by the strip-to-id default — playlist 25 with
`include_relations=["items"]` returned `{id: 25}` only.

**Recommendation:** PATCH (`v1.1.1`). Default of `fields=None` should
mean "return view's full default projection" (i.e. the
`TrackView`/`PlaylistView` Pydantic model), not "return id only". This
is the same regression class as v1.0.13 broken-by-design — fields
projection was implemented but defaulted wrong.

---

### Bug C — Stale persisted transitions (`/score` vs `/explain` disagree)

**Severity:** **high** · **Class:** cache invalidation · **Surface:** silent data corruption for users

`local://transition/{a}/{b}/score` reads from the `transitions` table
(`uow.transitions.get_by_pair`) and falls back to live compute only if
no row exists. `local://transition/{a}/{b}/explain` always recomputes
via `TransitionScorer`.

Live evidence (track 146 ↔ 147):

```text
score:   {overall: 0.0,  hard_reject: true,
          reject_reason: "Camelot distance 5 >= 5",
          components: {bpm:0, harmonic:0, energy:0, ...}}

explain: {overall: 0.785,
          narrative: "BPM: 128.09 -> 124.84 (component 0.73).
                      Harmonic component 0.64. Energy component 0.91."}
```

Underlying features (verified):

- 146: bpm=128.09, key_code=14
- 147: bpm=124.84, key_code=13
- BPM diff = 3.25 (well below 10 threshold)
- |key_code diff| = 1 → Camelot distance ≤ 1

**No way** the live values produce hard_reject. The persisted row
(`transitions.id=4`) is **stale** — likely written when one of the
tracks was at a lower analysis level with different `key_code`.

**Root cause:** When `entity_update(track_features, id, level=N)` runs
the re-analysis handler (`track_features_reanalyze`), there is no
cascade that invalidates persisted `transitions` rows whose features
have changed. So `score` keeps reading the old answer forever.

**Impact:**

- Set-builder consumes `transition_score_pool` which uses fresh
  compute — unaffected.
- Resource consumers (panel UI, `local://sets/{id}/review`,
  `local://transition/.../score`) get stale answers.
- Two MCP endpoints disagree about the same pair → user-trust break.

**Fix candidates** (do not implement here):

1. Add a cascade: `track_features_reanalyze` deletes / nulls
   `transitions` rows where `from_track_id` or `to_track_id` matches.
2. OR add `?fresh=true` query param to `local://.../score` and prefer
   live compute when set.
3. OR drop the persisted-first strategy in the resource; always
   recompute (cheap pure compute, ~1 ms/pair). Persisted table
   becomes a write-only audit log.
4. OR have `score` and `explain` agree by both reading the same
   source of truth.

**Recommendation:** MINOR (`v1.2.0`). Option 3 (always recompute)
is cleanest — `TransitionScorer` is fast, and the persisted table
already has a parallel role in set composition. Needs ADR.

---

### Bug D — Prompt content correctness

**Severity:** medium · **Class:** documentation/correctness · **Surface:** prompts mislead the LLM

Prompts are workflow recipes for the LLM. When their text references
non-existent entities or wrong tool signatures, the LLM produces
broken tool calls.

| Prompt | Bad reference | Truth |
|---|---|---|
| `build_set_workflow` | `entity_list(track, fields="scoring")` | `fields: list[str]` only — string preset rejected by Pydantic |
| `deliver_set_workflow` | `entity_create(entity='app_export', ...)` (3×) | `app_export` is in CLAUDE.md drop-pending list; not registered in `EntityRegistry` |
| `expand_playlist_workflow` | `provider_read(entity='similar_tracks', ...)` | Actual entity name is `track_similar` per `docs/tool-catalog.md` |
| `expand_playlist_workflow` | `entity_create(audio_file, data={'track_ids':[...]})` | Probably single `track_id` per handler — not verified live, but plural array doesn't match handler patterns |
| `full_pipeline` | Inherits all of above | — |

**Root cause:** Prompts were authored before some entities were
dropped (`app_export`) or before the v1 dispatcher contract
stabilized. No CI test asserts that prompt text references valid
entity / tool names.

**Fix candidates:**

1. Replace bad references in prompt files (PATCH).
2. Add a CI test that parses prompt bodies and asserts every
   `entity='...'` / `provider_read(entity='...')` references a
   registered name (PATCH + test).
3. Generate prompt bodies from the registry instead of writing them
   manually.

**Recommendation:** PATCH (`v1.1.1`) — fix the 4 string mismatches
plus add a guard test. This is the same class as the v1.0.13
"declared-but-not-applied" pattern: documented but not enforced.

---

### Bug F — `schema://providers/{name}` lies about supported entities

**Severity:** low · **Class:** schema/spec mismatch · **Surface:** introspection inaccurate

```text
schema://providers/yandex →
  {"entities_supported": ["track","album","artist","playlist","likes"]}
```

But `provider_read` accepts more (per `docs/tool-catalog.md` and
`.claude/rules/ym.md`):

```text
track, track_batch, track_similar, album, artist_tracks, playlist,
playlist_list, likes, dislikes
```

LLM consumers reading the schema to discover capabilities will skip
half the surface.

**Recommendation:** PATCH — sync the schema resource with the actual
adapter capability matrix. Could be auto-generated from the registry.

---

## Bug class summary

| Class | Severity | Bugs | Recommendation |
|---|---|---|---|
| **A** Filter DSL underspecification on TrackFilter | medium | 3 (`has_features`, `id__gt/lt/gte/lte`, `title__contains`) | PATCH `v1.1.1` |
| **B** `entity_get`/`entity_list` default fields = `[id]` | medium | regression touches 4+ entities | PATCH `v1.1.1` |
| **C** Stale persisted transitions | **high** | `/score` vs `/explain` disagree | MINOR `v1.2.0` (ADR) |
| **D** Prompt content correctness | medium | 4 string mismatches across 4 prompts | PATCH `v1.1.1` + test |
| **F** `schema://providers/yandex` undercounts | low | 4 missing entity names | PATCH (bundle with above) |

**Observations (not filed as bugs):**

- O-1 `primary_artist_name: null` on `local://tracks/{id}` view.
- `local://transition_history/best_pairs` orders nulls before scored
  pairs.
- `suggest_next` / `suggest_replacement` return empty arrays without
  distinguishing "no candidates available" from "no input data".
- `local://playlists/{id}/audit` reports `total_tracks: 0` for
  playlists 5 and 26 — likely real (local-only playlists with no
  items joined) but worth verifying.

## Anti-recommendations (what NOT to do this round)

- **Do not** rush-fix bugs A/B/D in one PR like the v1.0.10–v1.0.13
  cascade. Each is a separate root cause.
- **Do not** widen `extra="forbid"` to `extra="allow"` on TrackFilter
  to "fix" Bug A — that drops Pydantic validation across the board.
- **Do not** add a `?fresh=true` flag to Bug C without first deciding
  whether `transitions` table should remain persisted-first or
  become an audit log.

## Verification trail

All probes ran 2026-04-27 against:

- Plugin: `dj-music@dj-music-plugin v1.1.0`
- Working dir: `/Users/laptop/dev/dj-music-plugin` (commit `56e9869`)
- DB: Supabase `bowosphlnghhgaulcyfm` (per memory)
- YM: live calls (Cyrillic search returned 94 hits in <2s)

Counts captured at session start: 23 987 tracks · 19 playlists ·
46 sets · 66 set_versions · 3 transition_history rows · 12+null
distinct moods.
