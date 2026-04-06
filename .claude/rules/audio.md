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

- `classify_mood` and `distribute_to_subgenres` persist `mood` and `mood_confidence` to `track_audio_features_computed`
- Pipeline features → DB: always use `TrackAudioFeaturesComputed.filter_features(result.features)` — pipeline may return keys without columns
- Tiered auto-trigger: `classify_mood`/`build_set`/`deliver_set` auto-analyze tracks — no need to call `analyze_track` manually
- P1 analyzers: essentia DFA danceability is unbounded (not 0-1), dissonance 0-1, dynamic_complexity 0-~10
- P2 analyzers: SpectralComplexityAnalyzer, PitchSalienceAnalyzer depend on essentia; BpmHistogramAnalyzer depends on `beat` (depends_on); PhraseAnalyzer depends on `beat` + `bpm`
- `depends_on`: `ClassVar[frozenset[str]]` — Phase 2 pipeline passes `prior_results` to dependent analyzers
- `_ANALYZER_REGISTRY`: global dict, `importlib` doesn't re-register decorator on re-import — in tests delete only `_test_*` keys, never `clear()`
- Beat analyzer: processes first `settings.audio_beat_analysis_duration` seconds (default 60), not the entire track
- MP3 analysis: requires `uv sync --extra audio` (librosa + soundfile)
