# DJ Music Plugin

**MIT** · MCP-сервер для управления личной DJ techno библиотекой, анализа аудио, построения оптимизированных DJ-сетов и интеграции с внешними музыкальными сервисами.

## Возможности

- **MCP-интерфейс** для управления библиотекой, анализа, set-building, transition planning и delivery workflows.
- **Аудиоанализ** с tiered/staged обработкой, переиспользованием DSP-контекста и typed analysis contracts.
- **DJ set generation** с генерацией кандидатов, техническими ограничениями и музыкальным scoring.
- **Universal AI DJ Engine** с разделением анализа, candidate generation, validation, scoring, planning и rendering.
- **Transition planning** с явными планами, decision contracts, reproducibility/provenance и rollout-safe режимами.
- **Yandex Music integration** для поиска, чтения и управления библиотечными сущностями через provider boundary.
- **Экспорт и delivery** результатов набора в поддерживаемые форматы и workflow.

Актуальный runtime surface не перечисляется вручную в README. Для точного списка tools/resources/prompts используй FastMCP discovery/introspection и schema tests.

## Быстрый старт

```bash
uv sync
uv sync --extra audio
cp .env.example .env
uv run fastmcp run server.py
```

Настройки и доступы описаны в `.env.example` и соответствующих configuration docs.

## Установка как Claude Code plugin

Внутри Claude Code:

```bash
/plugin marketplace add evgenygurin/dj-music-plugin
/plugin install dj-music
```

Для session-only проверки:

```bash
git clone https://github.com/evgenygurin/dj-music-plugin.git
claude --plugin-dir /path/to/dj-music-plugin
```

Перед публикацией или PR проверяй plugin manifests штатным validator'ом соответствующей платформы.

## Разработка

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy app/
uv run lint-imports
make check
```

Для конкретной подсистемы предпочитай её targeted tests и проверки. Свежий результат команды важнее любого числа, сохранённого в документации.

## Архитектура

Высокоуровневая граница системы:

```text
MCP clients
    │
    ▼
FastMCP composition
    │
    ├── tools/resources/prompts
    │
    ▼
application orchestration
    │
    ├── domain
    ├── audio
    ├── providers
    └── persistence
```

Подробнее: [docs/architecture.md](docs/architecture.md).

### Ключевые решения

- **MCP — primary interface.** Workflow composition выполняется через MCP surface; domain logic не переносится в transport layer.
- **Polymorphism over proliferation.** Универсальные schema-driven операции предпочтительнее размножения почти одинаковых endpoint-ов.
- **Pure domain.** `app/domain/` не зависит от DB, HTTP или FastMCP.
- **Explicit boundaries.** Persistence, providers и audio execution изолированы от domain policy.
- **Typed contracts.** Между крупными этапами engine используются явные contracts с provenance/identity там, где это нужно для воспроизводимости.

## Audio

Аудиоподсистема построена как staged pipeline. Дешёвые вычисления могут использоваться для triage, глубокий анализ подключается по необходимости, а expensive/optional backends остаются behind capability checks.

Подробнее: [docs/audio-pipeline.md](docs/audio-pipeline.md).

## DJ Engine

Основной концептуальный pipeline:

```text
analysis
  → candidate generation
  → hard technical validation
  → musical scoring
  → planning
  → rendering
  → persistence
```

Hard constraints отвечают за техническую пригодность, scoring — за ранжирование пригодных вариантов. Rollout новых реализаций должен сохранять безопасную совместимость до явной смены production policy.

Подробнее: [docs/transition-scoring.md](docs/transition-scoring.md).

## Документация

- Архитектурные инварианты: [docs/architecture.md](docs/architecture.md)
- Аудиопайплайн: [docs/audio-pipeline.md](docs/audio-pipeline.md)
- Domain glossary: [docs/domain-glossary.md](docs/domain-glossary.md)
- Development/runtime notes: [docs/dev-mode.md](docs/dev-mode.md)
- Research, audits, plans и reports — исторические/исследовательские материалы, а не обязательный source of truth.
