# DJ Music Plugin

MCP-сервер для управления личной DJ techno библиотекой, построения оптимизированных DJ сетов и интеграции с Яндекс Музыкой.

## Возможности

- **44 MCP tools** в 10 категориях (CRUD, поиск, построение сетов, доставка, анализ, курирование, синхронизация)
- **Audio analysis pipeline** — BPM, тональность, энергия, спектр, структура, классификация по 15 subgenres
- **DJ set generation** — генетический алгоритм + greedy builder с 8 шаблонами
- **Transition scoring** — 5-компонентная оценка переходов между треками (BPM, гармония, энергия, спектр, грув)
- **Yandex Music интеграция** — поиск, импорт, скачивание, синхронизация плейлистов
- **Экспорт** — M3U8, Rekordbox XML, JSON guide, текстовая шпаргалка

## Быстрый старт

```bash
# Установка
uv sync

# Настройка
cp .env.example .env
# Заполни DJ_YM_TOKEN и DJ_YM_USER_ID в .env

# Запуск dev-сервера
uv run fastmcp dev app/server.py --reload
```

## Разработка

```bash
uv run pytest -v                           # Тесты
uv run ruff check && uv run ruff format --check  # Линтер
uv run mypy app/                           # Типы
uv run alembic upgrade head                # Миграции
make check                                 # Всё вместе
```

## Архитектура

FastMCP v3.1 сервер с слоистой архитектурой:

```text
Models → Repositories → Services → MCP Tools
                                  → MCP Resources
                                  → MCP Prompts
```

Подробности: [Design Specification](docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md)

## Конфигурация

Все настройки через переменные окружения с префиксом `DJ_`. См. [.env.example](.env.example).

## Требования

- Python 3.12+
- uv (менеджер пакетов)
- SQLite (по умолчанию) или PostgreSQL 16+ (prod)
- Опционально: librosa (audio analysis), demucs (stem separation)
