# Cell 07 Report — Repository Governance

Baseline SHA: e9351f839403ec722f0ce530c69cd1c1f357ccfa
Branch: mece/wave-2026-09-03

## Findings
1. AGENTS.md says it should be about 100 lines, but the current file is much longer and mixes routing with detailed rules.
2. Runtime entrypoint documentation is inconsistent: AGENTS.md/root OpenCode config reference server.py, while the Makefile runs app/server/__init__.py.
3. Root opencode.json and .opencode/opencode.json overlap but have different scopes and plugin declarations; precedence should be explicit.
4. Installed OpenCode CLI is 1.18.27 while .opencode/package.json pins @opencode-ai/plugin 1.17.15.
5. Pre-existing OpenCode/Mem0 work was preserved.

## Recommendations
Split detailed rules into rules/, define the authoritative FastMCP entrypoint, document OpenCode config precedence/version compatibility, and keep CI disabled.

Risk: medium configuration/governance drift.
