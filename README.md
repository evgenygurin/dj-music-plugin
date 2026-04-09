# DJ Music Plugin

MCP-сервер для управления личной DJ techno библиотекой, построения оптимизированных DJ сетов и интеграции с Яндекс Музыкой.

## Возможности

- **50 MCP tools** в 12 категориях (46 visible + 4 hidden atomic)
- **Audio analysis pipeline** — 18 анализаторов в layered architecture с двухфазным параллельным выполнением через `asyncio.to_thread`
- **DJ set generation** — генетический алгоритм + greedy builder с transition scoring
- **Transition scoring** — 6-компонентная оценка с persist в DB (BPM, гармония, энергия, спектр, грув, тембр) и context-aware весами
- **Yandex Music интеграция** — поиск, импорт, скачивание MP3, синхронизация, расширение плейлистов
- **Экспорт** — M3U8, Rekordbox XML, JSON guide, cheat sheet + копирование файлов
- **Background tasks** — длинные операции через FastMCP Docket (expand, analyze, deliver)
- **Mood classification** — 15 techno subgenres с injectable Strategy profiles, Gaussian scoring

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

Внутри Claude Code (slash-команды):

```bash
/plugin marketplace add evgenygurin/dj-music-plugin
/plugin install dj-music
```

Из терминала через `claude` CLI (non-interactive, годится для скриптов и CI):

```bash
# stable (default branch)
claude plugin marketplace add evgenygurin/dj-music-plugin
claude plugin install dj-music@dj-music-plugin

# dev branch
claude plugin marketplace add evgenygurin/dj-music-plugin@dev
claude plugin install dj-music@dj-music-plugin
```

Альтернативный синтаксис через git URL (любая ветка/тег/SHA):

```bash
claude plugin marketplace add https://github.com/evgenygurin/dj-music-plugin.git#dev
```

Плагин поднимает два MCP сервера:

| Сервер | Назначение |
|--------|------------|
| `mcp` | 50 DJ tools — построение сетов, аудиоанализ, YM, экспорт (FastMCP) |
| `db` | Read-only инспекция БД: схема, SQL, миграции, логи |

