# Cell 15 — Tempo & BeatGrid

Own only: `app/audio/**` plus narrowly scoped audio-analysis tests/docs if required. Do not edit `app/domain/**`, models/repositories, or MCP tools.

Implement the analysis foundation described by Wave 5:
- Introduce/upgrade a first-class BeatGrid representation in the audio layer with beat timestamps, downbeats, phase, beats-per-bar, phrase/bar metadata, confidence, stability, and tempo curve where supported.
- Represent tempo hypotheses rather than relying solely on one BPM float; explicitly handle 0.5x/1x/2x ambiguity and confidence.
- Reuse existing librosa/Essentia analyzers and project conventions. Do not add heavy dependencies just for this task.
- Keep cheap library analysis distinct from deeper mixing analysis. Do not run real Demucs inference.
- Add deterministic unit tests using synthetic/small fixtures where possible.
- Preserve existing analyzer APIs or provide adapters.

Before editing, inspect current audio analyzers and use GitNexus impact where available. At finish write `.mece/cells/15-tempo-beatgrid/REPORT.md` with paths, verification, blockers, and OpenCode session id.
