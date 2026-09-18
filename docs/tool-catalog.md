# MCP Surface Guide

This document explains the stable shape of the MCP interface. It is not a generated inventory of every current tool, resource, prompt or provider operation.

## Surface model

The MCP surface has three primary kinds of objects:

- **Tools** perform operations and expose typed input/output contracts.
- **Resources** expose read-only context and projections through URI-addressable views.
- **Prompts** describe repeatable workflows for the model to execute against the real MCP surface.

The server uses schema-driven composition and registry-backed dispatch where appropriate. This keeps the external surface composable without duplicating business logic across many endpoint implementations.

## Entity operations

Generic entity operations resolve their target through the entity registry and validate data through the corresponding schemas. Side effects that are specific to an entity belong to application handlers rather than to the generic dispatcher itself.

The exact entity set and schema are runtime facts. Inspect `schema://entities` or the registry/tests when an exact current contract is required.

## Provider operations

External music services are accessed through a provider boundary. Provider-specific entities and operations are discovered from the provider registry/capabilities rather than copied into a permanent catalog.

Treat provider credentials, authentication modes, endpoint quirks and current capability matrices as provider/runtime concerns. Keep durable provider policy in the dedicated provider documentation.

## Analysis and DJ engine

Higher-level compute and render operations compose audio analysis with DJ-domain logic. Analysis produces typed feature information; candidate generation and transition scoring operate on that information; planning chooses a sequence; rendering materializes the plan.

Heavy audio operations may run as background tasks where the runtime supports them. This is an implementation detail of the execution layer, not a reason to duplicate a complete endpoint inventory here.

## Namespace and visibility

Some operations may be gated or hidden from model discovery while remaining callable by UI or internal composition. Current visibility is runtime state. Use the server's visibility configuration and framework discovery when troubleshooting what a client can see.

## Contract validation

When changing the MCP surface, update executable registration/schema tests. Prefer tests that derive allowed names and fields from the same registries and schemas used by the runtime.

Never repair a stale documentation count instead of fixing the executable contract.

## Exact current inventory

For an exact list of current MCP objects, use FastMCP discovery/introspection or the corresponding schema/registry resources. This file intentionally does not reproduce those lists.
