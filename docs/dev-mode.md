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

## Claude Code CLI tools для plugin dev

### Pre-push / pre-release: `claude plugin validate`

Полная проверка plugin manifest до push'а:

```bash
claude plugin validate /Users/laptop/dev/dj-music-plugin
# Проверяет: .claude-plugin/plugin.json + marketplace.json синтаксис,
# commands/*.md + agents/*.md + skills/**/SKILL.md frontmatter,
# hooks/hooks.json валидность, .mcp.json (если есть),
# отсутствие `..` в source paths, отсутствие дубликатов имён.
```

Стоит запускать после правок `plugin.json` / `marketplace.json` / любых `*.md` со фронтматтером. Эквивалент `/plugin validate <path>` внутри сессии.

### Session-only тест без install: `--plugin-dir`

Альтернатива `DJ_PLUGIN_DEV_PATH` для проверки в чистом environment (без записи в `~/.claude/settings.json`, без `installed_plugins.json` update):

```bash
claude --plugin-dir /Users/laptop/dev/dj-music-plugin
```

Каждый запуск подтягивает плагин свежий — изменения видны мгновенно без `claude plugin update`. Полезно когда нужно проверить плагин «как у нового пользователя» без затирания текущей user-scope установки.

### Plugin loading debug

```bash
# Фильтр только по plugins+hooks+mcp (без шума file/1p)
claude --debug "plugins,hooks,mcp"

# В файл (для отправки в issue)
claude --plugin-dir /Users/laptop/dev/dj-music-plugin --debug-file /tmp/dj-debug.log
```

### Diagnostics

```bash
claude doctor
# Installation type + version, malformed settings.json, MCP server config errors,
# plugin/agent loading errors, context usage warnings.
```

Внутри сессии: `/plugin` → вкладка **Errors** показывает все ошибки загрузки плагинов с путями и трассировкой.

### После release tag — обновить marketplace + plugin

После `git push origin v1.X.Y` GitHub-marketplace user'ам нужно:

```bash
claude plugin marketplace update dj-music-plugin    # подтянуть свежий marketplace.json
claude plugin update dj-music@dj-music-plugin       # apply (требует restart Claude Code)
```

`@docs/dev-mode.md` локальный dev не затронут — он работает через directory-source marketplace (см. CLAUDE.md «Plugin cache ≠ working dir»).

## Платформенные ограничения

- **Cursor пропускает `SessionStart` hooks.** Наш welcome banner / health smoke-test (`hooks/session-start.sh` в `SessionStart`) не сработает в Cursor — запусти проверку вручную (`mcp__plugin_dj-music_mcp__entity_aggregate(entity="track", operation="count")` или `ui_library_dashboard`).
- **Windows native без WSL / Git-Bash не запустит наши хуки.** `PostToolUse` (`hooks/reload-mcp.sh`) и `FileChanged` (`hooks/dev-filewatch-reload.sh`) требуют bash. На Windows используй WSL2 или Git-Bash; альтернативно — перепиши hooks на sh-совместимый shell.
- **`$schema` поле в `plugin.json` / `marketplace.json`** отвергается validator'ом Claude Code 2.1.114+ с ошибкой `Unrecognized key`. Не добавляй для IDE-completion — оно сломает install.
- **`claude plugin marketplace remove dj-music-plugin`** автоматически удалит установленный плагин из всех scopes (user/project/local). Осторожно при чистке dev-окружений.

## Доступ к БД по окружениям (cloud / local / teleport)

У плагина два MCP-сервера (см. `.claude-plugin/plugin.json`): сам плагин
(`mcp` — `entity_*` и пр., транспорт **SQLAlchemy + asyncpg** на порт **6543**)
и `db` (`@supabase/mcp-server-supabase`, **Supabase Management API по HTTPS**
на :443). Где какой работает — зависит от окружения.

| Окружение | asyncpg `entity_*` (:6543) | `db` MCP / REST (:443) | Канон |
|---|---|---|---|
| **Локально** (терминал, Cursor) | ✅ открыт | ✅ | asyncpg напрямую |
| **`claude --teleport`** (web→локаль) | ✅ открыт | ✅ | asyncpg напрямую |
| **Облачная песочница** (claude.ai/code) | ❌ заблокирован | ✅ | `db` MCP **или** teleport |

### Почему в облаке :6543 заблокирован

Облачная песочница Claude Code гоняет весь исходящий трафик через
**HTTP/HTTPS egress-прокси** с фильтрацией по **домену**, не по порту
([официальная дока](https://code.claude.com/docs/en/claude-code-on-the-web)
§ «Network access»):

> *«Environments run behind an HTTP/HTTPS network proxy… All outbound
> internet traffic passes through this proxy»* + *«Content filtering for
> enhanced security»*.

Уровни доступа (None / Trusted / Full / Custom) управляют **списком доменов**,
а не портами: даже `Full` = *«Any domain»* по HTTP/HTTPS. Произвольный TCP
(Postgres wire protocol на :6543) не предусмотрен архитектурой и **не
открывается из контейнера** — это не конфиг, а свойство прокси.

### Почему `db` MCP всё-таки работает в облаке

MCP-коннекторы не идут через egress-прокси песочницы:

> *«MCP connector traffic is routed through Anthropic's servers, so the
> connectors you enable… work without adding their hosts to Allowed
> domains»* ([там же](https://code.claude.com/docs/en/claude-code-on-the-web)).

Поэтому `db` MCP (Supabase Management API по HTTPS) читает живую БД в облаке:
`mcp__*__execute_sql`, `mcp__*__list_tables` (project_id `bowosphlnghhgaulcyfm`).
Это **read-only через Management API** — не полноценный ORM-слой `entity_*`.

### Канон для полноценных `entity_*` в облаке — `--teleport`

Официальная дока прямо отправляет всё, что облако не покрывает, на своё
железо:

> *«For workloads beyond these limits, use Remote Control to run Claude Code
> on your own hardware»* (`--remote` / `--teleport`,
> [docs](https://code.claude.com/docs/en/claude-code-on-the-web) § «Move tasks
> between web and terminal»).

`claude --teleport` переносит активную web-сессию на локальную машину, где
egress-прокси нет и asyncpg :6543 открыт → `entity_*` работают напрямую.

### Туннель Postgres через :443 — отклонён

Идея пробросить Postgres через :443 (cloudflared `access tcp` WSS / ngrok TCP)
**отклонена**: она опирается на недокументированное поведение
content-filtering прокси (пройдёт ли WSS-upgrade / HTTP CONNECT — в доке нет),
а ngrok TCP вообще отдаёт случайный порт ≠ 443, который allowlist по домену не
пропустит. Канон `db` MCP + teleport покрывает обе потребности (чтение в
облаке, полный ORM локально) без хрупкой инфраструктуры.

### Диагностика

```bash
bash scripts/check_db_egress.sh
# Грузит .env, пробит :443 / :6543 / :5432 через python socket,
# делает живой asyncpg-коннект и печатает контекстный вывод.
# Локально/teleport: все OPEN + "entity_* работают напрямую".
# В облаке: :6543 BLOCKED — это норма, скрипт подскажет db MCP / teleport.
```
