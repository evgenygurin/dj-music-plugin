# DJ Music Plugin

> Инструкции для Claude Code. Общие правила проекта и устойчивые архитектурные инварианты находятся в [`AGENTS.md`](AGENTS.md) и [`rules/`](rules/).

## Язык и инструменты

Отвечай по-русски, если пользователь не указал другое. Используй `uv` для проектного Python runtime и существующие repository-native quality gates.

Не создавай GitHub Actions/CI только ради локальной проверки, если это противоречит текущей конфигурации репозитория. Проверяй фактические доступные gates перед изменением workflow.

## Документация

Для архитектурных вопросов сначала смотри [docs/architecture.md](docs/architecture.md). Для аудио — [docs/audio-pipeline.md](docs/audio-pipeline.md). Для DJ transition/set policy — соответствующие domain docs и правила в `.claude/rules/`.

Не воспринимай historical research, audits, reports и changelogs как текущий runtime contract.

Не используй документацию как ручной runtime catalog. Количество MCP objects, тестов, файлов, индексных сущностей и другие volatile facts получай из кода, FastMCP discovery, validators или свежих команд.

## Архитектурные принципы

- MCP является внешним интерфейсом; бизнес-логика не должна уходить в transport layer.
- Domain policy должна оставаться отделённой от persistence и внешних провайдеров.
- Audio и DJ engine orchestration должны иметь явные границы между analysis, validation, scoring, planning и rendering.
- Schema-driven универсальные операции предпочтительнее размножения однотипных endpoint-ов.
- Для изменений существующих символов используй GitNexus impact workflow из `rules/gitnexus.md`.

## Claude-specific workflow

Перед существенным изменением сначала найди фактический runtime contract в коде и тестах. Для MCP tools/resources/prompts проверяй зарегистрированные схемы, а не копируй старые списки из docs.

При изменении prompt загрузи `.claude/rules/prompts.md` и соответствующие domain rules. Runtime identifiers внутри prompt должны проверяться тестами/registry/schema, а не ручным каталогом.

При изменении audio/DJ logic загрузи соответствующие `.claude/rules/` и проверь актуальную реализацию; не тащи исторические workarounds в новый код без подтверждения, что ограничение всё ещё существует.

## Plugin development cache

Claude Code может работать с отдельной plugin-копией. Не копируй рабочие файлы в cache вручную. Для dev workflow используй предусмотренные проектом механизмы и проверяй, откуда реально загружен plugin.

## Quality gate

Перед завершением изменения запускай релевантные проверки. Полный gate — `make check`, когда изменение относится к коду или shared contracts. Для чисто текстового изменения достаточно соответствующей проверки содержимого и diff.

Сохраняй evidence свежего запуска; не подставляй в отчёт исторические counts из README/CLAUDE/docs.
