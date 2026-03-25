# Storage Backends

Проект использует FastMCP storage backends для персистентности кешей и состояния.

## Зачем это нужно

1. **Response Caching** — кеширование read-only MCP tool вызовов (get_track, filter_tracks, score_transitions)
2. **Transition Score Cache** — хранение вычисленных transition scores между треками (дорогая операция)
3. **Persistence** — сохранение данных между перезапусками сервера

## Доступные backends

| Backend | Dev | Prod (single) | Prod (multi) | Persistence |
|---------|-----|--------------|-------------|-------------|
| **memory** | ✅ | ⚠️ | ❌ | Нет |
| **file** | ✅ | ✅ | ❌ | Да |
| **redis** | ⚠️ | ✅ | ✅ | Да |

### Memory (default)

```bash
DJ_STORAGE_BACKEND=memory
```

- Быстрый, не требует настройки
- Данные теряются при перезапуске
- Не подходит для multi-process (например, uvicorn workers > 1)

### File

```bash
DJ_STORAGE_BACKEND=file
DJ_STORAGE_FILE_DIR=cache/storage
```

- Персистентность — данные сохраняются при перезапуске
- Читаемые JSON файлы на диске (один файл = один ключ)
- Подходит для single-server prod
- НЕ подходит для distributed/multi-server

### Redis

```bash
DJ_STORAGE_BACKEND=redis
DJ_STORAGE_REDIS_HOST=localhost
DJ_STORAGE_REDIS_PORT=6379
DJ_STORAGE_REDIS_PASSWORD=your_password
DJ_STORAGE_REDIS_DB=0
```

- Distributed caching — работает для multi-server
- Высокая доступность
- Встроенный TTL
- Требует Redis инфраструктуру

## Использование в проекте

### 1. Response Caching Middleware

Автоматически кеширует read-only tool calls:

```python
# app/server.py
from fastmcp.server.middleware.caching import ResponseCachingMiddleware

mcp.add_middleware(
    ResponseCachingMiddleware(
        cache_storage=create_storage_backend(),
        call_tool_settings=CallToolSettings(
            enabled=True,
            ttl=settings.response_cache_ttl,  # default 300s
        ),
    )
)
```

Включается через `DJ_RESPONSE_CACHE_ENABLED=true` (по умолчанию включён).

### 2. Transition Score Cache

Использует отдельное хранилище с namespacing:

```python
# app/services/transition_cache.py
from app.core.storage import create_transition_cache_backend

cache_store = create_transition_cache_backend()
cache = TransitionScoreCache(
    storage=cache_store,
    ttl=settings.transition_cache_ttl,  # default 3600s
)

# Cache transition score
await cache.set(score)

# Retrieve from cache
score = await cache.get(track_id_a=1, track_id_b=2)

# Invalidate when audio features change
await cache.invalidate(track_id=1)
```

## Конфигурация

Все настройки в `app/config.py` через environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DJ_STORAGE_BACKEND` | `memory` | Backend: memory, file, or redis |
| `DJ_STORAGE_FILE_DIR` | `cache/storage` | File backend directory |
| `DJ_STORAGE_REDIS_HOST` | `localhost` | Redis host |
| `DJ_STORAGE_REDIS_PORT` | `6379` | Redis port |
| `DJ_STORAGE_REDIS_PASSWORD` | — | Redis password (optional) |
| `DJ_STORAGE_REDIS_DB` | `0` | Redis DB number |
| `DJ_RESPONSE_CACHE_ENABLED` | `true` | Enable response caching |
| `DJ_RESPONSE_CACHE_TTL` | `300` | Response cache TTL (seconds) |
| `DJ_TRANSITION_CACHE_TTL` | `3600` | Transition cache TTL (seconds) |

## Примеры использования

### Development (default)

```bash
# .env
DJ_STORAGE_BACKEND=memory
DJ_RESPONSE_CACHE_ENABLED=true
```

### Single-server production

```bash
# .env
DJ_STORAGE_BACKEND=file
DJ_STORAGE_FILE_DIR=/var/cache/dj-music/storage
DJ_RESPONSE_CACHE_ENABLED=true
DJ_RESPONSE_CACHE_TTL=600
```

### Multi-server production (Redis)

```bash
# .env
DJ_STORAGE_BACKEND=redis
DJ_STORAGE_REDIS_HOST=redis.example.com
DJ_STORAGE_REDIS_PASSWORD=secure_password
DJ_RESPONSE_CACHE_ENABLED=true
```

## Архитектура

```text
┌─────────────────────────────────────────┐
│           FastMCP Server                │
│  ┌────────────────────────────────────┐ │
│  │ ResponseCachingMiddleware          │ │
│  │ (cache_storage=storage_backend)    │ │
│  └────────────────────────────────────┘ │
│  ┌────────────────────────────────────┐ │
│  │ TransitionScoreCache               │ │
│  │ (storage=transition_cache_backend) │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
         │                  │
         ▼                  ▼
┌─────────────────┐  ┌──────────────────┐
│ create_storage_ │  │ create_transition│
│ backend()       │  │ _cache_backend() │
└─────────────────┘  └──────────────────┘
         │                  │
         ▼                  ▼
┌─────────────────────────────────────────┐
│      py-key-value-aio KeyValueStore     │
│  ┌─────────────────────────────────┐   │
│  │ MemoryStore / FileTreeStore /   │   │
│  │ RedisStore                       │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## Transition Cache Invalidation

Когда изменяются audio features трека, все transition scores с этим треком нужно инвалидировать:

```python
# После изменения audio features (в репозитории или сервисе)
cache = get_transition_cache()
await cache.invalidate(track_id=123)
```

Это O(n) операция (scan всех ключей), но выполняется редко (только при ре-анализе трека).

## Тесты

```bash
# Unit tests для storage factory
uv run pytest tests/test_core/test_storage.py -v

# Unit tests для TransitionScoreCache
uv run pytest tests/test_services/test_transition_cache.py -v
```

## Ссылки

- [FastMCP Storage Backends](https://gofastmcp.com/servers/storage-backends.md)
- [py-key-value-aio GitHub](https://github.com/strawgate/py-key-value)
- Transition scoring: `docs/transition-scoring.md`
