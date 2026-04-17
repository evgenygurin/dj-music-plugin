# Performance Benchmark Report — 2026-03-27

## Environment

- DB: SQLite (dj_music.db), 30 tracks, 5 with audio features
- Python: 3.12.0, FastMCP 3.1.1
- Hardware: macOS (local, Apple Silicon)
- Audio: MP3 320kbps, 3-7 min tracks

---

## Audio Analysis (ГЛАВНЫЙ BOTTLENECK)

### Single Track Pipeline

| Анализатор | Время (ms) | % от total | Библиотека |
|-----------|-----------|-----------|------------|
| **beat** | **17,813** | **58%** | librosa |
| spectral | 3,744 | 12% | numpy |
| key | 1,487 | 5% | librosa |
| energy | 1,153 | 4% | numpy |
| bpm | 872 | 3% | librosa |
| mfcc | 244 | <1% | librosa |
| structure | 82 | <1% | numpy |
| loudness | 58 | <1% | numpy |
| **TOTAL pipeline** | **30,090** | **100%** | — |

### Batch Analysis (4 tracks)

| Metric | Value |
|--------|-------|
| Total time | **165,116 ms** (2.75 min) |
| Average per track | **41,279 ms** (~41 sec) |
| Overhead vs single | +37% (pipeline re-init, I/O) |

### Экстраполяция

| Масштаб | Время (sequential) | Время (4x parallel) |
|---------|-------------------|---------------------|
| 30 треков | ~20 min | ~5 min |
| 100 треков | ~69 min | ~17 min |
| 500 треков | ~5.7 hours | ~1.4 hours |
| 3000 треков | **~34 hours** | **~8.5 hours** |

---

## Database Operations

| Operation | Time (ms) | Notes |
|-----------|----------|-------|
| list_tracks(limit=100) | 33.1 | 30 tracks, pagination + serialize |
| get_set(view=tracks, 30) | 8.1 | N+1 queries (30 get_by_id calls) |
| get_set(view=full, 30) | 71.0 | With features loaded |
| get_set(view=summary) | 4.2 | Single query |
| get_track(id=1) | 2.2 | Single row |
| get_playlist + items | 2.0 | Eager load |
| get_artist_names_batch(30) | 1.0 | Single SQL, batch |
| get_scoring_features_batch(30) | 0.8 | Single SQL, batch |
| get_track_features(id=1) | 0.5 | Single row |

---

## Set Building & Scoring

| Operation | Time (ms) | Notes |
|-----------|----------|-------|
| build_set(greedy, 30 tracks) | 179 | With features — actual greedy algorithm |
| score_transitions(10 pairs) | 1.2 | C(5,2)=10 pairs, pure math |
| classify_mood(5 tracks) | 223 | Rule-based, includes DB fetches |

### Экстраполяция scoring

| Масштаб | Пар | Время |
|---------|-----|-------|
| 30 треков | C(30,2) = 435 | ~52 ms |
| 100 треков | C(100,2) = 4,950 | ~594 ms |
| 3000 треков | C(3000,2) = 4.5M | ~9 min (с pruning ~1 min) |

---

## Yandex Music API

| Operation | Time (ms) | Notes |
|-----------|----------|-------|
| ym_search (1 query) | 458 | Network latency |
| ym_get_tracks (5 IDs batch) | 224 | Single HTTP request |
| Rate limit delay | 1,500 | Between every request |

### Import 30 tracks pipeline

| Phase | Est. Time | Notes |
|-------|----------|-------|
| Search (5 queries) | ~9 sec | 5 × (458ms + 1500ms rate limit) |
| Batch get_tracks (30) | ~0.5 sec | 1 batch call |
| Enrichment (30 tracks) | ~0.5 sec | DB writes |
| Download MP3 (30) | ~90 sec | 30 × ~3 sec per file |
| **Total import** | **~100 sec** | Dominated by downloads |

---

## Bottleneck Ranking

```text
                              0        10       20       30       40 sec
                              |--------|--------|--------|--------|
 1. beat analyzer (per track) ████████████████████████████████████ 17.8s  [58%]
 2. spectral analyzer         ████████  3.7s                              [12%]
 3. YM rate limit (per req)   ███  1.5s (fixed delay)
 4. key analyzer              ███  1.5s                                   [ 5%]
 5. energy analyzer           ██  1.2s                                    [ 4%]
 6. bpm analyzer              █  0.9s                                     [ 3%]
 7. YM search (network)       █  0.5s
 8. classify_mood (5 trk)     █  0.2s
 9. build_set(greedy, 30)     █  0.2s
10. DB operations (all)       ·  <0.1s
11. score_transitions(10)     ·  0.001s
```

---

## Recommendations

### P0 — Critical (beat analyzer = 58% total time)

**Параллельный audio pipeline**: beat analyzer занимает 17.8 сек из 30 — это ~58% всего времени. Решения:
- `multiprocessing.Pool(4)` для параллельного анализа 4 треков → **4x speedup** (34h → 8.5h для 3000)
- Или `concurrent.futures.ProcessPoolExecutor` с asyncio
- Beat analyzer можно запустить параллельно с другими анализаторами (они независимы)

### P1 — High (beat analyzer optimization)

**Оптимизация beat detector**: librosa `beat_track` + `onset_strength` — тяжёлые. Варианты:
- Анализировать первые 60 сек вместо полного трека (BPM стабилен в техно)
- Использовать `madmom` вместо librosa для beat detection (в 2-3x быстрее)
- Кэшировать onset strength (используется и в beat, и в energy)

### P2 — Medium

- **N+1 в get_set**: заменить 30 `get_by_id` на batch `WHERE id IN (...)` — ~8ms → ~2ms
- **YM rate limit**: увеличить batch size для get_tracks (до 100 за раз)
- **Incremental analysis**: skip уже проанализированные треки (уже есть `force` flag)

### P3 — Low

- **Transition cache**: уже реализован, проверить hit rate
- **Timing middleware**: логировать длительность каждого MCP tool call
- **Progress reporting**: ctx.report_progress для batch operations

---

## Bugs Found During Testing

### BUG-015: download_tracks не резолвит local track IDs

`download_tracks(track_refs=["1", "2", "3"])` скачивает YM track IDs 1, 2, 3 (Max Roach, Status Quo) вместо local tracks 1, 2, 3 (Techno 2024, etc.). Tool принимает только YM track IDs, но документация говорит "Accepts strings or ints" без уточнения.

**Severity**: Medium — пользователь скачает неправильные треки.
**Workaround**: передавать YM track IDs ("135055088"), не local IDs ("1").

### BUG-016: download_tracks с local IDs → linked_to_library: 0

При скачивании с local IDs файлы скачиваются но не привязываются к трекам (`linked_to_library: 0`). С YM IDs привязка работает корректно (`linked_to_library: 5`).

**Severity**: Medium — скачанные файлы бесполезны без привязки.

### BUG-014: Fixed

`get_set` tracks view теперь включает `artist_names` через batch query.
