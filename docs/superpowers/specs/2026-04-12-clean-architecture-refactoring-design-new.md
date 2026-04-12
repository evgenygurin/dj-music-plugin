# Clean Architecture Refactoring — Design Spec

> Полная перестройка dj-music-plugin из flat monolith в Modular Monolith с Clean Architecture.

## Проблема

Текущий проект (~304 Python файла, ~28.6K LOC без миграций):

1. **Flat monolith** — 18 пакетов на одном уровне в `app/` без bounded contexts
2. **Три слоя данных без границ** — `db/models/` (ORM), `entities/` (dataclass), `schemas/` (Pydantic) пересекаются
3. **controllers/ гигант** — tools, dependencies, resources, prompts, middleware, schemas в одном пакете
4. **services/ flat bag** — 15+ сервисов без группировки
5. **Дублирование** — `build_ym_client()` x2, `_classify_mood` x2, `resolve_track_refs` x2
6. **Layer violations** — 21 прямой импорт `app.db.models` в services
7. **Config god-object** — 100+ настроек в одном `Settings` классе
8. **Ghost directories** — 6 пустых директорий без кода

## Что уже хорошо (не ломать)

- `transition/` — чистый домен, хорошая декомпозиция
- `audio/` — layered, GoF паттерны (Registry, Strategy, Template Method)
- `export/` — pure domain writers
- `optimization/` — Strategy pattern, чистый домен
- `import-linter` — 6 контрактов
- UnitOfWork pattern реализован
- FileSystemProvider auto-discovery работает

## Принятые решения

| Решение | Выбор | Причина |
|---------|-------|---------|
| Архитектура | Clean Architecture | Строгие слои, dependency rule |
| Корневой пакет | `src/dj_music/` | Правильное Python packaging |
| Domain entities | Да (Pydantic BaseModel) | Сервисы не знают об ORM. Pydantic = валидация + сериализация |
| Mapper | `from_attributes=True` | `Entity.model_validate(orm_obj)` — Pydantic маппит автоматически |
| Ports (Protocol) | Да, на границах | Repositories + YM client + Cache |
| Config split | Да, по доменам | Решает god-object |
| FileSystemProvider | `presentation/mcp/` | Одна строка в server_builder |
