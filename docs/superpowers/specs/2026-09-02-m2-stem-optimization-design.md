# M2 Stem Separation Optimization Design

Date: 2026-09-02
Status: approved for implementation planning
Author: dj-music-plugin / superpowers brainstorming

## Goal

Сделать локальное разделение треков на стемы (vocals/drums/bass/harmonic/percussion) стабильным и быстрым на MacBook Air M2 8GB, без OOM и без блокировки MCP-лупа, сохранив качество, достаточное для DJ-рендера.

Текущий путь `app/audio/deep/demucs_runner.py` — PyTorch MPS `htdemucs` с `shifts=5`, `overlap=0.25`, `segment=10`, `-j 2` — на 8GB даёт 50-90s на 3-мин трек и риск `MPS OOM` (свободно 2.2GB из 8GB). Нужно: а) выбрать оптимальную модель/рантайм для Apple Silicon, б) не давать процессу сожрать память, в) вынести работу в async background.

## Исследованные доказательства

* **Demucs docs (context7 /facebookresearch/demucs):** `separator = Separator(model="htdemucs_ft", device="mps", shifts=1, overlap=0.25, split=True, segment=10, jobs=0)`, `update_parameter(segment=8, device="cpu")` для нехватки памяти. Для GPU нужно 3GB минимум, 7GB рекомендовано. `PYTORCH_NO_CUDA_MEMORY_CACHING=1` помогает на 2GB. Hybrid Transformer max segment 7.8s. `apply_model(model, mix, shifts, overlap, device, split)`.
* **Benchmarks (exa):** M4 MPS `htdemucs` RTF 0.20 (22s/3мин), `htdemucs_ft` RTF 0.49 (88s/3мин) — 4× дороже, bag из 4 специалистов по 316MB (1.26GB). `mdx_extra_q` 11.49 dB drums vs 10.11 у htdemucs_ft. `demucs-onnx`: CPU 1.31× быстрее PyTorch, GPU/CoreML 5-10× быстрее, паритет 1.6e-4, `fp16weights` 166MB vs 316MB. `demucs-mlx` (MLX-native): 34× realtime на M4 Max (3 мин →5.3s, 1 мин →1.8s), 11× быстрее PyTorch CPU, точность <1ppm, STFT через Torch.
* **Текущий проект:** `pyproject.toml:43` `stems = ["demucs>=4.0", "torch>=2.0"]`, `app/handlers/_orchestrator/stem_resolver.py` резолвит 5 стемов, `demucs_runner.py:19-35` уже имеет `DEMUCS_SHIFTS=5` и т.д., `PERCUSSION_SPLIT_HZ=2000`, кэш `sha256(path)[:12]`, `fastmcp[tasks]` уже в зависимостях.

## Non-Goals

* Не писать новый алгоритм разделения — только обвязка рантаймов.
* Не трогать Suno/YM провайдеры.
* Не требовать 16GB — должно работать на 8GB с чанкингом.

## Architecture

### 1. Three-tier runtime с авто-детектом

```
detect_runtime() -> "mlx" | "onnx-coreml" | "torch-mps"
  1. try import mlx + demucs_mlx → mlx         # 30× realtime, 80MB модель
  2. elif onnxruntime + CoreML EP available → onnx
  3. else torch.backends.mps.is_available() → torch-mps
  4. else cpu
```

Конфиг `app/config/stems.py` (новый):

```python
class StemsConfig:
    runtime: Literal["auto","mlx","onnx","torch"] = "auto"
    model: str = "htdemucs"  # htdemucs | htdemucs_ft | htdemucs_6s
    shifts: int = 1  # 1 для превью, 5 для финала — профиль, не константа
    overlap: float = 0.25
    segment: float = 7.8  # не 10, лимит HTDemucs
    jobs: int = 0  # 0 на 8GB, 2 только на 16GB+
    fp16: bool = True  # для onnx/mlx
```

Env: `DJ_STEMS_RUNTIME`, `DJ_STEMS_MODEL`, `DJ_STEMS_SHIFTS`, существующий `DJ_DEMUCS_MODEL` остаётся алиасом.

### 2. Адаптеры

`app/audio/deep/`:

