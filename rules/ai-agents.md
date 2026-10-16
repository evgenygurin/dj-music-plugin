# AI Agents / OpenCode Rules

## Default model provider

**HARD RULE — ALWAYS USE OPENROUTER FREE**

For every OpenCode agent invocation started for this repository, the default
model/provider MUST be:

`openrouter/openrouter/free`

Do not default to `opencode/*`, Anthropic, OpenAI, or any paid model.

### Invocation policy

- Prefer explicit CLI selection: `--model openrouter/openrouter/free`.
- If an OpenCode configuration defines a default agent model, it must not
  override this repository rule for delegated implementation work.
- A different provider/model may be used only when the user explicitly
  requests it in the current task.
- Never silently fall back to a paid provider after a free-model failure.
- When `openrouter/openrouter/free` is unavailable or fails, stop and report
  the failure rather than switching providers without explicit approval.

### Resource discipline

- Prefer one implementation agent at a time on this Mac.
- Keep agent context and token budgets bounded where OpenCode supports it.
- Kill stale/hung agent processes before starting another implementation agent.

### Verification

Before reporting an agent task as complete, verify the agent's result in the
worktree: inspect git diff/status, run the applicable project checks, and verify
that only the intended scope changed.

### Repository rules

These AI-agent rules complement `AGENTS.md`, `rules/general.md`, and
`rules/development.md`. They do not replace GitNexus impact/detect-change
requirements or the repository's `uv`-only execution rule.
