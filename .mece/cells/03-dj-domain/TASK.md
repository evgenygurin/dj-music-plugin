# Cell 03 — DJ Domain

## Mission
Own pure DJ-domain logic: transitions, scoring, optimization, templates, subgenres, set construction rules, and domain invariants.

## Read
- `AGENTS.md` and relevant `rules/`
- `app/domain/**`
- domain-facing schemas/handlers for contracts
- transition/scoring/template/subgenre documentation and references
- relevant domain tests

## Scope
- Transition scoring and hard constraints.
- Camelot/harmonic compatibility.
- Set sequencing and optimization algorithms.
- Template registry and aliases.
- Subgenre profiles/constants and genre journeys.
- Pure audit/rules/decision logic.

## Write ownership
- `app/domain/**`
- domain-specific schema/model-adjacent logic only when it is demonstrably pure and parent-approved

## Do not touch
`app/audio/**`, MCP composition, provider/database infrastructure, root config, or another cell's files.

## Constraints
- `app/domain/` must remain independent of DB, HTTP, and FastMCP.
- Preserve canonical template/subgenre naming and aliases.
- Do not introduce service-layer coupling merely to simplify orchestration.
- Run GitNexus impact before symbol edits.

## Deliverable
`REPORT.md` with invariants, changed symbols, impact analysis, tests, algorithmic/performance risks, and cross-cell dependencies.
