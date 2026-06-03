#!/usr/bin/env bash
# Диагностика сетевого доступа к Supabase из разных окружений Claude Code.
#
#   bash scripts/check_db_egress.sh
#
# Окружения и что в них работает (official docs §"Network access"):
#   • Облачная песочница (claude.ai/code) — HTTP/HTTPS-only egress-прокси,
#     allowlist по ДОМЕНУ, не по порту. asyncpg :6543 заблокирован архитектурой
#     (это норма). Живая БД доступна через `db` MCP (HTTPS, MCP-трафик идёт
#     через серверы Anthropic) или через `claude --teleport` на локальную машину.
#   • Локально / teleport — прокси нет, asyncpg :6543 открыт, entity_* работают.
#
# Что проверяет:
#   1. HTTPS:443  — REST API Supabase
#   2. TCP:6543   — transaction pooler (asyncpg) — целевой порт dj-music MCP
#   3. TCP:5432   — session pooler / direct
#   4. Реальный asyncpg-коннект через DJ_DATABASE_URL (если .env загружен)
#
# Реализация TCP-проб — через python socket (кроссплатформенно), а НЕ через
# `timeout + /dev/tcp`: на macOS GNU `timeout` отсутствует, из-за чего прежняя
# версия скрипта давала ложные BLOCKED на всех портах.

set -u

# Перейти в корень репозитория (скрипт лежит в scripts/).
cd "$(dirname "$0")/.." || exit 1

# Загрузить .env, чтобы DJ_DATABASE_URL был виден asyncpg-пробе.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

POOLER_HOST="${POOLER_HOST:-aws-1-eu-central-1.pooler.supabase.com}"
REST_HOST="${REST_HOST:-bowosphlnghhgaulcyfm.supabase.co}"

# Облачная песочница выставляет CLAUDE_CODE_REMOTE_SESSION_ID; локально его нет.
if [ -n "${CLAUDE_CODE_REMOTE_SESSION_ID:-}" ]; then
  ENV_KIND="cloud"
else
  ENV_KIND="local"
fi

echo "=== Окружение: ${ENV_KIND} ==="
echo

uv run python - "$REST_HOST" "$POOLER_HOST" "$ENV_KIND" <<'PY'
import asyncio
import socket
import sys

rest_host, pooler_host, env_kind = sys.argv[1], sys.argv[2], sys.argv[3]


def probe(host: str, port: int, label: str) -> bool:
    try:
        with socket.create_connection((host, port), timeout=5):
            print(f"  ✅ {label} ({host}:{port}) — OPEN")
            return True
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ {label} ({host}:{port}) — BLOCKED ({type(e).__name__})")
        return False


print("=== TCP egress probes ===")
p443 = probe(rest_host, 443, "HTTPS REST API")
p6543 = probe(pooler_host, 6543, "asyncpg transaction pooler")
probe(pooler_host, 5432, "session pooler / direct")

print()
print("=== Live asyncpg connection via DJ_DATABASE_URL ===")


async def _db_check() -> bool:
    import os

    if not os.environ.get("DJ_DATABASE_URL"):
        print("  ⚠️  DJ_DATABASE_URL не задан (нет .env?) — пропускаю")
        return False
    from sqlalchemy import text

    from app.config import reset_settings_cache

    reset_settings_cache()
    from app.db.session import dispose, get_session_factory

    try:
        factory = get_session_factory()
        async with factory() as sess:
            n = (await sess.execute(text("SELECT COUNT(*) FROM tracks"))).scalar()
            f = (
                await sess.execute(
                    text("SELECT COUNT(*) FROM track_audio_features_computed")
                )
            ).scalar()
            print(f"  ✅ DB OK — tracks={n}, features={f}")
        await dispose()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ DB connect failed: {type(e).__name__}: {e}")
        return False


db_ok = asyncio.run(_db_check())

print()
print("=== Вывод ===")
if db_ok:
    print("  ✅ entity_* tools работают напрямую через asyncpg.")
elif p6543:
    print("  ⚠️  Порт :6543 открыт, но asyncpg-коннект не прошёл — проверь .env / креды.")
elif env_kind == "cloud":
    print("  ℹ️  :6543 заблокирован — это НОРМА для облачной песочницы")
    print("     (HTTP/HTTPS-only прокси). Для живой БД используй:")
    print("       • `db` MCP-сервер (HTTPS, mcp__*__execute_sql / list_tables), или")
    print("       • `claude --teleport` на локальную машину (там asyncpg открыт).")
else:
    print("  ❌ :6543 заблокирован локально — неожиданно. Проверь firewall / VPN /")
    print("     корпоративный egress. Локально порт должен быть открыт.")

# Информативный код выхода: 0 если есть рабочий путь к данным, иначе 1.
# В облаке доступность REST:443 достаточна (db MCP идёт через HTTPS).
sys.exit(0 if (db_ok or (env_kind == "cloud" and p443)) else 1)
PY
