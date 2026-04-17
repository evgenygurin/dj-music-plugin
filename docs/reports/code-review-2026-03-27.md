# Code Review: DRY/SOLID/OOP Audit — 2026-03-27

## Summary

18 findings across service, tool, and repository layers. 6 high, 5 medium, 7 low/nit.

## High Priority (P1)

### 1. `get_or_create` pattern duplicated 4x in MetadataService

**Files:** `app/services/metadata_service.py:260-337`
**Pattern:** `_get_or_create_artist`, `_get_or_create_genre`, `_get_or_create_label` — identical 10-line blocks.
**Fix:** Extract generic `BaseRepository.get_or_create(**match_fields)` or a service helper.

### 2. Junction link pattern duplicated 4x in MetadataService

**Files:** `app/services/metadata_service.py:341-396`
**Pattern:** `_link_track_artist`, `_link_track_genre`, `_link_track_label`, `_link_track_release` — identical "check exists, create if not" blocks.
**Fix:** Extract `_link_if_not_exists(model, **fields)`.

### 3. TransitionScorer.score() vs score_with_candidates() — 15-line exact duplicate

**Files:** `app/services/transition.py:43-87` vs `:89-177`
**Fix:** Extract `_check_hard_constraints()` and `_compute_weighted()` shared methods.

### 4. Four services bypass repository layer with raw AsyncSession SQL

**Files:** `audio_service.py`, `candidate_service.py`, `metadata_service.py`, `embedding_service.py`
**Fix:** Create AudioRepository, EmbeddingRepository; extend MetadataRepository.

### 5. "Load set version + items" pattern repeated 7x

**Files:** `set_service.py:336,368,437`, `delivery_service.py:50`, `curation_service.py:219`, `reasoning_service.py:44,229`
**Fix:** Extract `SetService.get_latest_version_with_items(set_id)`.

### 6. Mood classification duplicated in AudioService vs CurationService

**Files:** `audio_service.py:169-205` vs `curation_service.py:59-84`
**Problem:** AudioService builds feature dict manually (17 fields), CurationService uses `to_classifier_dict()`. Divergence risk.
**Fix:** Unify into single `classify_track_features()` using `to_classifier_dict()` everywhere.

## Medium Priority (P2)

### 7. Entity resolution pattern repeated 7x in tool layer

**Files:** All tools with `id: int | None, query: str | None` params (tracks.py x2, playlists.py, crud.py, audio.py x2, curation.py)
**Fix:** Extract `resolve_entity()` helper in `app/mcp/tools/_helpers.py`.

### 8. iCloud stub detection in 4 places (3 with magic number 0.9)

**Files:** `audio_atomic.py:76`, `delivery.py:151`, `audio_service.py:92`, `delivery_service.py:234`
**Fix:** Extract `is_icloud_stub(path)` in `app/utils/files.py`, use `settings.delivery_icloud_stub_threshold` everywhere.

### 9. analyze_one_track (atomic tool) duplicates AudioService.analyze_track entirely

**Files:** `audio_atomic.py:34-109` vs `audio_service.py:34-120`
**Fix:** Atomic tool should delegate to AudioService, not reimplement.

### 10. DjLibraryItem lookup by track_id — raw SQL in 3 places

**Files:** `audio_atomic.py:65`, `audio_service.py:74`, `track.py:186` (canonical)
**Fix:** Use `TrackRepository.get_library_item()` everywhere.

### 11. TransitionScorer instantiated directly in 5 places instead of DI

**Files:** `set_service.py:303`, `set_service.py:569`, `candidate_service.py:50`, `reasoning_service.py:80`, `background_tasks.py:65`
**Fix:** Inject via DI factory `get_transition_scorer()`.

## Low Priority (P3)

### 12. Export format dispatch — if-elif chain in 2 places

**Files:** `delivery_service.py:156-168` and `:249-258`
**Fix:** Registry dict `{format: (writer_fn, extension)}`.

### 13. YM batch-add-to-playlist loop duplicated 3x

**Files:** `discovery_service.py:284-298`, `sync_service.py:147-151`, `sync_service.py:229-233`
**Fix:** Extract `YandexMusicClient.batch_add_tracks()`.

### 14. Paginated response — inconsistent format (Pydantic vs dict)

**Files:** `tracks.py` uses `PaginatedResponse`, all others use raw dicts.
**Fix:** Use `PaginatedResponse[T]` consistently.

### 15. Features raw SQL in atomic tools (4 places)

**Files:** `audio_atomic.py:53-59,123-128,167-172`, `audio_service.py:54-59`
**Fix:** Use `FeatureRepository.get_by_track_id()`.

### 16. `manage_set` action dispatch 50-line if-elif

**Files:** `set_service.py:464-534`
**Note:** Accepted pattern per REQUIREMENTS.md for token overhead reduction.

### 17. PlaylistService.list_all() calls private `_repo._paginate()` directly

**Files:** `playlist_service.py:48-56`
**Fix:** Add `PlaylistRepository.list_filtered()`.

### 18. `ensure_list`/`ensure_dict` lazy import inconsistency

**Files:** 10 call sites across 7 files — some module-level, some function-level.
**Note:** Cosmetic, lazy imports prevent circular dependencies.

## Refactoring Roadmap

| Phase | Items | Effort | Impact |
|-------|-------|--------|--------|
| 1 | #8 iCloud stub + #6 mood unify + #3 scorer DRY | 1-2h | Fix bug-divergence risks |
| 2 | #1+#2 MetadataService generics + #5 version+items | 2-3h | Eliminate ~200 lines |
| 3 | #4 Create repos for 4 services + #9+#10+#15 atomic | 3-4h | Architecture compliance |
| 4 | #7 entity resolution + #14 paginated response | 2-3h | Tool layer consistency |
