# BUG-013: Plugin cache staleness — code changes not reflected in MCP server

- **Status**: KNOWN LIMITATION
- **Severity**: Medium (dev workflow friction)
- **Root cause**: `${CLAUDE_PLUGIN_ROOT}` in `.mcp.json` resolves to `~/.claude/plugins/cache/dj-music-plugin/dj-music/0.3.0/`, not source directory. Changes to source files require manual rsync to cache.
- **Additional issue**: Running MCP server process caches Python modules — even after rsync, changes don't take effect until server restart.
- **Workaround**: `rsync -av app/ ~/.claude/plugins/cache/.../app/` + restart Claude Code session
- **Proper fix**: Either bump plugin version on each change, or switch `.mcp.json` to use source directory directly for dev
