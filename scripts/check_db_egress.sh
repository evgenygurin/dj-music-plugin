#!/usr/bin/env bash
# Проверка сетевого доступа к Supabase из песочницы Claude Code on the web.
# Запусти ПОСЛЕ смены Network access на Full (в новой сессии).
#
#   bash scripts/check_db_egress.sh
#
# Что проверяет:
#   1. HTTPS:443  — REST API Supabase (должен работать всегда)
#   2. TCP:6543   — transaction pooler (asyncpg) — целевой порт dj-music MCP
#   3. TCP:5432   — session pooler / direct
#   4. Реальный asyncpg-коннект через DJ_DATABASE_URL (если порт открылся)

set -u

POOLER_HOST="${POOLER_HOST:-aws-1-eu-central-1.pooler.supabase.com}"
REST_HOST="${REST_HOST:-bowosphlnghhgaulcyfm.supabase.co}"

probe() { # host port label
  if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$1/$2" 2>/dev/null; then
    echo "  ✅ $3 ($1:$2) — OPEN"
  else
    echo "  ❌ $3 ($1:$2) — BLOCKED"
  fi
}

echo "=== TCP egress probes ==="
probe "$REST_HOST"   443  "HTTPS REST API"
probe "$POOLER_HOST" 6543 "asyncpg transaction pooler"
probe "$POOLER_HOST" 5432 "session pooler / direct"

echo
echo "=== Live asyncpg connection via DJ_DATABASE_URL ==="
if [ -z "${DJ_DATABASE_URL:-}" ]; then
  echo "  ⚠️  DJ_DATABASE_URL не задан — пропускаю"
  exit 0
fi

uv run python - <<'PY'
import asyncio, os
from app.config import reset_settings_cache
reset_settings_cache()

async def main() -> None:
    from app.db.session import get_session_factory, dispose
    from sqlalchemy import text
    try:
        factory = get_session_factory()
        async with factory() as sess:
            n = (await sess.execute(text("SELECT COUNT(*) FROM tracks"))).scalar()
            f = (await sess.execute(text("SELECT COUNT(*) FROM track_audio_features_computed"))).scalar()
            print(f"  ✅ DB OK — tracks={n}, features={f}")
        await dispose()
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ DB connect failed: {type(e).__name__}: {e}")

asyncio.run(main())
PY
