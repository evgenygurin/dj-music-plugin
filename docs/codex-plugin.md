# Codex Plugin

The Codex package is isolated from the existing Claude Code package:

- `.codex-plugin/plugin.json` — Codex plugin manifest.
- `.mcp.json` — the DJ Music FastMCP server only.
- `.agents/plugins/marketplace.json` — Codex marketplace metadata.
- `skills/` — shared read-only workflow instructions.

Claude Code continues to use `.claude-plugin/` and `hooks/` unchanged.

## Requirements

- Codex CLI 0.142.0 or newer.
- `uv`.
- Python 3.12 or newer.
- A project `.env` for live database and Yandex Music access.

The plugin starts without Yandex credentials, but provider operations require
`DJ_YM_TOKEN`. Live library access requires `DJ_DATABASE_URL`.
The Codex MCP launcher reads `.env` from the project where the thread starts;
credentials are not copied into the installed plugin cache.

## Install

```bash
codex plugin marketplace add evgenygurin/dj-music-plugin --ref main
codex plugin add dj-music@dj-music-plugin
```

Start a new Codex thread after installation.

## Verify

```bash
codex plugin marketplace list
codex plugin list --available
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

In a new thread, ask:

```text
Use the DJ Music plugin to list playlists and build a short demonstration set.
```

The expected MCP surface is 26 runtime tools, including 6 UI tools, plus
30 workflow prompts.

## Development smoke test

Use an isolated Codex home so the test does not modify the normal installation:

```bash
export CODEX_HOME=/tmp/dj-music-codex-smoke
codex plugin marketplace add evgenygurin/dj-music-plugin \
  --ref <branch>
codex plugin add dj-music@dj-music-plugin
codex plugin list
```

The Claude-specific reload hook under `hooks/` does not match Codex's
`apply_patch` tool and remains inert in Codex sessions.
