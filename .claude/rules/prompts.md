# MCP Prompts (v1)

19 workflow prompts under `app/prompts/` — pure text-builders that chain
the tool surface into reproducible DJ recipes. Catalog + techno-domain
research: `docs/research/2026-06-22-techno-set-construction-and-mcp-prompts.md`.

## Canonical structure

- One prompt per file under `app/prompts/`; file name = prompt name.
  FileSystemProvider auto-discovers (no manual registration).
- Use the standalone `@prompt` decorator from `fastmcp.prompts`. Return a
  `PromptResult(messages=[Message(...)], description=...)` (gives us
  `description` + `meta` version stamping).
- Body is built by a private `_body(...)` helper (f-string). Tags:
  `{"namespace:workflow", "<category>"}`. `meta=PROMPT_META`.
- **Pure text only.** Prompts MUST NOT import repositories, tools,
  providers, DB, or domain — enforced by `import-linter` ("v2 prompts
  must be pure text builders"). They emit instructions the LLM executes
  against `entity_*` / `provider_*` / `compute_*` / `playlist_sync` tools
  and `local://` / `reference://` / `session://` resources.
- Signatures: no `*args`/`**kwargs`; params without defaults are
  required, with defaults optional. Keep types simple (`int`, `str`,
  `bool`, `int | None`).

## Catalog (19)

- Core (6): `dj_expert_session`, `build_set_workflow`,
  `deliver_set_workflow`, `expand_playlist_workflow`, `full_pipeline`,
  `quick_mix_check`.
- Library/analysis (2): `library_health_workflow`,
  `analyze_library_workflow`.
- Set design (5): `harmonic_journey_workflow`,
  `subgenre_journey_workflow`, `scenario_set_workflow`,
  `b2b_planning_workflow`, `extend_set_workflow`.
- Set repair (3): `set_review_workflow`, `fix_transition_workflow`,
  `replace_track_workflow`.
- Discovery/ops (3): `crate_digging_workflow`, `taste_profile_workflow`,
  `playlist_sync_workflow`.

Add a new prompt to `EXPECTED_PROMPTS` (registration test), the `PROMPTS`
tuple + `_render` dispatcher (content test), and the docs counts.

## Content-correctness contract (HARD — pinned by tests)

Every name a prompt body tells the LLM to use MUST resolve to something
the runtime actually exposes. Audit 2026-04-27 + the 2026-06-22 deep
verification found 7 classes of "docs lied about contracts" bugs (each a
runtime hard error when the LLM follows the recipe). `tests/prompts/`
pins all of it — **render the prompt and grep, do not eyeball**:

- **Entity names** (`entity="X"`) ∈ `EntityRegistry.names()` (11 entities)
  — `test_entity_names_are_registered`.
- **Provider read entities** (`provider_read(entity="X")`) ∈
  `YandexAdapter.entities_supported` — `test_provider_entities_match_adapter_surface`.
- **Field presets** (`fields="X"`) declared on that entity — only
  `track_features` has `scoring`; `track` has `id|ref|summary|full`.
- **Filter keys** (`filters={"k": ...}`) ∈ the entity's Pydantic Filter
  schema. Filter schemas are `extra="forbid"` → an unknown key is a hard
  `ValidationError`, not a no-op. Bare keys normalize to `__eq`
  (`{"mood": x}` → `mood__eq`, valid), so use the real lookup suffix for
  anything else (`net_sentiment__lte`, not `__lt`). **`track` /
  `track_features` have NO `playlist_id` column** — resolve the playlist's
  track ids via `local://playlists/{id}?include_tracks=true`, then filter
  `track_id__in` / `id__in`. `test_filter_keys_valid_against_schema`.
- **Create/Update data keys** (`entity_create/update(... data={...})`) ∈
  the Create/Update schema (also `extra="forbid"`). E.g. `track_affinity`
  create accepts only `track_a_id|track_b_id|avg_score` — the count
  columns (`ban_count`, …) are update-only.
  `test_create_update_data_keys_valid_against_schema`.
- **Provider write operations** (`provider_write(entity=X, operation=Y)`)
  ∈ `YandexAdapter.operations_supported` — `playlist` ×
  `{create,rename,set_description,delete,add_tracks,remove_tracks}`,
  `likes` × `{add,remove}`. There is no `create_from_set`; push a set as
  `create` → `add_tracks`. `test_provider_write_operations_match_adapter`.

Also verified (live, non-vacuous) and kept correct when editing:
`entity_aggregate` `field=` ∈ model columns + valid `operation`;
cross-prompt references (`run the X prompt`) ∈ real prompt names;
`provider_search type` ∈ `{tracks,albums,artists,playlists,all}`;
`sequence_optimize` `algorithm` ∈ `{ga,greedy}` and `template` ∈ the 8
real template names; `suggest_next` `energy_direction` ∈ `{up,down,flat}`.

## Honesty about engine limits

Don't promise what the engine can't do: no real stem separation (vocal
detection is spectral proxies), no `FILTER_SWEEP`/`LOOP_ROLL` presets,
downbeat/cue/loop tables are empty, MP3s download only under
`deliver_set_workflow`. See `docs/transition-scoring.md` § Known
Limitations + `docs/audio-schema.md`.
