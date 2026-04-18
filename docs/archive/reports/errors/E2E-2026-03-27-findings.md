# E2E Test Findings — 2026-03-27

## MCP Server Connection

### FIXED: MCP server not loading in Claude Code
- **Root cause**: `.mcp.json` не имел обёртки `"mcpServers"` — Claude Code не распознавал формат
- **Secondary cause**: Plugin cache (`~/.claude/plugins/cache/`) хранил устаревшую копию `.mcp.json` с `{"mcpServers": {}}`. `/reload-plugins` не обновляет файлы в кэше — только перечитывает конфиги
- **Fix**: Добавлена обёртка `"mcpServers"` + ручной rsync в кэш

## BUG-012: artist_names empty after import

- **Status**: FIXED (in source, synced to cache)
- **Root cause**: `to_brief()`/`to_standard()` в TrackService не загружали artist_names из БД — всегда возвращали `[]`
- **Fix**: Добавлен `get_artist_names_batch()` в TrackRepository (batch JOIN), tools `list_tracks`, `get_track`, `get_playlist` используют его
- **Tests**: 756 passed

## Warnings

### YM add_tracks format
- `ym_playlists(action="add_tracks")` с массивом простых track_ids возвращает 400
- **Требуется** формат `"trackId:albumId"` — нужен предварительный `ym_get_tracks` для получения albumId
- Это задокументировано в `docs/ym-api-guide.md` и `CLAUDE.md` gotchas

### BPM/key/energy null для всех треков
- **Ожидаемо**: аудио-файлы не скачаны → анализ невозможен
- Для полного E2E нужен `download_tracks` + `analyze_track` (требует `[audio]` extra)

### Acid techno search empty
- `ym_search(query="acid techno industrial 2025", type="tracks")` → 0 results
- YM поиск плохо работает с составными жанровыми запросами — лучше искать по одному ключевому слову

### Plugin cache staleness
- При разработке directory-source плагина, изменения исходников не попадают в кэш автоматически
- `autoUpdate: true` в settings.json не помогает — версия не меняется (0.3.0 → 0.3.0)
- **Workaround**: `rsync` исходников в `~/.claude/plugins/cache/dj-music-plugin/dj-music/0.3.0/`
- **TODO**: Автоматизировать sync через PostToolUse hook или bump version

### Pyright false positives
- `reportCallIssue` на `@tool` decorated functions — ложные срабатывания FastMCP
- Игнорируем per CLAUDE.md rules
