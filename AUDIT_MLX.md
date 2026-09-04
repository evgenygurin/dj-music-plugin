# MLX/Demucs Pipeline Audit — Phase 1 Results

Confirmed: user analysis is exactly correct.

## Problems Found (all confirmed by source inspection)

1. `pyproject.toml` has `mlx>=0.20` but NO `demucs-mlx` dependency.
2. `demucs_mlx_runner.py` expects wrong API: `from demucs_mlx import separate` (does not exist).
3. Actual `demucs-mlx` (v1.4.6) uses `from demucs_mlx import Separator`; `separator.separate_audio_file(path)` handles chunking/OLA/resampling natively.
4. `_get_mlx_model()` returns `None` when import fails → silent zero arrays (`np.zeros(...)`) written to FLAC.
5. `_load_audio()` returns `np.zeros(...)` on missing/corrupt input instead of raising.
6. `mlx_separate()` catches ALL exceptions with `except Exception:` and falls back to zeros.
7. `tests/audio/deep/test_mlx_runner.py` uses `np.zeros()` mock outputs — validates silent failure, not audio integrity.
8. `detect_runtime()` in `app/config/stems.py` checks only `import mlx.core` — does not verify `demucs_mlx` or `Separator` availability.
9. Custom chunking/OLA in `demucs_mlx_runner.py` duplicates `demucs-mlx` native split/overlap-add, but incorrectly (e.g., `mx.eval()` after each chunk is wrong for lazy arrays).
10. No audio integrity validation after separation (only `path.exists()`).

## Design Decision (Phase 2)
- Use native `demucs-mlx.Separator` for MLX path; remove custom chunking/OLA.
- Dependency pair: `demucs-mlx>=1.4.4`, `mlx>=0.31.0`, `mlx-audio-io>=1.3.8`, `mlx-spectro>=0.2.4` (macOS only).
- Remove silent zero fallback; raise `StemInferenceError` or propagate.
- Add `validate_stem_output()` with RMS/peak/duration checks.
- Keep external contract: `mlx_separate(input_path, cache_root, *, model, flac) -> dict[str, Path]`.
- Runtime detection must verify `demucs_mlx.Separator` import, not just `mlx.core`.
