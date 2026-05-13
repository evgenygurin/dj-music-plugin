---
description: Logging rules for long-running CLI jobs and services
globs: scripts/**/*.py
---

# Logging for long-running CLI

Правила для скриптов и сервисов которые крутятся часами/днями (batch import/analyze jobs, systemd services, любые long-running CLI поверх v1 dispatchers).

> **История:** `scripts/vm_import_and_analyze.py` (continuous loop) и
> `scripts/vm_analyze.py` (one-shot) удалены в Phase-7 cutover —
> зависели от legacy `app.services.*` / `app.ym.*` /
> `app.controllers.*`, которых больше нет. Continuous batch job на v1
> surface (`entity_create(entity="track_features", ...)` через MCP)
> пока не переписан. Паттерны ниже — канон для будущей реализации.

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

## Handlers — `safe_info` / `safe_report_progress` (v1.3.7)

Handlers (`app/handlers/*.py`) больше **не** зовут `ctx.info()` / `ctx.report_progress()` напрямую. Эти методы требуют активной MCP-сессии, которой нет в headless-скриптах и unit-тестах — прямой вызов падает с `RuntimeError`.

Канонический паттерн:

```python
from app.handlers._context_log import safe_info, safe_report_progress

async def my_handler(ctx, uow, data, _registry=None):
    safe_info(ctx, "starting work on %s items", len(items))
    for i, item in enumerate(items):
        await do_work(item)
        safe_report_progress(ctx, progress=i + 1, total=len(items))
    safe_info(ctx, "done")
```

`safe_info` / `safe_report_progress` молча fallback'ятся в stdlib `logging` когда `ctx is None` или сессия не активна. 5 handlers переведены в v1.3.7 (`track_import`, `track_features_{analyze,reanalyze}`, `audio_file_download`, `set_version_build`). Никогда не вызывай `ctx.info` напрямую из handler — пишем через wrapper.

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
