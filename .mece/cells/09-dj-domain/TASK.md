# Cell 09 — DJ Domain

## Mission
Own pure DJ-domain behavior and invariants.

## Read
- `app/domain/**`
- domain-facing schemas and tests
- transition, scoring, harmonic, BPM, sequencing and template docs

## Scope
- Transition compatibility and hard constraints.
- BPM/harmonic scoring and phase logic.
- Set sequencing and optimization.
- Templates, aliases, subgenre profiles, and pure decision rules.

## Write ownership
- `app/domain/**`
- Pure domain-facing contracts only when clearly domain-owned.

## Constraints
- No DB, HTTP, FastMCP, or provider dependency in domain code.
- Preserve canonical names and aliases.
- GitNexus impact before symbol edits.

## Deliverable
`REPORT.md` with invariants, changed symbols, tests, risks, and dependencies.