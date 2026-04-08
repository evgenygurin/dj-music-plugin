# VM Deployment

Запуск continuous import+analyze loop из Yandex Music на отдельной VM. Используется для прогрева библиотеки треков на L5 без блокировки локальной машины.

## VM specs

| Параметр | Значение |
|---|---|
| Хост | `root@155.212.128.27` |
| OS | Ubuntu 22.04+ (`/proc/sys/kernel/osrelease` — Linux 5.15+) |
| CPU | 16 ядер AMD EPYC (минимум 8) |
| RAM | 32 GB (минимум 16) |
| Disk | 200+ GB NVMe |
| Установлено | `tmux`, `python3`, `systemd 249+` |
| Не установлено | `uv` (deploy скрипт ставит сам) |

VM поддерживает live resize — `nproc` и `free` обновляются без переустановки `.venv`.

## Layout на VM

```text
/opt/dj-music/                  # Корень проекта (rsync с локального)
├── .venv/                      # uv-managed venv
├── .env                        # Секреты (DJ_*) — копируется отдельно через scp
├── scripts/
│   ├── vm_import_and_analyze.py
│   └── deploy_to_vm.sh
├── vm_loop_latest.log          # Stdout/stderr текущего loop'а
└── ...
```

## Deploy

Локально:

```bash
# 1. Sync code
rsync -az --delete \
  --exclude .venv --exclude .git --exclude __pycache__ --exclude "*.pyc" \
  --exclude .pytest_cache --exclude .mypy_cache --exclude .ruff_cache \
  --exclude generated-sets --exclude data --exclude cache \
  --exclude panel/node_modules --exclude panel/.next \
  --exclude "*.log" --exclude "in-memoria*.db" \
  ./ root@155.212.128.27:/opt/dj-music/

# 2. Sync .env с реальными секретами
scp .env root@155.212.128.27:/opt/dj-music/.env

# 3. Setup venv (на VM)
ssh root@155.212.128.27 'cd /opt/dj-music && \
  if ! command -v uv &>/dev/null; then \
    curl -LsSf https://astral.sh/uv/install.sh | sh; \
  fi; \
  export PATH="$HOME/.local/bin:$PATH"; \
  uv sync --all-extras'
```

## systemd-run pattern

**НЕ используй tmux** для long-running jobs. Detached `tmux new-session -d` создаёт transient tmux server, привязанный к ssh-сессии — после disconnect'а server умирает и убивает все окна.

Используй transient `systemd-run` unit — он живёт независимо от ssh, имеет auto-restart, выживает VM resize:

```bash
ssh root@155.212.128.27 '
systemctl reset-failed dj-loop 2>/dev/null
> /opt/dj-music/vm_loop_latest.log

systemd-run --unit=dj-loop \
  --working-directory=/opt/dj-music \
  --setenv=PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  --setenv=PYTHONUNBUFFERED=1 \
  --setenv=OMP_NUM_THREADS=1 \
  --setenv=OPENBLAS_NUM_THREADS=1 \
  --setenv=MKL_NUM_THREADS=1 \
  --setenv=PYTHONFAULTHANDLER=1 \
  --property=Restart=on-failure \
  --property=RestartSec=15s \
  --property=StartLimitBurst=999 \
  --property=StartLimitIntervalSec=0 \
  --property=TimeoutStopSec=20s \
  --property=KillMode=mixed \
  --property=StandardOutput=append:/opt/dj-music/vm_loop_latest.log \
  --property=StandardError=append:/opt/dj-music/vm_loop_latest.log \
  /opt/dj-music/.venv/bin/python -u -X faulthandler \
  /opt/dj-music/scripts/vm_import_and_analyze.py \
  --level 5 --batch 100 --workers 12 --sleep 600
'
```

Ключевые `--property`:

| Property | Назначение |
|---|---|
| `Restart=on-failure` | systemd сам перезапускает после non-zero exit / сигнала |
| `RestartSec=15s` | Пауза перед рестартом — не флудить ресурсы при flapping |
| `StartLimitBurst=999` + `StartLimitIntervalSec=0` | Снимает лимит "5 рестартов в 10 сек" — иначе systemd кидает unit в `failed` после 5 крашей |
| `TimeoutStopSec=20s` | Сколько ждать graceful shutdown перед SIGKILL |
| `KillMode=mixed` | SIGTERM main процессу, SIGKILL всем child'ам |
| `StandardOutput=append:PATH` | Append (не truncate) stdout в файл — для tail -F |

`--setenv=PYTHONUNBUFFERED=1` + `python -u` — для real-time tail -F (см. `.claude/rules/logging.md`).

`--setenv=OMP/OPENBLAS/MKL_NUM_THREADS=1` — отключает internal parallelism BLAS-библиотек, чтобы не плодить CPU oversubscription поверх своих ThreadPoolExecutor'ов.

`--setenv=PYTHONFAULTHANDLER=1` + `python -X faulthandler` — на SEGV дампит C-стек, без него видно только `signal=SEGV` в журнале.

## vm_import_and_analyze.py CLI

```text
python scripts/vm_import_and_analyze.py [flags]
```

