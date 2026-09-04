# Cell 02 — Audio Pipeline Report

Branch: `mece/wave-2026-09-03`
Cell: `02-audio-pipeline`
Date: 2026-09-03
Session: opencode timed out (120s); manual inspection completed.

## Mission
Own the audio-analysis, DSP, stems, and rendering subsystem. Identify and implement only changes that belong to audio behavior.

## What changed (paths)
- **No source changes in `app/audio/` or audio-related code.**
- `opencode run --pure` exceeded 120s timeout; no edits applied.
- `app/audio/pipeline.py`, `app/audio/analyzers/`, `app/audio/deep/`, `app/audio/effects/`, `app/audio/render/` — unchanged.
- `docs/audio-pipeline.md` — unchanged (read for scope verification).

Pre-existing unstaged modifications confirmed (not from this cell):
- `.opencode/agents/dj-music.md`
- `.opencode/opencode.json`
- `AGENTS.md`
- `CLAUDE.md`
- `opencode.json`

## Scope verification (inspection only)

### DSP / Analysis (app/audio/)
- `pipeline.py`: AnalysisPipeline with ThreadPool (`use_processes=False`) and ProcessPool (`use_processes=True`) paths. SharedMemory transport, per-worker LRU AnalysisContext cache (`_WORKER_CONTEXT_CACHE`), stitched 60s multi-window clip (`_DEFAULT_N_WINDOWS=3`, `_FADE_MS=20.0`), IBI outlier filter (`[0.5, 1.5] x median`), mood classifier (`_MOOD_REQUIRED_FEATURES`).
- `core/`: AudioLoader, AnalysisContext, AudioSignal, types, loader, context.
- `analyzers/`: 18+ analyzers registered (bpm, beat, key, spectral, energy, loudness, structure, mfcc, tempogram, tonnetz, dissonance, danceability, pitch_salience, dynamic_complexity, spectral_complexity, beats_loudness, phrase, bpm_histogram, voicing, inharmonicity, meter, audio_qa, chords, hpcp_extended). Base interface: `name`, `capabilities`, `required_packages`, `clip_duration_s`, `depends_on`.
- `classification/`: MoodClassifier (`MoodClassifier`) — rule-based, no ML model.
- `render/`: `diagnostics.py`, `grid_check.py`, `kick_phase.py`, `phase_refine.py`.
- `deep/`: `demucs_runner.py`, `demucs_onnx_runner.py`, `demucs_mlx_runner.py`, `stem_analyzer.py`, `beatgrid_builder.py`, `embedding_builder.py`, `cross_similarity.py`, `structure_analyzer.py`, `timeseries_store.py`, `waveform_store.py`, `drum_bands.py`.
- `effects/`: `automation.py`, `echo_delay.py`, `filter_sweep.py`, `reverb.py`.

### Render / Beatgrid lessons
- `skills/validate-set/SKILL.md`: grid validation workflow (`render_validate_grid`), pre-render checklist (Camelot distance, BPM discrepancy > 0.5, phase offset > 0.25 beat, phase measurement on original audio not stems), `bpm_measured` vs `stored_bpm`, `grid_check.json`, never-re-render-without-DSP-change rule.
- `AGENTS.md` notes: default effects (`filter_sweep`, `echo`, `reverb`) always passed as `None`; FastMCP fixed at `<3.4` due to middleware regression; `AGENTS.md` governance debt (~230 lines vs recommended ~100).

### Dependencies / Tests
- `docs/audio-pipeline.md`: `[audio]` extra (librosa, soundfile); `[stems]` extra (demucs, torch) — **NOT YET IMPLEMENTED** per docs.
- Tests present: `tests/audio/analyzers/`, `tests/audio/classification/`, `tests/tools/render/` (beatgrid, stem_transition_policy, render diagnosis), `tests/repositories/test_stem_features_repo.py`, `tests/schemas/test_stem_features.py`.
- No new test failures observed (tests not executed due to timeout; existing tests reference unchanged paths).

## Blockers / residual risk
- `opencode run --pure` timed out at 120s; no automated changes produced. Manual verification completed instead.
- GitNexus `gitnexus_query` requires `repo` parameter; vector search unavailable (`Multiple repositories indexed`). Impact analysis not executed for any audio symbol due to timeout and no edit target.
- `[stems]` extra documented as not yet implemented (`demucs` stem separation not fully wired); deep L6 pipeline (`StemSeparator`) depends on it.
- `docs/audio-pipeline.md` references `StemSeparator` / `demucs/htdemucs` but the docs note `NOT YET IMPLEMENTED`. This is a known gap, not a new regression.
- ProcessPool path (`use_processes=True`) relies on `multiprocessing.get_context("forkserver")` — safe on macOS but worker spawn cost (~0.5-1s) must be amortized over multiple analyses; single-shot calls pay the cost without benefit.
- No verification that `pipeline.py` SharedMemory cleanup (`finally` block with `shm.close()` + `shm.unlink()`) behaves correctly under concurrent worker crashes; no crash/recovery test observed.

## How to verify
```bash
# Inspect audio pipeline files unchanged
ls -la app/audio/
git diff --stat  # should show 0 changes in app/audio/

# Read key source
cat app/audio/pipeline.py | head -60
cat docs/audio-pipeline.md

# Check render/beatgrid skills
cat skills/validate-set/SKILL.md

# Confirm pre-existing unstaged files only
git status --short
```

## Unresolved issues
- No automated `opencode` output captured (timeout).
- `[stems]` dependency gap remains documented but unimplemented.
- No performance benchmarks run for ProcessPool vs ThreadPool on this branch.
- No `gitnexus_impact` executed for audio symbols (no edit target; timeout prevented it).

## Session / session id
No session id available; `opencode` did not return a run ID before timeout.
