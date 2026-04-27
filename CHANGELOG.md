# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
- `fastmcp.json` `deployment.env` with `${VAR}` interpolation for string-valued DJ_* secrets (`DJ_DB_URL`, `DJ_YM_TOKEN`, `DJ_YM_LIBRARY_PATH`, `DJ_SENTRY_DSN`, `DJ_MCP_CODE_MODE` with default `0`).

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
