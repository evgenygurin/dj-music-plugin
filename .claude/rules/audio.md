---
description: Audio analysis patterns
globs: app/audio/**/*.py
---

# Audio Analysis

- Check optional dependencies with try/except ImportError at module level
- Register analyzers in `AnalyzerRegistry` via `@registry.register` or explicit call
- Each analyzer returns a typed dataclass result (not dict)
- Pipeline handles partial failures: known errors bubble up, unexpected errors wrapped
- Use `settings.audio_*` for sample rate, hop length, MFCC coefficients
- Timeseries data saved as NPZ files via `app/audio/timeseries.py`
- Stem separation (demucs) requires `[stems]` extra — never import unconditionally
- Beat/MFCC/key detection requires `[audio]` extra (librosa)
- Core analyzers (loudness, energy, spectral) use only numpy — no optional deps

## Gotchas

- Mood classification fires inside the `track_features_analyze` handler — `mood` + `mood_confidence` land directly in `track_audio_features_computed`. No separate `classify_mood` tool exists in v1; invoke mood classification via `entity_create(entity="track_features", data={track_ids, level=2})`.
- Pipeline features → DB: always use `TrackAudioFeaturesComputed.filter_features(result.features)` — pipeline may return keys without columns
- Tiered auto-trigger: `transition_score_pool`, `sequence_optimize`, `deliver_set_workflow` prompt, and `entity_create(entity="set_version")` auto-upgrade missing features to the needed tier. No manual pre-analysis call required.
- P1 analyzers: essentia DFA danceability is unbounded (not 0-1), dissonance 0-1, dynamic_complexity 0-~10
- P2 analyzers: SpectralComplexityAnalyzer, PitchSalienceAnalyzer depend on essentia; BpmHistogramAnalyzer depends on `beat` (depends_on); PhraseAnalyzer depends on `beat`
- `depends_on`: `ClassVar[frozenset[str]]` — Phase 2 pipeline passes `prior_results` to dependent analyzers
- `_ANALYZER_REGISTRY`: global dict, `importlib` doesn't re-register decorator on re-import — in tests delete only `_test_*` keys, never `clear()`
- Per-analyzer clip duration: heavy librosa analyzers (beat, bpm, key, spectral, mfcc, tonnetz, tempogram, pitch_salience) declare `clip_duration_s: ClassVar[float | None] = 60.0`. Pipeline builds a stitched-multi-window 60s `AnalysisContext` for them and a full-track context for analyzers with `clip_duration_s = None` (loudness, structure, energy). One STFT per unique clip duration, shared across bucket members
- Stitched clip strategy: 60s clip = 3 windows of 20s sampled from positions ~1/6, 3/6, 5/6 of the source, hann-fade-blended at boundaries (~20ms ramps) to avoid click artifacts. Skips intro/outro padding, captures variation between sections (build/drop/breakdown). Falls back to a single centered window if the source is too short for non-overlapping sub-windows
- Shared onset envelope: `bpm`, `beat`, `tempogram` read `ctx.get_onset_env()` (lazy + lock-protected) instead of recomputing `librosa.onset.onset_strength` three times
- Librosa warmup: pipeline pre-imports librosa submodules on the main thread before parallel dispatch (`_warmup_librosa()`). Without this, multiple worker threads racing the lazy loader hit "Module 'scipy' has no attribute '_lib'" / "PytestTester circular import" errors
- MP3 analysis: requires `uv sync --extra audio` (librosa + soundfile)
- **Loader fallback chain (v1.3.7).** `app/audio/core/loader.py` wraps the `wave.Error` fallback so non-WAV inputs without `soundfile` / `librosa` installed raise a typed `RuntimeError("audio decode failed: …")` instead of leaking `wave.Error("file does not start with RIFF id")`. Pipeline-level error envelopes surface a clear cause instead of stdlib internals.
- **BPM analyzer (`app/audio/analyzers/bpm.py`)**: НЕ использует `librosa.beat.beat_track` для tempo — она квантует к integer frames-per-beat (sr=22050 hop=512 → только {123.05, 129.20, 136.00} в 120-140 BPM). Используется `_bpm_from_onset_autocorrelation` (parabolic peak interpolation на onset autocorrelation) для sub-frame precision. `min_bpm=80` чтобы избежать half-tempo lock на 60-70 BPM. См. regression `tests/test_audio/test_bpm_detector.py`
- **PLP confidence**: `librosa.beat.plp(...).max()` ≈ 1.0 на любом ритмичном сигнале — НЕ используй для confidence. Используй `np.mean(plp)` (BPMDetector это делает)
- **`variable_tempo` / `bpm_stability`**: вычисляются через `compute_tempo_stability(beat_times)` в `app/audio/analyzers/bpm.py`. Stitched-clip pipeline НЕ сохраняет beat-фазу на seam'ах → 2-4 spurious IBI (≈0 или ≈2x median) per track. Без outlier filter cv взлетает, 63% треков ложно-помечаются variable. Фильтр: оставляем IBI в `[0.5, 1.5] x median` перед расчётом CV. Реальный tempo drift (> 15% CV) остаётся detected. См. regression `tests/audio/analyzers/test_bpm_stability.py`.

