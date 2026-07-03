# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.6.1] - 2026-07-03

**MCP `entity_*` hardening.** A systematic probe of the six entity
dispatchers plus the transition resources surfaced several
false-advertised contracts and a masked DB error; all fixed and pinned
by tests. No tool/resource surface change.

### Fixed
- **`entity_get.include_relations` actually loads relations.** The parameter
  was validated against `EntityConfig.relations` but never used — the response
  `data` silently omitted the relation payload (false-advertised contract).
  Each declared relation now has a loader (`EntityConfig.relation_loaders`,
  wired in `app/registry/defaults.py`) and the payload is attached under the
  relation name after `fields` projection. Supported: track ×
  `artists|features`, playlist × `items`, set × `versions`, set_version ×
  `items`, audio_file × `beatgrids`.
- `build_set_workflow` prompt step 1 recommended
  `entity_list(..., include_relations=["tracks"])` — a parameter `entity_list`
  doesn't have and a relation `playlist` doesn't declare. Now
  `entity_get(entity="playlist", id=..., include_relations=["items"])`.
- **`local://transition/{a}/{b}/score` and `/explain` double-converted features.**
  `get_scoring_features_batch` already returns `TrackFeatures`, but the resource
  ran `TrackFeatures.from_db()` on them a second time, silently dropping
  `energy_bands` (rebuilt from `energy_sub`/… columns absent on the dataclass)
  and zeroing the bass-band term of `S_bass`. The same pair scored 0.784 via
  `transition_score_pool` but 0.7725 via the resource; both paths now agree.
- **`entity_aggregate` sum/avg/min_max leaked a masked DB error on boolean
  columns.** `bool` subclasses `int` in Python, so a Boolean column passed the
  numeric gate and died in Postgres (`sum(boolean) does not exist`); `min_max`
  had no gate at all. All three now raise a typed `ValidationError`; min/max
  over strings/dates stays allowed.
- **`entity_list(search=…)` was a silent no-op on non-searchable entities.**
  `track_features`, `transition`, `transition_history`, `track_feedback`,
  `track_affinity` declare no searchable fields and ignored the term, returning
  the full unfiltered list. Now raises a typed `ValidationError`.
- **`track_affinity` self-pairs forbidden at the DB level.** The pydantic gate
  rejected `track_a_id == track_b_id`, but a raw insert bypassed it and one
  degenerate row survived in prod. Added `ck_affinity_distinct_pair` + a SQL
  migration (`migrations/2026-07-03_affinity_distinct_pair.sql`) that deletes
  survivors before applying the CHECK. **Apply to Supabase manually** — not yet
  run against prod.
- MCP launcher (`.mcp.json`) now sources the project `.env` with `set -a`
  instead of `uv run --env-file`, which does not override variables already
  present in the environment — a stale `DJ_DATABASE_URL` inherited from the
  client process silently beat the fresh `.env`.

### Added
- **`__isnull` lookups for NULL-heavy `track_features` columns** (`key_code`,
  `bpm_confidence`, `true_peak_db`, `danceability`, `dynamic_complexity`,
  `spectral_complexity_mean`, `pitch_salience_mean`) — the only way to find
  not-yet-analyzed tracks (`__gte`/`__lte` silently drop NULL rows). The
  documented `key_code__isnull` example previously raised `ValidationError`.

## [1.6.0] - 2026-06-23

**Transition-scoring correctness + audio-feature research.** A deep audit of
every `track_audio_features_computed` column against the live library's real
distributions, turned into scoring fixes, a per-feature reference, and
prompt/rule improvements. No MCP tool/resource surface change.

### Added
- `docs/research/2026-06-23-track-feature-reference-and-set-construction.md` —
  per-feature DJ reference (with measured signal-quality grades) + advanced
  set-construction playbook v2.
- `hard_reject_key_confidence_floor` setting (default 0.5) — the Camelot reject
  now requires reliable tonal content on both sides.
- Diagnostic tooling: `scripts/diag_mood_classifier.py`,
  `scripts/reclassify_moods.py`.

### Changed
- **Camelot is now key-reliability-aware — both the hard reject AND the soft
  `S_bass`/`S_harmonic` term.** Atonal / low-confidence keys (98.7% of this
  library is atonal) no longer false-reject or carry a meaningless key penalty;
  they fall back to neutral. Implemented on the scalar and vectorised paths
  (parity-tested).
- Unified the live Camelot base tables into `weights.py`
  (`CAMELOT_HARMONIC_BASE` / `CAMELOT_BASS_BASE`) as the single source for both
  scorers; annotated dead/reference-only constants in `weights.py` and
  `config/transition.py`.
- Mood catch-all penalty `0.85` → `0.97` so `driving` is reachable again
  (the old value zeroed it across the library in the classifier's low-margin
  regime). The `dj_expert_session` prompt now primes feature-first curation.

### Fixed
- `chroma_entropy` proximity scale (`/3.0` → `/1.0`) in the vocals-stem compat —
  the [0,1]-normalized feature was divided by the old raw-bits scale.
- `beat_loudness_band_ratio` now populates at L5 — the analyzer inherited the
  full-track clip while `beat` produced beat_times on the 60s stitched clip;
  pinned `clip_duration_s=60.0`.

## [1.5.2] - 2026-06-22

**Fix: green `make check` on a fresh resolve.** A fresh dependency
resolution pulled the newest upstreams, two of which broke the build/test
gate. No runtime surface change.

### Fixed
- **fastmcp pinned `<3.4`.** The 3.4.x `_run_middleware` refactor renamed
  the chain wrapper's first parameter to `ctx`, but the built-in
  `ResponseCachingMiddleware` still calls `call_next(context=...)` by
  keyword — every client tool/prompt call through the middleware chain
  raised `TypeError` (5 client/e2e tests failed). 3.3.x uses the
  `partial(mw, call_next=chain)` runner that accepts the keyword. Pin
  capped at `>=3.2.4,<3.4` until upstream fixes the regression.
- **essentia pinned to `==2.1b6.dev1389`.** The latest dev build (dev1438)
  dropped cp310–313 wheels and ships cp314 only, so `>=dev1389` resolved to
  a build with no CPython 3.12 wheel and `uv sync --all-extras` failed.
  dev1389 has manylinux + macOS cp312 wheels.
- **Deterministic mypy on optional imports.** `observability.py` and
  `sentry_context.py` guarded their optional `sentry_sdk` import under
  `if TYPE_CHECKING:` so mypy no longer flips between "Success" (extra
  absent) and an `Incompatible types in assignment` error (extra present
  via `--all-extras`).
- Removed the stale `demucs.*` entry from the mypy `ignore_missing_imports`
  override (StemSeparator is unimplemented / never imported) — silences the
  `unused section(s)` mypy note.

## [1.5.1] - 2026-06-22

**Fix: MCP server startup env var mismatch.** `fastmcp.json`
`deployment.env` interpolated the connection string under `DJ_DB_URL`,
but `app/config/database.py` reads `DJ_DATABASE_URL` (`env_prefix="DJ_"`
+ field `database_url`). The mismatch silently dropped the configured
Supabase URL, falling back to the default in-memory SQLite — the MCP
server appeared to start but had no live data.

### Fixed
- `fastmcp.json` `deployment.env`: `DJ_DB_URL` → `DJ_DATABASE_URL` so the
  interpolated value reaches the name `DatabaseSettings` actually reads.
- Corrected stale `DJ_DB_URL` references in `CHANGELOG.md` (1.4.x Added
  note) and `docs/superpowers/plans/2026-04-18-surface-redesign-v2-phase1.md`.

## [1.5.0] - 2026-06-22

**Workflow prompt catalog 6 → 19 + deep techno research.** Additive
release — no tool / resource surface change. 13 new research-backed
FastMCP prompts cover the full DJ lifecycle; a live-server verification
pass found and fixed 7 classes of prompt content-contract bugs and pinned
them with new guard tests. The broken GitHub Actions CI workflow was
removed (Actions disabled at the account level).

### Fixed — prompt filter/data contract bugs (manual verification pass)

- Live-server verification of the prompt catalog surfaced filter/data keys
  that would raise a hard `ValidationError` (Filter/Create schemas declare
  `extra="forbid"`):
  - `playlist_id` used as a filter on `track` / `track_features` (no such
    column) in `library_health`, `analyze_library`, `harmonic_journey`,
    `subgenre_journey`, `scenario_set`, `b2b_planning` — rewritten to the
    canonical "resolve playlist track ids via
    `local://playlists/{id}?include_tracks=true`, then `track_id__in` /
    `id__in`" pattern.
  - `net_sentiment__lt` (only `__lte` exists) on `track_affinity` in
    `taste_profile`, `crate_digging` → `net_sentiment__lte`.
  - `track_affinity` create with `ban_count` (create accepts only
    track_a_id/track_b_id/avg_score) in `taste_profile` → create minimal,
    then `entity_update` the count column.
  - Pre-existing: `expand_playlist_workflow` filtered `track_feedback` by
    `{'banned': True}` (no such field) → `{"status": "banned"}`.
- New guard tests pin the contract going forward:
  `test_filter_keys_valid_against_schema` and
  `test_create_update_data_keys_valid_against_schema` validate every
  `filters={...}` / `data={...}` key in every prompt against the live
  Pydantic Filter/Create/Update schemas (29 filter + 52 create + 4 update
  keys across 19 prompts).
- Pre-existing: `deliver_set_workflow` told the LLM to call
  `provider_write(entity='playlist', operation='create_from_set')` — the
  adapter raises `ValueError('unknown playlist operation: create_from_set')`.
  Rewritten to the real two-step `create` → `add_tracks` sequence.
  `YandexAdapter.operations_supported` (new ClassVar, mirrors the `match`
  arms) is now the source of truth, pinned by a new
  `test_provider_write_operations_match_adapter` guard.
- Deeper live-server verification (non-vacuous) also confirmed valid:
  every `entity_aggregate` field is a real model column (8 refs),
  every cross-prompt reference resolves (14 refs / 9 prompts),
  `provider_search` types, `sequence_optimize` algorithm/template, and
  `suggest_next` energy_direction values.

### Added — workflow prompt catalog (6 → 19)

- **13 new FastMCP workflow prompts** under `app/prompts/` (additive — no
  tool / resource surface change). Each is a pure text-builder returning
  `fastmcp.prompts.PromptResult`, chaining the existing tool surface:
  - Library & analysis: `library_health_workflow`, `analyze_library_workflow`.
  - Set design: `harmonic_journey_workflow`, `subgenre_journey_workflow`,
    `scenario_set_workflow` (warmup/peak/closing/roller/wave/progressive),
    `b2b_planning_workflow`, `extend_set_workflow`.
  - Set repair: `set_review_workflow`, `fix_transition_workflow`,
    `replace_track_workflow`.
  - Discovery & ops: `crate_digging_workflow`, `taste_profile_workflow`,
    `playlist_sync_workflow`.
- `docs/research/2026-06-22-techno-set-construction-and-mcp-prompts.md` —
  deep research on techno subgenres, set-construction canon, DJ-school
  techniques, DB→domain mapping, FastMCP v3 prompt best practices, and the
  prompt-catalog design rationale.
- `tests/prompts/test_prompt_content_correctness.py` +
  `test_prompt_registration.py` extended to pin all 19 prompts (entity /
  provider / field-preset names validated against the live runtime).

### Changed

- Docs prompt counts updated 6 → 19 (`CLAUDE.md`, `docs/tool-catalog.md`,
  `docs/architecture.md`, `docs/structure.md`, `README.md`).
- New `.claude/rules/prompts.md` — canonical prompt-authoring rules + the
  full content-correctness contract (entity / provider / field-preset /
  filter-key / data-key / provider_write-op validation). Referenced from
  CLAUDE.md "FastMCP v3 правила".
- `docs/ym-api-guide.md` + `.claude/rules/ym.md` document the
  `YandexAdapter.operations_supported` provider-write matrix (no
  `create_from_set`).
- `app/__init__.__version__` synced `0.8.0` → `1.5.0` (was stale) so the
  `version` stamp in `PROMPT_META` / `RESOURCE_META` matches the release.

### Removed

- `.github/workflows/ci.yml` — GitHub Actions are disabled for this repo at
  the account level (billing lock): every run failed in 2-8s without a
  runner, producing a false red status on every PR. Quality is gated locally
  by `make check` + the `hooks/pre-push` hook. CLAUDE.md now forbids
  recreating any CI workflow ("⛔ НЕ создавать CI").

## [1.4.1] - 2026-05-13

**Phase 0 golden baseline for the v1.5.0 transition architecture refactor.** Tests-only, docs-only patch release: zero production code touched. Establishes the behavioural contract that every Phase 1-7 PR (Strategy / Composite / CoR / Template Method / Registry decomposition under `app/domain/transition/`) must satisfy. See [design spec](docs/superpowers/specs/2026-05-13-transition-architecture-refactor-design.md) (1 068 lines, 14 sections) and [implementation plan](docs/superpowers/plans/2026-05-13-transition-architecture-refactor.md) (3 146 lines, 8 phases, ~70 tasks).

### Added — Phase 0 (PR #224)

- `docs/superpowers/specs/2026-05-13-transition-architecture-refactor-design.md` — design spec for the v1.5.0 architecture refactor. 21 names of `app.domain.transition.__all__` frozen; 5 GoF patterns (Strategy / Composite / Chain of Responsibility / Template Method / Registry); scalar + bulk scoring co-located per component.
- `docs/superpowers/plans/2026-05-13-transition-architecture-refactor.md` — TDD-ready implementation plan with memory anchors and phase gates.
- `tests/domain/transition/_golden_harness.py` — tolerance-aware JSON snapshot helpers (1e-9 for component fields, 1e-7 for `overall`; exact for booleans / strings / enums).
- `tests/domain/transition/test_golden_scoring.py` — **Level 1** scoring math snapshots, 20 scenarios covering all four `TransitionIntent` values, all five `SectionPairClass` overlays, three hard-reject types, missing-field defensive paths, two asymmetric pairs, and the v1.4.0 acid-pair Phase-0 regression case.
- `tests/domain/transition/test_golden_recipes.py` — **Level 2** recipe envelopes, 21 scenarios (7 `NeuralMixTransition` presets × bars ∈ {16, 32, 64}). Per-keyframe + per-fx-event snapshots.
- `tests/domain/transition/test_golden_picker.py` — **Level 3** picker decisions, 14 scenarios covering all 7 rule branches (`hard_reject_rescue` / `drum_only_section` × 3 / `vocal_active` × 3 / `harmonic_sustain` / `energy_drop_to_slam` × 2 / `ambient_or_cooldown` / `cool_down_intent` / `default_safe` + acid pair).
- `tests/domain/transition/test_public_api_freeze.py` — assertion that `app.domain.transition.__all__` remains a superset of the v1.4.0 frozen set (21 names). Removals are breaking; additions allowed.
- `tests/domain/transition/_golden/*.json` — 55 frozen snapshot fixtures.

### Changed — Phase 0

