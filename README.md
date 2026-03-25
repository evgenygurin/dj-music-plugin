# DJ Music Plugin

MCP-сервер для управления личной DJ techno библиотекой, построения оптимизированных DJ сетов и интеграции с Яндекс Музыкой.

## Возможности

- **50 MCP tools** в 12 категориях (46 visible + 4 hidden atomic)
- **Audio analysis pipeline** — 7 анализаторов: BPM, тональность, энергия, спектр, beat, MFCC (3 numpy + 4 librosa)
- **DJ set generation** — генетический алгоритм + greedy builder с transition scoring
- **Transition scoring** — 5-компонентная оценка с persist в DB (BPM, гармония, энергия, спектр, грув)
- **Yandex Music интеграция** — поиск, импорт, скачивание MP3, синхронизация, расширение плейлистов
- **Экспорт** — M3U8, Rekordbox XML, JSON guide, cheat sheet + копирование файлов
- **Background tasks** — длинные операции через FastMCP Docket (expand, analyze, deliver)
- **Mood classification** — 15 techno subgenres, правила сохраняются в DB

## Быстрый старт

```bash
# Установка
uv sync

# Для audio analysis (BPM, key, beat detection)
uv sync --extra audio

# Настройка
cp .env.example .env
# Заполни DJ_YM_TOKEN и DJ_YM_USER_ID в .env

# Запуск
uv run fastmcp run app/server.py
```

### Установка как Claude Code плагин

```bash
/plugin marketplace add evgenygurin/dj-music-plugin
/plugin install dj-music
```

## Разработка

```bash
uv run pytest -v                           # Тесты (630+)
uv run ruff check && uv run ruff format --check  # Линтер
uv run mypy app/                           # Типы
uv run alembic upgrade head                # Миграции
make check                                 # Всё вместе
```

## Архитектура

FastMCP v3.1 + FileSystemProvider (standalone `@tool`, auto-discovery):

```text
Models → Repositories → Services → MCP Tools (@tool)
                                 → MCP Resources (@resource)
                                 → MCP Prompts (@prompt)
```

**Слои:**
- `app/models/` — SQLAlchemy 2.0 async (44 tables)
- `app/repositories/` — data access (flush only, never commit)
- `app/services/` — business logic (TrackService, PlaylistService, TransitionScorer + `TrackFeatures.from_db()`, GA/Greedy optimizer)
- `app/mcp/tools/` — thin MCP wrappers with Depends() DI
- `app/audio/` — 7 analyzers (3 numpy core + 4 librosa optional)
- `app/ym/` — async Yandex Music client (httpx, rate limiting)

**Middleware:** structured logging, timing, YM rate limiting, retry, error masking.

Подробности: [Design Specification](docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md)

## Конфигурация

Все настройки через переменные окружения с префиксом `DJ_`. См. [.env.example](.env.example).

## Требования

- Python 3.12+
- uv (менеджер пакетов)
- SQLite (по умолчанию) или PostgreSQL 16+ (prod)
- Опционально: librosa (audio analysis), demucs (stem separation), fastmcp[tasks] (background tasks)
