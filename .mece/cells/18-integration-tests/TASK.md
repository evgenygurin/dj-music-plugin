# Cell 18 — MCP Integration, End-to-End Contracts & Docs

Own `app/tools/**`, `app/resources/**`, `app/prompts/**`, `app/server/**`, `tests/**`, and `docs/**` as needed. Do not edit audio/domain/persistence implementation paths except to report integration blockers.

Consume cells 15–17 and integrate the new DJ mixing capabilities into the existing FastMCP surface. Expose useful analysis/transition functionality following current tool/resource patterns, while keeping the public API coherent. Add integration and regression tests for: track analysis → beatgrid, candidate cue points, alignment score, and transition recommendation. Tests must not run full Demucs inference on the 8 GB M2 machine.

Update concise architecture/research docs explaining BPM vs beatgrid vs phrase alignment and the staged cheap→deep analysis strategy. Run targeted tests plus the project's appropriate checks. Finish with `.mece/cells/18-integration-tests/REPORT.md`.
