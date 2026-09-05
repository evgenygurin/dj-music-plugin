---
description: Audio analysis engineering rules
globs: app/audio/**/*.py
---

# Audio Analysis Rules

Keep audio analysis modular, typed, deterministic where practical, and isolated from MCP transport concerns.

## Analyzer contracts

- Register analyzers through the project analyzer registry/discovery mechanism.
- Each analyzer returns the typed result expected by the pipeline; do not introduce ad-hoc dictionaries as public analyzer contracts.
- Declare analyzer dependencies explicitly so dependent analyzers receive prior results instead of recomputing or reaching through global state.
- Optional dependencies must be capability-checked and must not make the base audio module unimportable.
- Partial analyzer failure must preserve usable results while surfacing the failed analyzer through the pipeline's typed error/reporting mechanism.

## Pipeline

- Reuse shared DSP context for analyzers that operate on the same audio representation.
- Prefer staged/tiered analysis so inexpensive features can narrow work before expensive analysis.
- Keep expensive processing bounded and explicit; do not turn every high-level request into a full-library deep-analysis sweep.
- Cache keys must include every input that can materially change the computed artifact. Invalidate stale artifacts when those inputs change.
- When parallel execution is used, initialization and resource ownership must be safe for the worker model. Do not assume that an importable optional backend is necessarily executable on the current machine.

## Audio decoding and persistence

- Decode failures must cross the audio boundary as actionable typed errors, not raw backend exceptions where the caller cannot identify the cause.
- Persistent audio artifacts are registered through the application's persistence boundary before downstream analysis depends on them.
- Do not infer that a file existing on disk is equivalent to a persisted library registration.

## DSP correctness

- Shared derived signals (for example onset envelopes or STFT representations) should be computed once per compatible analysis context and reused.
- Tempo, beat phase, key and structural measurements must use algorithms appropriate to the signal and documented tolerance; do not substitute a convenient metric when it has known quantization or confidence failure modes.
- Windowing, stitching and resampling must not introduce artificial events that contaminate beat/tempo measurements. Regression tests should cover known seam and boundary artefacts.

## Heavy backends

Stem separation and other deep audio jobs are optional heavy capabilities. Keep them behind explicit capability checks and maintain a safe fallback/error path.

Do not encode machine-specific benchmark numbers, observed library distributions, batch sizes, memory limits or timing claims in this rule. Put measured evidence in research/benchmark documents and treat it as time-bounded evidence.

## Curation

Use feature distributions only when validated for the target library and task. A feature that is theoretically meaningful but nearly constant in the actual corpus is not a useful ranking signal. Keep corpus-specific findings in research documents rather than turning them into permanent architectural claims.
