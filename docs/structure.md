# Project Structure

This document describes the stable organization of the codebase. It is intentionally not a generated file tree or database snapshot.

## Repository-level responsibilities

```text
AGENTS.md / rules/       project and agent policy
README.md                user-facing overview and getting started
CLAUDE.md / agents/      host-specific agent guidance
app/                     application and domain implementation
docs/                    durable architecture and domain documentation
scripts/                 maintenance and verification utilities
tests/                   executable contracts and regression coverage
```

## Application boundaries

```text
app/
├── tools/                MCP operations and public tool contracts
├── resources/            MCP read-only context and views
├── prompts/              MCP workflow instructions
├── handlers/             application-side effects and orchestration
├── registry/             runtime entity/provider composition
├── repositories/         persistence access and transaction participation
├── models/               persistence models
├── schemas/              typed request/response contracts
├── domain/               pure DJ/music policy and algorithms
├── audio/                audio analysis and DSP orchestration
├── providers/            external music-service integrations
├── server/               FastMCP composition, DI and cross-cutting concerns
├── shared/               leaf cross-cutting primitives
└── config/               configuration by concern
```

The exact set of modules and files is owned by the repository itself. Do not copy the current tree into this document when implementation changes.

## Dependency direction

Keep transport-facing code above application orchestration and domain policy. Domain code must not acquire dependencies on FastMCP, HTTP, or persistence infrastructure.

Providers and audio execution are integration/processing concerns and should not become implicit dependencies of pure domain algorithms.

## Persistence

Repositories encapsulate persistence operations. Transaction lifecycle is coordinated at the application/server boundary rather than distributed across individual repository methods.

## MCP surface

Tools, resources and prompts are auto-discovered from their implementation packages where the framework configuration permits it. Runtime inventory must be obtained from FastMCP discovery, registries and schema tests rather than maintained as a duplicate file tree.

## Database schema

The authoritative database schema is represented by the SQLAlchemy models and migration history. This document deliberately does not embed a table count or a generated table list, because those values drift by design.

For current schema questions, inspect the models/migrations or use the project's database inspection tooling.

## Historical documents

Older architecture snapshots, implementation plans and audits remain valuable as history. They should be read as time-bounded records, not as current structure documentation.
