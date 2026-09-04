# Mem0 Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current fragile Mem0 patching approach with a maintainable Platform + OpenCode policy integration and a clean SDK/MCP boundary.

**Architecture:** Mem0 Platform remains the single backend. OpenCode keeps the official Mem0 plugin/native tools, while a local policy plugin owns proactive retrieval, durable-only capture, scope defaults, redaction, and failure-open behavior. Application code can use the Mem0 SDK independently; other MCP clients use hosted Mem0 MCP.

**Tech Stack:** OpenCode 1.18.27, `@mem0/opencode-plugin` 0.2.2, `mem0ai` SDK, TypeScript/JavaScript local OpenCode plugin, Mem0 Platform API, hosted Mem0 MCP.

**Spec:** `docs/superpowers/specs/2026-09-04-mem0-architecture-design.md`

## Global Constraints

- Keep Mem0 Platform as the managed backend; do not introduce a local vector or graph database.
- Keep project scope as the default; global cross-project retrieval requires explicit intent.
- Never persist API keys, passwords, tokens, credentials, raw `.env`, large logs, or secrets.
- Retrieval must be read-only and non-blocking; Mem0 failures must not stop OpenCode work.
- Capture only durable project knowledge or stable preferences.
- Do not leave modifications inside `node_modules/@mem0/opencode-plugin/dist/index.js` as the final implementation.
- Do not register duplicate Mem0 MCP tools alongside the official OpenCode plugin tools.
- Do not reboot the Mac or start heavy concurrent workloads.

---

### Task 1: Inventory the vendor plugin and current configuration

**Files:**
- Read: `.opencode/opencode.json`
- Read: `docs/MEM0_BEST_PRACTICES.md`
- Read: `~/.config/opencode/opencode.json`
- Read: `~/.config/opencode/node_modules/@mem0/opencode-plugin/dist/index.js`

- [x] **Step 1: Record the official plugin hooks and tool registration.**

Run:
```bash
node -e "import('/Users/laptop/.config/opencode/node_modules/@mem0/opencode-plugin/dist/index.js').then(async m=>{const h=await m.default({project:{},directory:process.cwd(),worktree:process.cwd(),client:{app:{log:async()=>{}}},$:Bun.$}); console.log(Object.keys(h).join('\\n'))})"
```
Expected: the current Mem0 lifecycle hooks and `tool` registration are listed.

- [x] **Step 2: Locate the current automatic retrieval/capture branches.**

Run:
```bash
grep -nE 'memoryCount|mem0\.search|mem0\.add|chatMessageHook|experimental\.chat\.messages\.transform|shell\.env' /Users/laptop/.config/opencode/node_modules/@mem0/opencode-plugin/dist/index.js
```
Expected: current gates and SDK calls are identified before changing behavior.

- [x] **Step 3: Confirm no active standalone Mem0 MCP is configured in OpenCode.**

Run:
```bash
grep -nE 'mcp\.mem0\.ai|mem0-mcp|"mem0"' /Users/laptop/.config/opencode/opencode.json /Users/laptop/dev/dj-music-plugin/.opencode/opencode.json 2>/dev/null || true
```
Expected: no duplicate hosted Mem0 MCP entry.

---

### Task 2: Add a maintainable local Mem0 policy plugin

**Files:**
- Create: `.opencode/mem0-policy.js`
- Modify: `.opencode/opencode.json`

**Interfaces:**
- Consumes: OpenCode plugin context and the official `@mem0/opencode-plugin` tools.
- Produces: proactive read-only retrieval and durable-only capture without editing vendor files.

- [x] **Step 1: Write a failing smoke test harness for the policy module.**

Create a temporary Node/Bun test that imports `.opencode/mem0-policy.js` with a mocked Mem0 client and asserts that a substantial prompt causes a `search` call even when the initial memory count is zero.

- [x] **Step 2: Implement project identity and explicit scope helpers.**

Use the repository git remote to derive `evgenygurin-dj-music-plugin`; use a stable non-secret `MEM0_USER_ID`; default retrieval filters to `{ AND: [{ user_id }, { app_id }] }`.

- [x] **Step 3: Implement durable classification and redaction.**

Classify only architecture decisions, debugging/root-cause findings, dependency choices, environment/setup knowledge, testing strategy, deployment/security constraints, code conventions, API contracts, and stable preferences. Redact credential-like values before any Mem0 call.

