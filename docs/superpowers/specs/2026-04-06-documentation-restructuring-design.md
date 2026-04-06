# Documentation Restructuring — Design Spec

> Модульная реструктуризация документации, правил и CLAUDE.md после активной фазы разработки (panel, REST API, Supabase, PostgreSQL).

## Проблема

Документация органически росла вместе с проектом. После добавления panel (Next.js + Supabase), REST API wrapper (serve_http.py), миграции на PostgreSQL и ряда рефакторингов (tiered analysis, 6-компонентный scoring, P1/P2 analyzers) — CLAUDE.md, docs/ и .claude/rules/ устарели и содержат дублирование.

### Конкретные проблемы

**CLAUDE.md (218 строк) — перегружен:**
- Принцип "MCP — единственный интерфейс" устарел — теперь есть panel + REST API
- Gotchas (30 пунктов) свалены в один список, дублируют rules/ и содержат уже исправленные баги
- Ключевые паттерны дублируют rules/tools.md, rules/services.md, rules/repositories.md
- Tiered Analysis — подробности реализации, которым место в docs/
- Нет упоминания panel/, serve_http.py, Supabase, startup скриптов

**docs/architecture.md — устарел:**
- Не знает о panel (Next.js + Supabase)
- Не знает о REST API wrapper (serve_http.py)
- Диаграмма не отражает текущий data flow

**.claude/rules/ — неполные:**
- Нет правил для panel/ (Next.js, Supabase, shadcn, server actions)
- Нет правил для REST API слоя
- Не все файлы имеют frontmatter с globs
- Gotchas разбросаны по CLAUDE.md вместо тематических rules/

**docs/ — смешаны живые docs и исторические артефакты:**
- Живые docs (architecture, tool-catalog) смешаны с историческими отчётами

---

## Решение: Модульная реструктуризация (три слоя)

### Слой 1: CLAUDE.md — компактный entry point (~80-100 строк)

**Остаётся:**

| Секция | Содержание |
|--------|------------|
| Цель проекта | Обновлённое: MCP server + Panel + REST API |
| Документация | Ссылки на docs/ (без дублирования содержания) |
| Принципы | Обновлённые: MCP = primary interface, panel = monitoring/analytics UI |
| Архитектура | Краткая диаграмма: Panel (Next.js) → REST API (FastAPI) → MCP Server (FastMCP) → DB (Supabase PostgreSQL) + app/ layer diagram |
| Команды | Обновлённые: + bun dev, startup script, serve_http |
| Плагины Claude Code | Без изменений |
| Правила архитектуры | 3 пункта (один файл = одна ответственность, время, линтер) |
| Версия | Обновить |

**Удаляется полностью:**
- Ключевые паттерны (дублируют rules/)
- Tiered Analysis подробности (оставить 3-строчную таблицу, детали в docs/)
- LLM Sampling (→ rules/llm-sampling.md)
- Gotchas 30 пунктов (→ разнесены по тематическим rules/)
- Known Issues (все исправлены)

### Слой 2: .claude/rules/ — модульные правила

**Существующие файлы (обновить):**

| Файл | Обновления |
|------|------------|
| tools.md | + gotchas: Depends(), ToolError, list_page_size, hidden tools, download_tracks refs, score_delivery_transitions tuple |
| ym.md | + gotchas: type=tracks, playlist diff, albumId resolve, action=get_tracks/remove_tracks |
| audio.md | + gotchas: classify_mood persist, filter_features(), tiered auto-trigger, P1/P2 analyzers, depends_on, registry, beat duration |
| repositories.md | + gotchas: AsyncSession.delete() async, flush pattern. + frontmatter globs |
| models.md | + gotchas: energy band column names. + frontmatter globs |
| config.md | + gotchas: background tasks, error masking. + frontmatter globs |
| resources.md | + frontmatter globs |
| services.md | без изменений (уже имеет frontmatter) |
| tests.md | без изменений (уже имеет frontmatter) |

**Новые файлы:**

| Файл | Globs | Содержание |
|------|-------|------------|
| panel.md | `panel/**/*` | Next.js app router conventions, server actions в actions/, Supabase query layer в lib/supabase/, shadcn components, Recharts charts, cyberpunk theme, bun as package manager |
| rest-api.md | `serve_http.py` | FastAPI wrapper — тонкая обёртка над MCP, не дублировать бизнес-логику, CORS config, lifespan pattern, endpoint conventions |
| supabase.md | `panel/lib/supabase/**/*` | Direct SQL queries (не ORM), RLS отключён, connection через env vars, query patterns |
| llm-sampling.md | `app/mcp/tools/discovery.py` | Два режима: client-driven (Claude Code MAX) и server-side (DJ_ANTHROPIC_API_KEY), search_queries param pattern, llm_discovery_workflow prompt |
| gotchas.md | — (общие) | Python-specific ловушки: from __future__ import annotations, circular imports TYPE_CHECKING, linter removes unused imports |