- `tests/domain/transition/test_bulk_scorer_parity.py` — extended with 20 cases (4 intents × 5 SectionPairClass values) documenting the current v1.4.0 asymmetry: the bulk path in `bulk_scorer.score_pairs_bulk` does NOT yet apply the section_context overlay (added scalar-side in PR #219), so bulk overall always matches scalar overall WITHOUT context regardless of the ctx parameter. Phase 3 will wire bulk into `CompositeScorer` and strengthen this guard.

### Test totals

- Baseline: 240 passed + 1 xfailed in `tests/domain/transition/`.
- After Phase 0: 318 passed + 1 xfailed (+78: 20 scoring + 21 recipe + 14 picker + 20 bulk-context + 3 API-freeze).

## [1.4.0] - 2026-05-13

**Transition scoring v2 — Phase 0 + Phase 1.** First two phases of the [v2 refactor roadmap](docs/transitions-refactor.md): fixes the acid-techno false-positive in the vocal-detection heuristic (Phase 0, PR #218) and wires `section_context` end-to-end through schema → handler → scorer → picker, applying a multiplicative weight overlay for DRUM_ONLY (outro↔intro) pairs (Phase 1, PR #219). Together: picker now produces **real preset variety** (drum_swap / drum_cut / fade) for techno sets that previously collapsed to monotone `vocal_cut` (acid mis-classification) or monotone `echo_out` (no section context).

### Added — Phase 0 (PR #218)

- `app/domain/transition/picker.py` — new gate `_VOCAL_PRESENCE_MIDBAND_RATIO = 0.40` on `energy_bands` distribution. Vocal detection now requires **three** spectral proxies: `pitch_salience_mean > 0.55` AND `spectral_centroid_hz > 2200 Hz` AND `(energy_bands[lowmid] + energy_bands[mid]) / sum(bands) > 0.40` (when band data available). Acid TB-303-style leads (high pitch_salience + high centroid but energy concentrated in highmid) no longer trip vocal-active rule.
- 5 regression tests in `tests/domain/transition/test_picker.py` covering acid false-positive, real vocal positive case, pitch_salience boundary (0.54 below 0.55 threshold), legacy `energy_bands=None` 2-signal fallback, and defensive `len < 6` malformed-bands guard.
- `docs/transition-scoring.md` § Known Limitations — 3-signal heuristic explained, what the proxy cannot distinguish, forward reference to Phase 3 demucs path.
- `docs/audio-pipeline.md` § Gotchas — `pitch_salience_mean` semantics clarified as proxy for "harmonic presence", not vocal-specific.

### Changed — Phase 0

- `_VOCAL_PRESENCE_PITCH_SALIENCE` raised from `0.4` → `0.55`. Combined with the new midband gate, eliminates the most common acid false-positive without rejecting real vocal tracks.
- `picker.py` module docstring updated to describe the 3-signal vocal heuristic.

### Added — Phase 1 (PR #219)

- `SectionPairClass` StrEnum in `app/domain/transition/section_context.py` with 5 buckets: `DRUM_ONLY`, `DROP_TO_DROP`, `BREAKDOWN_OUT`, `BUILDUP_IN`, `GENERIC`.
- `SectionContext.section_pair_class` cached property classifying an (out, in) section pair into one of the 5 buckets.
- `TransitionScore.section_pair_class: str | None` field — surfaces the resolved pair class when scoring with a `SectionContext`.
- `SECTION_PAIR_OVERLAY` table in `app/domain/transition/weights.py` — multiplicative modifiers per pair class. Phase 1 ships DRUM_ONLY active (`drums×1.30`, `bass×0.70`, `harmonics×0.40`, `vocals×0.30`, `bpm×1.10`, `energy×0.95`); the four other classes carry identity overlays for now (Phase 3 calibrates).
- `SectionContextDTO` Pydantic schema in `app/schemas/transition.py`. `TransitionCreate.section_context: SectionContextDTO | None` accepts `{from_section, to_section}` where each is a `SectionType` enum name (`"OUTRO"`), integer value (`7`), or null.
- `transition_persist_handler` resolves the DTO into a `SectionContext` via new `_resolve_section_context()` helper and passes it to both `scorer.score()` and `_build_recipe_or_none()`. Handler response surfaces `section_pair_class` so callers can see which overlay applied.
- 6 new tests in `tests/domain/transition/test_scorer.py` (no-context regression, drum_only overlay raises overall, pair class field population, renormalisation invariant, …) + 19 tests in `tests/domain/transition/test_section_context.py` covering all 5 pair classes + None handling + cached_property identity.
- `docs/transitions-refactor.md` — full v2 ADR + design spec + 7-phase migration plan + risks + 12 sources (Algoriddim, Mosaikbox ISMIR 2024, Hybrid Demucs, EDMFormer, Rekordbox 7, Serato Stems Pro 3.0, Mixxx 2.5.4 ONNX).
- `docs/research/2026-05-13-neural-mix-transitions-deep-dive.md` — research note that produced the ADR.

### Changed — Phase 1

- `TransitionScorer.score()` removes the `del section_context` stub and actually consumes the context: per-intent base weights are multiplied component-wise by the appropriate `SECTION_PAIR_OVERLAY` row and renormalised to sum to 1.0. Same applies to `score_all_intents()` and `score_with_candidates()`.
- Legacy callers (no `section_context` kwarg) get byte-identical behaviour to v1.3 — regression test `test_scorer_without_section_context_unchanged` is the primary guard.
- `is_drum_only_pair` kept as legacy property on `SectionContext` — wraps the new `section_pair_class == DRUM_ONLY` so `picker.py` callers continue to work without modification.

### Tests

- `make check`: **1359 passed**, 3 skipped, 44 xfailed, 20 xpassed.
- `tests/domain/transition/test_picker.py`: 24/24 green (existing + 5 Phase 0 new).
- `tests/domain/transition/test_scorer.py`: 6/6 green (Phase 1 new).
- `tests/domain/transition/test_section_context.py`: 25/25 green (6 pre-existing + 19 Phase 1 new).
- Bulk scorer parity preserved (`test_bulk_scorer_parity.py` stays green — bulk path runs no-overlay until Phase 3 wires `section_contexts` kwarg).

### Smoke verification

- Real acid pair 173→177 (Byakuya→Transmission, Nina Kraviz set):
  - no context → `echo_out` ✅ (Phase 0: acid no longer routes to vocal_cut)
  - DRUM_ONLY (OUTRO→INTRO) → **`drum_swap`** ✅ (Phase 1: drums-priority routing), overall 0.8959 → 0.9026
  - DROP_TO_DROP → identity overlay (Phase 3 calibrates), but class surfaced as `"drop_to_drop"`
- Full re-score of 43-track Nina Kraviz set with DRUM_ONLY context: **6 drum_swap / 35 drum_cut / 1 fade**, mean 0.78 (vs prior monotone collapse).
- 27-track Trip-Style Acid Roller v2 (Camelot diamond 7A/7B/8A/9A): **17 drum_swap / 9 drum_cut / 0 fade**, mean **0.83**, bass scores 0.87-1.00 (zero clash physically possible at dist ≤ 2).

### Notes

- **Out of scope for v1.4.0** (deferred to Phase 2-7 in the [ADR](docs/transitions-refactor.md)): `S_phrase` + `S_structure` scoring components, full 5-class overlay calibration, Tonnetz-primary harmonic refactor, explicit bass clash gate in `hard_constraints.py`, declarative picker rule table, `FILTER_SWEEP` 8th preset, demucs L4 stem precompute, taxonomy unification of `STEM_SUSTAIN`/`STEM_CUT`.
- MCP tool surface unchanged: 20 tools / 27 resources / 6 prompts / 11 registered entities.
- `TransitionCreate` schema gained an optional `section_context` field — backwards compat (default `None`). Legacy callers see no behaviour change.
- For GitHub-marketplace users: `claude plugin marketplace update dj-music-plugin && claude plugin update dj-music@dj-music-plugin` picks it up.

## [1.3.8] - 2026-05-13

**Docs-only release.** Brings GitHub-marketplace consumers up to the documentation surface produced in #215 (CHANGELOG backfill) and #216 (full v1.3.7 md sweep). No code, no MCP surface, no behaviour changes vs. v1.3.7 — installing from `@v1.3.7` would have given users an MCP-runtime equivalent to 1.3.7 but with stale docs claiming "13 dispatchers", missing v1.3.7 specifics (FK gate, validation gates, `safe_info` wrappers, SQLite PRAGMA, AggregateResult bool fix), and missing the v1.3.7 CHANGELOG entry. This tag fixes that drift.

### Changed
- All 20 documentation files (4 `agents/`, 5 `skills/**/SKILL.md`, 3 `commands/`, 11 `docs/` top-level, 7 `.claude/rules/`, `README.md`, `CLAUDE.md`) synchronized to v1.3.7 surface state. Stale "13 dispatchers" claim replaced with "20 tools (14 core + 6 UI Prefab)" across 7 files. Transition formula weights in `agents/dj-assistant.md` aligned with `docs/transition-scoring.md` (0.20/0.15/0.15/0.15/0.20/0.15). FK gate (`app/tools/entity/_fk_gate.py`), `safe_info`/`safe_report_progress` wrappers (`app/handlers/_context_log.py`), SQLite `PRAGMA foreign_keys=ON` event listener, `DomainErrorMiddleware` resource+prompt envelope wrap, `AggregateResult` bool-before-int union, validation gates, cursor non-unique sort guard, `provider_read.id int|str`, `track_batch` legacy `ids` alias, `wave.Error` → typed `RuntimeError` — all documented across rules/docs.
- Bug fixes in 5 `SKILL.md`: `entity_aggregate operation="group_by"` (invalid op) → `operation="count" + group_by="X"` (curate-library); `pinned_track_ids` misattributed to `entity_create(set_version)` → split into `sequence_optimize(pinned, excluded)` → `entity_create(set_version, data={track_order})` (build-set); `external_id__in` filter on `track` (column doesn't exist) → documented via `external_ids` relation (expand-playlist); locked-namespace wording softened to reflect v1.3.7 `DISABLED_NAMESPACE_TAGS=frozenset()` (ym-sync).
- All 5 `SKILL.md` descriptions: `"Use when..."` → `"This skill should be used when..."` per `plugin-dev:skill-development` (third-person required for correct triggering).
- `.claude/agents/bg-jobs-watcher.md`: non-existent `get_library_stats` tool → `entity_aggregate` examples. `panel-doctor.md`: removed references to deferred `/api/tools/{name}/schema` endpoint.

### Added
- `docs/dev-mode.md`: new sections "Claude Code CLI tools для plugin dev" (`claude plugin validate`, `--plugin-dir`, `--debug filter`, `claude doctor`, `/plugin → Errors tab`) and "Платформенные ограничения" (Cursor SessionStart skip, Windows-bash hooks, `$schema` validator reject, marketplace remove cascade).
- `README.md`: session-only `--plugin-dir` install option + `claude plugin validate` pre-PR check.
- `.claude/rules/git.md`: post-tag user-side `claude plugin marketplace update` + `claude plugin update` step in release checklist.
- `CLAUDE.md`: one-line reference to `Skill(dj-music:reload-plugin)` under Plugin cache block.
- `chore(ruff)`: `F401 / F811 / F841` added to `[tool.ruff.lint] unfixable` to prevent PostToolUse hook from auto-deleting unused imports between multi-step edits (was a recurring agent-loop pain point).

### Tests
- 1323 passed, 0 failed (unchanged from v1.3.7 — no code changes).
- `ruff` / `mypy` / `import-linter` all green.

### Notes
- MCP tool surface unchanged: 20 tools / 27 resources / 6 prompts / 11 registered entities.
- For users already on `@v1.3.7` via directory-source or `DJ_PLUGIN_DEV_PATH`: this release is a no-op (you already see updated docs from main). For GitHub-marketplace users: `claude plugin marketplace update dj-music-plugin && claude plugin update dj-music@dj-music-plugin` picks it up.

## [1.3.7] - 2026-05-13

**Manual MCP hardening + systemic FK gate refactor.** Outcome of ~11 rounds of manual MCP testing through the in-memory FastMCP client and the REST proxy (curl). Each round picked a fresh angle — entity CRUD edges, build-a-set workflow, FK gates, resource templates, pagination, provider tools — and fixed every issue surfaced before the next round. After per-entity FK gates accreted across rounds 4–10, the final commit collapses them into a single source-of-truth design driven by SQLAlchemy ORM metadata. **28 distinct bug classes fixed, ~70 regression tests added.** Substance: #213 (squashed to ``d8ff1fc``). Version bump: #214 (squashed to ``0f62b27``). Full notes in the [v1.3.7 GitHub Release](https://github.com/evgenygurin/dj-music-plugin/releases/tag/v1.3.7).

### Added
- ``app/db/session.py`` — ``connect`` event listener issuing ``PRAGMA foreign_keys=ON`` on every aiosqlite connection. Erases the prod-on-Supabase-Postgres / dev-on-SQLite FK-enforcement drift that hid orphan-row bugs through 9 rounds of testing.
- ``app/tools/entity/_fk_gate.py`` — ``validate_fk_constraints(uow, config, validated, partial_keys=...)``. ``EntityConfig.fk_constraints`` is auto-derived from ``cls.__table__.foreign_keys`` ∩ Create/Update schema fields at ``register_default_entities()`` time. ``_HANDLER_ONLY_FKS`` overrides cover handler-only fields not present as columns (e.g. ``TrackCreate.playlist_id``).
- ``app/handlers/_context_log.py`` — ``safe_info(ctx, …)`` and ``safe_report_progress(ctx, …)`` wrappers. ``ctx.info()`` / ``ctx.report_progress()`` require an active MCP session, which doesn't exist behind the REST proxy; wrappers fall back to stdlib logger so successful builds aren't misreported as failures.
- ~70 regression tests across ``tests/handlers/``, ``tests/repositories/``, ``tests/resources/``, ``tests/server/middleware/``, ``tests/tools/admin/``, ``tests/tools/compute/``, ``tests/tools/entity/``, ``tests/tools/provider/``, ``tests/tools/sync/``, ``tests/tools/ui/``.

### Changed
- ``DomainErrorMiddleware`` wraps **resource** + **prompt** envelopes too (``on_read_resource`` / ``on_get_prompt``), not just tools. Catches ``fastmcp.exceptions.NotFoundError`` distinctly so ``Unknown prompt: 'bogus'`` surfaces as ``"not found: …"`` instead of ``"internal error: …"``.
- ``entity_create`` / ``entity_update`` translate raw ``pydantic.ValidationError`` into typed ``app.shared.errors.ValidationError("invalid payload for entity 'X': …")`` so production (``mask_details=True``) no longer collapses to a blank ``"internal error"``.
- ``AggregateResult.value`` union now includes ``bool`` BEFORE ``int`` — ``distinct(variable_tempo)`` was returning ``[0]`` instead of ``[false]`` because Pydantic v2 picked ``int`` first (``bool`` is an ``int`` subclass), inconsistent with the ``group_by`` branch.
- ``provider_read.id`` accepts ``int`` (YM track IDs are naturally numeric; was rejected by Pydantic strict). ``YandexAdapter.read("track_batch", …)`` accepts both canonical ``track_ids`` and legacy ``ids``; numeric IDs are stringified before the YM client.
- ``BaseRepository.filter`` refuses to emit ``next_cursor`` when the first sort field is non-unique, and rejects an incoming ``cursor`` on a non-unique sort with a clear message — was silently dropping rows that shared the boundary value with the last seen row.
- 5 handlers (``track_import``, ``track_features_{analyze,reanalyze}``, ``audio_file_download``, ``set_version_build``) switched from ``ctx.info()`` / ``ctx.report_progress()`` to the ``safe_*`` wrappers.
- ``playlist_sync`` uses ``uow.playlists.get_track_ids()`` instead of accessing ``pl.items`` (lazy-load triggered ``greenlet_spawn has not been called`` in async sessions).
- ``unlock_namespace`` accepts ``"ui:read"`` (was advertised in ``app/server/visibility.py`` but missing from the ``Literal``).
- Removed 5 piecemeal per-entity FK branches from ``entity_create`` / ``entity_update`` (added across rounds 4–10 and now collapsed into ``_fk_gate``).

### Fixed
- **Silent typos / orphan args validation gates.** ``entity_get.include_relations`` rejects typos against ``config.relations.keys()`` (was silently dropped). ``local://tracks/{id}/suggest_next?energy_direction=…`` rejected against ``{up, down, flat, None}``. ``transition.scoring_profile`` (``entity_create``) validated against ``uow.scoring_profiles.get_by_name``. ``transition.fx_type`` (``entity_update``) validated against the seven ``NeuralMixTransition`` enum members. ``transition.persist=false`` now actually honored by the handler (was a dead parameter). ``sequence_optimize`` rejects ``pinned`` ids not in pool and ``excluded`` covering the entire pool. ``ui_score_pool_matrix`` rejects duplicate ids. ``ui_transition_score`` rejects ``from == to``. ``entity_update set`` enforces cross-row BPM-range invariant on partial updates (``min`` alone vs existing ``max`` and vice versa).
- ``local://transition/{a}/{b}/score`` names the actually-missing id instead of the ambiguous ``"X or Y"``.
- ``provider_write`` missing-param errors are typed ``ValidationError`` listing the missing keys (was a bare ``KeyError('title')`` → wire message ``"'title'"``).
- ``set_version_build`` checks ``track_order`` FK references up-front in ``SetVersionRepository.create_items`` (FK gate before bulk insert).
- ``app/audio/core/loader.py`` wraps the ``wave.Error`` fallback so non-WAV inputs without ``soundfile`` / ``librosa`` installed get a clear ``RuntimeError("audio decode failed: …")`` instead of ``wave.Error("file does not start with RIFF id")``.

### Tests
- 1262 → **1323 passed, 0 failed** (+~70 regression tests covering every closed bug class).
- ``make check`` clean (ruff, mypy on changed files, import-linter 5 kept / 0 broken, pytest ``-n auto``).
- Manual curl verification of all 28 bug classes end-to-end via REST API — **38/38 assertions pass**.

### Notes
- No MCP tool surface changes: 20 tools / 27 resources / 6 prompts / 11 registered entities unchanged from v1.3.6.
- Tooling used: ``rg`` for cross-cutting FK inventory, ``sg`` (ast-grep) for AST-precise ``ForeignKey($STRING)`` enumeration across ``app/models/*``, ``jq`` / ``yq`` for metadata + config inspection.

## [1.3.6] - 2026-05-07

**Silence basedpyright `reportMissingImports` on the optional `prefect` flow.** ``flows/dj_health_check.py`` is deployed via Prefect Cloud (``uvx prefect-cloud deploy …``); Prefect installs its own runtime remotely, so ``prefect`` is intentionally absent from the local ``pyproject.toml``. A one-line ``# pyright: ignore[reportMissingImports]`` keeps the basedpyright IDE noise away without dragging Prefect into the local virtualenv.

### Changed
- ``flows/dj_health_check.py:23`` — annotated the ``from prefect import …`` line with ``# pyright: ignore[reportMissingImports]``.

### Notes
- ``make check`` unaffected — its mypy run targets ``app/`` only; ``flows/`` is out-of-scope (mypy on the file still reports the missing module, which is by design).
- ``ruff`` on ``flows/`` stays clean.
- No behaviour change; v1 dispatcher surface and tool catalog unchanged from v1.3.5.

## [1.3.5] - 2026-05-07

**Vectorised eager-populate via numpy bulk-scoring.** The Python loop in v1.3.3 (intent-share serial) and the process-pool in v1.3.4 (intent-share parallel) were both O(N²) calls into a per-pair scalar code path. v1.3.5 introduces ``app.domain.transition.bulk_scorer`` — a numpy clone of the six scoring components plus the hard-reject gate that runs the entire (idx_a, idx_b) pair set as a single batch of vectorised ops. Parity is enforced by ``test_bulk_scorer_parity.py`` on a randomised 30-track pool with field-dropout: every component plus the end-to-end overall matches the scalar path within 1e-9 across all four intents. After this, ``GeneticAlgorithm._eager_populate_cache`` is a 3-line call into the bulk path.

### Added
- ``app/domain/transition/bulk_scorer.py`` — ``FeatureArrays`` view + ``extract_feature_arrays`` + ``score_bpm_bulk`` / ``score_energy_bulk`` / ``score_drums_bulk`` / ``score_bass_bulk`` / ``score_harmonics_bulk`` / ``score_vocals_bulk`` + ``hard_reject_mask_bulk`` + ``score_pairs_bulk`` (the public API the GA uses). 24x24 Camelot distance lookup table and TRANSITION_STEM_WEIGHTS / TRANSITION_ENERGY_BIAS pre-packed as numpy arrays for the bulk-of-7 path.
- ``tests/domain/transition/test_bulk_scorer_parity.py`` — 11 cases: per-component parity (6), hard-reject mask parity (1), and end-to-end ``score_pairs_bulk`` overall parity for every TransitionIntent (4).

### Changed
- ``GeneticAlgorithm._eager_populate_cache`` collapsed from ~50 lines of per-intent / per-pair / parallel-or-serial branching into one bulk call. The parallel-populate process pool, ``_W_TRACKS`` / ``_W_SCORER`` worker globals, ``_populate_init`` / ``_populate_pair`` shims, and ``parallel_populate`` / ``max_workers`` / ``parallel_populate_threshold`` constructor parameters were removed — the numpy path is faster than the parallel path on every workload measured, so the IPC layer became dead weight.

### Performance
- ``Subgenre: peak_time`` n=242 (real DB pull): 26.0 s (v1.3.2 baseline) → ~7 s (v1.3.4 auto-greedy) → **sub-second eager populate** (v1.3.5; GA branch is now bottlenecked by generations + 2-opt, not the scoring engine).

### Tests
- 1247 → **1262 passed** (+4 auto-algorithm in v1.3.4, +11 parity in v1.3.5).
- ``make check`` clean (mypy strict 239/0, ruff, import-linter 5/0, pytest -n auto).

## [1.3.4] - 2026-05-06

**`sequence_optimize` algorithm auto-pick.** GA's wall-clock dominates pools above ~200 tracks even after the v1.3.2/1.3.3 populate-stage fixes — the eager-populate's O(N²·|intents|) scorer pass + ~10² generations of fitness evaluations can't beat what greedy chain-building gets in a single O(N²) sweep. Add an ``algorithm="auto"`` choice (now the default) that resolves to ``greedy`` for pools at or above 200 tracks and ``ga`` otherwise. Explicit ``"ga"`` and ``"greedy"`` still force the choice.

### Added
- ``sequence_optimize.algorithm: Literal["auto", "ga", "greedy"]`` — ``auto`` is the new default. The response carries the resolved name (``"ga"`` or ``"greedy"``) so callers can observe what actually ran.
- ``_AUTO_GREEDY_THRESHOLD = 200`` — pool-size cutoff above which ``auto`` picks greedy.
- ``tests/tools/compute/test_sequence_optimize_auto_algorithm.py`` — 4 cases covering boundary inclusivity and explicit-override semantics.

### Changed
- Default algorithm flipped from ``"ga"`` to ``"auto"``. Existing callers that pass ``"ga"`` or ``"greedy"`` are unaffected.

### Tests
- 1247 → **1251 passed** (+4 auto-algorithm).
- ``make check`` clean (mypy strict 238/0, ruff, import-linter 5/0, pytest -n auto).

## [1.3.3] - 2026-05-06

**`sequence_optimize` second-stage perf cut targeting real-world subgenre playlists.** v1.3.2's eager-populate stage worked great on synthetic randomised pools but stalled on production pools that share a subgenre / BPM range — those have a much lower hard-reject rate (~25-30 % vs ~50 % synthetic), which doubles the surviving-pair count and therefore the wall-clock of `_eager_populate_cache`. v1.3.3 attacks the populate stage on two fronts: a bulk-scoring API that shares the expensive stem-compat compute across all four intents, and an opt-in process-pool that fans the populate sweep across CPU cores.

### Added
- ``TransitionScorer.score_all_intents(a, b, intents=...)`` — bulk path that calls ``NeuralMixScorer.score`` + ``score_bpm`` + ``score_energy`` exactly once per pair and derives the four per-intent ``TransitionScore`` objects from the shared parts. ~80 % of one ``score`` call's wall-clock is the stem compats, which the per-intent loop in v1.3.2 was repeating 4× per pair.
- ``GeneticAlgorithm(parallel_populate=True, max_workers=…, parallel_populate_threshold=200)`` — pool-size-gated process pool for the populate stage. Workers receive ``tracks`` once via ``initializer`` and then per-task messages are just ``(idx_a, idx_b)`` pairs; results stream back as ``{intent_value: overall}`` dicts.

### Changed
- ``GeneticAlgorithm._eager_populate_cache`` now batches surviving pairs into a single list and dispatches via ``score_all_intents``. For pools at or above ``parallel_populate_threshold`` the dispatch fans out across ``ProcessPoolExecutor``; below the threshold it stays in-process.

### Performance
Real ``Subgenre: peak_time`` playlist (n=242, 99 % features coverage):
- v1.3.2 baseline (per-intent loop, serial populate): n=100 17.0 s, n=242 26.0 s.
- v1.3.3 intent-share + parallel populate (target measurement): see post-deploy bench in `docs/`.

### Tests
- 1247 → **1247 passed** (no test count change; pure refactor of the populate path).
- ``make check`` clean (mypy strict 238/0, ruff, import-linter 5/0, pytest -n auto).

### Open
- Parallel-populate threshold (200) and worker cap (8) are currently hard-coded constants — TODO surface them via ``settings.optimization`` if the field finds a real use case for tuning.

## [1.3.2] - 2026-05-06

**`sequence_optimize` wall-clock collapse on >100-track pools.** The GA + 2-opt loop is now strictly bound. On a synthetic 200-track techno pool, optimisation drops from OOM/timeout to **~9 s**; on a 100-track pool, **78 s → 3.6 s** (~22×) at the cost of ~12 % quality recovered via the adaptive expansion path.

### Changed
- ``GeneticAlgorithm.optimize`` now eagerly populates ``score_cache`` for every surviving ``(idx_a, idx_b, intent)`` triple after ``_prefilter_pool``. After this pre-pass, the GA + 2-opt inner loop never re-enters ``TransitionScorer.score``: every fitness evaluation lands on a dict lookup. Cost: ``|surviving_pairs| · 4`` scorer calls (≈84 k for n=200 after prefilter, single-digit seconds).
- ``GeneticAlgorithm._two_opt`` now uses **adaptive window expansion**: starts at ``window=12`` (cheap local groove repair), keeps the window when a pass finds an improvement, doubles the window on plateau, and only escalates to the full O(N²) sweep when the local search has run out of moves. Total passes capped by ``settings.optimization.two_opt_iterations`` (default 50).

### Added
- Module-level ``_TWO_OPT_WINDOW`` constant (12) and ``_PRECOMPUTE_INTENTS`` tuple (MAINTAIN / RAMP_UP / COOL_DOWN / CONTRAST) covering every intent ``infer_intent`` can return.
- ``GeneticAlgorithm._eager_populate_cache`` helper documenting the pair × intent eager fill.

### Performance
- n=50: 8.8 s → **1.3 s** (~6.8×), quality 0.724 → 0.715.
- n=100: 78.2 s → **3.6 s** (~21.7×), quality 0.752 → 0.658 (adaptive expansion recovers most of the loss vs fixed window=12 which scored 0.632).
- n=200: baseline OOM/timeout → **8.7 s**, quality 0.621.

### Tests
- 1247 → **1247 passed** (no test count change; behaviour-preserving inside the existing optimisation contract).
- ``make check`` clean (mypy strict 238/0, ruff, import-linter 5/0, pytest -n auto).

## [1.3.1] - 2026-05-06

**Score-column / weight-column rename to match Neural Mix stem vocabulary.** Closes the residual mismatch from v1.3.0 where the four perceptual ``TransitionScore`` fields kept their pre-Neural-Mix names (``harmonic`` / ``spectral`` / ``groove`` / ``timbral``) even though they semantically held stem compats. v1.3.1 renames them everywhere — dataclass fields, DB columns, weight dict keys, Pydantic schemas, Django-style filter lookups, ``ScoringProfile`` weight fields and CheckConstraint names — to match the Neural Mix stem they hold.

### Changed
- ``TransitionScore`` fields: ``harmonic→harmonics``, ``spectral→bass``, ``groove→drums``, ``timbral→vocals``. Field order: ``bpm, energy, drums, bass, harmonics, vocals, overall, hard_reject, reject_reason, best_transition``.
- DB columns on ``transitions`` and ``transition_history``: same rename.
- ``DEFAULT_WEIGHTS`` and ``INTENT_WEIGHT_MODIFIERS`` dict keys: same rename.
- ``ScoringProfile`` columns + Pydantic schemas: ``harmonic_weight→harmonics_weight``, ``spectral_weight→bass_weight``, ``groove_weight→drums_weight``, ``timbral_weight→vocals_weight``.
- ``ScoringProfile`` CheckConstraint names: ``ck_profile_{harm,spectral,groove,timbral}→ck_profile_{harmonics,bass,drums,vocals}``.
- Picker constants: ``_DRUM_ONLY_GROOVE_{HIGH,MID}→_DRUM_ONLY_DRUMS_{HIGH,MID}``.
- `app/resources/transition.py` JSON output keys mirror the field rename.

### Migration
- ``migrations/2026-05-06_neural_mix_score_columns.sql`` — direct SQL DDL renaming the 4+4+4 columns plus 4 CheckConstraint names. Apply against Supabase once.

### Tests
- 1247 → **1247 passed** (no test count change; bulk rename, behaviour identical).
- ``make check`` clean (mypy strict, ruff, import-linter, pytest -n auto).

## [1.3.0] - 2026-05-06

**Adopt the djay Pro 5 Neural Mix paradigm.** Collapse four parallel transition enums (``TransitionStyle``×6, ``TransitionType``×12, ``DjayTransition``×6, ``NeuralMixTransition``×9) into a single ``NeuralMixTransition`` with exactly seven values matching the djay Pro 5 Automix UI: FADE, ECHO_OUT, VOCAL_SUSTAIN, HARMONIC_SUSTAIN, DRUM_SWAP, VOCAL_CUT, DRUM_CUT. Replace the prose ``RecipeStep`` / ``EQPlan`` recipe model with a stem-keyframe envelope. Rework the six-component scorer around four stem compatibilities (drums / bass / harmonics / vocals) plus BPM and energy.

### Added
- **NeuralMixTransition × 7** — matches the djay Pro 5 Automix transition presets.
- **Stem-keyframe recipe model** (``StemKeyframe``, ``MuteFXEvent``, ``MuteFXTrigger``, ``NeuralMixRecipe``) — declarative envelope describing per-deck per-stem level over bars + Mute FX echo-tail events.
- **7 32-bar pure builders** in ``app/domain/transition/builders.py`` — one per preset, materialise the published Algoriddim stem-routing matrices.
- **Context-aware picker** in ``app/domain/transition/picker.py`` — selects a Neural Mix preset from score + features + section context + subgenre pair + intent. Decision tree first-match-wins on hard reject → drum-only → vocal-active → harmonic motif → energy ramp-up → ambient/cool-down → default.
- **build_recipe_for_pair** convenience wrapper materialises a fully-populated ``NeuralMixRecipe`` from a scoring pair.
- **Recipe persistence** — ``transition_persist`` and ``set_version_build`` now write ``fx_type``, ``transition_bars``, and ``transition_recipe_json`` columns alongside every score upsert.
- **TransitionScore.best_transition** — argmax over the seven Neural Mix per-preset stem-weighted scores from ``NeuralMixScorer``.

### Changed
- **6-component scorer reworked stem-aware**: the four perceptual components (harmonic / spectral / groove / timbral) now hold the four Neural Mix stem compatibilities (HARMONICS / BASS / DRUMS / VOCALS). Public field names are preserved to avoid a column rename in this commit; semantic mapping documented in ``app/domain/transition/score.py``.
- **DEFAULT_WEIGHTS**: bpm 0.20, harmonic 0.15, energy 0.15, spectral 0.15, groove 0.20, timbral 0.15 (groove uplift reflects techno DJ practice).
- **All seven transitions default to bars=32**; templates may scale via ``clamp_bars`` per subgenre pair.

### Removed
- ``TransitionStyle`` (6 values) and ``TRANSITION_STYLE_PROFILES`` from ``app/shared/constants.py``.
- ``TransitionType`` (12 values), ``DjayTransition`` (6 values), ``StemAction``, ``RecipeStep``, ``EQPlan``, and ``TransitionRecipe`` from ``app/domain/transition/recipe.py``.
- ``app/domain/transition/recipe_engine.py`` (522 lines) and ``app/domain/transition/style.py`` (140 lines).
- ``app/domain/transition/components/{harmonic,spectral,groove,timbral}.py`` — replaced by stem-compat helpers in ``neural_mix.py``.
- ``StyleRules`` dataclass + ``DRUM_ONLY_WEIGHT_OVERRIDE`` + ``DRUM_ONLY_HARMONIC_FLOOR`` from ``weights.py``.
- ``preferred_type_for_pair`` from ``subgenre_rules.py``.
- ``DEFAULT_TRANSITION_WEIGHTS`` from ``app/shared/constants.py`` (now in ``app/domain/transition/weights.py:DEFAULT_WEIGHTS``).

### Migration notes
- DB columns ``harmonic_score``, ``spectral_score``, ``groove_score``, ``timbral_score`` retain their v1.2 names but now hold stem compats. Deferred rename → ``harmonics_score``, ``bass_score``, ``drums_score``, ``vocals_score`` is a follow-up.
- ``transitions.fx_type`` is now constrained at the application layer to one of the seven ``NeuralMixTransition`` values when populated.
- Panel (``ManualTransitionStyle`` UI override) is intentionally out of scope for this release.

### Tests
- 1228 → **1247 passed** (+19 picker, +54 builder, − removed legacy style/recipe-engine/component-scorer tests).
- ``make check`` clean (mypy strict, ruff, import-linter, pytest).

## [1.2.58] - 2026-04-28

**Audit-fix loop, iteration 60.** ``TrackFeedbackCreate`` had no cross-field validation between ``kind`` and ``rating``.

### Fixed
- **T-58:** ``entity_create(track_feedback, {"kind":"rate"})`` (without rating) would persist a "rate" with ``rating=null`` — a no-op rate. ``{"kind":"like", "rating":5}`` would persist a stray rating alongside a binary like. Both broke downstream consumers (UI showing 0★ rates, affinity scoring confused by phantom values).

  Fix: ``model_validator(mode="after")`` on ``TrackFeedbackCreate`` enforces the kind/rating pairing:
  - ``kind="rate"`` → rating REQUIRED (1-5)
  - ``kind="like"`` / ``kind="ban"`` → rating MUST be absent (binary signals)

### Tests
- 1201 → **1210 passed** (+9 kind/rating pairing regression tests).
- ``make check`` clean.

## [1.2.57] - 2026-04-28

**Audit-fix loop, iteration 59.** ``best_pairs`` returned leftover self-pair rows from pre-T-52 inserts.

### Fixed
- **T-57:** ``local://transition_history/best_pairs`` and ``/history`` (which falls back to ``best_pairs``) returned ``from_track_id == to_track_id`` rows that historical pre-v1.2.51 inserts had left in production. Live confirmation: ``best_pairs?limit=3`` returned 2 of 3 entries with ``146→146`` self-pairs polluting the "best" view.

  Schema validators (v1.2.51-52) prevent NEW self-pair inserts, but the existing rows still surfaced through every read. Fix: ``_best_pairs_stmt`` adds ``WHERE from_track_id != to_track_id`` so all consumers (best_pairs resource + history endpoint) skip degenerate rows.

### Tests
- 1199 → **1201 passed** (+2 self-pair filter regression tests).
- ``make check`` clean.

## [1.2.56] - 2026-04-28

**Audit-fix loop, iteration 58.** ``local://sets/{id}/versions/compare/{a}/{b}`` had three issues.

### Fixed
- **T-56:**
  - Same-version compare (``a == b``) returned a trivial ``delta=0, changed_positions=[]`` row instead of rejecting. Live confirmation: ``/sets/5/versions/compare/6/6`` succeeded with empty diff. Now: ``ValidationError`` with explicit "two distinct version ids" message.
  - Cross-set ids leaked a misleading ``set_version not found: 3`` even though version 3 existed in a different set. Now: ``NotFoundError("set_version", "3 (belongs to set 4, not 5)")``.
  - ``zip(items_a, items_b, strict=False)`` silently dropped tail positions when the two versions had different lengths. Switched to length-aware iteration: tail differences are now counted as changed.

### Tests
- 1194 → **1199 passed** (+5 compare-resource regression tests).
- ``make check`` clean.

## [1.2.55] - 2026-04-28

**Audit-fix loop, iteration 57.** Same-track score / explain resources mirrored T-52 hole.

### Fixed
- **T-55:** ``local://transition/{from_id}/{to_id}/score`` and ``/explain`` recomputed via ``TransitionScorer`` regardless of whether ``from_id == to_id``, returning a synthetic 0.93 self-similarity row for a track-against-itself query. The read paths mirrored the T-52 hole on the write path (``entity_create(transition)`` with same id) which v1.2.51-52 already closed.

  Fix: ``_load_features_pair`` now rejects same-id input up front with a clean ``ValidationError`` — both ``/score`` and ``/explain`` flow through this helper, so the guard fires once for both endpoints.

### Tests
- 1191 → **1194 passed** (+3 same-track resource regression tests).
- ``make check`` clean.

## [1.2.54] - 2026-04-28

**Audit-fix loop, iteration 56.** ``SetVersionCreate`` accepted track-order pathologies.

### Fixed
- **T-54:** ``entity_create(set_version, {"track_order": [146, 147, 146]})`` succeeded — set version 67 persisted with track 146 played twice, an obvious bug. Plus ``track_order=[146]`` (single track) was also accepted, producing a "set" with no transitions. Both contradict ``sequence_optimize`` and ``transition_score_pool`` which already reject duplicates.

  Fix: ``model_validator(mode="after")`` on ``SetVersionCreate``:
  - Duplicate track ids in ``track_order`` rejected with the explicit duplicate list
  - Fewer than 2 tracks rejected (a set without transitions is not a set)

### Tests
- 1185 → **1191 passed** (+6 track-order schema validation tests).
- ``make check`` clean.

## [1.2.53] - 2026-04-28

**Audit-fix loop, iteration 55.** ``TrackFeaturesCreate`` accepted no-target payloads, leaking ``KeyError``.

### Fixed
- **T-53:** ``entity_create(track_features, {"level": 3})`` (no ``track_id`` and no ``track_ids``) leaked ``Error calling tool 'entity_create': 'track_ids'`` — a bare KeyError raised by the analyze handler when it tried to read the missing key. Same drift as the original ``AudioFileCreate`` no-target path (long since fixed by an explicit ``model_validator``).

  Fix: ``model_validator(mode="after")`` on ``TrackFeaturesCreate`` mirrors ``AudioFileCreate``:
  - Requires exactly one of ``track_id`` (single) or ``track_ids`` (batch)
  - Empty ``track_ids: []`` rejected
  - Both-set rejected (avoids ambiguous handler routing)

### Tests
- 1178 → **1185 passed** (+7 schema target-validation tests).
- ``make check`` clean.

## [1.2.52] - 2026-04-28

**Audit-fix loop, iteration 54 (continued).** v1.2.51 added schema validators rejecting same-track endpoints, but the dispatcher's handler path bypassed the schema entirely.

### Fixed
- **T-52 (continued):** ``entity_create`` for handler-backed entities (``transition``, ``track``, ``track_features``, ``audio_file``, ``set_version``) read ``data`` raw and skipped ``config.create_schema.model_validate``. Live confirmation after v1.2.51: ``entity_create(transition, {"from_track_id":146,"to_track_id":146})`` STILL succeeded with overall=0.93 because the new validator on ``TransitionCreate`` was never invoked.

  Fix: move ``config.create_schema.model_validate(data)`` BEFORE the handler dispatch in ``entity_create``. Cross-field invariants (T-52 distinct endpoints, T-49 weight sum, T-47 BPM range) are now enforced for ALL create paths, not just the default-INSERT path. Handlers continue to receive raw ``data`` (no signature change).

### Tests
- 1178 passed (no new tests; existing handler tests confirm no regression).
- ``make check`` clean.

## [1.2.51] - 2026-04-28

**Audit-fix loop, iteration 54.** Three relational schemas accepted "from track to itself" / "track paired with itself" rows.

### Fixed
- **T-52:**
  - ``TransitionCreate`` accepted ``from_track_id == to_track_id`` — live confirmation: ``entity_create(transition, {"from_track_id":146,"to_track_id":146})`` returned a row with ``overall=0.93`` (track scored against its own features). The persisted row would mislead any "find best transitions from track X" query.
  - ``TransitionHistoryCreate`` accepted the same self-pair — meaningless history row (nothing was actually mixed).
  - ``TrackAffinityCreate`` accepted ``track_a_id == track_b_id`` — degenerate "self-affinity" row.

  Fix: ``model_validator(mode="after")`` on all three Create schemas rejects same-id endpoints with a clean ``must differ`` error at schema-validation time. Update schemas don't carry the endpoint columns so they're naturally safe.

### Tests
- 1172 → **1178 passed** (+6 distinct-endpoints regression tests).
- ``make check`` clean.

## [1.2.50] - 2026-04-28

**Audit-fix loop, iteration 53.** Playlist hierarchy could contain cycles.

### Fixed
- **T-51:** ``entity_update(playlist, id=X, data={parent_id: X})`` accepted self-cycles; ``entity_update`` also accepted N-cycles (e.g. setting playlist 32's parent to its descendant 33, when 33's parent was already 32). Live confirmation::

      entity_create(playlist, {"name":"X"})              -> id=32
      entity_update(playlist, 32, {"parent_id": 32})     -> 200 OK   ← self-cycle
      entity_create(playlist, {"name":"Y","parent_id":32})-> id=33
      entity_update(playlist, 32, {"parent_id": 33})     -> 200 OK   ← 32→33→32

  Fix:
  - New ``PlaylistRepository.ancestor_ids(playlist_id)`` walks the ``parent_id`` chain root-first (with ``max_depth=1000`` and a ``seen`` set to terminate on pre-existing data drift).
  - ``entity_update`` rejects ``parent_id == id`` with a self-cycle message and walks the proposed parent's ancestor chain — if the playlist being updated appears in it, raises ``ValidationError`` with the full cycle path in ``details``.

  ``entity_create`` is naturally safe (id is auto-generated post-insert; FK already catches non-existent parent).

### Tests
- 1165 → **1172 passed** (+7 cycle-prevention regression tests).
- ``make check`` clean.

## [1.2.49] - 2026-04-28

**Audit-fix loop, iteration 52.** Schema-mismatch ``ProgrammingError`` leaked raw SQL.

### Fixed
- **T-50:** ``entity_create(track_feedback, {"track_id": 99999, "kind": "like"})`` leaked::

      (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError)
      <class 'asyncpg.exceptions.UndefinedColumnError'>:
      column "kind" of relation "track_feedback" does not exist
      [SQL: INSERT INTO track_feedback ...]

  The actual issue is well-known: the SQLAlchemy model has a ``kind`` column the production Supabase doesn't yet (Alembic migration ``p2_drop_dead_tables`` and friends are pending). Same drift class as v1.2.47 (T-48) but on ``ProgrammingError`` not ``IntegrityError``.

  Fix: extend ``BaseRepository`` to also catch ``ProgrammingError`` and convert via ``_programming_error_to_validation``:
  - Undefined column → ``schema mismatch on TrackFeedback: column 'kind' missing in table 'track_feedback'. Apply the pending Alembic migration.``
  - Undefined table → ``schema mismatch on X: table 'Y' does not exist. Apply the pending Alembic migration.``
  - Anything else → ``database programming error on X``.

  Surfaces the actionable cause (missing migration) instead of the SQL dump.

### Tests
- 1163 → **1165 passed** (+2 ProgrammingError mapping regression tests).
- ``make check`` clean.

## [1.2.48] - 2026-04-28

**Audit-fix loop, iteration 51.** ``ScoringProfile`` accepted weights that didn't sum to 1.0.

### Fixed
- **T-49:** ``entity_create(scoring_profile, {"name":"bad", "bpm_weight":0.5, "harmonic_weight":0.5, ...})`` succeeded — every weight set to 0.5 yields sum=3.0. The 6 component weights are convex-combination weights; anything other than ``sum=1.0`` produces out-of-range scores when applied to a transition.

  Fix: ``model_validator(mode="after")`` on ``ScoringProfileCreate`` and ``ScoringProfileUpdate`` rejects weights whose sum deviates from 1.0 by more than ``±0.001`` (float drift tolerance). On ``Update``, the check fires only when ALL 6 weights are supplied — partial patches can't enforce the cross-row invariant without a DB read of the existing values.

### Tests
- 1154 → **1163 passed** (+9 weight-sum schema tests).
- ``make check`` clean.

## [1.2.47] - 2026-04-28

**Audit-fix loop, iteration 50.** asyncpg integrity errors leaked raw SQL traces to MCP clients.

### Fixed
- **T-48:** ``entity_create(playlist, {"parent_id": 99999})`` and ``entity_create(set, {"source_playlist_id": 99999})`` leaked the raw asyncpg ``ForeignKeyViolationError`` to MCP clients — including the full SQL + parameter dump and the constraint name. The wall of text told the caller nothing actionable.

  Fix: ``BaseRepository.create`` / ``update`` / ``delete`` now catch ``IntegrityError`` and convert via ``_integrity_error_to_validation``:
  - FK violation → ``foreign key violation on Playlist.parent_id: value '99999' does not exist in dj_playlists`` (with structured ``details``).
  - Unique-key collision → ``unique constraint violation on Track``.
  - Anything else → ``integrity violation on X``.

  SQL details are kept off the wire (truncated to first 200 chars in ``details``) so production logs stay clean.

### Tests
- 1151 → **1154 passed** (+3 integrity-error mapping regression tests).
- ``make check`` clean.

## [1.2.46] - 2026-04-28

**Audit-fix loop, iteration 49.** ``SetCreate`` accepted inverted BPM ranges; ``entity_create`` / ``entity_update`` skipped the View enricher.

### Fixed
- **T-47 (BPM range):** ``entity_create(set, {"target_bpm_min": 130, "target_bpm_max": 120})`` succeeded — the set persisted with min > max, an obviously bogus constraint that any downstream "in target range" query treats as "match nothing" silently. Same problem on ``entity_update``.

  Fix: ``model_validator(mode="after")`` on both ``SetCreate`` and ``SetUpdate`` rejects ``target_bpm_min > target_bpm_max`` when both are supplied. Equal endpoints are valid (singleton range); half-open ranges (only one side) pass through — the other side stays untouched on the row, and the dispatcher remains responsible for the cross-row invariant on partial updates.

- **T-47 (enricher consistency):** ``entity_create(set, ...)`` returned ``version_count: null`` even on a fresh row — the View enricher (added in v1.2.43 / T-44) was wired only to ``entity_get`` and ``entity_list``, not ``entity_create`` or ``entity_update``. Fresh rows now correctly return ``0``; updates re-populate derived fields too.

### Tests
- 1142 → **1151 passed** (+9 BPM-range schema validation tests).
- ``test_update_template_validation.py`` updated: mock ``uow.sets.version_count`` since update now runs the enricher.
- ``make check`` clean.

## [1.2.45] - 2026-04-28

**Audit-fix loop, iteration 48.** ``sequence_optimize`` crashed on typo'd / un-analysed track ids — same drift class as T-42 (``transition_score_pool``) but with a stack trace instead of silent empty.

### Fixed
- **T-46:** ``sequence_optimize(track_ids=[99999, 99998])`` crashed with::

      'NoneType' object has no attribute 'integrated_lufs'

  ``features.get(tid)`` returned ``None`` for missing ids and the optimizer indexed it into the GA / greedy fitness function. Same drift class as v1.2.41 (T-42) on ``transition_score_pool``, but here it leaked an internal exception instead of returning silently empty.

  Fix: same upfront guard pattern.
  - All ids missing → typed ``ValidationError`` with the explicit list.
  - Partial pool with ≥ 2 valid ids → drop the dead ids and run the optimizer on the valid subset.
  - Partial pool with < 2 valid ids → ``ValidationError`` (need ≥ 2 to optimize meaningfully).

### Tests
- 1139 → **1142 passed** (+3 ``sequence_optimize`` missing-features regression tests).
- Existing ``test_template_validation.py`` updated to seed real features for success-path tests (the prior ``_mock_uow`` returned ``{}`` and now hits the new guard).
- ``make check`` clean.

## [1.2.44] - 2026-04-28

**Audit-fix loop, iteration 47.** Misleading error messages on ``entity_aggregate`` field validation.

### Fixed
- **T-45:** ``entity_aggregate(track, "distinct", field="nonexistent_field")`` raised ``operation 'distinct' requires field`` — implying the caller forgot the parameter, when in fact they passed it but mistyped the column name. The other field-required ops (``sum``, ``avg``, ``min_max``, ``histogram``) said ``"requires a valid field"`` — only marginally clearer.

  Fix: distinguish the two cases in ``BaseRepository.aggregate``:
  - field omitted entirely → ``operation 'X' requires a `field` parameter``
  - field provided but unknown → ``unknown field 'nonexistent_field' on Track (operation 'X')``

  Now mistypes are caught with the actual field name in the error.

### Tests
- 1128 → **1139 passed** (+11 ``aggregate`` field-validation regression tests).
- ``make check`` clean.

## [1.2.43] - 2026-04-28

**Audit-fix loop, iteration 46.** Derived View fields (``item_count``, ``version_count``) were declared but permanently ``null``.

### Fixed
- **T-44:** ``PlaylistView.item_count`` and ``SetView.version_count`` were declared in the schemas (and thus advertised via ``schema://entities/{name}``) but every ``entity_get`` / ``entity_list`` response returned ``null``. The dispatcher built the View via ``model_validate(orm_row)`` and the ORM row has no such columns. Live confirmation: ``entity_get(playlist, 5)`` returned ``item_count: null`` for a playlist with 60 tracks; ``entity_get(set, 5)`` returned ``version_count: null`` for a set with 3 versions.

  Fix:
  - ``EntityConfig`` gained an optional ``view_enricher: Callable[(uow, row, view_dict), Awaitable[view_dict]]`` hook.
  - ``entity_get`` and ``entity_list`` invoke the enricher (when present) after ``model_validate`` and before field-projection so derived fields land in the dumped View.
  - ``PlaylistRepository.item_count(playlist_id)`` and the existing ``SetRepository.version_count(set_id)`` are wired to the playlist / set EntityConfigs respectively.

  N+1 in ``entity_list`` (one count per row) is acceptable for the affected entities — both populations are small (< 100 rows). Future scale-up: gather IDs and bulk-enrich.

### Tests
- 1123 → **1128 passed** (+5 view-enricher regression tests).
- ``make check`` clean.

## [1.2.42] - 2026-04-28

**Audit-fix loop, iteration 45.** ``get_prompt`` rejected native int / float / bool prompt argument values.

### Fixed
- **T-43:** ``mcp__plugin_dj-music_mcp__get_prompt(name="quick_mix_check", arguments={"from_track_id": 146, "to_track_id": 147})`` failed with::

      2 validation errors for GetPromptRequestParams
      arguments.from_track_id
        Input should be a valid string [type=string_type, input_value=146]

  The MCP wire format types ``GetPromptRequestParams.arguments`` as ``dict[str, str]``. ``list_prompts`` advertises ints via "Provide as a JSON string matching schema integer", but most clients (including Claude Code) pass native ints. Pydantic then crashed instead of coercing.

  Fix: ``JSONAwarePromptsAsTools.get_prompt`` now coerces every non-``None`` value to a string via ``json.dumps(v)`` before forwarding to ``render_prompt``. Strings pass through; ``None`` values are dropped (treated as not-supplied per MCP semantics). Booleans become ``"true"`` / ``"false"``.

### Tests
- 1120 → **1123 passed** (+3 prompt-arg coercion regression tests).
- ``make check`` clean.

## [1.2.41] - 2026-04-28

**Audit-fix loop, iteration 44.** ``transition_score_pool`` silently returned empty pairs when callers passed typo'd / un-analysed track ids.

### Fixed
- **T-42:** ``transition_score_pool(track_ids=[99999, 99998])`` returned ``{"pairs":[],"hard_rejects":0}`` for non-existent ids — caller couldn't tell typo apart from "no compatible pairs". The same silent-empty applied to mixed pools (some valid, some un-analysed) — the missing ids were dropped without trace.

  Fix:
  - ``ScorePoolResult`` gained a ``missing_track_ids: list[int]`` field — track ids that had no scoring features (no ``track_audio_features_computed`` row).
  - On non-trivial pools (``len(track_ids) >= 2``) where EVERY id is missing, raise typed ``ValidationError`` instead of returning silently — almost certainly a typo or un-analysed library.
  - Mixed pools: continue computing pairs for the valid subset, but surface the rest in ``missing_track_ids``.

### Tests
- 1118 → **1120 passed** (updated existing duplicate-ids test + 2 new T-42 regression tests).
- ``make check`` clean.

## [1.2.40] - 2026-04-28

**Audit-fix loop, iteration 43.** ``suggest_next?energy_direction=up|down`` was a no-op.

### Fixed
- **T-41:** ``local://tracks/{id}/suggest_next?energy_direction=up|down`` filtered candidates against absolute thresholds — ``up`` dropped tracks with ``energy_mean <= 0``, ``down`` dropped tracks with ``energy_mean >= 1``. Real ``energy_mean`` always falls in (0, 1) for techno, so neither threshold ever fired and the directional knob did nothing. Live confirmation: ``?limit=5&energy_direction=down`` returned the same 5 candidates as the no-filter call.

  Fix: compare candidate ``energy_mean`` against the SOURCE track's ``energy_mean`` — ``up`` = candidate hotter than source; ``down`` = candidate cooler. When either side has no energy data, the candidate falls through (we don't silently drop it).

### Tests
- 1114 → **1118 passed** (+4 ``energy_direction`` regression tests).
- ``make check`` clean.

## [1.2.39] - 2026-04-28

**Audit-fix loop, iteration 42.** ``suggest_replacement`` returned hardcoded ``score=0.0`` for every candidate.

### Fixed
- **T-40:** ``local://tracks/{id}/suggest_replacement/{set_id}/{position}`` returned ``score=0.0`` on every candidate, regardless of how compatible it was. The hardcoded zero made the resource useless for ranking — caller couldn't tell which BPM-compatible candidate was actually the best replacement.

  Fix: score each candidate against the surrounding set track using the live ``TransitionScorer``. Anchor selection:
  - ``position - 1`` if it exists (candidate mixes INTO predecessor)
  - else ``position + 1`` (candidate mixes OUT to successor)
  - else no anchor (single-track set) — ``score=0.0`` honestly, with a reason string explaining why.

  Candidates returned best-score-first.

### Tests
- 1111 → **1114 passed** (+3 ``suggest_replacement`` scoring regression tests).
- ``make check`` clean.

## [1.2.38] - 2026-04-28

**Audit-fix loop, iteration 41.** Closing the widening sweep on the last two narrow entities — ``track_affinity`` + ``playlist``. Same drift class as v1.2.29/31/32/35/36/37.

### Fixed
- **T-39 (TrackAffinity):**
  - ``Filter`` previously had only 3 keys (``track_a_id__eq``, ``track_b_id__eq``, ``avg_score__gte``). Widened with ``id__eq/in/gt/gte/lt/lte``, ``track_a_id__in``, ``track_b_id__in``, ``avg_score__lte/range``, and crucially ``play_count__gte/lte``, ``positive_count__gte/lte``, ``negative_count__gte/lte`` — the canonical "popular pairs" / "all-positive feedback" queries depend on those columns and they were unfilterable.
  - ``Update`` only mutated ``avg_score`` and ``play_count``. Added ``positive_count`` and ``negative_count`` so callers can do explicit recalibration without going through the implicit refresh handler.
- **T-39 (Playlist):**
  - ``View`` dropped ``source_app`` (rekordbox / ym / serato) and ``platform_ids`` (JSON-encoded provider IDs needed for ``playlist_sync``).
  - ``Filter`` rejected ``id__gt/gte/lt/lte`` (drift from ``set_version``); added lookups for the 2 newly-exposed columns plus ``parent_id__in``, ``source_of_truth__in``.
  - ``Create`` and ``Update`` couldn't write the same 2 columns — re-attaching a freshly-imported YM playlist to its bare-bones local twin required ``delete + recreate``. Added with ``max_length`` matching the model.
- **EntityRegistry**: ``filterable_fields`` for ``playlist`` (+ id range, ``parent_id`` ``__in``, ``source_app``, ``platform_ids``) and ``track_affinity`` (+ id range, batch, count lookups). ``sortable_fields`` for ``playlist`` + ``source_app``. CI guards stay green.

### Tests
- 1074 → **1111 passed** (+37 widening regression tests in ``tests/schemas/test_iter41_affinity_playlist_widening.py``).
- ``make check`` clean.

## [1.2.37] - 2026-04-28

**Audit-fix loop, iteration 40.** ``TrackFeaturesView`` widening — the largest View gap in the codebase.

### Fixed
- **T-38:** ``TrackFeaturesView`` exposed 11 of the 47+ persisted columns. Live confirmation: ``entity_get(track_features, 146, fields=["danceability"])`` returned ``"unknown field name(s) in fields: ['danceability']"`` even though the column was populated. None of the P1 enrichment fields (``danceability``, ``dynamic_complexity``, ``dissonance_mean``, ``tonnetz_vector``, ``tempogram_ratio_vector``, ``beat_loudness_band_ratio``), none of the P2 fields (``spectral_complexity_mean``, ``pitch_salience_mean``, BPM histogram, phrase metadata), none of the loudness columns beyond ``integrated_lufs`` (``true_peak_db``, ``crest_factor_db``, ``loudness_range_lu``, ``rms_dbfs``, ``short_term_lufs_mean``, ``momentary_max``), and none of the energy bands or band ratios were projectable.

  Fix: View now exposes ~45 fields. Heavy vectors (``mfcc_vector``, ``tonnetz_vector``, ``tempogram_ratio_vector``, ``beat_loudness_band_ratio``, ``phrase_boundaries_ms``) stay as JSON strings — caller does ``json.loads`` if they want.

- **TrackFeaturesFilter** widened with 12 new lookup classes for the canonical scoring-debug queries:
  - ``true_peak_db__gte/lte`` (clipping audit)
  - ``key_confidence__gte/lte`` (filter unreliable keys)
  - ``atonality__eq``, ``variable_tempo__eq`` (boolean discriminators)
  - ``danceability__gte/lte``, ``dissonance_mean__gte/lte``
  - ``bpm_confidence__gte/lte``, ``bpm_stability__gte/lte``
  - ``onset_rate__gte/lte``, ``pulse_clarity__gte/lte``

- **EntityRegistry**: ``filterable_fields`` for ``track_features`` synced (10 new column entries × their lookup ops). CI guards stay green.

### Tests
- 1015 → **1074 passed** (+59 widening regression tests in ``tests/schemas/test_iter40_track_features_view_widening.py``).
- ``make check`` clean.

## [1.2.36] - 2026-04-28

**Audit-fix loop, iteration 39.** Same drift class on Set + AudioFile schemas — View dropped persisted columns, Update dropped fields that Create accepted, Filter dropped canonical id range queries.

### Fixed
- **T-37 (Set):**
  - ``SetFilter``: + ``id__gt/gte/lt/lte`` (consistency with ``set_version`` which already had them).
  - ``SetUpdate``: + ``target_bpm_min``, ``target_bpm_max``, ``source_playlist_id`` with ``ge/le`` validators mirroring ``SetCreate``. Without them, retargeting BPM range or re-attaching the source playlist required delete + recreate.
- **T-37 (AudioFile):**
  - ``AudioFileView``: + ``file_uri`` (file:// scheme), ``file_hash`` (sha256 dedup), ``mime_type`` (REQUIRED on the model — was always invisible), ``source_app``.
  - ``AudioFileFilter``: + ``file_uri__icontains``, ``file_hash__eq/isnull``, ``mime_type__eq/in``, ``source_app__eq/in/isnull``.
  - ``AudioFileUpdate``: + same 4 columns the View now exposes (with ``max_length`` matching the model). Re-running dedup or relocating ``source_app`` no longer requires delete + recreate.
- **EntityRegistry**: ``filterable_fields`` for ``set`` and ``audio_file`` synced; both CI guards green.

### Tests
- 986 → **1015 passed** (+29 widening regression tests in ``tests/schemas/test_iter39_set_audio_widening.py``).
- ``make check`` clean.

## [1.2.35] - 2026-04-28

**Audit-fix loop, iteration 38.** ``TransitionView`` and ``TransitionFilter`` widening — same drift class as v1.2.29 (filterable_fields) and v1.2.31 (sortable_fields), this time on the View side.

### Fixed
- **T-36:** ``TransitionView`` dropped 7 persisted columns on the floor; ``entity_get(transition, id)`` and ``entity_list(transition)`` could not surface them. Of these, ``transition_bars`` and ``transition_recipe_json`` are even write-able via ``TransitionUpdate`` — i.e. callers could write but had no read path back. Added to View: ``key_distance_weighted``, ``low_conflict_score``, ``transition_bars``, ``from_section_id``, ``to_section_id``, ``overlap_ms``, ``transition_recipe_json``.
- **TransitionFilter** widened: ``id__eq/in/gt/gte/lt/lte`` (canonical "load these specific scored pairs"), ``key_distance_weighted__gte/lte``, ``low_conflict_score__gte/lte``, ``transition_bars__eq/in/gte/lte``, ``overlap_ms__gte/lte``.
- **EntityRegistry**: ``filterable_fields`` and ``sortable_fields`` for transition synced with the new schema. Added ``transition_bars`` and ``overlap_ms`` to ``sortable_fields``.

### Tests
- 966 → **986 passed** (+20 widening regression tests in ``tests/schemas/test_iter38_transition_widening.py``).
- ``make check`` clean.

## [1.2.34] - 2026-04-27

**Audit-fix loop, iteration 37.** Two long-dead resource paths brought back online.

### Fixed
- **T-35:** ``local://tracks/{id}/suggest_next`` and ``local://tracks/{id}/suggest_replacement/{set_id}/{position}`` always returned ``candidates=[]`` with placeholder reasons — *"transitions repository does not expose list_from yet"* and *"tracks repository does not expose search_by_bpm_range yet"*. Both repository methods were planned in Phase 5 but never landed; the resources had been silently no-op since v1.0.

  Live confirmation: track 146 has 3+ persisted ``Transition`` rows from it, yet ``local://tracks/146/suggest_next`` returned the placeholder reason — i.e. the resource never actually queried the data.

  Fix:
  - ``TransitionRepository.list_from(from_track_id, *, limit)`` — best-quality-first (``overall_quality DESC NULLS LAST``, tiebreak ``id DESC``).
  - ``TrackRepository.search_by_bpm_range(*, bpm_min, bpm_max, exclude_ids, limit)`` — INNER JOIN to ``track_audio_features_computed``, ``status=0`` active filter, ``exclude_ids`` honoured.

### Tests
- 959 → **966 passed** (+7 repo-method regression tests).
- ``make check`` clean.

## [1.2.33] - 2026-04-27

**Audit-fix loop, iteration 36.** Resource ``local://tracks/{id}/features`` published two fields that were always ``null``.

### Fixed
- **T-34:** ``local://tracks/{id}/features`` returned ``analysis_level: null`` and ``mood_confidence: null`` for every track, including fully L3-analyzed ones. Root cause: the resource builds its payload via ``getattr(feat, ...)`` on a ``TrackFeatures`` dataclass, but ``app/shared/features.py:TrackFeatures`` simply did not declare those two fields. ``from_db`` filled the dataclass from a ``TrackAudioFeaturesComputed`` row (where both columns exist), but the dataclass dropped them on the floor.

  Fix: declare ``analysis_level: int | None`` and ``mood_confidence: float | None`` on ``TrackFeatures``; populate them in ``from_db``. Callers can now tell which P3-tier fields are populated, and mood confidence is finally surfaced.

### Tests
- 957 → **959 passed** (+2 ``TrackFeatures.from_db`` regression tests).
- ``make check`` clean.

## [1.2.32] - 2026-04-27

**Audit-fix loop, iteration 35.** Critical regression introduced by v1.2.31's sortable_fields widening.

### Fixed
- **T-33 (critical):** ``entity_list(track, sort=['created_at__desc'])`` and similar non-integer sort fields crashed with ``int() argument must be a string, ..., not 'datetime.datetime'`` (or ``NoneType`` for nullable floats like ``mood_confidence``). The cursor encoder hardcoded ``int(getattr(last_row, first_field))``; v1.2.31 widened sortable_fields without adapting cursor logic.

  Fix: ``BaseRepository.filter`` now detects non-integer sort columns up front. Cursor encode/decode is gated by ``_is_integer_column`` — non-integer sorts return ``next_cursor=None`` cleanly (signalling end-of-stream); attempting to pass a cursor on a non-integer sort raises a typed ``ValidationError`` instead of crashing the dispatcher. Composite cursors (``(sort_value, pk)``) are out of scope here; callers paginating by datetime should use ``id`` sort or rely on the explicit error.

### Tests
- 954 → **957 passed** (+3 cursor regression tests).
- ``make check`` clean.

## [1.2.31] - 2026-04-27

**Audit-fix loop, iteration 34.** Mass ``sortable_fields`` widening + CI guard. Same drift class as v1.2.29's ``filterable_fields`` mass-sync.

### Fixed
- **T-32:** ``entity_list(track, sort=['created_at__desc'])`` rejected with "cannot sort track by 'created_at'". ``sortable_fields`` for every entity was hand-curated to a tiny subset and never updated as columns landed:
  - ``track``: + ``sort_title, status, created_at, updated_at``
  - ``playlist``: + ``created_at, updated_at``
  - ``set``: + ``template_name, target_duration_ms, created_at, updated_at``
  - ``set_version``: + ``label, created_at``
  - ``audio_file``: + ``track_id, bitrate, created_at``
  - ``track_features``: + ``key_code, analysis_level, integrated_lufs, energy_mean, mood, mood_confidence``
  - ``transition``: + ``from_track_id, to_track_id, hard_reject, fx_type, created_at``
  - ``transition_history``: + ``from/to_track_id, user_reaction, style, duration_sec, created_at``
  - ``track_feedback``: + ``track_id, kind, rating, created_at, updated_at``
  - ``track_affinity``: + ``play_count``
  - ``scoring_profile``: + ``created_at, updated_at``

### Added
- **CI guard** ``tests/registry/test_sortable_fields_match_model.py``: walks every registered entity and asserts every name in ``sortable_fields`` is a real attribute on the SQLAlchemy model. Catches typos and stale entries on the same drift principle as v1.2.29's filterable_fields guard.

### Tests
- 943 → **954 passed** (+11 sortable_fields guard tests, one per entity).
- ``make check`` clean.

## [1.2.30] - 2026-04-27

**Audit-fix loop, iteration 33.** ``transition_score_pool(intent=...)`` was the third silent-no-op parameter found in this loop (after ``sequence_optimize.template`` in v1.2.12 and ``set.template_name`` in v1.2.16/v1.2.26).

### Fixed
- **T-31:** ``transition_score_pool(intent='ramp_up')`` returned identical scores regardless of intent value (or with ``intent='bogus_intent'``). The parameter was declared on the tool signature but never threaded to ``scorer.score(...)``. Now validated against the ``TransitionIntent`` enum (``maintain | ramp_up | cool_down | contrast``) at the dispatcher and passed through; per-intent component weights from ``INTENT_WEIGHT_MODIFIERS`` actually influence the result.

### Tests
- 941 → **943 passed** (+2 intent-threading regression tests).
- ``make check`` clean.

## [1.2.29] - 2026-04-27

**Audit-fix loop, iteration 32.** Mass ``filterable_fields`` ↔ ``filter_schema`` drift sync + CI guard.

### Fixed
- **T-30:** ``schema://entities/{entity}.filterable_fields`` was stale on **5 of 11 entities** vs the actual ``filter_schema`` Pydantic class:
  - ``track``: missing ``id__gt/gte/lt/lte``, ``has_features``, ``sort_title``, ``title__contains``, ``duration_ms__gte/lte``
  - ``playlist``: missing ``name__eq``, ``name__startswith``, ``parent_id``, ``source_of_truth``
  - ``set_version``: missing ``id__gt/gte/lt/lte``, ``label__eq``
  - ``track_features``: missing ``mood_confidence``, ``mood__isnull``, ``energy_mean``, ``spectral_centroid_hz``, ``hp_ratio``, ``kick_prominence``
  - ``transition``: missing ``fx_type``, all 6 component scores
  - ``transition_history``: missing 30+ lookups added across iterations 21-23

  Each iteration that widened a Filter schema in this loop forgot to also sync the registry's ``filterable_fields`` (the human-readable summary). Introspection clients reading ``schema://entities/{entity}`` saw an old narrow contract while the dispatcher actually accepted the wider one.

### Added
- **CI guard** ``tests/registry/test_filterable_fields_sync.py``: walks every registered entity and asserts every ``__<lookup>`` declared on the filter schema appears in ``filterable_fields``. Future schema widenings that forget to sync the summary fail CI immediately.

### Tests
- 930 → **941 passed** (+11 sync regression tests, one per entity).
- ``make check`` clean.

## [1.2.28] - 2026-04-27

**Audit-fix loop, iterations 28-29 — re-converged.** Two consecutive clean iterations after the v1.2.27 widening pass. No code changes; release marks the convergence point of the second sweep (v1.2.16 → v1.2.27).

### Final loop summary (v1.2.0 → v1.2.28)

29 patches across 29 iterations. Cumulative test count: 826 → **930 passed** (+104 regression tests).

### Bug class taxonomy (all closed for typical surface)

1. **Schema underspec** (Bug A class) — 30+ filter/update widenings across 9 entities. Every Pydantic Filter and most Update DTOs got widened to match the canonical DJ queries.
2. **Silent caps** — 3 dashboards (``ui_library_dashboard``, ``ui_camelot_wheel``, ``ui_library_audit``) all had hardcoded ``LIMIT 10000`` / ``LIMIT 500`` silently truncating production-scale data.
3. **Silent failures** — pinned/excluded overlap, fields=unknown_preset, provider_search empty query, sequence_optimize template name, set.template_name on create+update, provider_search type=all aggregation.
4. **Type coercion** — Decimal → JSON string for ``avg(integer)``.
5. **Cross-domain validation** — set.template_name registry check on both create and update dispatchers.
6. **Drift sync** — ``EntityRegistry.filterable_fields`` synced on each entity to match the live filter schema.

### Outstanding work (operations, not code)

- ``track_feedback.kind`` column missing in production Supabase (declared on ORM)
- ``track_affinity.positive_count`` / ``negative_count`` missing in production Supabase

Apply Alembic migrations to sync. Code path is correct; the production schema lagged.

### Tests
- 930 passed, no regressions in this release.
- ``make check`` clean.

## [1.2.27] - 2026-04-27

**Audit-fix loop, iteration 27.** AudioFileUpdate widening + SetVersionFilter id range.

### Fixed
- ``AudioFileUpdate`` accepts ``bitrate``, ``sample_rate``, ``channels`` with sane bounds (8-2000 kbps, 8-384 kHz, 1-8 channels). Tag analysis runs that detect these properties post-import had no way to write them back through ``entity_update``.
- ``SetVersionFilter`` accepts ``id__gt/gte/lt/lte`` for paging through versions.

### Tests
- 927 -> **930 passed**.
- ``make check`` clean.

## [1.2.26] - 2026-04-27

**Audit-fix loop, iteration 26.** ``entity_update(set, ...)`` mirror of v1.2.16's create-side template validation.

### Fixed
- **T-26:** ``entity_update(set, {template_name: 'bogus'})`` silently overwrote the set's template_name with the bogus string. v1.2.16 added template-name validation to the create dispatcher; the update dispatcher had no equivalent check, so the same bug class re-surfaced through the update path. Validation now mirrors create-side: bogus template_name raises ``ValidationError``; valid names pass through to the repo.

### Tests
- 925 -> **927 passed**.
- ``make check`` clean.

## [1.2.25] - 2026-04-27

**Audit-fix loop, iteration 25.** TrackFeaturesFilter scalar/confidence widening - the analytics-quality filters.

### Fixed
- ``TrackFeaturesFilter`` accepts ``mood_confidence__gte/lte`` ("exclude low-confidence mood classifications") + ``mood__isnull`` + ``energy_mean``, ``spectral_centroid_hz``, ``hp_ratio``, ``kick_prominence`` (gte/lte each). The canonical "filter analytics-grade tracks" query is now expressible directly through entity_list.

### Tests
- 914 -> **925 passed** (+11 parametrized lookup tests).
- ``make check`` clean.

## [1.2.24] - 2026-04-27

**Audit-fix loop, iteration 24.** ScoringProfileFilter weight lookups + id family.

### Fixed
- ``ScoringProfileFilter`` accepts ``id__eq/in`` and ``__gte/lte`` for all 6 weight columns. ``EntityRegistry.scoring_profile.filterable_fields`` synced.

### Tests
- 907 -> **914 passed**.
- ``make check`` clean.

## [1.2.23] - 2026-04-27

**Audit-fix loop, iteration 23.** TransitionHistoryFilter component scores + tempo_match_ratio - mirrors the v1.2.22 symmetry.

### Fixed
- ``TransitionHistoryFilter`` accepts ``__gte/lte`` for all 6 component scores and ``tempo_match_ratio``. The analytics surface ("which logged transitions had high BPM compatibility but the DJ rated them poorly?") is now expressible.

### Tests
- 900 -> **907 passed** (+7 component-score parametrized tests).
- ``make check`` clean.

## [1.2.22] - 2026-04-27

**Audit-fix loop, iteration 22.** TransitionFilter component scores + fx_type, TransitionHistoryFilter duration_sec.

### Fixed
- ``TransitionFilter`` adds ``__gte/lte`` for all 6 component scores (``bpm_score, harmonic_score, energy_score, spectral_score, groove_score, timbral_score``). Canonical scoring-debug queries ("find pairs with high BPM compatibility but weak harmonic") are now expressible directly through ``entity_list``.
- ``TransitionFilter`` adds ``fx_type__eq/in`` so callers can filter persisted transitions by the recommended mix style (``long_blend``, ``bass_swap_short``, ``echo_out``, ...).
- ``TransitionHistoryFilter`` adds ``duration_sec__gte/lte/range`` for "find transitions over 60 seconds long" queries.

### Tests
- 891 -> **900 passed** (+9 component-score parametrized tests).
- ``make check`` clean.

## [1.2.21] - 2026-04-27

**Audit-fix loop, iteration 21.** TransitionHistoryFilter and PlaylistFilter widening.

### Fixed
- ``TransitionHistoryFilter.style`` (eq, in, icontains) - "find transitions where the DJ used a long_blend / bass_swap_short / echo_out" was rejected.
- ``PlaylistFilter.name__startswith`` - "find all Subgenre: ..." playlists, complementing the existing ``name__icontains``.

### Tests
- 889 -> **891 passed**.
- ``make check`` clean.

## [1.2.20] - 2026-04-27

**Audit-fix loop, iteration 20.** Found a non-schema bug for the first time in many iterations.

### Fixed
- **T-21:** ``provider_search(type='all')`` silently returned ``{total: 0, items: []}`` regardless of the query. The parser read ``raw.get('results')`` while YM (and most providers) return a sectioned shape ``{tracks: {results, total}, albums: {results, total}, artists: {...}, playlists: {...}}``. Now ``type='all'`` aggregates items across every section and tags each result with ``_section`` so callers can disambiguate which kind of object each row is. ``total`` sums the per-section totals.

### Tests
- 886 -> **889 passed** (+3 type-all aggregation tests).
- ``make check`` clean.

## [1.2.19] - 2026-04-27

**Audit-fix loop, iteration 19.** 3 more filter schemas underspec'd vs canonical "filter audio quality" / "find rejected pairs" queries.

### Fixed
- ``AudioFileFilter`` adds ``sample_rate (eq, in)`` and ``channels (eq)`` for separating studio-quality from streaming-quality files.
- ``TransitionFilter`` adds ``reject_reason (icontains, isnull)`` so "find all pairs rejected for BPM diff" / "list pairs that didn't get rejected" become single-call entity_list queries instead of full-table scans + Python filtering.
- ``EntityRegistry.audio_file.filterable_fields`` and ``EntityRegistry.transition.filterable_fields`` synced.

### Tests
- 883 -> **886 passed**.
- ``make check`` clean.

## [1.2.18] - 2026-04-27

**Audit-fix loop, iteration 18.** Live-MCP probe with ``avg(key_code)`` returned ``"9.16472..."`` (string) instead of ``9.16472`` (float).

### Fixed
- **T-18:** ``BaseRepository.aggregate`` coerces ``Decimal`` → ``float`` for ``avg`` and ``→ int`` for ``count``. Postgres ``AVG(integer_column)`` returns ``NUMERIC``; asyncpg surfaces it as ``Decimal``; Pydantic JSON-serialises ``Decimal`` as a quoted string. Callers expecting numbers got strings and couldn't compute without an extra parse step. SQLite returns ``float`` natively so unit tests didn't catch it.

### Tests
- 881 -> **883 passed**.
- ``make check`` clean.

## [1.2.17] - 2026-04-27

**Audit-fix loop, iteration 17.** ``SetFilter`` rejected target_bpm and target_duration range queries even though ``SetView`` exposes all three columns.

### Fixed
- **T-17:** ``SetFilter`` accepts ``target_bpm_min__gte/lte``, ``target_bpm_max__gte/lte``, and ``target_duration_ms__gte/lte``. ``EntityRegistry.set.filterable_fields`` synced.

### Tests
- 879 -> **881 passed**.
- ``make check`` clean.

## [1.2.16] - 2026-04-27

**Audit-fix loop, iteration 16.** Re-opened after v1.2.15's "TRUE convergence" marker — deeper CRUD probe found one more silent-accept on cross-domain references.

### Fixed
- **T-16:** ``entity_create(set, {template_name: 'bogus_template_xyz'})`` silently created the set with the bogus template name. Same anti-pattern as v1.2.12's ``sequence_optimize`` template fix - dispatcher accepted a free-form string that the optimizer would later reject. Validation now runs at the ``entity_create`` dispatcher (not in ``SetCreate`` itself, because schemas can't import ``app.domain`` per the v2-server import contract). Bogus template_name raises ``ValidationError`` listing the valid set; absent / null template stays accepted.

### Tests
- 877 -> **879 passed** (+2 dispatcher + schema regression tests).
- ``make check`` clean.

### Note
v1.2.15's "TRULY converged" claim was premature - one more silent-accept found in iter 16. Convergence verification is a moving target: each iteration that introduces a new probe area can surface a new bug. The loop continues.

## [1.2.15] - 2026-04-27

**Audit-fix loop, iterations 14-15 — TRULY CONVERGED.** Two consecutive clean iterations against live MCP after the v1.2.14 sweep. No code changes; the release exists to mark the convergence point.

### Final loop summary (v1.2.0 → v1.2.15)

15 patches across 15 iterations of the audit-fix loop. Cumulative test count: 826 → **877 passed** (+51 regression tests across 16 new test files).

| Iter | Release | Bugs closed |
|---|---|---|
| 0 | v1.2.0 | 5 bug classes (A/B/C/D/F) + 4 observations from initial manual audit |
| - | v1.2.1 | has_features dispatcher path (audit residual) |
| 1 | v1.2.2 | UI dashboard / camelot wheel 10000-row cap; bpm bucket order |
| 2 | v1.2.3 | ui_library_audit hardcoded 500-row cap |
| 3 | v1.2.4 | compute tools reject duplicate track_ids |
| 4 | v1.2.5 | aggregate sum/avg numeric type pre-validation |
| 5 | v1.2.6 | sequence_optimize pinned/excluded overlap, fields validation, provider_search empty query |
| 6 | v1.2.7 | TrackFeaturesFilter widening (key_code, lufs) |
| 6c | v1.2.8 | TrackFeedbackFilter widening + filterable_fields drift |
| 7 | v1.2.9 | TransitionFilter widening (hard_reject) |
| 8 | v1.2.10 | SetVersion / AudioFile widening + reject_reason on TransitionView |
| 9-10 | v1.2.11 | first stabilization marker |
| 11 | v1.2.12 | sequence_optimize template parameter validation + threading |
| 12 | v1.2.13 | SetFilter widening (template_name__in, source_playlist_id__in) |
| 13 | v1.2.14 | batched widening (Track sort_title, SetVersion label, AudioFile bitrate, TransitionHistory range) |
| 14-15 | v1.2.15 | TRUE convergence (no new code bugs) |

### Outstanding work (not code)

Two pre-existing Postgres migration drifts deferred as operations work:
- ``track_feedback.kind`` (declared iter 7)
- ``track_affinity.positive_count`` / ``negative_count`` (declared iter 9)

Apply Alembic to sync.

### Tests
- 873 -> 877 passed (no change in this release).
- ``make check`` clean.

## [1.2.14] - 2026-04-27

**Audit-fix loop, iteration 13.** Systematic sweep across remaining filter schemas - 4 widenings batched into one release instead of one-per-iteration.

### Fixed
- ``TrackFilter.sort_title__icontains`` (the canonical "find by sort name" query was rejected).
- ``SetVersionFilter.label__eq`` (only the icontains form was declared).
- ``AudioFileFilter.bitrate__eq/gte/lte`` (no bitrate lookups existed at all).
- ``TransitionHistoryFilter.overall_score__lte/range`` (only ``__gte`` was declared).

### Tests
- 873 -> **877 passed**.
- ``make check`` clean.

## [1.2.13] - 2026-04-27

**Audit-fix loop, iteration 12.** ``SetFilter`` rejected ``template_name__in`` ("show me sets built with classic_60 or peak_hour_60").

### Fixed
- ``SetFilter`` now accepts ``template_name__in`` and ``source_playlist_id__in``. ``EntityRegistry.set.filterable_fields`` synced.

### Tests
- 871 -> **873 passed**.
- ``make check`` clean.

## [1.2.12] - 2026-04-27

**Audit-fix loop, iteration 11.** Re-opened after v1.2.11 stabilization marker — deeper probe found one more declared-but-unused parameter.

### Fixed
- **T-14:** ``sequence_optimize(template='bogus')`` was silently accepted. The tool's ``template`` parameter was exposed but the call hardcoded ``template=None`` to the optimizer, so the result was identical with and without the argument. Now invalid template names raise ``ValidationError`` listing valid options, and valid names resolve via ``app.domain.template.registry.get_template`` to a real ``SetTemplateDefinition`` that's threaded into the optimizer call. Template-aware fitness inside the GA is still gated on Phase 6, but at least the parameter contract holds and prompts that recommend ``template='classic_60'`` work end-to-end without silent ignore.

### Tests
- 868 -> **871 passed** (+3 template validation tests).
- ``make check`` clean.

## [1.2.11] - 2026-04-27

**Audit-fix loop, iterations 9-10 — STABILIZED.** Two consecutive clean iterations against live MCP found no new code bugs; only Postgres-side migration drift on two columns (``track_feedback.kind`` declared in iter 7 + ``track_affinity.positive_count`` / ``negative_count`` declared here). Loop terminates.

### Audit summary (v1.2.0 → v1.2.11)

11 patches across 10 iterations of the audit-fix loop. Cumulative test count: 826 → **868 passed** (+42 regression tests across 12 new test files). Each fix landed via TDD red→green and live-MCP verification after a fresh respawn.

| Iter | Release | Findings closed |
|---|---|---|
| 0 | v1.2.0 | 5 bug classes (A/B/C/D/F) + 4 observations from manual audit |
| - | v1.2.1 | has_features dispatcher path (audit residual) |
| 1 | v1.2.2 | UI dashboard + camelot wheel 10000-row cap; bpm bucket order |
| 2 | v1.2.3 | ui_library_audit hardcoded 500-row cap |
| 3 | v1.2.4 | compute tools reject duplicate track_ids consistently |
| 4 | v1.2.5 | aggregate sum/avg pre-validates numeric column type |
| 5 | v1.2.6 | sequence_optimize pinned/excluded overlap, fields validation, provider_search empty query |
| 6 | v1.2.7 | TrackFeaturesFilter widening (key_code, integrated_lufs) |
| 6c | v1.2.8 | TrackFeedbackFilter widening + filterable_fields drift sync |
| 7 | v1.2.9 | TransitionFilter widening (hard_reject) |
| 8 | v1.2.10 | SetVersionFilter, AudioFileFilter widening + reject_reason on TransitionView |
| 9-10 | v1.2.11 | (no new code bugs — stabilized) |

### Documented operations issues (deferred — not code bugs)

These surface as ``UndefinedColumnError`` on live ``entity_list`` calls but the ORM declarations are correct; the production Supabase schema has lagged the model migrations. Apply Alembic to sync.

- ``track_feedback.kind`` (declared iter 7)
- ``track_affinity.positive_count``, ``track_affinity.negative_count`` (declared iter 9)

Same class as the drop-pending tables already documented in CLAUDE.md.

## [1.2.10] - 2026-04-27

**Audit-fix loop, iteration 8.** Three more filter schemas were underspec'd vs canonical scoring/library queries, plus ``TransitionView`` was missing ``reject_reason``.

### Fixed
- ``SetVersionFilter`` accepts ``quality_score__gte/lte/range`` ("show me set versions with quality >= 0.7" was rejected).
- ``AudioFileFilter`` accepts ``file_size__gte/lte/range`` (range queries to find suspect files).
- ``TransitionView`` declares ``reject_reason`` so ``entity_get(transition, id)`` exposes WHY a pair was hard-rejected. The column already existed on the ORM and the resource layer; only the entity DTO was missing it.
- ``EntityRegistry.set_version.filterable_fields`` and ``EntityRegistry.audio_file.filterable_fields`` synced with the new lookups.

### Tests
- 864 -> **868 passed**.
- ``make check`` clean.

## [1.2.9] - 2026-04-27

**Audit-fix loop, iteration 7.** ``TransitionFilter`` rejected ``hard_reject__eq``, the canonical "show me hard-reject transitions" query.

### Fixed
- ``TransitionFilter`` now accepts ``hard_reject__eq`` and ``overall_quality__range``. ``EntityRegistry.transition.filterable_fields`` synced.

### Known operations issue (deferred)
- ``entity_list(track_feedback, ...)`` against the production Supabase DB raises ``column track_feedback.kind does not exist`` - the ORM model declares ``kind: String(10)`` but the live table is missing the column. This is migration drift, not a code bug. Documented here so the fix can be scheduled as an Alembic migration apply rather than mistaken for a v1.2.x regression. Same class as the drop-pending tables in CLAUDE.md.

### Tests
- 860 -> **864 passed**.
- ``make check`` clean.

## [1.2.8] - 2026-04-27

**Audit-fix loop, iteration 6 cont.** ``TrackFeedbackFilter`` rejected the canonical ``rating__gte`` query and ``schema://entities/track_features.filterable_fields`` was stale relative to v1.2.7's TrackFeaturesFilter widening — same drift class.

### Fixed
- ``TrackFeedbackFilter`` now declares ``rating__eq/gte/lte/in`` and ``kind__in``.
- ``EntityRegistry.track_features.filterable_fields`` synced with the filter schema: now lists ``key_code (eq/in/range)``, ``integrated_lufs (gte/lte/range)``, and ``analysis_level (eq/gte/lt)`` so introspection clients see the real filter contract instead of a stale subset.
- ``EntityRegistry.track_feedback.filterable_fields`` similarly synced with the new rating + kind__in lookups.

### Tests
- 854 -> **860 passed**.
- ``make check`` clean.

## [1.2.7] - 2026-04-27

**Audit-fix loop, iteration 6.** Same class as Bug A from v1.2.0 (filter underspec): ``TrackFeaturesFilter`` rejected ``key_code__in`` even though every harmonic compatibility query needs it.

### Fixed
- ``TrackFeaturesFilter`` now accepts ``key_code__eq``, ``key_code__in``, ``key_code__range``, plus ``integrated_lufs__gte``, ``integrated_lufs__lte``, ``integrated_lufs__range``. ``find tracks in 8A or 8B with LUFS between -14 and -8`` is now expressible directly through ``entity_list``.

### Tests
- 847 -> **854 passed**.
- ``make check`` clean.

## [1.2.6] - 2026-04-27

**Audit-fix loop, iteration 5.** Three more silent-failure modes turned up in deeper edge probes — same anti-pattern across the surface: inputs that should be rejected up front instead leaked raw Python errors or quietly produced empty/contradictory results.

### Fixed
- **T-2:** ``sequence_optimize(pinned=[146,147], excluded=[146])`` no longer silently lets pinned win. Pinned ∩ excluded overlap raises ``ValidationError`` listing the conflicting ids.
- **T-3:** ``entity_get`` / ``entity_list`` with an unknown ``fields`` preset name (e.g. ``fields="unknown_preset"``) no longer falls through the CSV path and projects ``{single_token}`` against a model that has no such field — which produced ``[{},{},{},{},{}]`` (5 empty rows). ``resolve_field_projection`` now validates every field name against the view schema and raises ``ValidationError`` with the bad names.
- **T-4:** ``provider_search(query='')`` no longer leaks ``'str' object has no attribute 'get'`` from the YM client. Empty / whitespace-only queries fail fast with a typed error.

### Added
- ``tests/tools/test_iter5_silent_failures.py`` - 6 regression tests covering all three failures + sanity-positive paths.

### Tests
- 841 -> **847 passed**.
- ``make check`` clean.

## [1.2.5] - 2026-04-27

**Audit-fix loop, iteration 4.** Live MCP probe of ``entity_aggregate(track, avg, field='title')`` returned a raw asyncpg error: ``function avg(character varying) does not exist``. SQL backend errors should not surface to MCP clients — type validation belongs at the dispatcher / repo layer.

### Fixed
- ``BaseRepository.aggregate`` validates the column's Python type up front for ``sum`` / ``avg``. Non-numeric columns raise a clean ``ValidationError`` ("operation 'avg' requires a numeric field; 'title' has type str") instead of letting Postgres complain about a missing function. ``count`` / ``distinct`` / ``min_max`` / ``histogram`` are unchanged - lex min/max and discrete histograms over strings remain meaningful.

### Added
- ``tests/repositories/test_aggregate_type_check.py`` - 6 regression tests covering sum/avg type rejection, numeric sanity, plus distinct/min_max/count negative-space.

### Tests
- 835 -> **841 passed**.
- ``make check`` clean.

## [1.2.4] - 2026-04-27

**Audit-fix loop, iteration 3.** Live MCP probe with ``track_ids=[146, 146, 147]`` caught two compute tools disagreeing on duplicate-id semantics.

### Fixed
- ``transition_score_pool`` no longer counts duplicates as distinct slots in the N*(N-1) matrix - same input as ``sequence_optimize`` now produces a clear ValidationError naming the duplicate ids.
- ``sequence_optimize`` no longer silently dedupes through ``set()`` inside the optimizer. Same explicit ValidationError. The two compute tools now share input semantics; consumers know when their pool has accidental repetitions instead of getting two different answers from the same input.

### Added
- ``tests/tools/compute/test_duplicate_track_ids.py`` - regression coverage for both tools rejecting duplicates and accepting unique pools.

### Tests
- 832 -> **835 passed**.
- ``make check`` clean.

## [1.2.3] - 2026-04-27

**Audit-fix loop, iteration 2.** Same class as iter 1 (silent caps in UI tools), one cap location: ``ui_library_audit`` whole-library scope hardcoded ``limit=500``, reporting ``total_tracks: 500`` for a 24k library with no way for the caller to know they saw a 2% sample.

### Fixed
- ``ui_library_audit`` whole-library scope now exposes a configurable ``limit`` (default 5000, max 50000) and the response carries ``truncated``, ``library_size``, and ``limit`` so consumers can detect partial coverage. Per-playlist scope is still bounded by membership and reports ``truncated=null``.

### Added
- ``tests/tools/ui/test_library_audit_cap.py`` - regression coverage: default cap honoured, explicit limit above library size returns all tracks with ``truncated=False``, per-playlist scope ignores ``limit`` and ``truncated`` is null.

### Tests
- 829 -> **832 passed**.
- ``make check`` clean.

## [1.2.2] - 2026-04-27

**Audit-fix loop, iteration 1.** Broader probes against the live MCP turned up two silent data-loss bugs in the Prefab UI tools that had aged badly with the library: ``ui_library_dashboard`` and ``ui_camelot_wheel`` capped at 10000 rows. Production library is now 24k+ — both dashboards reported numbers about the first ~10k tracks while pretending to summarise the whole library.

### Fixed
- ``ui_library_dashboard._gather`` no longer hard-caps at ``LIMIT 10000``. ``mood_distribution`` and ``camelot_distribution`` now sum to the full analyzed-track count instead of stopping at 10000. Three tiny columns over 24k rows is ~700 KB — the cap was a pre-scale paranoia that became a silent regression.
- ``ui_library_dashboard.bpm_histogram`` is emitted in ascending bucket order (``<110, 110-119, ..., >=150``). Prior version returned ``Counter(...)`` insertion order, which scrambled the chart on Prefab-blind clients consuming the JSON fallback directly.
- ``ui_camelot_wheel`` whole-library scope queries ``track_audio_features_computed`` directly instead of going through ``tracks.filter(limit=10000)`` -> ``IN(...)``. Same root cause, same impact: numbers reflected the first ~10k tracks, not the whole library.

### Added
- ``tests/tools/ui/test_dashboard_caps_and_order.py`` - regression coverage for the bucket order and the no-cap path. Live MCP probe re-verifies the totals.

### Tests
- 826 -> **829 passed** (+3 dashboard regression tests).
- ``make check`` clean.

## [1.2.1] - 2026-04-27

**End-to-end verification follow-up to v1.2.0.** Live-MCP probe after the v1.2.0 release caught one residual bug class A symptom that the unit tests missed: ``has_features`` survived schema validation directly and survived the repository, but the ``entity_list`` dispatcher's ``normalize_bare_fields`` step in between rewrote ``has_features`` to ``has_features__eq`` before the schema saw it, and ``TrackFilter`` only declared the bare form. Real callers continued to get ``extra_forbidden`` despite v1.2.0.

### Fixed
- ``TrackFilter`` now declares both ``has_features`` and ``has_features__eq`` so the post-normalize shape passes validation. Repository already pops either form. Bug class same as v1.0.13: declared but not enforced — fix lives at the layer the user actually touches (the dispatcher).

### Added
- ``tests/tools/entity/test_has_features_dispatcher.py`` — end-to-end test that runs ``normalize_bare_fields`` against the schema, plus a dispatcher-level call. Pins the full path that the audit's manual probe exercises.

### Tests
- 823 → **826 passed** (+3 dispatcher coverage tests).
- ``make check`` clean.

## [1.2.0] - 2026-04-27

**Audit-driven sweep — closes 5 bug classes + 4 observations from the v1.1.0 manual MCP-surface audit.** v1.1.0 hardened the transport layer; this MINOR addresses the bug classes that hard-data probing of the live system surfaced that unit tests couldn't catch. Each fix landed via TDD red-green and ships with regression coverage. Net +48 tests in the suite (775 → 823).

Audit doc: `docs/audit/2026-04-27-mcp-surface-audit-v1.1.0.md`.

### Fixed (5 bug classes)

- **Bug A — TrackFilter underspecification.** Schema rejected three documented probe shapes: `id__gt/gte/lt/lte` for paging/range queries, `title__contains` (case-sensitive complement to `title__icontains`), and `has_features` — the magic boolean filter promised in `.claude/rules/repositories.md`. Schema now declares the missing lookups (still `extra="forbid"`); `TrackRepository.filter` translates `has_features` into the appropriate (NOT) EXISTS subquery against `track_audio_features_computed` and composes cleanly with other lookups.
- **Bug B — `entity_get` / `entity_list` default projection.** `default_preset="id"` made every response without explicit `fields=` collapse to `{"id": N}` — a UX regression vs pre-v1.0.13 when projection was advertised but not applied. All 11 registered entities now default to `"full"`, restoring the historic view-shape contract. New regression test asserts every default_preset is `"full"` so future entities don't backslide.
- **Bug C — Stale persisted transitions.** `local://transition/{a}/{b}/score` and `/explain` for the same pair returned different `overall` values because `/score` short-circuited to a persisted row from the `transitions` table that goes stale once `track_features_reanalyze_handler` raises a track to a higher analysis level (no cascade invalidation). The standalone resource now always recomputes via `TransitionScorer` (≈1 ms/pair); the persisted table remains the source of truth for set composition history. `/score` and `/explain` agree by construction.
- **Bug D — Prompt content correctness.** Four content drift issues across `build_set_workflow`, `deliver_set_workflow`, `expand_playlist_workflow`, and `full_pipeline` told the LLM to call non-existent surface (`entity='app_export'`, `provider_read(entity='similar_tracks')`, `entity_list(entity='track', fields='scoring')`). Strings corrected to match the live registry (`track_features` for the scoring projection, `track_similar` for the YM adapter, dropped `app_export` references in favour of client-side artefact assembly from existing resources until a server-side delivery handler ships).
- **Bug F — `schema://providers/yandex` introspection.** `entities_supported` returned a hardcoded fallback list missing `track_batch`, `track_similar`, `artist_tracks`, `playlist_list`, and `dislikes`. `YandexAdapter` now declares the canonical list as a `ClassVar`; the resource fallback drops the lying default in favour of an empty tuple.

### Fixed (4 observations)

- **O-1 — `local://tracks/{id}.primary_artist_name` always null.** `TrackView.from_attributes` looked for a column that doesn't exist on `Track`. Repository now exposes `get_primary_artist_name` (primary role with first-artist fallback) and the resource injects it after `model_validate`.
- **O-2 — `local://transition_history/best_pairs` ordered NULL scores first.** Postgres puts NULL first under `DESC` by default; SQLite hides this. Repository query now uses `.desc().nulls_last()`. New test compiles the SELECT against the Postgres dialect to guard the clause regardless of test backend.
- **O-3 — Empty `suggest_next` / `suggest_replacement` were ambiguous.** Added `reason: str | None` to both views. `None` when the empty result is legitimate (no candidates), a short string when there's a structural cause (no logged history, repo gap, energy filter rejected all, no features on target, no library tracks within ±2 BPM, …).
- **O-4 — `local://playlists/{id}/audit` reported `total_tracks: 0` for non-empty playlists.** The resource called `getattr(uow.playlists, "get_items", None)` and fell back to `[]` because the method was missing. Added `get_items` next to the existing `get_track_ids` (audit needs full items for per-track entries).

### Added

- New CI guard: `tests/prompts/test_prompt_content_correctness.py` renders every workflow prompt and cross-checks each `entity='...'` reference against `EntityRegistry`, each `provider_read(entity=...)` against `YandexAdapter.entities_supported`, and each `fields='<preset>'` against the entity's declared presets. Prompt drift fails CI.
- New regression test files: `tests/schemas/test_track_filter.py`, `tests/repositories/test_track_has_features_filter.py`, `tests/repositories/test_track_primary_artist.py`, `tests/repositories/test_playlist_get_items.py`, `tests/repositories/test_transition_history_best_pairs_order.py`, `tests/resources/test_transition_score_freshness.py`, `tests/resources/test_suggest_reason.py`, `tests/resources/test_track_resource_artist.py`.
- `YandexAdapter.entities_supported` ClassVar — single source of truth for `schema://providers/yandex`.

### Tests

- **823 passed** (was 775 at v1.1.0 — +48 new tests, ~1 ms/pair scorer regression covered, no SQLite-vs-Postgres drift left in the queries that matter).
- `make check` clean: ruff + mypy strict + import-linter (5 contracts kept) + pytest 18.8s.
- 3 SKIPPED (integration suite without `DJ_YM_TOKEN`), 44 xfailed, 20 xpassed — same baseline as v1.1.0.

## [1.1.0] - 2026-04-27

**Architectural hardening: closes the v1.0.10-v1.0.13 bug class at the architecture level.** The four PATCH releases that preceded this MINOR each fixed a different surface symptom of the same underlying problem: the FastMCP in-memory test client and the Claude Code stdio shim transport are not isomorphic, and the test suite was blind to it. This release replaces bug-by-bug patching with three system-level safeguards: (1) server-side coercion middleware, (2) stringified-args test fixture, (3) integration round-trip tests against real YM.

Also implemented as part of `superpowers:writing-plans` -> `test-driven-development` cycle (plan saved at `docs/superpowers/plans/2026-04-27-v1.1.0-architectural-hardening.md`).

### Added
- `app/server/middleware/json_string_coerce.py` - new `JsonStringCoerceMiddleware` (16th in the chain, position #2 after `DomainErrorMiddleware`). Inspects each tool's `inputSchema` and coerces stringified `array`/`object` args to native types before Pydantic validation. New tools no longer need per-param `JsonIntList` / `JsonStrListOrNone` / `JsonDictOrNone` opt-in helpers - existing tools keep them as belt-and-suspenders (coercing twice is idempotent).
- `tests/tools/conftest.py` - new `_StringifyingClientProxy` + `stringified_mcp_client` fixture that wraps `fastmcp.Client.call_tool` to JSON-stringify dict/list args before sending. Reproduces Claude Code stdio shim's transport quirk so transport-asymmetry regressions get caught in CI.
- `tests/tools/entity/test_get_transport_parity.py` - 4 tests pinning that `entity_get(include_relations=…)` and `entity_list(filters=…)` work under both native and stringified transport, even with the middleware absent (server tests run with `with_middleware=False`).
- `tests/providers/yandex/test_yandex_integration.py` - 3 round-trip tests against real `api.music.yandex.net` covering `provider_search`, `provider_read(likes)`, and `provider_write(playlist create+delete)`. Pins the v1.0.12 bare-`"ok"` shape that crashed the dispatcher before. Marker `pytest.mark.integration` + `skipif(not DJ_YM_TOKEN)` so CI without secrets stays green.
- `[tool.pytest.ini_options].markers` += `"integration: live external-service round-trips, skipped without secrets"`.

### Changed
- `app/server/middleware/__init__.py` - middleware chain length 15 -> 16; `JsonStringCoerceMiddleware` registered at position #2 so every other middleware (audit log, response cache, DB session, …) sees already-coerced args.
- `tests/server/test_ordering.py` - asserts `len(ALL_MIDDLEWARE) == 16` and the new ordering.

### Tests
- **775 passed** (was 761 at v1.0.13), +3 integration SKIPPED without YM token, +44 xfailed, +20 xpassed.
- `make check` clean: ruff + mypy strict (242 files) + import-linter (5 contracts kept) + pytest 23.6s.
- Live integration suite passes against real YM when `DJ_YM_TOKEN` is set: 3/3 PASSED.

### Architecture verdict
- v1.1.0 closes the bug class introduced in v1.0.10 and revisited in v1.0.11/v1.0.12/v1.0.13. New tools added with `Annotated[list[X], …]` or `Annotated[dict[str, Any], …]` are now safe by default.
- The `Json*` per-param helpers in `app/shared/types.py` remain in place but are no longer mandatory.

## [1.0.13] - 2026-04-27

**Fix: implement `entity_list` / `entity_get` field projection** — `fields=…` parameter was declared in tool signatures since v1.0 but **never applied** to responses. Every call returned the full row regardless of what the caller asked for. Discovered by `superpowers:systematic-debugging` skill during architectural review of the v1.0.10–v1.0.12 patch streak.

### Fixed
- `app/registry/entity.py` — new `resolve_field_projection(fields, config)` helper accepts four input shapes the dispatcher might see in production: preset name (`"id"`/`"ref"`/`"summary"`/`"full"`), native list, JSON-encoded list (Claude Code stdio transport), CSV. Returns `set[str]` for projection or `None` to signal "full row" (skip projection).
- `app/tools/entity/get.py` — applies projection via `view.model_dump(include=projection)`; falls back to full dump when projection is `None`.
- `app/tools/entity/list.py` — same projection applied per-row in the list comprehension.

### Added
- `tests/registry/test_field_projection.py` — 12 tests pinning every input shape (None default, preset name, full preset, native list, JSON-string, CSV, whitespace, empty inputs, malformed JSON fallback).

### Tests
- **761 passed** (was 749 at v1.0.12) — +12 regression tests.
- `make check` clean: ruff + mypy strict (241 files) + import-linter + pytest 14.0s.

### Known deferred (v1.1.0)
- Server-side input-coercion middleware to replace per-param `Json*` helpers (would have caught v1.0.10–v1.0.13 transport bugs at architecture level).
- Stringified-args test fixture to reproduce Claude Code stdio transport quirk in CI.
- Integration round-trip tests against real YM (would have caught v1.0.12 `ProviderWriteResult.data` shape mismatch).

## [1.0.12] — 2026-04-27

**Fix: `ProviderWriteResult.data` accepts bare string for YM delete** — completing the manual MCP-surface audit (now 20/20 dispatchers). YM `playlist delete` returns the bare string `"ok"` instead of a dict; the dispatcher previously crashed on response serialization with `Input should be a valid dictionary [type=dict_type]` even though the YM-side delete had already succeeded.

### Fixed
- `app/schemas/provider_dto.py` — `ProviderWriteResult.data` Union extended `dict[str, Any] | str`. The mismatch was invisible to the test suite because round-trip integration tests for `provider_write(playlist, delete)` against a real YM account didn't exist.

### Added
- `tests/schemas/test_tool_responses.py::test_provider_write_result_accepts_string_data` — regression test pinning the string variant.

### Tests
- **749 passed** (was 748 at v1.0.11) — +1 regression test.
- `make check` clean.

### MCP-surface audit closed
- **20 / 20 dispatchers verified end-to-end on live data** (was 18 / 20 at v1.0.11).
- `entity_delete`: round-trip via throwaway local playlist (count 19 → 20 → 19).
- `provider_write`: round-trip via throwaway YM playlist (`create kind=1387` → `delete data="ok"`).

## [1.0.11] — 2026-04-27

**Fix: extend JSON-string transport coercion to `get_prompt(arguments=…)`** — final residual JSON-string transport bug discovered during continuation of the manual MCP-surface audit. v1.0.10 covered tool params; this release covers the prompt path through FastMCP's stock `PromptsAsTools` transform, which used `dict[str, Any] | None` without a `BeforeValidator` and crashed on every Claude Code prompt invocation.

### Fixed
- `app/server/json_aware_prompts.py` (new) — `JSONAwarePromptsAsTools` subclass overrides `_make_get_prompt_tool` so `arguments` accepts EITHER a native dict OR a JSON-encoded string, via `app/shared/types.py:JsonDictOrNone`. Mirrors the existing `JSONAwareResourcesAsTools` pattern. `list_prompts` is preserved unchanged through `super()`.
- `app/server/transforms.py` — registration switched from upstream `PromptsAsTools` to `JSONAwarePromptsAsTools`.

### Added
- `tests/server/test_json_aware_prompts.py` — 3 regression tests covering native-dict, JSON-string, and no-args prompt rendering.

### Tests
- **748 passed** (was 745 at v1.0.10) — +3 regression tests.
- `make check` clean: ruff, mypy strict (240 files), import-linter (5 contracts kept), pytest.

## [1.0.10] — 2026-04-27

**Fix: align MCP tool list-params with Claude Code's JSON-string transport** — manual end-to-end MCP-surface audit (post-v1.0.9 install) hit three latent type-mismatch bugs the test suite missed because in-memory FastMCP `Client` always passes native types, while the real Claude Code stdio transport stringifies complex args. Production tools were silently broken on every list-typed parameter call.

### Fixed
- `app/schemas/tool_responses.py` — `AggregateResult.value` Union extended with `list[int | float | str | None]` so `entity_aggregate(operation="distinct", field="mood")` doesn't crash with 16-error pydantic ValidationError. Previously only `int | float | list[dict[str, Any]] | dict[str, Any]` was accepted, so distinct over any scalar column (mood, key_code, ...) returned a `list[scalar]` that matched no Union variant.
- `app/tools/entity/get.py` — `include_relations` retyped from `list[str] | None` → `JsonStrListOrNone`. Claude Code MCP shim sends `'["features", "artists"]'` as a JSON-encoded string for complex args; pydantic then crashed with `Input should be a valid list [type=list_type]`. The `JsonStrListOrNone` BeforeValidator (already present in `app/shared/types.py` for the same reason on dict-typed params) coerces the string before validation.
- `app/tools/compute/score_pool.py` + `app/tools/ui/score_pool_matrix.py` — `track_ids` retyped from `list[int]` → `JsonIntList`. Same root cause: `transition_score_pool` and `ui_score_pool_matrix` rejected every real Claude Code call with the JSON-string-vs-list mismatch. `sequence_optimize` already used `JsonIntList` (partial earlier migration); this completes the sweep.

### Added
- `tests/schemas/test_tool_responses.py` — `test_aggregate_result_accepts_distinct_scalar_list` regression test (str + int variants).
- `tests/tools/entity/test_get.py` — `test_include_relations_accepts_json_string` regression test for the JSON-string coercion path.

### Tests
- **745 passed** (was 743 at v1.0.9) — +2 regression tests.
- `make check` clean: ruff, mypy strict (240 files), import-linter (5 contracts kept), pytest in 16.7s.

## [1.0.9] — 2026-04-27

**Fix: align v1 entity_create surface with handler contracts** — first real-world run of `import → download → analyze → set` against a fresh user library exposed three latent schema/handler drifts that crashed every call following the schema as advertised.

### Fixed
- `app/schemas/track.py` — `TrackCreate` now requires `external_ids` (the field the `track_import` handler actually reads); the legacy `provider_ids` / lying `title` / `sort_title` / `duration_ms` / `status` "override" fields are removed because the handler unconditionally pulls them from provider metadata. Default `source` example fixed from non-existent `"yandex_music"` → `"yandex"`. `playlist_id` now properly typed (handler-level support pre-existed).
- `app/schemas/audio_file.py` — `AudioFileCreate.source` now defaults to `"yandex"` (matching `ProviderRegistry`); `model_validator(mode="after")` enforces "exactly one of `track_id` / `track_ids`" + non-empty batch at validation time so callers see a clean Pydantic error instead of a mid-handler `ValueError`.
- `app/repositories/track_features.py` — `_serialize_vectors()` helper called inside `upsert()` JSON-encodes 5 vector columns (`mfcc_vector`, `tonnetz_vector`, `tempogram_ratio_vector`, `beat_loudness_band_ratio`, `phrase_boundaries_ms`) before INSERT/UPDATE. Previously the analysis pipeline returned `list[float]` but the columns are `Mapped[str | None]` over `String(...)` — every L3 analyze crashed with `asyncpg DataError: expected str, got list`. Helper also coerces `numpy.ndarray` and `tuple` via `.tolist()` so a future analyzer that forgets the explicit conversion doesn't crash the whole sweep with an opaque `json.encoder` `TypeError`.
- `app/handlers/audio_file_download.py` — handler now accepts `track_id` (single) OR `track_ids` (batch) per schema; previously hard-failed with `KeyError: 'track_ids'` on the single form.
- `app/handlers/set_version_build.py` + `app/handlers/transition_persist.py` — extracted `persist_transition_score()` helper so both call sites route through a single source of truth instead of duplicating the 12-line `uow.transitions.upsert(...)` block.

### Added
- `app/prompts/expand_playlist_workflow.py` — recipe text updated from broken pre-v1 example (`{provider, provider_ids}`) to the actual v1 surface (`{source, external_ids}`); step numbering fixed; the obsolete `classify_mood` step removed (mood classification fires inside the analyze handler).

### Tests
- **743 passed** (was 722 at v1.0.8) — +21 regression tests:
  - `tests/schemas/test_pydantic_shapes.py` — 11 round-trip tests for `TrackCreate` / `AudioFileCreate` (required fields, defaults, legacy field rejection, xor invariant, empty batch).
  - `tests/repositories/test_track_features_repo.py` — 6 tests for `_serialize_vectors` covering list, None, already-encoded string, ndarray, tuple, and end-to-end ORM round-trip.
  - `tests/handlers/test_audio_file_download.py` — 3 tests for single-form acceptance, missing-id error, default source.
  - `tests/handlers/test_set_version_build.py` — `hard_reject=True` path test (in real libraries ~30% of pairs reject; previously only happy path was covered).

### Notes
- Dispatcher-level Pydantic validation for handler-driven entities (closing the "schema is dead code in MCP runtime" gap) was scoped out to a follow-up — it requires `DomainErrorMiddleware` to translate `pydantic_core.ValidationError` to `ToolError` so production users (where `mask_error_details=True`) see a clean message instead of `internal error`. Tracked for v1.1.0. PR #131 closed with rationale.

## [1.0.8] — 2026-04-26

**Fix: `read_resource` tool wrapper no longer returns JSON wrapped in an escaped string.**

### Fixed
- `app/server/json_aware_resources.py` (new) — `JSONAwareResourcesAsTools` replaces FastMCP's stock `ResourcesAsTools` transform. Stock transform's `read_resource` returns `str`, which FastMCP wraps in `structuredContent` as `{"result": "<json-string>"}` — every quote inside the inner JSON gets escaped on the wire (`\"`). The new transform returns a Pydantic `ReadResourceResult{uri, items: [{mime_type, data, encoding}]}` so JSON resources land in `structuredContent` as a parsed nested object. Tool-only clients (Claude Code, etc.) now see clean structured payloads.
- Workaround for upstream FastMCP 3.2.4 bug: `ResourceTemplate.convert_result` calls `ResourceResult(raw_value)` without forwarding `self.mime_type` ([fastmcp/resources/template.py:469](.venv/lib/python3.12/site-packages/fastmcp/resources/template.py)), so every templated resource (16 of 27 in this codebase) loses its declared `application/json` and arrives as `text/plain`. Heuristic JSON-parse for payloads starting with `{` or `[` recovers the mime type and produces a parsed object; non-JSON text passes through unchanged.

### Added
- `tests/server/test_json_aware_resources.py` — 8 regression tests: JSON-string, dict-return, plain text, malformed JSON, template mime-loss recovery, JSON-in-text/plain heuristic, base64 binary, schema shape.

### Changed
- `app/server/transforms.py` — swapped `ResourcesAsTools` → `JSONAwareResourcesAsTools` in `register_post_constructor_transforms`.

### Tests
- 722 passed (was 714 at v1.0.7) — all 27 resources verified end-to-end via the live MCP plugin.

## [1.0.7] — 2026-04-26

**Critical hotfix: plugin MCP stdio process crashed on startup.**

### Fixed
- `app/server/observability.py:bootstrap_observability` — `os.getenv("DJ_SENTRY_DSN")` returned the literal `"${DJ_SENTRY_DSN}"` string when the var was not set in `.env`, because FastMCP's `${VAR}` interpolation in `fastmcp.json` leaves placeholders intact for unset vars. The literal is truthy → `if dsn and ...` passed → `sentry_sdk.init(dsn="${DJ_SENTRY_DSN}")` crashed with `Unsupported scheme ''` → MCP stdio process died on import → Claude Code reported `Server "plugin:dj-music:mcp" is not connected` and **no native MCP tools were available**.
- New defensive guard `_looks_like_url(value)` rejects None / empty / whitespace / `${...}` literals / non-URL strings before passing to Sentry or OTEL.
- Same guard now applied to `DJ_OTEL_EXPORTER_OTLP_ENDPOINT`.
- 7 regression tests in `tests/server/test_observability_dsn.py`.

### Impact
Without this fix, fresh installs of the plugin (any user without `DJ_SENTRY_DSN` in `.env` — i.e. most users) could not use it from Claude Code at all — only via REST. v1.0.4 / v1.0.5 / v1.0.6 are all affected by this same bug; v1.0.7 is the first release where the plugin starts cleanly without observability env vars.

### Tests
- 714 passed (was 707 at v1.0.6).

## [1.0.6] — 2026-04-26

**Hotfix: session:// resources crashed on stateless callers.**

### Fixed
- `app/resources/session.py:_session_id` — `getattr(ctx, "session_id", None)` triggered the FastMCP v3 property descriptor that raises `RuntimeError` outside an active MCP session, so every read of `session://set-draft`, `session://tool-history`, and `session://energy-trend` returned 500 from REST/in-process callers. Wrapped in try/except so stateless callers fall back to `session_id="anonymous"`. Same pattern as the v1.0.5 sentry/cost/sampling/db_session middleware fixes — this site was missed because it lives in resource code, not middleware.
- 3 regression tests added in `tests/resources/test_session_id_helper.py` covering stateful / stateless property / missing attribute cases.

### Tests
- 707 passed (was 704 at v1.0.5).

## [1.0.5] — 2026-04-26

**Audit pass + Panel v1 rewire + Plugin packaging polish.**

### Fixed
- **MCP middleware stateless-context chain (5 bugs)** — every tool call via REST/in-process previously returned 500 with `'Context.session_id' raised RuntimeError`. Resolved across 4 middleware:
  - `sentry_context.py` — `getattr` over `session_id`/`client_id`/`request_id` properties guarded with `try/except (RuntimeError, AttributeError)`.
  - `cost_tracking.py` — `await fctx.set_state(...)` wrapped; cost telemetry skipped when no MCP session is active.
  - `sampling_budget.py` — `getattr` and `set_state` both guarded; stateless callers bucket under `__global__` with separate cap.
  - `db_session.py` — added module-level `ContextVar` (`_stateless_uow`) as a third DI fallback; `get_uow` reads it after typed paths fail. Also self-bootstraps `db_session_factory` from `app.db.session.get_session_factory()` when MCP lifespan was never entered.
- **REST stateless DI bootstrap** — `app/rest/lifespan.py` now enters MCP composed lifespan and copies yielded keys into new `app/server/_stateless_state.py`. Tools needing `provider_registry`, `audio_pipeline`, `transition_scorer`, etc. now work via REST/in-process — not just over MCP transport.
- **Real bugs surfaced by mypy `attr-defined` / `call-arg` drift**:
  - `app/tools/admin/unlock_namespace.py:62,64` — added missing `await` on `ctx.enable_components()` / `disable_components()` (FastMCP v3 made them async; coroutines were silently dropped → namespace lock/unlock no-op'd in production).
  - `app/tools/sync/playlist_sync.py` — `direction="diff"` no longer double-counts overlap (every remote_ext_id was emitted as `remote_only` regardless of local membership).
  - `app/handlers/track_import.py:80` — replaced non-existent `PlaylistRepository.add_track` with the real `append_tracks`.
  - `app/handlers/transition_persist.py:38` — added `TransitionRepository.upsert(...)` (handler referenced a non-existent method).
  - `app/handlers/audio_file_download.py:90` — widened `Provider.download_audio` Protocol to accept the `dest=` kwarg the handler actually passes.
- **Silent-failure hardening** (HIGH-severity audit findings):
  - `app/server/middleware/db_session.py` — split too-broad `except Exception` into `except ImportError` (legitimate degraded mode) vs misconfig (log ERROR with `exc_info=True` and re-raise). Bad DB URLs now fail loudly at first request.
  - `app/audio/core/loader.py` — backend chain distinguishes "library not installed" from "decode failed". Corrupt MP3s no longer silently fall through to `wave.open` with cryptic RIFF-id errors.
  - `app/audio/analyzers/base.py` — narrowed `except Exception` in `BaseAnalyzer.run()` to `(ValueError, RuntimeError, ImportError, ArithmeticError, AssertionError)`. `MemoryError` / `KeyboardInterrupt` / `SystemExit` and unknown exceptions now propagate.
  - `app/server/middleware/sampling_budget.py` — replaced unbounded `_used: dict` with `OrderedDict` LRU (`MCPSettings.sampling_buckets_max`, default 1024); added `MCPSettings.sampling_global_cap` (default 50) for stateless callers; WARN logs at 50% / 80% / 100%.

### Changed
- **`TrackFeatures` moved** `app/domain/transition/features.py` → `app/shared/features.py` (28 import sites updated atomically). Repos no longer reach into `domain` to grab a DTO. Resolves 1 of 3 import-linter violations.
- **`.importlinter`** — added narrow `ignore_imports` for the two legitimate `app.server.lifespan → app.domain.optimization` and `→ app.domain.transition.scorer` edges (lifespan publishing singleton compute services per blueprint §11). `make arch` now reports **5/5 contracts kept** (was 4/1 broken).
- **Panel actions rewired to v1 dispatcher API** — 13 action files updated, 30+ stale tool-name calls migrated:
  - `ym_search` → `provider_search(yandex, ...)`
  - `import_tracks` → `entity_create(track, ...)`
  - `analyze_track` / `classify_mood` → `entity_create(track_features, level=3 or 2)`
  - `audit_playlist` → `read_resource(local://playlists/{id}/audit)`
  - `sync_playlist` → `playlist_sync(direction, source)`
  - `build_set` / `rebuild_set` → composed `sequence_optimize` + `entity_create(set_version)`
  - `score_transitions` → `transition_score_pool`
  - `get_set_templates` → `read_resource(reference://templates)`
  - `get_set_cheat_sheet` → `read_resource(local://sets/{id}/cheatsheet)`
  - `like_track` / `ban_track` / `rate_track` → `entity_create(track_feedback, kind=...)`
  - `log_transition` / `update_reaction` → `entity_create / entity_update(transition_history, ...)`
  - feedback table-write → `entity_create(track_feedback)` (table dropped in v1)
- **Panel build green** — `bunx tsc --noEmit` exit 0, `bun run build` PASS, all 15 routes built.
- **Plugin packaging polish**:
  - Supabase `--project-ref` is now env-driven via `${DJ_DB_PROJECT_REF}` (was hardcoded `bowosphlnghhgaulcyfm` — not portable for marketplace install). `.env.example` documents the new var.
  - Removed unsupported `FileChanged` block from `hooks/hooks.json` (silently ignored in production; not a documented Claude Code hook event).
- **Panel P0 blockers fixed**:
  - `panel/lib/queries/mix-meta.ts` — hoisted async `await fetch(...)` out of a sync IIFE inside the return object.
  - `panel/components/audio-player/audio-player-context.tsx` — extracted missing `transitionLog` const referenced at line 1564.
  - `panel/.env.local` — created from `.env.example`; SSR pages no longer crash on Supabase `URL!`/`anon_key!` non-null asserts.
- **Docs sync to v1.0.4 reality**:
  - `README.md` — tool count 13 → 20, middleware 16 → 15, tests "1200+" → "704", added Panel section + Документация table + Лицензия.
  - `CLAUDE.md` — Panel state section refreshed (actions migration done; remaining 6 `TODO(v1.0-actions-rewrite)` markers documented).

### Added
- **`LICENSE`** file (MIT) at repo root — `plugin.json` and `pyproject.toml` declared MIT but no LICENSE file existed. Was the only blocker for public marketplace publish.
- **`app/server/_stateless_state.py`** — process-wide fallback storage for lifespan-yielded MCP state (used by REST/in-process callers that do not enter MCP's own lifespan).
- **Surface-redesign-v2 Phase 1 skeleton** (`app/server/surface.py`, 116 LOC) — `ToolTransformConfig` for 10 declarative managers + 2 smoke tests. Phase 1 Tasks 2-10 deferred to subsequent releases. Specs: [`docs/superpowers/specs/2026-04-18-surface-redesign-v2-design.md`](docs/superpowers/specs/2026-04-18-surface-redesign-v2-design.md), [plan](docs/superpowers/plans/2026-04-18-surface-redesign-v2-phase1.md).

### Tests
- **704 passed** (was 682 at v1.0.4) — +22 regression tests across 4 hardened middleware areas.

### Known follow-ups (panel only, deferred)
- 6 `TODO(v1.0-actions-rewrite)` markers for composer workflows: `distributeToSubgenres`, `pushSetToYm`, `deliverSet`, `exportSet` (M3U/Rekordbox writers), `scoreTransitions` consecutive-pair filter, transition recommended style/bars.
- `mixer-actions.ts` exports stubbed (not deleted) — DJ engine simulator removed in Phase 7 cutover (Blueprint §13 D15). Calling `set_eq` / `kill_eq` / `reset_eq` / `set_filter` / `mixer_state` / `mixer_crossfader` throws explicit error pointing at spec; UI button disable still pending.

## [1.0.4] — 2026-04-20

**FastMCP v3 polish — middleware dedupe, per-tool timeouts, fastmcp.json + CORS.**

### Changed
- Replaced 5 custom middleware with canonical FastMCP v3 built-ins: `DetailedTimingMiddleware`, `RetryMiddleware`, `ResponseLimitingMiddleware`, `ResponseCachingMiddleware`, `StructuredLoggingMiddleware`. Behaviour equivalent, covered by FastMCP core tests.
- Renamed `ErrorHandlingMiddleware` → `DomainErrorMiddleware` to avoid collision with FastMCP's built-in `ErrorHandlingMiddleware`. File renamed from `app/server/middleware/error_handling.py` to `app/server/middleware/domain_error.py`.
- Moved `TransientError` from `app/server/middleware/retry.py` to `app/shared/errors.py`.
- `DomainErrorMiddleware` now re-raises `McpError` unchanged, preserving native MCP protocol error codes (e.g. FastMCP timeout `-32000`) instead of wrapping them as `ToolError("internal error")`.
- `ResponseCachingMiddleware`: bounded `MemoryStore(max_entries_per_collection=settings.mcp.response_cache_max)` and explicit `included_tools` allowlist for 13 `readOnlyHint=True` tools (dispatchers + UI).
- `RetryMiddleware`: preserve the pre-migration 0.5s `base_delay` (FastMCP default 1.0s would double every retry wait).
- Per-tool timeouts now carry **both** the forward-looking `@tool(timeout=N)` kwarg and `meta={"timeout_s": N}` on 19 tools (14 dispatchers + 5 read-only UI). The kwarg is documentation/future-proof until FastMCP's `FileSystemProvider` learns to forward it; `ToolCallTimeoutMiddleware` reads `meta["timeout_s"]` as the effective cap today. `tool_invoke` opts out (proxy/fallback — delegated tool enforces its own timeout).
- CORS: explicit allowlist via `DJ_MCP_CORS_ALLOW_ORIGINS` (CSV or JSON array, read directly from env to avoid eager Settings load). Default remains `["http://localhost:3000"]`. Narrowed `allow_methods` to `["GET", "POST", "DELETE", "OPTIONS"]`, `allow_headers` to `["mcp-protocol-version", "mcp-session-id", "Authorization", "Content-Type"]`, added `expose_headers=["mcp-session-id"]` so browser MCP clients can read the session ID.
- `.claude-plugin/plugin.json`: the `mcp` server command now runs `if [ -f .env ]; then source .env; fi` before `exec`, so `fastmcp.json` env interpolation finds the DJ_* vars without hard-failing when the file is absent.

### Added
- `fastmcp.json` `environment` section (uv / python ≥ 3.12 / project root) for declarative env management.
- `fastmcp.json` `deployment.env` with `${VAR}` interpolation for string-valued DJ_* secrets (`DJ_DATABASE_URL`, `DJ_YM_TOKEN`, `DJ_YM_LIBRARY_PATH`, `DJ_SENTRY_DSN`, `DJ_MCP_CODE_MODE` with default `0`).

### Removed
- `OTELTracingMiddleware` — FastMCP v3 ships native OpenTelemetry instrumentation with MCP semantic conventions (`tools/call {name}`, `gen_ai.tool.name`).

### Breaking (internal to codebase only — MCP surface unchanged)
- Import: `from app.server.middleware.error_handling import ErrorHandlingMiddleware` → `from app.server.middleware.domain_error import DomainErrorMiddleware`.
- Import: `from app.server.middleware.retry import TransientError` → `from app.shared.errors import TransientError`.
- `app/server/middleware/otel_tracing.py` deleted.

## [1.0.2] — 2026-04-20

### Changed
- **FastMCP pin:** `fastmcp[tasks]>=3.1.0` → `fastmcp[tasks]>=3.2.4,<4`. Picks up fakeredis-regression fix (v3.2.3) and background-tasks auth-scoping + security hardening (v3.2.4). The v3.2.0 deprecations (`PromptToolMiddleware`, `ResourceToolMiddleware`) do not affect this project — we use `PromptsAsTools` / `ResourcesAsTools` (different classes). No code changes required.

## [1.0.1] — 2026-04-18

### Added
- **Yandex Music:** `set_playlist_description` endpoint in YandexClient + YandexAdapter (`POST /users/{owner}/playlists/{kind}/description`). Exposed via `provider_write(provider="yandex", entity="playlist", operation="set_description", params={playlist_id, description})`.
- **Developer ergonomics:** PostToolUse hook (`hooks/reload-mcp.sh` + `hooks/hooks.json`) that auto-kills the fastmcp stdio process on plugin edits so Claude Code respawns it with fresh code — no manual `/mcp` reconnect. Slash command `/reload-plugin` for manual cache purge + restart.

### Fixed
- **MCP entrypoint:** `fastmcp.json` now points at root `server.py` (self-referential `from app.server.X` imports broke when FastMCP loaded `app/server.py` as synthetic module).

## [1.0.0] — 2026-04-17

**Major release — global refactor to v1 bounded-contexts architecture.**

### Added
- **EntityRegistry** — polymorphic CRUD over 13 entity types (tracks, playlists, sets, transitions, ...)
- **ProviderRegistry** — pluggable music-platform providers (Yandex, stubs for Spotify/Beatport/SoundCloud)
- **UnitOfWork** — single-session-per-tool transaction boundary
- **16 middlewares** composed into `build_mcp_server()`: error_handling, sentry_context, otel_tracing, timing, audit_log, retry, response_limit, response_caching, deprecation_warning, cost_tracking, sampling_budget, progress_throttle, tool_timeout, provider_rate_limit, db_session, structured_logging
- **Domain layer**: pure `app/domain/{transition,optimization,camelot,template,audit}/` — scorer parity at 1e-9 vs legacy
- **Audio layer**: ported 18 analyzers to `app/audio/` with SharedMemory transport + per-worker AnalysisContext cache
- **Resources layer**: ~27 URI resources (entity-scoped, session-scoped, schema introspection, 4 static reference blobs)
- **Prompts layer**: 6 workflow recipes (dj_expert_session, build_set_workflow, deliver_set_workflow, expand_playlist_workflow, full_pipeline, quick_mix_check)
- **REST API**: thin FastAPI wrapper under `app/rest/` (extra `[http]`)
- **Observability**: Sentry + OpenTelemetry bootstrap under `[observability]` extra
- **AuditSettings**: 22 techno-audit thresholds accessible via `settings.audit.*`
- **Smoke test script**: `scripts/smoke_test_all_tools.py` verifying tool/resource/prompt registration end-to-end through `Client(mcp)`

### Changed
- **88 narrow tools → 13 generic dispatchers**: `entity_create/get/update/delete/list/aggregate`, `provider_search/resolve/download`, `sequence_optimize`, `transition_score_pool`, `playlist_sync`, `unlock_namespace`
- **Package layout**: flat `app/{tools,resources,prompts,handlers,repositories,registry,providers,domain,audio,schemas,server,rest,shared,config,models,db}/` — no more `app/controllers/`, `app/services/`, `app/entities/`, `app/engines/`
- **Settings**: split into 8 per-domain Pydantic settings classes (`audio`, `audit`, `database`, `delivery`, `discovery`, `mcp`, `optimization`, `transition`, `yandex`) aggregated via `get_settings()`
- **FastMCP composition**: explicit `FastMCP(providers=[FileSystemProvider(...)], transforms=[PromptsAsTools, ResourcesAsTools, BM25SearchTransform], lifespan=..., sampling_handler=...)`
- **Import-linter contracts**: reduced to 5 v1-scoped architectural gates

### Removed
- ~53,454 LOC of legacy sources: `app/engines/`, `app/infrastructure/`, `app/ym/`, `app/services/` (39 files), `app/controllers/`, `app/bootstrap/`, `app/api/`, `app/schemas/`, `app/transition/`, `app/optimization/`, `app/camelot/`, `app/templates/`, `app/audit/`, `app/entities/`, `app/audio/`, `app/core/`, `app/db/`, `app/config.py`, `app/server.py`, `app/telemetry.py`, `app/_version.py`
- 15 dead DB tables (drop migration `p2_drop_dead_tables`)

### Migration notes

- Panel (`panel/`) server actions call consolidated dispatchers — tool names and argument shapes changed; panel requires follow-up patch
- `scripts/vm_import_and_analyze.py` + `scripts/ym_bfs_expand.py` stubbed — require rewrite against `app.providers.yandex.*` + `app.handlers.*` (post-v1.0.0)
- Alembic `p2_drop_dead_tables` migration deferred to manual apply against Supabase after release

### Phase tags

Refactor executed in 7 phases, each tagged: `phase-1-foundation` → `phase-2-persistence` → `phase-3-tools` → `phase-6-domain-audio` → `phase-4-resources` → `phase-5-server` → v1.0.0 cutover.

## [0.8.0] — 2026-04-13

### Added
- **Smoke-test script** (`scripts/smoke_test_all_tools.py`) — calls all 88 MCP tools through FastMCP Client with in-memory DB, verifies registration + schema + execution
- Full MCP tool verification via Claude Code live client (91/91 tools responding correctly)

### Fixed
- `BestPairRead.avg_score` — was `float` (non-nullable), now `float | None` to handle entries with no score
- `ANNOTATIONS_READ_ONLY` test — updated to match current preset (`readOnlyHint` + `idempotentHint`)
- `test_unlock_tools_status` — removed stale `session_rules` assertion
- `test_fitness_template_intent` — fixed import `app.services.templates` → `app.templates`
- `audio_atomic` tools — use `FastMCPNotFoundError` instead of `ToolError` for missing entities
- MCP tool visibility — resolved FK errors and stale tests (#93)
- NOT NULL constraints in recent migration tables (#94)

### Changed
- `noqa B008` on `track_feedback` Depends() defaults (ruff compliance)
- Supabase added to sandbox network allowedDomains

## [0.7.1] — 2026-04-12

### Added
- `title` on all 88 `@tool()` decorators — Claude Code shows human-readable names instead of "Run Tool"
- 7 semantic annotation presets: `ANNOTATIONS_READ_ONLY`, `WRITE_IDEMPOTENT`, `WRITE_DESTRUCTIVE`, `WRITE_OPEN_WORLD`, `WRITE_DESTRUCTIVE_OPEN`, `READ_ONLY_OPEN_WORLD`, `WRITE`
- 16 SVG icon sets per tool category (tracks, sets, playlists, audio, ym, admin, etc.)
- `TOOL_META` / `RESOURCE_META` dicts on all tools and resources (`version`, `author`)
- `title`, `icons`, `meta` on all 9 `@resource()` decorators
- Neural Mix stem-aware scoring layer (cherry-picked from main #88)
- Speculative prefetch service for next-track preparation (#89)
- `PrefetchService` + DI factory + 3 test files
- `TransitionHistoryService` DI wiring via `Depends()` (was broken `= None`)
- GitHub Actions CI workflow (ruff + mypy + lint-imports + pytest)
- PR template (`.github/pull_request_template.md`)
- Branch strategy doc (`.github/BRANCH_STRATEGY.md`)
- Pre-push hook blocking direct pushes to main
- `.claude/rules/git.md` — project-specific git workflow rules

### Changed
- **Removed `BM25SearchTransform`** — was proxying all tool calls through `run_tool`, causing "Run Tool" display in Claude Code. Replaced with native `mcp.disable(tags=...)` tag-based visibility
- Visibility policy: extended categories (delivery, discovery, curation, sync, ym) disabled at startup, unlockable via `unlock_tools`
- Repo settings: squash-only merges (merge commits disabled), auto-delete branches enabled
- Main and dev branches synced (were 50 vs 14 commits diverged)

### Fixed
- `track_affinity.refresh_from_history()` — `func.cast(..., type_=None)` produced `NullType` DDL error, replaced with `func.count().filter()`
- Duplicate alembic revision `a1b2c3d4e5f6` — renamed `add_first_downbeat_ms` to `f4a1b2c3d5e6`
- Missing imports for `ICON_*`, `TOOL_META`, annotation constants in 34 tool/resource files

### Removed
- 4 backward-compatibility shims: `services/export.py`, `optimizer.py`, `templates.py`, `transition.py`
- `services/background_tasks.py` (dead code)
- Stale git branches (claude/keen-bardeen, docs/sync-markdown-with-project, fix/tool-title-display)

## [0.7.0] — 2026-04-11

### Added
- Transition Recipe Engine — 12 djay Pro AI transition types with stem-level instructions
- Beatgrid migration (23,755 tracks)
- Auto-DJ with smart track selection (BPM ±3, Camelot ≤2)
- Preload next track, echo-out LPF, click fix, transition logging
- Phase 1 — Transition History (model, repo, service, 4 MCP tools, migration)
- Phase 2 — Track Affinity Matrix (model, repo, service, 3 MCP tools)
- Phase 3 — Persistent Track Feedback (like/ban/rate, 6 MCP tools)
- Phase 4 — Adaptive Energy Arc (trend analysis, 3 MCP tools)
- Phase 5 — Set Narrative Engine (phase analysis + suggestions)
- Phase 6 — Personal Scoring Weights (profiles, 3 MCP tools)
- DJ Panel: 4-deck layout, waveforms, EQ faders, cue points, mixer, iOS PWA
- Mixer MCP tools: set_eq, kill_eq, reset_eq, set_filter
- Selectel VM deployment with systemd-run pattern

### Changed
- Scoring weights rebalanced: spectral 0.20 (was 0.15), groove 0.15 (was 0.10), harmonic 0.12 (was 0.20)
- Section-aware scoring with drum-only harmonic floor

## [0.6.0] — 2026-04-10

### Added
- Modular architecture: bootstrap/, api/, DI, workflows
- REST API wrapper (FastAPI) with Swagger docs
- Panel (Next.js) with Supabase direct reads + MCP mutations
- FileSystemProvider auto-discovery for tools/resources/prompts
- Visibility system with `unlock_tools` per-session toggle

### Changed
- Refactored from monolithic server to 5-band architecture
- Split controllers/dependencies into db, repos, services, audio, external, uow

## [0.5.0] — 2026-04-08

### Added
- Transition system redesign: 6-component scoring (+ timbral)
- Section-aware scoring with SectionContext
- Context-aware TransitionIntent with per-template phase tables
- Style recommendation + TransitionRecipeEngine design

## [0.4.0] — 2026-04-06

### Added
- P1 analyzers: danceability, tempogram, dissonance, dynamic_complexity, tonnetz, beats_loudness
- P2 analyzers: spectral_complexity, pitch_salience, bpm_histogram, phrase
- Two-phase pipeline: independent → dependent analyzers
- Audio core layer: AnalysisContext, AudioLoader, FrameParams
- Per-analyzer clip duration (60s stitched multi-window)
- Shared onset envelope cache

### Changed
- Audio module refactored to layered architecture: core/ → analyzers/ → classification/ → pipeline
- MoodClassifier refactored to Strategy pattern with SubgenreProfile dataclasses

## [0.3.0] — 2026-03-25

### Added
- Background tasks via FastMCP Docket for long-running tools
- Error masking + retry middleware for production safety
- Real MP3 download from Yandex Music API with iCloud stub detection
- BPM, Key, Beat, MFCC analyzers (librosa) + MP3 input support
- Transition scoring: compute + persist via TransitionScorer
- GA/Greedy optimizer wired to build_set tool
- Structured output: tracks tools return Pydantic models

### Changed
- Plugin bumped to v0.3.0 (51 tools: 47 visible + 4 atomic hidden)
- Server switched to FileSystemProvider

## [0.2.0] — 2026-03-24

### Added
- Hidden atomic tools layer + mood persist in DB
- Composable tools for playlist expansion and YM sync
- YM tools connected to real YandexMusicClient via DI

### Fixed
- Plugin spec alignment: .mcp.json, hooks format, marketplace.json

## [0.1.0] — 2026-03-24

### Added
- Project requirements specification (REQUIREMENTS.md)
- Architecture design specification
- Claude Code plugin with 5 DJ workflow skills
- 44 MCP tools across 10 categories
- 44 SQLAlchemy models
- Yandex Music async client with rate limiter
- Audio pipeline: 3 core analyzers (loudness, energy, spectral)
- MoodClassifier for 15 techno subgenres
- TransitionScorer: 5-component formula
- GA optimizer + greedy chain builder + 8 DJ set templates
- Export: M3U8, Rekordbox XML, JSON guide, cheat sheet
- FastMCP v3.1 server with db_lifespan, visibility system, DI
