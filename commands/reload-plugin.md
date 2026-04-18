---
name: reload-plugin
description: Полная зачистка кешей плагина dj-music (bytecode, fastmcp venv-pyc, mypy/ruff/pytest caches) + kill MCP stdio → Claude Code respawn'ит процесс с нуля. Использовать после pull, rebase, update плагина, или когда MCP капризничает.
allowed-tools: [Bash]
---

Зачисти все кеши установленного плагина и убей fastmcp процесс. Выполняй без подтверждения, один bash-блок:

```bash
set -euo pipefail

# Найти все инсталляции плагина dj-music (dev symlink + marketplace cache).
ROOTS=(
  "/Users/laptop/dev/dj-music-plugin"
  "/Users/laptop/.claude/plugins/cache/dj-music-plugin"
)

for root in "${ROOTS[@]}"; do
  [[ -d "$root" ]] || continue
  echo "→ Purging $root"
  find "$root" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
  find "$root" -type f -name '*.pyc' -delete 2>/dev/null || true
  for d in .mypy_cache .ruff_cache .pytest_cache; do
    rm -rf "$root/$d" 2>/dev/null || true
  done
done

# Kill fastmcp stdio-процесс(ы) плагина — Claude Code respawn'ит.
# Entry point v1 — root server.py (не app/server.py; последний теперь package).
pkill -f "cache/dj-music-plugin/.*/server\\.py" 2>/dev/null || true
pkill -f "dev/dj-music-plugin/.*/(server\\.py|fastmcp\\.json)" 2>/dev/null || true

echo "✓ Plugin caches purged. Call any mcp__plugin_dj-music_mcp__* tool to respawn."
```

После команды сразу вызови `mcp__plugin_dj-music_mcp__unlock_namespace` (action=status, namespace=all) — это поднимет свежий процесс и подтвердит работоспособность. Не жди подтверждения пользователя.
