# Cell 16 — Pure DJ Mixing Domain

Own only `app/domain/**` (and tests only if they are domain-local under an existing domain-test convention). Do not edit audio infrastructure, DB, repositories, or MCP tools.

Implement pure domain contracts and algorithms for:
- TempoHypothesis / TempoModel consumption contracts.
- Beat/phase alignment scoring.
- Accumulated beat drift over a transition window.
- Phrase/bar alignment and cue-point candidate representation.
- Musical transition durations constrained to 4/8/16/32/64 bars.
- A transition alignment component that can be composed with the existing TransitionScorer without importing infrastructure.
- Keep existing transition score APIs compatible; avoid magic numbers by putting tunables in the domain's existing configuration/weights mechanism.

Use NumPy only where the domain already permits it. Keep functions deterministic and testable. Do not infer timestamps with an LLM. Add tests for octave tempo matching, phase offset, drift, phrase boundaries, and transition duration selection.

Read cell 15 report before starting. Run GitNexus impact before symbol edits. Finish with `.mece/cells/16-mixing-domain/REPORT.md` including verification and session id.
