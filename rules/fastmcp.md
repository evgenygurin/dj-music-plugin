# FastMCP rules

FastMCP is the transport-facing framework boundary. Keep framework concerns explicit and keep business policy below it.

## Surface design

- Tools perform operations and expose typed schemas.
- Resources provide read-only context and views.
- Prompts describe reusable workflows and remain free of direct persistence/provider side effects.
- Prefer framework discovery and runtime schema introspection over manually duplicated inventories.

## Composition

Keep server construction, dependency injection, middleware, visibility and transforms in the server/composition layer. Do not move these concerns into domain algorithms.

Dependency injection may assemble application services and repositories, but domain code must remain framework-independent.

## Error boundary

Infrastructure and validation failures must cross the MCP boundary through the project's typed error handling rather than leaking raw implementation exceptions.

## Contract evolution

When changing a tool, resource or prompt contract, update the executable schema/registration tests in the same change. Prefer backward-compatible evolution when practical.

Do not encode current object counts or version-specific framework observations here. Verify those from the installed framework and runtime when needed.