- [x] **Step 4: Implement proactive retrieval without the `memoryCount > 0` gate.**

For substantial prompts, issue two read-only searches in parallel: the semantic prompt query and a category-focused query. Deduplicate by memory ID and cap injected context at five concise memories.

- [x] **Step 5: Implement asynchronous durable capture.**

Capture only classified durable prompts, with `infer: true`, project/user scope, category metadata, and session/branch metadata. Do not block the model response on capture.

- [x] **Step 6: Implement failure-open behavior.**

Wrap Mem0 retrieval/capture calls so timeouts or API failures are logged at low severity and do not mutate or abort the OpenCode response.

- [x] **Step 7: Run the policy test.**

Run the temporary test and require PASS for empty-scope proactive retrieval, redaction, category classification, and failure-open behavior.

---

### Task 3: Preserve official Mem0 tools without duplicate MCP registration

**Files:**
- Modify: `.opencode/opencode.json`
- Read: `.opencode/mem0-policy.js`

- [x] **Step 1: Confirm the official plugin remains enabled.**

Require `@mem0/opencode-plugin` in the project plugin list.

- [x] **Step 2: Load the local policy plugin after the vendor plugin.**

Ensure OpenCode loads the policy layer without replacing the official native memory tools/skills.

- [x] **Step 3: Verify tool names are unique.**

Run an OpenCode plugin inspection and assert exactly one registration for each Mem0 memory tool.

---

### Task 4: Remove the vendor-bundle patch and restore the package-managed file

**Files:**
- Restore: `~/.config/opencode/node_modules/@mem0/opencode-plugin/dist/index.js`
- Preserve: `~/.config/opencode/backups/mem0-plugin-cleanup-20260903/index.js`

- [x] **Step 1: Compare the current vendor bundle with the backup.**

Run:
```bash
diff -u /Users/laptop/.config/opencode/backups/mem0-plugin-cleanup-20260903/index.js /Users/laptop/.config/opencode/node_modules/@mem0/opencode-plugin/dist/index.js | head -120
```
Expected: differences are limited to our local patch.

- [x] **Step 2: Restore only the vendor bundle.**

Copy the known-good package backup back into `dist/index.js`; do not reinstall dependencies or alter unrelated packages.

- [x] **Step 3: Verify the restored bundle.**

Run:
```bash
node --check /Users/laptop/.config/opencode/node_modules/@mem0/opencode-plugin/dist/index.js
```
Expected: PASS.

---

### Task 5: Configure stable Mem0 identity and policy documentation

**Files:**
- Modify: `~/.config/opencode/MEM0_POLICY.md`
- Modify: `docs/MEM0_BEST_PRACTICES.md`
- Modify: `.opencode/opencode.json`

- [x] **Step 1: Document the Platform/SDK/MCP boundary.**

State: Platform is the backend; SDK/API is for application code; official plugin is for OpenCode lifecycle integration; hosted MCP is for other MCP clients.

- [x] **Step 2: Document scopes and the no-duplicate rule.**

State project as default, session for transient context, global only by explicit request, and no duplicate Mem0 MCP when the OpenCode plugin already supplies native tools.

- [x] **Step 3: Configure a stable non-secret user identity if one is already available.**

Never place an API key or other credential in the policy files.

---

### Task 6: Verify the complete round trip

**Files:**
- Test: temporary local verification script under `/tmp`, then remove it

- [x] **Step 1: Verify proactive search on an empty project scope.**

Use a substantial synthetic query and assert that `search` is called despite zero existing memories.

- [x] **Step 2: Verify a real add/search/delete round trip.**

Add one clearly synthetic test memory under project scope, search for it, verify it is returned, then delete exactly that memory. Do not leave test data in the account.

- [x] **Step 3: Verify secret redaction.**

Pass synthetic credential-shaped values through the capture path and assert the outbound payload contains no secret value.

- [x] **Step 4: Verify OpenCode config and plugin loading.**

Run the project's existing OpenCode/config validation command if available and inspect the final plugin list.

- [x] **Step 5: Verify repository cleanliness.**

Run:
```bash
git diff --check && git status --short
```
Expected: only intended Mem0 policy/config/docs changes are present.

- [x] **Step 6: Final verification gate.**

Run all focused Mem0 tests plus the project's relevant lightweight checks. Do not claim completion until command output confirms success.