## L5-финализация сета (download → reanalyze)

Канон для «довести треки сета до L5 перед доставкой» (см. также
@docs/audio-schema.md «Покрытие данными» — почти вся библиотека на L2,
физических MP3 ~десятки из ~24k).

- **L5-reanalyze требует зарегистрированный `audio_file`.**
  `entity_update(entity="track_features", id=<track_id>, data={"level": 5})`
  падает с `"audio_file not found: <id>"` / `"no audio file registered"`,
  если на трек нет строки в `dj_library_items`. Reanalyze читает
  `audio_file.file_path` — он НЕ качает сам. Сначала download, потом L5.
- **Download:** `entity_create(entity="audio_file", data={"track_ids": [...]})`
  (ключ — `track_ids`, не `track_id`). Handler `audio_file_download`
  резолвит yandex external_id, тянет MP3 в `/tmp/dj_audio/`, пишет
  `DjLibraryItem`. `skip_existing` проверяет **строку в БД**, НЕ файл на
  диске — повторный вызов на уже скачанный (но не закоммиченный) файл
  перекачивает заново.
- **120s MCP-таймаут vs download.** Каждый трек ≈20–40s (YM rate-limit
  1.5s × 3 HTTP-хопа + стрим MP3). Батч из 4–5+ часто >120s → MCP-клиент
  таймаутит → UoW **откатывается**: файлы остаются на диске, но строк в
  `dj_library_items` нет (и L5 их не увидит). Качай **батчами по 3–5**
  под лимит; на быстрой сети 5 проходит, на слабой — по 2–3. После
  таймаута проверь, что реально зарегистрировано:
  `entity_list(entity="audio_file", filters={"track_id__in": [...]})`,
  а не `ls` по диску.
- **L5-reanalyze (после download) быстрый и параллелится** — ~5–10s/трек
  (librosa на локальном файле, без сети). Можно слать по 4–5
  `entity_update(track_features, ..., {"level": 5})` параллельно. Результат —
  `feature_count: 62`, `analysis_level: 5`.
- **L5 переопределяет `key_code` (и пр.) относительно L2.** Acid/industrial
  треки после L5 могут схлопнуться в иные (часто более тесные) тональности
  — отбор по L2-`key_code` и финальная Camelot-картина после L5 различаются.
  Поэтому: пересобери `set_version` после L5 (re-score на точных фичах) и
  перечитай `local://sets/{id}/transitions` — picker на L5 надёжнее (не
  путает 303-резонанс с вокалом, корректнее роутит DRUM_SWAP vs ECHO_OUT).
- **Тяжёлые/массовые L5-прогоны — на VM** (см. @docs/dev-mode.md,
  feedback по heavy jobs). Таргетные 15–20 треков одного сета — окей
  локально батчами; полно-библиотечный sweep — нет.

## Numba/librosa version pinning

- **Минимум**: `numba>=0.65`, `llvmlite>=0.47`, `numpy>=2.4.4`. Закреплено в `pyproject.toml [audio]`.
- **Известный SEGV**: `numba 0.64.0 + llvmlite 0.46.0 + numpy 2.4.3` валит `librosa.beat.beat_track` по SIGSEGV на **single-threaded main вызове** с любым входным сигналом. Это бинарная регрессия в numba gufunc, не race condition. Симптом — `Current thread ... numba/np/ufunc/gufunc.py:263 __call__ → librosa/beat.py:505 __beat_tracker`. Фикс: `uv pip install --upgrade numba llvmlite`.
- **При апгрейде numpy** до новой 2.x — обязательно проверять что numba/llvmlite свежие. Старый numba собран против старого numpy ABI и сегфолтит.

## JIT warmup для multi-thread pipelines

