# Cell 08 — Audio Pipeline

## Mission
Own audio analysis, DSP, stems, and rendering gaps identified by Wave 3.

## Read
- `AGENTS.md`, `rules/**`, `docs/audio-pipeline.md`
- `app/audio/**` and audio-specific tests
- beatgrid, Demucs, stem analyzer, renderer contracts

## Scope
- BPM/key/beat/energy/spectral/structure analysis.
- Beatgrid and stem contracts.
- `[stems]` implementation readiness and safe resource handling.
- Rendering validation and deterministic audio contracts.

## Write ownership
- `app/audio/**`
- isolated audio handler implementation when clearly audio-owned

## Constraints
- Preserve canonical `htdemucs` and five-stem semantics.
- Avoid full real Demucs inference on the 8 GB local machine unless authorized.
- GitNexus impact before symbol edits.

## Deliverable
`REPORT.md` with changes, tests, resource impact, and cross-cell dependencies.