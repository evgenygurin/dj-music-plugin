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
