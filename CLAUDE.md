# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

## Цель проекта

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс Музыкой.

- Спецификация: @REQUIREMENTS.md
- Дизайн-документ: @docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md

## Документация

При работе с конкретной областью — загрузи соответствующий doc:

- @docs/architecture.md — слои, data flow, ключевые решения
- @docs/domain-glossary.md — DJ терминология (BPM, Camelot, LUFS, subgenres)
- @docs/tool-catalog.md — 50 MCP tools (46 visible + 4 atomic hidden)
- @docs/audio-pipeline.md — анализаторы, pipeline, mood classifier
- @docs/ym-api-guide.md — YM API quirks, rate limiting, diff format
- @docs/transition-scoring.md — 5-компонентная формула, Camelot wheel, caching
- @docs/reports/tiered-analysis-design-2026-03-27.md — спека tiered pipeline (L1-L4)
- @docs/reports/performance-benchmark-2026-03-27.md — бенчмарк всех операций

## Принципы

- MCP — единственный интерфейс (нет REST API, нет CLI, нет web UI)
- FastMCP v3.1 — FileSystemProvider auto-discovers tools (standalone `@tool`, не `@mcp.tool`)
- Python 3.12+, все операции async
- Strict typing: mypy strict + pydantic v2
- Тесты обязательны для каждого компонента
- **Никаких magic numbers** — все настройки в `app/config.py` (`settings.*`), все константы в `app/core/constants.py`

## Архитектура (слои)

```text
app/models/       → SQLAlchemy модели (данные)
app/repositories/ → Data access (flush, never commit)
app/services/     → Business logic (domain errors, no MCP imports)
app/mcp/tools/    → MCP tools (standalone @tool, FileSystemProvider auto-discovers)
app/mcp/resources/ → MCP resources (read-only data views)
app/mcp/prompts/  → Workflow prompt templates
app/audio/        → Audio analysis, tiered pipeline, level config, temp download
app/ym/           → Yandex Music client (async httpx)
app/core/         → Shared: errors, constants, pagination, entity resolver
```

Правило: каждый слой импортирует только слой ниже. Tools → Services → Repositories → Models.

## Команды

```bash
uv sync                                    # Install deps
uv run pytest -v                           # Tests
uv run ruff check && uv run ruff format --check  # Lint
uv run mypy app/                           # Type-check
uv run alembic upgrade head                # Migrations
uv run fastmcp dev app/server.py --reload  # Dev server
make check                                 # lint + typecheck + test
```

## Ключевые паттерны

### Конфигурация
```python
# ✅ Из settings
if bpm_diff > settings.transition_hard_reject_bpm_diff:
    return 0.0

# ❌ Никогда
if bpm_diff > 10:
    return 0.0
```

### MCP Tools
```python
from fastmcp.tools import tool              # standalone, NOT from app.server
from fastmcp.dependencies import Depends

@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def my_tool(
    id: int,
    view: Literal["summary", "full"] = "summary",
    svc=Depends(get_my_service),       # param=Depends() NOT Annotated[T, Depends()]
) -> MyModel:
    """Short description ≤50 words."""
    ...
```

### Feature loading для scoring
```python
# ✅ Через classmethod + repository
feat = TrackFeatures.from_db(row)                         # classmethod, не копипаста 10 полей
feat = await feat_repo.get_scoring_features(track_id)     # single track
features_map = await feat_repo.get_scoring_features_batch(track_ids)  # batch: 1 SQL
# ❌ Никогда: копировать 10 полей вручную
TrackFeatures(bpm=row.bpm, key_code=row.key_code, ...)   # дубликат!
```

### Repositories
```python
# flush(), никогда commit() — commit делает DI wrapper get_db_session()
await self.session.flush()
```

### Errors
```python
from app.core.errors import NotFoundError, ValidationError
# В services — raise domain errors
raise NotFoundError("Track", id)  # NotFoundError(entity_type, identifier)
# В tools — ToolError для input validation
raise ToolError("Provide either id or query")
```

## Tiered Audio Analysis (L1→L4)

Ленивый анализ — features вычисляются по мере необходимости, MP3 не сохраняются до deliver:

| Уровень | Когда | Анализаторы | Время/трек |
|---------|-------|-------------|-----------|
| L1+L2 (TRIAGE) | `classify_mood`, `audit_playlist` | loudness, energy, spectral, bpm, key, mfcc | ~5с |
| L3 (SCORING) | `build_set`, `score_transitions` | + beat | ~7с |
| L4 (TRANSITION) | `deliver_set` | + structure, permanent MP3 | ~3с |

- `analysis_level` поле в `track_audio_features_computed` (0/2/3)
- `TieredPipeline` (app/services/tiered_pipeline.py) — ensure_level + parallel Semaphore pool
- `temp_download_track` (app/audio/temp_download.py) — скачать в /tmp → analyze → удалить
- `AnalysisLevel` enum (app/audio/level_config.py) — NONE=0, TRIAGE=2, SCORING=3, TRANSITION=4
- Tools авто-триггерят нужный уровень через `Depends(get_tiered_pipeline)`

## Плагины Claude Code