Перед запуском любого pipeline c `max_workers > 1` (особенно в long-running CLI) **прогреть numba JIT на main thread** до того как ThreadPoolExecutor запустит analyzers параллельно. Без warmup'а несколько threads вызывают numba JIT compilation одновременно — race condition в C коде → SEGV.

Минимальный warmup (≈3s, runs once at startup):

```python
import librosa, numpy as np
sr = 22050
y = (np.random.RandomState(42).randn(sr * 5).astype(np.float32) * 0.1)
librosa.onset.onset_strength(y=y, sr=sr)
librosa.beat.beat_track(y=y, sr=sr)
librosa.feature.chroma_cqt(y=y, sr=sr)
librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
librosa.feature.spectral_centroid(y=y, sr=sr)
```

Должно быть реализовано в любом long-running batch CLI до запуска `AnalysisPipeline`. Тест-сервер MCP (`fastmcp dev`) обычно не нуждается — анализирует треки последовательно. Long-running batch jobs — обязательно.

`AnalysisPipeline._warmup_librosa()` делает только pre-import submodules (избегает scipy/PytestTester race на lazy loader), но **не** прогревает JIT. Это два разных warmup'а — нужны оба.

## Сигнальное качество фич на ЭТОЙ библиотеке (curation rule)

Полный per-feature разбор + DJ-применение + измеренные распределения —
@docs/research/2026-06-23-track-feature-reference-and-set-construction.md.
Библиотека акустически однородна (acid/industrial/detroit/dub @122–130), у
многих «теоретически сильных» фич **крошечный реальный разброс** → они не
разводят треки здесь. Это корень вырожденности mood-классификатора.

- **Курируй по фичам с реальным разбросом:** `integrated_lufs`,
  `spectral_centroid_hz` (лучший спектральный дискриминатор, p10/p90
  1533/2853), `energy_mean`, `bpm`, `key_code`, `hp_ratio`, `energy_low`.
- **НЕ фильтруй и НЕ ранжируй по near-constant фичам:** `dissonance_mean`
  (≈0.50), `spectral_contrast` (~3.6 dB), `spectral_flux_mean/std`,
  `bpm_stability` (0.92–0.96), `onset_rate` (1.75–2.18), `energy_std`,
  `chroma_entropy` (0.96–0.99). Они не отделят один трек от другого.
- **`mood` — слабый сигнал** (median confidence ≈0.05): только грубый хинт,
  не ground truth. Curate FEATURE-FIRST.
- **NULL на L2 — не фильтруй `__gte/__lte`:** `bpm_confidence`,
  `true_peak_db`, `danceability`, `dynamic_complexity`, `pitch_salience_mean`,
  `mfcc_vector`, `tonnetz_vector`, `spectral_complexity_mean` (essentia/L3+).
  NULL проваливает `>=`/`<=` → тихо опустошает выборку. Проверяй их только на
  L5'нутых треках сета.
- **`energy_mean` ≠ громкость** (нормирован per-track к max=1.0): ранжируй им
  интенсивность ВНУТРИ слота, но шаг громкости между треками меряй
  `integrated_lufs` (engine: hard-reject >6 LUFS, предпочтительный рост +0.5).

## Гармония/тональность: ключ — мягкое предпочтение

- **Camelot hard-reject теперь key-reliability-aware** (фикс 2026-06-23):
  дистанция ≥5 реджектит только если ОБА трека тональны (`not atonality`) и
  уверены (`key_confidence >= settings.transition.hard_reject_key_confidence_floor`,
  дефолт 0.5). На нашей библиотеке **98.7% атональны** → безусловный gate ложно
  реджектил перкуссивные пары, у которых «клэш» неслышим. Unknown (None) →
  считается надёжным (легаси-поведение сохранено). Реализовано на обоих путях
  (`hard_constraints._key_reliable` + `bulk_scorer.hard_reject_mask_bulk`, parity).
- **Мягкий** `S_harmonic` всё ещё взвешивает Camelot 40% независимо от поджанра;
  единственное живое смягчение мягкого скора — `hnr_db`-множитель (per-subgenre
  downweight — открытый Phase-2). Атональные/перкуссивные пары всё равно лучше
  роутить по groove (`S_groove`/`S_bpm`) — picker выберет DRUM_SWAP/DRUM_CUT/FADE.
- Детальные «known code quirks» (chroma-шкала, единый источник Camelot-таблиц,
  beats_loudness clip, intent-веса) — в @docs/transition-scoring.md и справочнике.
