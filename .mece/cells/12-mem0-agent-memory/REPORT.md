# Cell 12 Report — Mem0 / Agent Memory

Baseline SHA: e9351f839403ec722f0ce530c69cd1c1f357ccfa

## Changes

- Removed the project-local Mem0 wrapper from auto-discovery because it caused
  an OpenCode `config` hook failure.
- Disabled the duplicate global wrapper at
  `~/.config/opencode/plugins/mem0-policy.js.disabled` rather than deleting it.
- Project config now uses the official `@mem0/opencode-plugin` package once.
- Kept `.opencode/mem0-policy.js` and its tests as policy research/contract code;
  it is not auto-loaded as an OpenCode plugin.

## Runtime evidence

The official plugin factory was loaded through Bun and exposed 10 native tools,
including `add_memory` and `search_memories`.

A real Mem0 runtime probe executed:
1. `add_memory` — returned `SUCCEEDED` with a memory ID.
2. `search_memories` — returned the just-created probe memory.
3. `delete_memory` — removed the probe memory immediately.

No probe memory was intentionally left behind.

## OpenCode CLI

A CLI startup after disabling the duplicate wrapper showed no plugin config-hook
error. The full model prompt did not complete within the bounded 20-second test,
so end-to-end OpenCode model-mediated tool invocation remains unclaimed.

## Verification

`bun test ./.opencode/tests/mem0-policy.test.js`: **4 passed, 0 failed**.
