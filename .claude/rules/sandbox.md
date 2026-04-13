# Sandbox Limitations (Claude Code Web)

## Network

Claude Code web sandbox proxy пропускает **только HTTP/HTTPS**.
Raw TCP (PostgreSQL asyncpg, SSH, Redis) **заблокирован навсегда** —
`allowedDomains` влияет только на HTTP, не на TCP.

**Что работает:**
- Supabase REST API (HTTP): `httpx.get(f"{SUPABASE_URL}/rest/v1/...")`
- Yandex Music API (HTTP)
- PyPI downloads
- GitHub API

**Что НЕ работает:**
- `asyncpg` → PostgreSQL (TCP port 6543)
- `psycopg2` → PostgreSQL
- SSH tunnels
- Redis

## Последствия для MCP сервера

MCP сервер (`app/server.py`) **не может запуститься** в sandbox —
его lifespan (`bootstrap/lifespans.py:db_lifespan`) требует asyncpg
для seed_reference_data.

**Workaround для sandbox:**
1. Используй Supabase REST API напрямую (как `scripts/build_set_from_db.py`)
2. MCP tools тестируй через in-memory FastMCP Client с SQLite
3. Полный MCP сервер — только на локальной машине или VM

## allowedDomains

Не ставь `["*"]` — это не откроет TCP. Перечисляй конкретные домены:

```json
"allowedDomains": [
  "aws-1-eu-central-1.pooler.supabase.com",
  "bowosphlnghhgaulcyfm.supabase.co",
  "api.music.yandex.net"
]
```

Горячая перезагрузка настроек **не поддерживается** — нужен рестарт сессии.
