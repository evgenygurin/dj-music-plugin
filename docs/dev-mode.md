# Dev Mode — MCP hot-reload без рестарта сессии

Три канонических механизма Claude Code, выстроенных послойно. Каждый
уровень покрывает свой class изменений; вместе они дают dev-loop без
«exit → claude → новая сессия».

## 1. `DJ_PLUGIN_DEV_PATH` — MCP запускается из working dir

Плагин по умолчанию живёт в cache'е (`~/.claude/plugins/cache/dj-music-plugin/...`),
и правки в `app/` не видны. Переменная окружения переключает stdio
MCP-сервер на working dir:

```json
// ~/.claude/settings.json
{
  "env": { "DJ_PLUGIN_DEV_PATH": "/Users/you/dev/dj-music-plugin" }
}
```

После этого `bash -c 'cd "${DJ_PLUGIN_DEV_PATH:-${CLAUDE_PLUGIN_ROOT}}" && ...'`
в [.claude-plugin/plugin.json](../.claude-plugin/plugin.json) поднимает
`fastmcp run fastmcp.json` из working dir вместо cache.

## 2. `PostToolUse` hook — авто-reload на edit'ах Claude

Файл: [hooks/reload-mcp.sh](../hooks/reload-mcp.sh). Срабатывает на
`Edit|Write|MultiEdit` из Claude Code — чистит bytecode/tool caches и
убивает `fastmcp run` процесс под dj-music. Claude Code сам respawn'ит
stdio-процесс при следующем tool call с нового кода.

## 3. `FileChanged` hook — авто-reload на правках из IDE

Официальный Claude Code hook event ([docs](https://code.claude.com/docs/en/plugins-reference#hooks)):

> `FileChanged` — When a watched file changes on disk. The `matcher`
> field specifies which filenames to watch.

Hook срабатывает при изменении файла **любым процессом** — VS Code,
vim, git checkout, rsync, что угодно. Не нужны ни `fswatch`, ни
`watchdog`, ни фоновые демоны.

Файл: [hooks/dev-filewatch-reload.sh](../hooks/dev-filewatch-reload.sh).
Конфиг в [hooks/hooks.json](../hooks/hooks.json):

```json
"FileChanged": [
  {
    "matcher": "server.py|fastmcp.json|.env|pyproject.toml|app.py|lifespan.py|di.py",
    "hooks": [{
      "type": "command",
      "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/dev-filewatch-reload.sh\"",
      "timeout": 10,
      "statusMessage": "Reloading dj-music MCP (external edit)..."
    }]
  }
]
```

`matcher` — pipe-separated список **литеральных имён файлов** (не
regex, не glob). Покрывает entrypoint, lifespan, DI, pyproject. Для
изменений глубоко внутри `app/` из внешнего редактора — см. уровень 4.

## 4. `/reload-plugins` — канонический ручной fallback

Официальная slash-команда ([docs](https://code.claude.com/docs/en/plugins)):

> As you make changes to your plugin, run `/reload-plugins` to pick up
> the updates without restarting. This reloads plugins, skills, agents,
> hooks, plugin MCP servers, and plugin LSP servers.

Когда редактируешь глубоко в `app/` из внешнего IDE и хочешь быть
уверен — одна команда `/reload-plugins` в Claude Code перезапускает
всё plugin-wide без потери сессии.

## Матрица покрытия

| Изменение | Уровень | Авто? |
|---|---|---|
| Claude правит файл через Edit/Write | #2 PostToolUse | ✅ |
| Внешний IDE сохраняет server.py / fastmcp.json / .env / lifespan.py | #3 FileChanged | ✅ |
| Внешний IDE сохраняет `app/**/*.py` (глубоко) | #4 `/reload-plugins` | ❌ (ручной) |
| Правка `hooks.json` / `plugin.json` / `.mcp.json` | полный restart Claude Code | ❌ |

## Проверка

```bash
# Положить плагин в working dir и стартовать MCP из него
export DJ_PLUGIN_DEV_PATH=/Users/you/dev/dj-music-plugin

# Симулировать FileChanged payload
echo '{"file_path":"/Users/you/dev/dj-music-plugin/server.py"}' \
  | bash hooks/dev-filewatch-reload.sh
# → {"systemMessage":"🔄 FileChanged: server.py — killed N dj-music MCP proc(s); ..."}

# Проверить hooks.json валидный
python3 -c "import json; json.load(open('hooks/hooks.json'))"
```
