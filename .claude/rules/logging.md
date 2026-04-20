---
description: Logging rules for long-running CLI jobs and services
globs: scripts/**/*.py
---

# Logging for long-running CLI

Правила для скриптов и сервисов которые крутятся часами/днями (импорт/анализ на VM, batch jobs, систем сервисы). Применяются в `scripts/vm_*.py` и любых других long-running CLI.

> **История:** `scripts/vm_import_and_analyze.py` был удалён в v1.0.4
> — сломался при Phase-7 cutover на v1 (импорты `app.services.*`,
> `app.ym.*`, `app.controllers.*`). Текущий batch анализ —
> `scripts/vm_analyze.py` (одноразовый, без continuous loop).
> Continuous-loop скрипт на v1 surface пока не переписан. Паттерны
> ниже — канон для любого нового long-running CLI.

## Real-time output (без буферизации)

`tail -F log` через ssh должен показывать новые строки **сразу**. Без этого пользователь видит "висит" а не реально работающий процесс.

Включить **все три** механизма — каждый отдельно недостаточен:

```python
# 1. Force line-buffered stdout (works inside python process)
import sys
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass
```

```bash
# 2. CLI flag — disables stdio buffering at interpreter level
python -u script.py

# 3. Env var — same effect, also propagates to child processes
PYTHONUNBUFFERED=1
```

В `systemd-run` все три должны быть выставлены: `--setenv=PYTHONUNBUFFERED=1` + ExecStart с `python -u`.

## Глушить шумные библиотеки

Долгие jobs делают тысячи HTTP-запросов. Дефолтный `httpx`-логгер на INFO заполняет лог `HTTP Request: GET ...` строками и **скрывает реальный прогресс**. Глушить до WARNING:

```python
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
```

Свой логгер и `app.*` — оставлять INFO:

```python
logging.getLogger("app.audio").setLevel(logging.INFO)
logging.getLogger("app.handlers").setLevel(logging.INFO)
```

## Per-task progress

В batch обработке (N задач, асинхронно) видеть только `chunk done` через 10 минут — бесполезно. Логать каждый завершённый item:

```bash
[42/100] track=1093 ym=137518650 OK in 57.1s (ok=42 fail=0)
```

Формат: `[done/total] item=ID status in elapsed (ok=X fail=Y)`. Работает для tracks, downloads, jobs — что угодно.

Реализация для async с одновременными воркерами — `asyncio.Lock` вокруг counter и log call:

```python
counters = {"done": 0, "ok": 0, "fail": 0}
log_lock = asyncio.Lock()

async def _wrapped(task_id):
    t0 = time.time()
    try:
        res = await orig(task_id)
        return res
    finally:
        async with log_lock:
            counters["done"] += 1
            ok = res is not None
            counters["ok" if ok else "fail"] += 1
            log.info(
                "    [%d/%d] task=%s %s in %.1fs (ok=%d fail=%d)",
                counters["done"], total, task_id,
                "OK" if ok else "FAIL", time.time() - t0,
                counters["ok"], counters["fail"],
            )
```

Lock обязателен — `log.info` сам по себе thread-safe, но **counter race** даст неверные числа без lock.

## Format

Префикс `name`-логгера в формате помогает отделить ваш CLI от чужих библиотек:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("loop")  # короткий name → "loop:" в строках
```

## Wrapping core services for progress

Если core service (например `TieredPipeline`) логирует только итоги, **не патчь core** — оборачивай метод в скрипте через monkey-patch:

```python
tiered = TieredPipeline(...)
_orig = tiered._download_and_analyze
async def _wrapped(*args, **kwargs):
    # ... timing, counters, log.info(...)
    return await _orig(*args, **kwargs)
tiered._download_and_analyze = _wrapped  # type: ignore[method-assign]
```

Скрипт-специфичный прогресс остаётся в скрипте, core service не меняется.
