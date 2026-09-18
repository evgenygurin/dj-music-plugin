# Architecture

## System Overview

```text
MCP client
   │
   ▼
FastMCP composition
   │
   ├── tools ───────► application/handler orchestration
   ├── resources ───► read-only views and context
   └── prompts ─────► workflow instructions
                     │
                     ▼
              application layer
               │      │      │
          domain   audio   providers
               │      │      │
               └──────┼──────┘
                      ▼
              repositories / UoW
                      │
                      ▼
                 persistence
```

FastMCP is the transport-facing composition boundary. Business behaviour belongs below that boundary and must remain testable without an MCP client.

## Layer boundaries

| Layer | Responsibility |
|---|---|
| MCP surface | Exposes tools, resources and prompts; validates public contracts and composes workflows. |
| Application | Coordinates use cases, side effects and dependency injection. |
| Domain | Implements pure DJ/music policy and algorithms without transport or persistence dependencies. |
| Audio | Extracts and transforms audio information behind typed analysis contracts. |
| Providers | Integrates external music platforms behind explicit provider contracts. |
| Repositories | Encapsulates persistence and transaction participation. |
| Shared/config | Holds cross-cutting primitives and configuration without becoming a hidden service layer. |

The exact inventory of runtime objects belongs to the code and framework discovery, not to this document.

## Data flow

A normal tool call crosses the MCP boundary, resolves dependencies, executes application/domain logic, persists through the repository/UoW boundary when required, and returns a typed result. Failures are translated at the appropriate boundary rather than leaking infrastructure exceptions to callers.

Transactions are owned by the application/server composition. Repositories do not become an alternative transaction manager.

## Bounded contexts

The main conceptual boundaries are library/entity management, audio analysis, DJ transition/set logic, external music providers, and MCP composition. Each context owns its policy and contracts; integration happens through explicit interfaces or application orchestration.

## Audio architecture

Audio processing follows a staged analysis model: inexpensive information can be computed before deeper analysis, dependent analysis consumes prior results, and expensive capabilities remain isolated behind optional dependencies/capability checks.

Shared analysis state should be reused where multiple analyzers need the same DSP primitives. Cache identity and invalidation must account for all inputs that can change the computed result.

## Universal AI DJ Engine

The DJ engine conceptually separates:

`analysis → candidate generation → hard technical validation → musical scoring → planning → rendering → persistence`

Technical feasibility and musical preference are separate dimensions. A hard constraint rejects an unusable transition; scoring ranks technically valid candidates.

Transition and set plans carry explicit identity/provenance so results can be reproduced and compared. Rollout of replacement implementations must preserve a safe compatibility path until the new path is intentionally promoted.

## MCP composition principles

Prefer polymorphic, schema-driven operations and workflow composition over proliferating near-duplicate endpoints.

Resources provide context and representations. Tools perform operations. Prompts describe repeatable workflows. None of these should silently replace a domain service or repository abstraction.

## Source of truth

Runtime surface, registration, schemas, dependency versions, test counts, and generated inventories are derived facts. Use the code, manifests, framework introspection, tests and validators to obtain them.

This architecture document intentionally does not repeat volatile counts, index statistics, historical implementation snapshots, or release-specific inventories.
