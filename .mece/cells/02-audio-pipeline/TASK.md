# Cell 02 — Audio Pipeline

## Mission
Own the audio-analysis, DSP, stems, and rendering subsystem. Identify and implement only changes that belong to audio behavior.

## Read
- `AGENTS.md` and relevant `rules/`
- `app/audio/**`
- audio-specific handlers/resources/skills
- `docs/audio-pipeline.md`, render documentation, and relevant reference material
- related audio tests

## Scope
- DSP primitives and analysis context.
- L1→L4 analyzer pipeline.
- BPM/key/beat/energy/spectral/structure analysis.
- Demucs/stem processing and canonical stem semantics.
- Audio rendering and render validation.

## Write ownership
- `app/audio/**`
- audio-specific handler implementation files when clearly isolated to audio behavior
- audio-specific reference/docs only when necessary and parent-approved

## Do not touch
`app/domain/**`, MCP surface, provider/database implementation, shared root config, unrelated tests/docs, or another cell's files.

## Constraints
- Preserve canonical `htdemucs` behavior and current 5-stem postprocessed contract.
- Respect render lessons in `AGENTS.md`, `skills/validate-set/`, and `reference://render/*`.
- Run GitNexus impact before modifying symbols.

## Deliverable
`REPORT.md` with changed files, architectural impact, tests, performance/resource considerations, and unresolved issues.
