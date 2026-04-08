#!/usr/bin/env bash
# deploy_to_vm.sh — копирует проект на VM и запускает анализ треков
#
# Использование:
#   ./scripts/deploy_to_vm.sh user@vm-host [--level 5] [--workers 20] [--batch 200]
#
# Пример:
#   ./scripts/deploy_to_vm.sh root@192.168.1.100 --level 5 --workers 20

set -euo pipefail

# ── Аргументы ────────────────────────────────────────────────────────────────
VM_HOST="${1:-}"
if [[ -z "$VM_HOST" ]]; then
  echo "Использование: $0 user@host [--level N] [--workers N] [--batch N] [--force]"
  exit 1
fi
shift

LEVEL=5
WORKERS=0        # 0 = авто (скрипт сам выберет по CPU)
BATCH=200
FORCE=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --level)   LEVEL="$2";   shift 2 ;;
    --workers) WORKERS="$2"; shift 2 ;;
    --batch)   BATCH="$2";   shift 2 ;;
    --force)   FORCE="--force"; shift ;;
    --dry-run) EXTRA_ARGS+=("--dry-run"); shift ;;
    *) echo "Неизвестный аргумент: $1"; exit 1 ;;
  esac
done

REMOTE_DIR="/opt/dj-music"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "════════════════════════════════════════"
echo " DJ Music Plugin — деплой на VM"
echo " Host:    $VM_HOST"
echo " Уровень: L$LEVEL | Воркеры: $WORKERS | Батч: $BATCH"
echo " Источник: $LOCAL_DIR"
echo " Цель:    $REMOTE_DIR"
echo "════════════════════════════════════════"

# ── 1. Синхронизация кода ─────────────────────────────────────────────────────
echo ""
echo "▶ [1/5] Синхронизация кода..."
rsync -az --progress \
  --exclude ".venv" \
  --exclude ".git" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude ".pytest_cache" \
  --exclude ".mypy_cache" \
  --exclude ".ruff_cache" \
  --exclude "generated-sets" \
  --exclude "data" \
  --exclude "cache" \
  --exclude "panel/node_modules" \
  --exclude "panel/.next" \
  --exclude "*.log" \
  --exclude "in-memoria*.db" \
  "$LOCAL_DIR/" "$VM_HOST:$REMOTE_DIR/"
echo "✓ Код синхронизирован"

# ── 2. Копируем .env с реальными секретами ────────────────────────────────────
echo ""
echo "▶ [2/5] Копируем .env..."
if [[ -f "$LOCAL_DIR/.env" ]]; then
  scp "$LOCAL_DIR/.env" "$VM_HOST:$REMOTE_DIR/.env"
  echo "✓ .env скопирован"
else
  echo "⚠ .env не найден — убедись что переменные на VM уже есть"
fi

# ── 3. Настройка окружения на VM ─────────────────────────────────────────────
echo ""
echo "▶ [3/5] Настройка окружения на VM..."
ssh "$VM_HOST" bash <<'REMOTE_SETUP'
set -euo pipefail
REMOTE_DIR="/opt/dj-music"
cd "$REMOTE_DIR"

echo "  Python: $(python3 --version 2>/dev/null || echo 'не найден')"

# Установка uv если нет
if ! command -v uv &>/dev/null; then
  echo "  Устанавливаю uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "  uv: $(uv --version)"

# Синхронизация зависимостей со ВСЕМИ экстрами (audio + stems + essentia)
echo "  Устанавливаю зависимости (все экстры)..."
uv sync --all-extras --quiet
echo "  ✓ Зависимости установлены"

# Проверка librosa и essentia
echo "  Проверка анализаторов..."
.venv/bin/python -c "
import importlib
for lib in ['librosa', 'soundfile', 'numpy']:
    try:
        importlib.import_module(lib)
        print(f'  ✓ {lib}')
    except ImportError:
        print(f'  ✗ {lib} — НЕ установлен')
try:
    import essentia
    print(f'  ✓ essentia {essentia.__version__}')
except ImportError:
    print('  ⚠ essentia — не установлен (L5 ADVANCED частично недоступен)')
"
REMOTE_SETUP
echo "✓ Окружение готово"