Сервер `db` принудительно изолирован (security hardening по [официальным рекомендациям Supabase MCP](https://github.com/supabase-community/supabase-mcp#security-risks)):

- `--read-only` — мутации БД блокируются (выполняются через `mcp`)
- `--project-ref=bowosphlnghhgaulcyfm` — scoped к одному проекту
- `--features=database,docs,debug` — surface ограничен: SQL, схема, миграции, логи. Account/branches/storage/edge-functions tools отключены

Конфигурация токена — в [.env](.env.example):

```bash
DJ_DB_ACCESS_TOKEN="..."   # personal access token
```

> Реализация — `@supabase/mcp-server-supabase@0.7.0` (запускается через `npx`). Токен генерится в [Supabase Dashboard](https://supabase.com/dashboard/account/tokens).

#### Платформенные ограничения

Сервер `db` использует `bash`-wrapper для авто-загрузки `.env` (Claude Code не делает этого нативно). На **Windows без WSL/Git-Bash не запустится** — альтернатива: экспортировать `DJ_DB_ACCESS_TOKEN` в shell вручную и заменить wrapper на нативный `env`-блок в `plugin.json`.

Сервер `mcp` использует нативный `command`/`cwd` — pydantic-settings (`app/config.py`) читает `.env` сам, кроссплатформенно.

## Разработка

```bash
uv run pytest -v                           # Тесты (923+)
uv run ruff check && uv run ruff format --check  # Линтер
uv run mypy app/                           # Типы
uv run alembic upgrade head                # Миграции
make check                                 # Всё вместе

# Верификация audio pipeline на реальном MP3
uv run python scripts/verify_audio_pipeline.py [path/to/track.mp3]
```

## Архитектура

FastMCP v3.1 + FileSystemProvider (standalone `@tool`, auto-discovery):

```text
Models → Repositories → Services → MCP Tools (@tool)
                                 → MCP Resources (@resource)
                                 → MCP Prompts (@prompt)
```

**Слои:**
- `app/db/models/` — SQLAlchemy 2.0 async (44 tables)
- `app/db/repositories/` — data access (flush only, never commit)
- `app/services/` — business logic (TrackService, PlaylistService, TransitionScorer + `TrackFeatures.from_db()`, GA/Greedy optimizer)
- `app/controllers/tools/` — thin MCP wrappers with Depends() DI
- `app/audio/` — layered audio analysis (see below)
- `app/ym/` — async Yandex Music client (httpx, rate limiting)

### Audio module (`app/audio/`)

Layered architecture with GoF patterns:

```text
core/             ← L1: DSP primitives (0 app deps)
  types.py           FrameParams, AudioSignal, AnalyzerResult
  framing.py         frame energies, energy slope
  spectral.py        STFT, band energies, centroid, rolloff
  loader.py          AudioLoader (soundfile → librosa → wave)
  context.py         AnalysisContext (eager STFT, thread-safe)

analyzers/        ← L2: feature extractors (18 total)
  base.py            BaseAnalyzer (Template Method), @register_analyzer, Registry
  beat, bpm, energy, key, loudness, mfcc, spectral, structure  (8 core)
  danceability, tempogram, dissonance, dynamic_complexity,     (6 P1, optional essentia/librosa)
  tonnetz, beats_loudness
  spectral_complexity, pitch_salience, bpm_histogram, phrase   (4 P2, optional essentia/librosa)

classification/   ← L2b: mood/subgenre
  profiles.py        15 SubgenreProfile frozen dataclasses
  classifier.py      MoodClassifier (Strategy pattern)

pipeline.py       ← L3: orchestrator (asyncio.to_thread parallelism)
```

- **Template Method**: `BaseAnalyzer.run()` handles guard + error wrapping; subclass implements `_extract(ctx)`
- **Two-phase pipeline**: independent analyzers run in parallel (Phase 1), dependent analyzers receive merged results (Phase 2)
- **Registry**: `@register_analyzer` + `pkgutil.iter_modules()` auto-discovery — new analyzer = one file
- **Strategy**: `MoodClassifier` accepts injectable `SubgenreProfile` sequence
- **Eager context**: STFT/magnitude/freqs computed once, shared read-only — thread-safe by design

**Middleware:** structured logging, timing, YM rate limiting, retry, error masking.

Подробности: [Design Specification](docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md)

## Конфигурация

Все настройки через переменные окружения с префиксом `DJ_`. См. [.env.example](.env.example).

### LLM-assisted discovery (два режима)

**Claude Code MAX (подписка, без API key):**
Claude Code сам генерирует search queries и передаёт в `find_similar_tracks`:

```python
# Claude Code генерирует queries на основе характеристик трека
find_similar_tracks(track_id=42, strategy="llm",
    search_queries=["Amelie Lens acid techno", "FJAAK industrial"])
```

Или используй prompt `llm_discovery_workflow` для пошагового воркфлоу.

**Server-side sampling (автоматика через API key):**
```bash
# В .env
DJ_ANTHROPIC_API_KEY=sk-ant-...
```
`ctx.sample()` генерирует queries автоматически. Для headless-сценариев.

## E2E Pipeline

Полный цикл обработки трека:

```text
import_tracks → download_tracks → analyze_track    → classify_mood → build_set
     ↓              ↓                  ↓                   ↓              ↓
  Track +       MP3 файл +      AudioLoader            15 subgenres   DJ set с
  YM metadata   DjLibraryItem    → AnalysisContext      + confidence   transition
                                 → 18 analyzers ∥                      scoring
                                 → 60 features
```

`download_tracks` автоматически создаёт `DjLibraryItem` записи — `analyze_track` сразу находит файлы.

## Требования

- Python 3.12+
- uv (менеджер пакетов)
- SQLite (по умолчанию) или PostgreSQL 16+ (prod)
- Опционально: librosa (audio analysis), demucs (stem separation), fastmcp[tasks] (background tasks)
