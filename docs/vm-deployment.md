# VM Deployment

Batch-анализ треков на удалённой VM через `scripts/deploy_to_vm.sh` +
`scripts/vm_analyze.py`. Используется для прогрева библиотеки на L5 без
блокировки локальной машины.

> **История:** ранее существовал continuous-loop скрипт
> `scripts/vm_import_and_analyze.py` (systemd-run + self-healing). Он
> был написан против legacy `app.ym.*` / `app.services.*` /
> `app.controllers.*` и сломался при Phase 7 cutover. Файл удалён в
> v1.0.4. Текущий VM workflow — одноразовый batch-анализ; continuous
> import+analyze loop на v1 surface пока не переписан.

## VM specs

| Параметр | Значение |
|---|---|
| Пример хоста | `root@155.212.128.27` |
| OS | Ubuntu 22.04+ |
| CPU | 16+ ядер (опт.: 60 cores / 32 GB RAM) |
| RAM | 32 GB (минимум 16) |
| Disk | 200+ GB NVMe |
| Установлено | `python3`, `tmux` или `screen` (опц.) |
| Не установлено | `uv` (deploy скрипт ставит сам) |

## Layout на VM

```text
/opt/dj-music/                  # rsync с локального
├── .venv/                      # uv-managed venv
├── .env                        # секреты (DJ_*) — scp отдельно
├── scripts/
│   ├── vm_analyze.py
│   └── deploy_to_vm.sh
└── vm_analyze_latest.log       # stdout/stderr текущего анализа
```

## Deploy & run (one-shot)

```bash
./scripts/deploy_to_vm.sh root@<vm-host> --level 5 --workers 20 --batch 200
```

Скрипт делает всё:

1. **rsync** кода в `/opt/dj-music/` (исключает `.venv`, `.git`,
   `panel/node_modules`, кеши, логи).
2. **scp .env** с локальными секретами.
3. **Ставит uv** на VM если нет, делает `uv sync --all-extras`.
4. **Smoke-check** БД через короткий async-скрипт.
5. **Запускает `vm_analyze.py`** в tmux / screen / nohup (в таком
   порядке приоритета). Stdout идёт в `vm_analyze_latest.log`.

Флаги `--level`, `--workers`, `--batch`, `--force`, `--dry-run`
пробрасываются в `vm_analyze.py`.

## vm_analyze.py CLI

```text
python scripts/vm_analyze.py [flags]
```

| Flag | Default | Назначение |
|---|---|---|
| `--level {2,3,4,5}` | `5` | Целевой `AnalysisLevel` |
| `--batch N` | `200` | Размер chunk'а внутри pool |
| `--workers N` | `0` (auto) | Размер ThreadPoolExecutor |
| `--force` | — | Пере-анализировать уже готовые треки |
| `--dry-run` | — | Показать план без выполнения |

Уровни:

- **L2 (TRIAGE)** — BPM, LUFS, энергия, спектр, key, MFCC
- **L3 (SCORING)** — + beat (onset, kick, hp_ratio, pulse)
- **L4 (TRANSITION)** — + structure (секции)
- **L5 (ADVANCED)** — + danceability, dissonance, tonnetz, tempogram, …

Для 60-core VM рекомендуется `--workers 20 --level 5`.

## Monitoring

```bash
# Живой хвост
ssh root@<vm-host> 'tail -f /opt/dj-music/vm_analyze_latest.log'

# tmux (если скрипт запустился в tmux)
ssh root@<vm-host> 'tmux attach -t dj_analyze'

# Остановить
ssh root@<vm-host> 'tmux kill-session -t dj_analyze'
# или если nohup:
ssh root@<vm-host> 'kill $(cat /opt/dj-music/vm_analyze.pid)'
```

## Troubleshooting

### `signal=SEGV` в `librosa.beat.beat_track`

Бинарная регрессия в `numba 0.64.0 + llvmlite 0.46.0 + numpy 2.x`.
SEGV на single-threaded main call.

**Фикс:**

```bash
ssh root@<vm-host> \
  'cd /opt/dj-music && export PATH="$HOME/.local/bin:$PATH" && \
   uv pip install --upgrade numba llvmlite'
```

Минимум: `numba>=0.65`, `llvmlite>=0.47`. Закреплено в
`pyproject.toml [audio]`.

### `BrokenProcessPool` deadlock

После первого краха worker'а `ProcessPoolExecutor` уходит в broken
state, и pipeline не пересоздаёт executor → зависание.

**Фикс:** `vm_analyze.py` использует `use_processes=False`
(ThreadPoolExecutor). Изоляция через процессы не нужна, numba SEGV
решается апгрейдом (выше).

### Все треки пропускаются (`skipped=N, analyzed=0`)

Это нормально — треки уже на нужном `analysis_level`. Запусти с
`--force` или выбери более высокий `--level`.

## Long-running / continuous loops

Для continuous import+analyze sweep'ов (BFS-раскрутка плейлиста,
периодическое добавление лайков) используй Claude Code `/loop` или
cron на VM — `vm_analyze.py` сам по себе одноразовый. Переписанный
continuous-loop скрипт на v1 surface не реализован.