| Плагин | Когда использовать |
|--------|-------------------|
| **fastmcp-builder** | Перед реализацией MCP tools/resources/prompts |
| **mcp-server-dev** | При проектировании tool patterns, elicitation, auth |
| **superpowers** | Brainstorming, planning, TDD, debugging |
| **feature-dev** | Guided feature development с пониманием codebase |
| **python** | pytest fixtures, ruff config, mypy |
| **fastapi** | Alembic migrations (fastapi plugin имеет migrate-* скиллы) |
| **tech-lead** | Architecture review, dependency analysis |
| **context7** | Документация библиотек (FastMCP, SQLAlchemy, librosa) |
| **commit-commands** | Git commit workflow |

## Правила архитектуры

- **Один файл = одна ответственность.** НИКОГДА не создавать дублирующие/расширяющие файлы (например `middleware.py` + `custom_middleware.py`). Если нужно расширить — расширяй в том же файле
- **Время:** все datetime-операции через `app/utils/time.py` (`utc_now()`, `utc_timestamp_iso()`, `sa_now()`). Не используй `datetime.now()` / `func.now()` напрямую
- **Линтер:** ruff + mypy. Pyright **игнорируй** — он выдаёт ложные ошибки (reportMissingImports, reportCallIssue на @tool). VSCode Pyright предупреждения — НЕ баги

## LLM Sampling и Claude Code MAX

Два режима работы LLM-assisted tools (`find_similar_tracks` strategy="llm"):

### 1. Client-driven (Claude Code MAX, по умолчанию — API key не нужен)

Claude Code сам является LLM — он генерирует search queries и передаёт их в tool:

```python
find_similar_tracks(
    track_id=42,
    strategy="llm",
    search_queries=["Amelie Lens acid techno", "FJAAK industrial", "Kobosil dark techno"]
)
```

Используй prompt `llm_discovery_workflow` для пошаговой инструкции.

**Почему так**: Claude Code не поддерживает MCP sampling (`createMessage`) —
ctx.sample() внутри tools не может вызвать клиента обратно. Но Claude Code
и так является LLM, поэтому он генерирует данные сам и передаёт через параметры.

### 2. Server-side (требует `DJ_ANTHROPIC_API_KEY`)

ctx.sample() внутри tools вызывает Anthropic API через fallback handler.
Для headless/автоматизированных сценариев.

## Gotchas

- `Depends()`: используй `param=Depends(factory)`, НЕ `Annotated[Type, Depends(factory)]` — FastMCP не резолвит Annotated
- `list_page_size` в config должен быть >= числа tools (100) — Claude Code не следует nextCursor
- YM search API: `type=tracks` (plural), не `type=track`
- YM playlist add_tracks: формат `"trackId:albumId"`, albumId обязателен
- MP3 анализ: нужен `uv sync --extra audio` (librosa + soundfile)
- `from __future__ import annotations` делает аннотации строками — runtime вызовы (TrackFeatures()) требуют реальных импортов
- `AsyncSession.delete()` IS async в SQLAlchemy 2.0 — `await` корректен
- Background tasks: `task=True` требует `pip install 'fastmcp[tasks]'`
- Error masking: `mask_error_details=not settings.debug` в production
- Circular imports repos→services: используй `TYPE_CHECKING` + lazy import внутри метода
- Linter (ruff) удаляет неиспользуемые импорты при сохранении — добавляй import+использование в одной правке
- **ctx.sample()**: Claude Code не поддерживает MCP sampling — используй client-driven режим (search_queries param)
- **Pipeline features → DB**: всегда используй `TrackAudioFeaturesComputed.filter_features(result.features)` при записи — pipeline может вернуть ключи без колонок
- **download_tracks**: автоматически создаёт `DjLibraryItem` через `_link_file_to_track()` — не нужно вручную
- **Hidden tools**: после `unlock_tools` Claude Code не перезагружает tool list — hidden tools (audio, atomic) доступны только через скрипт `Client(mcp)`
- **Energy bands**: имена колонок — `energy_sub`, `energy_lowmid`, `energy_highmid` (не `energy_band_*`, не `energy_low_mid`)
- **download_tracks refs**: принимает YM track IDs (`"135055088"`) или local IDs (auto-resolves через `resolve_local_ids_to_ym`). Числа < 100000 = local, >= 100000 = YM
- **score_delivery_transitions**: возвращает `tuple[int, int]` (scored, conflicts), НЕ dict
- **build_set без features**: fallback на `playlist_order` (не greedy/ga) — это корректное поведение
- **beat analyzer**: обрабатывает первые `settings.audio_beat_analysis_duration` секунд (default 60), не весь трек
- **get_set tracks view**: включает `artist_names` через batch query (`get_by_ids` batch, не N+1)
- **Tiered auto-trigger**: classify_mood/build_set/deliver_set автоматически анализируют треки — не нужно вызывать analyze_track вручную

## Версия

Plugin v0.5.0, 50 tools (46 visible + 4 atomic hidden), 7 audio analyzers (3 core + 4 librosa), tiered analysis (L1-L4), FileSystemProvider.

## Known Issues (docs/reports/errors/)

BUG-014/015/016: Fixed (artist_names, download ID resolution, library linking).
All issues resolved as of 2026-03-27.
