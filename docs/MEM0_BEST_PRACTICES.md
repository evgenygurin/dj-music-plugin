# Mem0 + OpenCode — Best Practices

Current stack: OpenCode 1.18.27, `@mem0/opencode-plugin` 0.2.2, Mem0 Platform.

## Architecture

- Mem0 Platform is the single managed memory backend.
- Application code should use the `mem0ai` SDK/API directly.
- OpenCode uses a local policy wrapper around the official Mem0 plugin so native memory tools and skills remain available without running duplicate lifecycle hooks.
- Other MCP clients may use the hosted Mem0 MCP server (`https://mcp.mem0.ai/mcp`).
- Do not register the hosted Mem0 MCP alongside the native OpenCode Mem0 tools in the same OpenCode instance.
- The policy plugin is the canonical source in `.opencode/mem0-policy.js` and is symlinked into `~/.config/opencode/plugins/` for global use.

## Scopes and identity

- `project`: default; filters by stable `user_id` + repository `app_id`.
- `session`: transient run context; use `run_id` only for short-lived state.
- `global`: cross-project access only after an explicit user request.
- Project identity for this repository is `evgenygurin-dj-music-plugin`.
- `MEM0_USER_ID` may be set explicitly to keep personal memory stable across machines.

## Retrieval policy

Every substantial prompt is eligible for proactive read-only retrieval, even when the project has zero stored memories. The policy performs two bounded searches in parallel: a semantic query and a category-focused query. Results are deduplicated and capped at five memories before context injection. Mem0 errors fail open and do not block the task.

## Durable capture

Automatic capture is not periodic prompt sampling. A prompt must first pass a durability classifier. Candidates include architecture decisions, debugging/root causes, dependency choices, environment/setup knowledge, testing strategy, deployment/security constraints, code conventions, API contracts, and stable preferences. Captures use project scope, category metadata, and `infer: true`, and run asynchronously.

Do not store API keys, passwords, access tokens, credentials, raw `.env` content, large logs, source dumps, temporary state, or speculation. Credential-shaped values are redacted before Mem0 calls.

## Official plugin boundary

The official `@mem0/opencode-plugin` package is package-managed and is not patched in `node_modules`. The local policy imports its `config` and native `tool` registrations but intentionally replaces its automatic lifecycle hooks so proactive behavior is controlled in one place.

## MCP boundary

Use hosted Mem0 MCP when an agent needs memory tools but does not have the OpenCode plugin. MCP exposes `add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`, `delete_memory`, `delete_all_memories`, `delete_entities`, and `list_entities`. MCP has no OpenCode lifecycle hooks; those belong to the plugin/policy layer.

## Desktop

The Mem0 API key must not be written to OpenCode or project configuration. The policy resolves it from `MEM0_API_KEY` or standard shell profiles without printing it. No reboot is required for file-level verification; a running OpenCode process must reload plugins before runtime changes become active.

## Verification

Run the focused Bun policy tests, syntax checks, plugin loading inspection, project identity check, proactive-search smoke test, and a real add/event-status/search/delete round trip with synthetic data. Remove all synthetic verification memories after testing.

## Mem0 Platform project configuration

The managed Mem0 project is configured for the coding-agent workload with:

- 20 custom categories: architecture_decisions, api_design, data_models, algorithms,
  dependencies, environment_setup, testing_strategy, debugging_notes, performance, security,
  deployment, code_conventions, error_handling, refactoring_history, integrations, onboarding,
  project_meta, user_preferences, tooling_workflow, research_findings.
- Descriptions are attached to every category so the classifier can distinguish similar concepts.
- `custom_instructions` explicitly prioritizes durable engineering knowledge and excludes secrets,
  raw logs, large code blocks, transient state, and speculation.
- `agent_custom_instructions` applies the same rules to coding-agent memory.
- `multilingual=true` supports mixed Russian/English project work.
- `decay=true` is enabled so recently reinforced memories receive a ranking boost while stale
  memories are gently dampened; nothing is filtered out solely because it is old.

Mem0's current Platform automatically performs Supersede and Merge during memory ingestion.
Dream Synthesis is plan-gated (Pro/Enterprise) and must be enabled from the Mem0 project Dream
settings; it is not silently emulated by the local policy. This is intentional because Synthesis
only considers user-scoped memories without `app_id`, while this project uses `user_id + app_id`
for strict project isolation.