# ── 4. Проверяем доступность БД и YM ─────────────────────────────────────────
echo ""
echo "▶ [4/5] Проверка подключения..."
ssh "$VM_HOST" bash <<REMOTE_CHECK
set -euo pipefail
cd /opt/dj-music
.venv/bin/python -c "
import asyncio, os
os.environ.setdefault('DJ_AUDIO_SCORING_WORKERS', '4')  # temp for check
from app.config import settings

async def check():
    from app.db import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as s:
        r = await s.execute(text('SELECT COUNT(*) FROM tracks WHERE status = 0'))
        total = r.scalar()
        r2 = await s.execute(text('''
            SELECT COUNT(*) FROM tracks t
            LEFT JOIN track_audio_features_computed f ON f.track_id = t.id
            WHERE t.status = 0 AND (f.track_id IS NULL OR f.analysis_level < $LEVEL)
        '''))
        need = r2.scalar()
        print(f'  Всего треков: {total}')
        print(f'  Нужен анализ L$LEVEL: {need}')

asyncio.run(check())
"
REMOTE_CHECK
echo "✓ Подключение OK"

# ── 5. Запуск анализа ─────────────────────────────────────────────────────────
echo ""
echo "▶ [5/5] Запуск анализа на VM..."
echo "  Команда: python scripts/vm_analyze.py --level $LEVEL --workers $WORKERS --batch $BATCH $FORCE ${EXTRA_ARGS[*]:-}"
echo ""

# Запускаем в tmux (если есть) или screen или просто в фоне с nohup
ssh "$VM_HOST" bash <<REMOTE_RUN
set -euo pipefail
cd /opt/dj-music

WORKERS_ARG=""
if [[ "$WORKERS" -gt 0 ]]; then
  WORKERS_ARG="--workers $WORKERS"
fi

CMD=".venv/bin/python scripts/vm_analyze.py --level $LEVEL --batch $BATCH \$WORKERS_ARG $FORCE ${EXTRA_ARGS[*]:-}"

if command -v tmux &>/dev/null; then
  # Запуск в tmux — можно переподключиться в любое время
  SESSION="dj_analyze"
  tmux kill-session -t "\$SESSION" 2>/dev/null || true
  tmux new-session -d -s "\$SESSION" "\$CMD 2>&1 | tee -a vm_analyze_latest.log"
  echo "✓ Запущено в tmux (сессия: \$SESSION)"
  echo ""
  echo "  Переподключиться: ssh $VM_HOST 'tmux attach -t \$SESSION'"
  echo "  Смотреть лог:     ssh $VM_HOST 'tail -f /opt/dj-music/vm_analyze_latest.log'"
  echo "  Остановить:       ssh $VM_HOST 'tmux kill-session -t \$SESSION'"
elif command -v screen &>/dev/null; then
  screen -dmS dj_analyze bash -c "\$CMD 2>&1 | tee -a vm_analyze_latest.log"
  echo "✓ Запущено в screen (сессия: dj_analyze)"
  echo ""
  echo "  Переподключиться: ssh $VM_HOST 'screen -r dj_analyze'"
  echo "  Смотреть лог:     ssh $VM_HOST 'tail -f /opt/dj-music/vm_analyze_latest.log'"
else
  nohup \$CMD > vm_analyze_latest.log 2>&1 &
  PID=\$!
  echo "\$PID" > vm_analyze.pid
  echo "✓ Запущено в фоне (PID: \$PID)"
  echo ""
  echo "  Смотреть лог: ssh $VM_HOST 'tail -f /opt/dj-music/vm_analyze_latest.log'"
  echo "  Остановить:   ssh $VM_HOST 'kill \$(cat /opt/dj-music/vm_analyze.pid)'"
fi
REMOTE_RUN

echo ""
echo "════════════════════════════════════════"
echo " ✓ Деплой завершён!"
echo ""
echo " Следить за прогрессом:"
echo "   ssh $VM_HOST 'tail -f /opt/dj-music/vm_analyze_latest.log'"
echo ""
echo " Или подключиться к tmux:"
echo "   ssh $VM_HOST 'tmux attach -t dj_analyze'"
echo "════════════════════════════════════════"