### Слой 3: docs/ — реорганизация

**Обновляемые файлы:**

| Файл | Изменения |
|------|-----------|
| architecture.md | + Panel layer в диаграмму (Next.js → REST API → MCP), + REST API layer (serve_http.py), + Supabase PostgreSQL как production DB, + startup flow (start.sh), + новые Key Architectural Decisions |
| transition-scoring.md | 6 компонентов вместо 5 (+ timbral 0.10), обновлённые веса (bpm 0.22, harmonic 0.20, energy 0.23, spectral 0.15, groove 0.10, timbral 0.10), + TransitionIntent (context-aware scoring) |

**Новые файлы:**

| Файл | Содержание |
|------|------------|
| panel-guide.md | Архитектура panel (app router, pages, server actions), data flow (Panel → Supabase read / REST API → MCP write), component structure, theme, charts, dev setup |

**Без изменений:**
- domain-glossary.md, tool-catalog.md, audio-pipeline.md, ym-api-guide.md
- reports/ (исторические)
- superpowers/ (артефакты brainstorming)
- sync-service-api-design.md

---

## Распределение Gotchas

Полная карта переноса 30 gotchas из CLAUDE.md:

| Gotcha | Целевой файл |
|--------|-------------|
| `Depends()` — `param=Depends()` NOT `Annotated[T, Depends()]` | rules/tools.md |
| `list_page_size` >= числа tools | rules/tools.md |
| Hidden tools — unlock не перезагружает tool list | rules/tools.md |
| `download_tracks refs` — YM IDs vs local IDs, threshold 100000 | rules/tools.md |
| `score_delivery_transitions` — returns tuple, не dict | rules/tools.md |
| `build_set` без features — fallback на playlist_order | rules/tools.md |
| `get_set tracks view` — artist_names через batch query | rules/tools.md |
| YM search API `type=tracks` (plural) | rules/ym.md |
| YM playlist add_tracks — albumId auto-resolves | rules/ym.md |
| `ym_playlists` action=get_tracks/remove_tracks | rules/ym.md |
| `classify_mood`/`distribute_to_subgenres` persist mood | rules/audio.md |
| Pipeline features → DB: `filter_features()` | rules/audio.md |
| Tiered auto-trigger — не нужно вызывать analyze_track вручную | rules/audio.md |
| P1 analyzers: essentia unbounded values | rules/audio.md |
| P2 analyzers: depends_on, prior_results | rules/audio.md |
| `_ANALYZER_REGISTRY`: global dict, тесты удаляют только `_test_*` | rules/audio.md |
| Beat analyzer — первые N секунд, не весь трек | rules/audio.md |
| MP3 анализ: `uv sync --extra audio` | rules/audio.md |
| `AsyncSession.delete()` IS async | rules/repositories.md |
| Energy band column names: energy_sub, energy_lowmid, energy_highmid | rules/models.md |
| Background tasks: `task=True` requires `fastmcp[tasks]` | rules/config.md |
| Error masking: `mask_error_details=not settings.debug` | rules/config.md |
| `from __future__ import annotations` — runtime vs type-time | rules/gotchas.md |
| Circular imports repos→services: TYPE_CHECKING + lazy import | rules/gotchas.md |
| Linter (ruff) удаляет неиспользуемые импорты | rules/gotchas.md |
| `ctx.sample()` не работает в Claude Code | rules/llm-sampling.md |
| `download_tracks` автоматически создаёт DjLibraryItem | rules/tools.md |
| TransitionIntent context-aware enum | rules/tools.md |
| score_timbral — 6-й компонент, суммарные веса = 1.0 | rules/tools.md |

---

## Порядок реализации

1. Создать новые rules/ файлы (panel.md, rest-api.md, supabase.md, llm-sampling.md, gotchas.md)
2. Обновить существующие rules/ (добавить frontmatter, перенести gotchas)
3. Переписать CLAUDE.md (компактный entry point)
4. Обновить docs/architecture.md (panel, REST API, PostgreSQL)
5. Обновить docs/transition-scoring.md (6 компонентов, TransitionIntent)
6. Создать docs/panel-guide.md
7. Верификация: проверить что ни один gotcha не потерялся

---

## Критерии успеха

- CLAUDE.md ≤ 100 строк (сейчас 218)
- Каждый rules/ файл имеет frontmatter с description и globs
- Ноль дублирования между CLAUDE.md и rules/
- Все 30 gotchas перенесены в тематические файлы
- docs/architecture.md отражает текущую архитектуру (Panel + REST API + MCP + Supabase)
- Panel задокументирован (rules/panel.md + docs/panel-guide.md)