| Flag | Default | Назначение |
|---|---|---|
| `--level {2,3,4,5}` | `5` | Целевой уровень `AnalysisLevel` |
| `--batch N` | `100` | Размер chunk внутри одного pool |
| `--workers N` | `0` (auto) | Размер ThreadPoolExecutor в `AnalysisPipeline` |
| `--sleep N` | `600` | Пауза между sweep'ами в continuous mode (сек) |
| `--test-one` | — | Импорт + анализ **одного** трека из плейлиста `TECHNO FOR DJ SETS` (kind=1280) и выход |
| `--test-batch N` | — | Импорт + анализ **первых N** треков того же плейлиста и выход |
| `--once` | — | Один полный sweep по лайкам + всем подходящим плейлистам и выход |
| `--no-likes` | — | Пропустить пул лайкнутых треков |
| `--playlist-filter REGEX` | `techno\|tech\s*house\|minimal\|peak\s*time\|dub\s*techno\|acid` | Фильтр названий плейлистов |
| `--force` | — | Пере-анализировать треки даже если уже на target_level |

**Continuous mode** (без `--test-*` / `--once`): бесконечный цикл `sweep → sleep → sweep`. Каждый sweep — пул лайков (414 треков) + все плейлисты совпадающие с regex. Идемпотентен — уже проанализированные на target level пропускаются.

**Workers**: 12 на 16-CPU VM — оптимум. Главный поток + IO + системные процессы поедают остальные 4 ядра. На 8-CPU VM — 4-6.

## Monitoring

```bash
# Живой хвост
ssh root@155.212.128.27 'tail -F /opt/dj-music/vm_loop_latest.log'

# Только прогресс треков (без шума)
ssh root@155.212.128.27 \
  'tail -F /opt/dj-music/vm_loop_latest.log | grep -E "\[[0-9]+/|chunk done|LOOP|totals"'

# Статус сервиса
ssh root@155.212.128.27 'systemctl status dj-loop --no-pager'

# Live CPU/mem текущего PID
ssh root@155.212.128.27 'PID=$(systemctl show dj-loop -p MainPID --value); top -bn1 -p $PID | tail -2'

# История крашей
ssh root@155.212.128.27 \
  'journalctl -u dj-loop --since "1 hour ago" --no-pager | grep -E "SEGV|killed|Failed|restart counter"'
```

## Управление

```bash
# Стоп
ssh root@155.212.128.27 'systemctl stop dj-loop'

# Рестарт
ssh root@155.212.128.27 'systemctl restart dj-loop'

# Полное удаление transient unit
ssh root@155.212.128.27 'systemctl stop dj-loop; systemctl reset-failed dj-loop'
```

## Cron-watcher (опционально)

Из локальной Claude сессии можно запустить self-healing loop через `/loop`:

```text
/loop 10m проверь dj-loop.service на root@155.212.128.27: systemctl is-active,
последние 30 строк /opt/dj-music/vm_loop_latest.log, если is-active != active —
restart и сообщи; иначе короткий статус (loop, chunk, imp/skip/ana/fail)
```

Это создаёт recurring `CronCreate` job, который каждые 10 минут дёргает VM, проверяет статус и при падении сам делает `systemctl restart`. Session-only, авто-удаляется через 7 дней.

## Troubleshooting

### `signal=SEGV` в `librosa.beat.beat_track`

**Симптом**: `journalctl -u dj-loop` показывает `Main process exited, code=killed, status=11/SEGV` через 30-90 секунд после старта. С `PYTHONFAULTHANDLER=1` в логе виден трейс `numba/np/ufunc/gufunc.py:263 __call__ → librosa/beat.py:505 __beat_tracker`.

**Причина**: бинарная регрессия в `numba 0.64.0 + llvmlite 0.46.0` несовместима с `numpy 2.x` ABI. SEGV в **single-threaded main вызове**, не race.

**Фикс**:

```bash
ssh root@155.212.128.27 \
  'cd /opt/dj-music && export PATH="$HOME/.local/bin:$PATH" && \
   uv pip install --upgrade numba llvmlite'
```

Минимум — `numba>=0.65`, `llvmlite>=0.47`. Закреплено в `pyproject.toml [audio]` extras.

### `BrokenProcessPool` deadlock

**Симптом**: после первого `BrokenProcessPool` exception все следующие треки тоже падают с тем же сообщением, лог замирает на середине chunk'а, главный python жив но 0% CPU.

**Причина**: `AnalysisPipeline(use_processes=True)` — после краха worker'а `ProcessPoolExecutor` входит в broken state, и pipeline не пересоздаёт executor → `gather()` висит навсегда.

**Фикс**: использовать `use_processes=False` (ThreadPoolExecutor) — что и сделано в `vm_import_and_analyze.py:_process_refs`. Изоляция воркеров через процессы здесь не нужна, потому что numba SEGV исправлен апгрейдом (см. выше).

### tmux session умирает с ssh disconnect

**Симптом**: запустил `tmux new-session -d -s X 'long_command'` через ssh, после `exit` → `tmux ls` показывает `no server running on /tmp/tmux-0/default`, процесс ушёл.

**Причина**: transient tmux server привязан к ssh user-сессии. systemd-logind kill'ит её при `loginctl terminate-user` / disconnect.

**Фикс**: `systemd-run --unit=...` вместо `tmux new-session -d`. См. секцию "systemd-run pattern" выше.

### Лог обновляется раз в N минут вместо real-time

**Симптом**: `tail -F log` показывает строки большими порциями, прогресс не виден.

**Причина**: stdout буферизуется (ни python, ни systemd append не делают line-buffer по умолчанию).

**Фикс**: `python -u` + `--setenv=PYTHONUNBUFFERED=1` + в скрипте `sys.stdout.reconfigure(line_buffering=True)`. Все три. См. `.claude/rules/logging.md`.

### Все треки пропускаются (`skipped=N, analyzed=0`)

**Это нормально**: треки уже на нужном `analysis_level`. Запусти с `--force` чтобы пере-анализировать. Или выбери более высокий `--level`.
