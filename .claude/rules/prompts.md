# MCP Prompt Rules

Prompts are workflow instructions exposed through the MCP surface. Keep them deterministic, explicit about the workflow they describe, and aligned with the runtime contracts they invoke.

## Canonical structure

- Keep prompt implementation separate from repositories, providers, DB access, and domain computation.
- Prefer pure text builders that describe actions for the model to execute through the actual MCP surface.
- Keep prompt signatures simple and explicit; avoid variadic parameters and hidden state.
- Use the project-supported FastMCP prompt APIs and follow the surrounding implementation pattern.

## Contract correctness

Every runtime identifier embedded in a prompt must resolve to a real current contract. Prompt tests should validate entity names, provider operations, schema fields, filter keys, mutation payloads, cross-prompt references, and other constrained literals against runtime registries or schemas rather than relying on a manually maintained catalog.

When a contract changes, update the prompt and the corresponding executable validation together.

Do not maintain a second hand-written list of prompt names or counts for documentation purposes. Runtime registration and tests are the source of truth.

## Workflow honesty

Prompt text must not promise capabilities that the engine does not provide. Known limitations belong in the domain documentation or tests that define the limitation; do not encode temporary implementation gaps as permanent architecture.

## Domain accuracy

For set-building, transition, delivery, and repair workflows, keep musical terminology and decision rules consistent with the current domain contracts. Prefer references to durable concepts over hard-coded snapshots of today's presets, counts, or implementation details.

## FastMCP upgrades

When upgrading FastMCP, verify prompt discovery, result shape, metadata, and registration behavior through the running framework and tests. Do not use this file as a version-by-version compatibility ledger.
