# Runtime surface

The MCP runtime surface is intentionally derived from the application and FastMCP discovery. This document explains how to inspect it; it is not a manually maintained catalog.

## Source of truth

Use, in order of preference:

1. FastMCP discovery/introspection for the currently exposed surface.
2. Runtime registries and Pydantic schemas for entity/provider contracts.
3. Registration and contract tests for executable guarantees.
4. Manifest/configuration files for declared composition.

## Documentation policy

Do not copy the current number of tools, resources, prompts, entities, handlers, middleware layers, analyzers, tests, or other inventory into README, AGENTS, CLAUDE or architecture docs.

When a human needs the exact current catalog, generate it from the runtime or inspect the corresponding registry/source. When a machine needs the contract, tests should validate it directly.

## Changes to the surface

When adding or removing a runtime object, update its implementation and executable registration/contract tests. Update human documentation only when the change introduces or removes a durable capability or architectural concept.

A new prompt does not require a documentation count update. A new analyzer does not require an architecture count update. A new registry entry does not require a README inventory update.

## Historical material

Audits and changelogs may retain historical runtime counts when those counts are part of the historical record. Those documents must not be treated as current runtime documentation.