* `demucs_runner.py` — остаётся torch-mps путь, но `segment` → 7.8, `jobs` → 0 на 8GB, добавить `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0` и `PYTORCH_NO_CUDA_MEMORY_CACHING=1` при `available < 3GB`.
* `demucs_mlx_runner.py` (новый) — `from demucs_mlx import separate` или `mlx_audio_separator`, `device="mps"`, chunk 7.8s, `shifts` эмулируется повторными прогонами (если нужно).
* `demucs_onnx_runner.py` (новый) — `onnxruntime.InferenceSession(..., providers=["CoreMLExecutionProvider","CPUExecutionProvider"])`, грузит `htdemucs_fp16weights.onnx` или 4 специалиста по требованию (vocals-only 22s vs 88s bag).

Все три реализуют `StemRunner Protocol { async def separate(input: Path, cache_root: Path) -> dict[str, Path] }`.

### 3. Async + FastMCP Tasks

Сейчас `stem_resolver._separate_stems` делает `await asyncio.to_thread(run_demucs, ...)` — блокирует воркера на минуты, без прогресса и отмены.

Новое:

* `app/tools/stems.py` → `stems_separate` как `@mcp.task` (FastMCP 3.x Tasks) — возвращает `task_id`, клиент поллит `get_task`.
* Внутри: `async with asyncio.Semaphore(1)` — на 8GB нельзя 2 трека параллельно.
* Прогресс: `ctx.report_progress(progress, total, message=f"demucs {stem} {pct}%")` из колбэка `apply_model(progress=True)` или по чанкам.
* Отмена: `task.cancel()` → `torch.mps.empty_cache()` + `ffmpeg` kill.
* Кэш: уже есть `sha256[:12] / model / stem.flac` — добавить `lru_cache` на загруженную модель (`@lru_cache(maxsize=1)`), чтобы не грузить 316MB каждый раз.

### 4. Память на 8GB

* Детект `psutil.virtual_memory().available` — если < 3GB → `segment=5`, `shifts=1`, `jobs=0`, `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0`.
* Чанкование: `split=True` всегда, `segment=7.8` (не 10) — лимит HTDemucs, экономит ~20% RAM.
* `fp16` для onnx/mlx — 166MB vs 316MB, same speed.
* После каждого трека `gc.collect(); torch.mps.empty_cache()` (уже есть в `_run_with_retry`).

### 5. Data Flow

```
MCP tool stems_separate(track_ids) -> FastMCP Task
  -> stem_resolver.resolve -> detect_runtime -> StemRunner.separate
  -> cache hit? -> return dict[str, Path] (vocals/drums/bass/harmonic/percussion)
  -> miss -> chunked inference (7.8s, overlap 0.25) -> harmonic=other copy, percussion=2000Hz split -> flac + manifest
  -> report_progress per chunk
```

### 6. Error Handling

* `FileNotFound` → fallback classic render (уже есть).
* `MPS OOM` → `update_parameter(segment=5, device="cpu")` и ретрай 1 раз.
* `onnx CoreML not available` → fallback torch.
* `mlx not installed` → fallback.

### 7. Testing & Verification

* Юнит: `test_demucs_runner` уже есть — расширить на `test_mlx_runner`, `test_onnx_runner` с моком.
* Бенч: `scripts/bench_stems_m2.py` — меряет на 2 реальных треках из `/tmp/dj_audio` (30s, 3мин) для 3 рантаймов, `rtf`, `peak RSS` (psutil), `SDR proxy` (уже есть stem_analyzer).
* Интеграция: `pytest -k stems -n 0` на M2 — все 3 рантайма должны дать 5 файлов `*.flac` и `diagnostics.json` без OOM.
* Ручная: `DJ_STEMS_RUNTIME=mlx uv run python -m demucs_mlx ...` → 3 мин <15s.

## Rollout

1. PR1: `StemsConfig` + `segment=7.8` + `jobs=0` на 8GB + `PYTORCH_MPS_HIGH_WATERMARK_RATIO`.
2. PR2: `demucs_onnx_runner` + CoreML, флаг `fp16`.
3. PR3: `demucs_mlx_runner` + детект.
4. PR4: `FastMCP task` для `stems_separate`, `Semaphore(1)`, прогресс.

## Risks

* MLX порт `htdemucs_6s` untested — не используем.
* onnxruntime CoreML требует `onnxruntime-silicon` — пин в `[stems]` extra.
* shifts=5 на MLX не нативен — эмулируем, может быть дороже.

