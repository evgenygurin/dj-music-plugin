# Performance Benchmark Report

Date: 2026-03-26 | DB: SQLite (39 tracks, 10 with features) | Machine: macOS ARM

## Light Operations (<50ms)

All 35 CRUD/read/search/reasoning tools complete under 37ms.

| Operation | ms | Note |
|-----------|---:|------|
| list_tracks(3) | 36 | First call, session warmup |
| compare_set_versions | 33 | Error path (1 version only) |
| export_set(m3u8) | 17 | File write |
| distribute(dry) | 16 | 47 tracks |
| export_set(json) | 15 | |
| list_sets | 13 | |
| list_tracks(20) | 11 | |
| score_transitions(set) | 9 | 9 transitions |
| audit_playlist | 9 | |
| build_set(greedy,dry) | 8 | |
| get_track(query) | 8 | ILIKE search |
| quick_set_review | 6 | |
| get_library_stats | 5 | Multiple COUNT queries |
| classify_mood(10) | 5 | Rule-based, no I/O |
| resource:library | 5 | |
| All other reads | 1-4 | |

**Verdict: Local DB operations are fast. No optimization needed.**

## Heavy Operations

| Operation | ms | sec | Bottleneck |
|-----------|---:|----:|------------|
| **analyze_track(force)** | **20,906** | **20.9s** | **Audio I/O + numpy FFT** |
| ym_get_tracks(1) | 1,580 | 1.6s | YM API latency + rate limit |
| ym_artist_tracks | 1,514 | 1.5s | YM API |
| ym_search | 1,361 | 1.4s | YM API |
| find_similar(ym) | 344 | 0.3s | YM API (cached?) |
| build_set(ga,dry) | 131 | 0.1s | GA optimizer |
| build_set(greedy,real) | 27 | 0.0s | |
| deliver_set(dry) | 25 | 0.0s | |

## Bottleneck Analysis

### 1. analyze_track: 21 seconds (CRITICAL)

Breakdown (estimated from pipeline):
- **MP3 decode**: ~3s (librosa.load 22050Hz mono)
- **BPM detection**: ~5s (librosa.beat.beat_track)
- **Key detection**: ~4s (chroma CQT + template matching)
- **Energy FFT**: ~2s (numpy rfft on full signal)
- **Loudness**: ~2s (LUFS computation)
- **Spectral**: ~2s (centroid, rolloff, flux)
- **Beat/MFCC**: ~3s (librosa onset, MFCC)

**Optimization options:**
1. **Chunk analysis** — analyze first 60s instead of full track (90% info, 3x speedup)
2. **Parallel analyzers** — run independent analyzers concurrently with asyncio.gather
3. **Cache audio signal** — load once, share across analyzers (already done)
4. **Lower sample rate** — 11025 Hz for energy/spectral (2x speedup, minor quality loss)
5. **Skip librosa for core** — BPM/key optional, loudness/energy/spectral are numpy-only

### 2. YM API calls: 1.4-1.6s each

Rate limiter adds 1.5s delay between calls (`settings.ym_rate_limit_delay`).

**Optimization options:**
1. **Batch endpoints** — `get_tracks([id1,id2,...])` instead of per-track calls
2. **Reduce rate limit** — test with 0.5s delay (risk: 429 errors)
3. **Cache YM responses** — LRU cache for repeated searches
4. **Prefetch** — background fetch metadata during import

### 3. GA optimizer: 131ms (OK for dry run)

With real data (100+ tracks, 200 generations) this will be 5-30s.
Already has `task=True` support.

## Found Bugs During Benchmarking

1. `ym_artist_tracks` expects `artist_id: str`, but int was passed → ValidationError
2. `compare_set_versions` fails with "Need at least 2 versions" (expected, set has 1 version)

## Recommendations (Priority Order)

| # | Optimization | Impact | Effort |
|---|-------------|--------|--------|
| 1 | analyze_track: 60s chunk + parallel analyzers | 21s → ~5s | Medium |
| 2 | YM batch API calls where possible | 1.5s/call → 0.3s/batch | Low |
| 3 | Cache YM search results (LRU, 5min TTL) | Repeat searches: 1.4s → 0ms | Low |
| 4 | analyze_track: optional librosa skip | 21s → ~6s (core only) | Low |
| 5 | Lower sample rate for energy/spectral | ~20% speedup | Low |
| 6 | GA 2-opt: limit iterations or early exit | 500 tracks: 18s → ~3s | Medium |

## GA Optimizer Deep Profile

**Test conditions:** 12 tracks, pop=100, max_gens=200, mut=0.15, conv=20

### Atomic operation costs

| Operation | Time | Notes |
|-----------|-----:|-------|
| `transition.score()` | 0.003 ms | Pure math, very fast |
| `compute_fitness(12t)` | 0.031 ms | 11 transitions × 5 components |
| `ox_crossover()` | 0.001 ms | |
| `mutate()` | 0.0003 ms | |
| `tournament_select()` | 0.001 ms | |
| `init_population(100)` | 0.17 ms | 100 random shuffles |
| `eval_population(100)` | 3.32 ms | **91% of generation cost** |
| `two_opt(12t)` | 10.23 ms | O(n²) per iteration |

### GA run results

| Metric | Value |
|--------|-------|
| Total time | **199 ms** |
| Generations run | 49 / 200 (converged at 20 stagnant) |
| Avg per generation | 4.0 ms |
| Score (GA) | **0.681** |
| Score (Greedy) | 0.621 |
| GA improvement | +9.7% over greedy |

### Cost breakdown per generation

```text
Fitness evaluation:  3.1 ms  (100 × 0.031)  ← 91% of cost
Genetic operators:   0.3 ms  (100 × 0.003)
─────────────────────────────────────────────
Total per gen:       3.4 ms
2-opt (post-GA):    10.2 ms  (one-time)
```

**Bottleneck: fitness evaluation (91%).** Each individual requires n-1 transition scores.

### Scaling projection

| Tracks | Per-gen | 2-opt | Total (49 gens) | Status |
|-------:|--------:|------:|-----------------:|--------|
| 12 | 3 ms | 10 ms | 0.2s | OK |
| 20 | 5 ms | 28 ms | 0.3s | OK |
| 50 | 13 ms | 178 ms | 0.8s | OK |
| 100 | 26 ms | 710 ms | 2.0s | OK |
| 200 | 52 ms | 2,841 ms | 5.4s | warn |
| 500 | 129 ms | 17,753 ms | **24.1s** | **SLOW** |

### GA optimization recommendations

1. **2-opt is the scaling bottleneck** — O(n²) per iteration, dominates at 200+ tracks
   - Fix: limit 2-opt iterations (`max_2opt_passes=3`) or skip for n>100
   - Fix: only try 2-opt swaps on worst-scoring transitions

2. **Fitness caching** — same individual may appear across generations
   - Cache fitness by tuple(order) → score (LRU, ~1000 entries)

3. **Parallel fitness eval** — independent per individual
   - Use `concurrent.futures.ProcessPoolExecutor` for population eval

4. **Adaptive population** — scale pop_size with track count
   - 10-50 tracks: pop=50, 50-200: pop=100, 200+: pop=200

5. **Early termination** — convergence_threshold=20 already works well
   - 49/200 gens used (75% savings) — this is effective
