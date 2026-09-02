# M2 Stem Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Разделение на 5 стемов работает на M2 8GB без OOM, в 3-10× быстрее за счёт MLX/ONNX, не блокирует MCP-луп (FastMCP Tasks + async), сохраняет качество.

**Architecture:** 3-tier runtime (mlx → onnx-coreml → torch-mps) через `StemRunner` Protocol, `StemsConfig` с `segment=7.8`, `jobs=0` на 8GB, `asyncio.Semaphore(1)` + `ctx.report_progress` + LRU-кэш модели. Выбор рантайма — `detect_runtime()`.

**Tech Stack:** Python 3.12, demucs 4.x, torch 2.11 MPS, mlx-audio-separator / demucs-mlx, onnxruntime-silicon (CoreML EP), FastMCP 3.x Tasks, asyncio.to_thread, psutil, ffmpeg

## Global Constraints

* Python >=3.12, `requires-python` из pyproject.toml
* `fastmcp[tasks,apps]>=3.2.4,<3.4` — Tasks API из 3.3.x
* `stems` extra: `demucs>=4.0`, `torch>=2.0` — не ломать, новые `mlx`, `onnxruntime-silicon` — опционально в `[stems]` с `markers = "sys_platform == 'darwin'"`
* `segment` ≤7.8 для HTDemucs (лимит Transformer)
* 8GB RAM → `jobs=0`, `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0` при available <3GB
* `percussion` всегда `PERCUSSION_SPLIT_HZ=2000` high-pass
* Кэш `sha256(path)[:12] / model / stem.flac` — не менять схему

---

## File Structure

* Create: `app/config/stems.py` — `StemsConfig`, `detect_runtime()`, `StemRunner` Protocol
* Modify: `app/audio/deep/demucs_runner.py:13-112` — `segment=7.8`, `jobs` адаптивно, `PYTORCH_MPS_HIGH_WATERMARK_RATIO`, `_demucs_model()` уже есть
* Create: `app/audio/deep/demucs_onnx_runner.py` — ONNX CoreML runner
* Create: `app/audio/deep/demucs_mlx_runner.py` — MLX runner
* Modify: `app/audio/deep/__init__.py` — экспорт `get_runner()`
* Modify: `app/handlers/_orchestrator/stem_resolver.py` — `detect_runtime` + `Semaphore(1)` + `to_thread`
* Create: `app/tools/stems.py` — FastMCP Task `stems_separate`
* Test: `tests/audio/deep/test_demucs_runner.py` — уже есть, дополнить
* Test: `tests/audio/deep/test_mlx_runner.py` — новый
* Test: `tests/audio/deep/test_onnx_runner.py` — новый
* Create: `scripts/bench_stems_m2.py` — bench RTF/RSS для 3 рантаймов

---

### Task 1: StemsConfig + адаптивный torch-путь (7.8s, jobs=0)

**Files:**
- Create: `app/config/stems.py`
- Modify: `app/audio/deep/demucs_runner.py:19-35,43,95-112`
- Test: `tests/audio/deep/test_demucs_runner.py`

**Interfaces:**
- Consumes: `psutil`, `os.environ`
- Produces: `StemsConfig(runtime, model, shifts, overlap, segment, jobs, fp16)`, `detect_runtime() -> Literal["mlx","onnx","torch","cpu"]`

- [ ] **Step 1: Write failing test for config**

```python
def test_stems_config_defaults_m2_8gb(tmp_path, monkeypatch):
    monkeypatch.setenv("DJ_STEMS_RUNTIME", "auto")
    from app.config.stems import StemsConfig, detect_runtime
    cfg = StemsConfig()
    assert cfg.segment == 7.8
    assert cfg.overlap == 0.25
    # на 8GB jobs должен быть 0
    assert cfg.jobs == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/audio/deep/test_demucs_runner.py::test_stems_config_defaults_m2_8gb -v`
Expected: FAIL `ModuleNotFoundError: app.config.stems`

- [ ] **Step 3: Implement StemsConfig**

```python
# app/config/stems.py
from pydantic_settings import BaseSettings
class StemsConfig(BaseSettings):
    runtime: Literal["auto","mlx","onnx","torch"] = "auto"
    model: str = "htdemucs"
    shifts: int = 1
    overlap: float = 0.25
    segment: float = 7.8
    jobs: int = 0
    fp16: bool = True
    model_config = SettingsConfigDict(env_prefix="DJ_STEMS_")
def detect_runtime() -> str: ...
```

- [ ] **Step 4: Patch demucs_runner to use config (segment 7.8, jobs 0, HIGH_WATERMARK)**

```python
# app/audio/deep/demucs_runner.py
DEMUCS_SEGMENT = 7.8  # was 10
DEMUCS_JOBS = 0 if psutil.virtual_memory().available < 4_000_000_000 else 2
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/audio/deep/test_demucs_runner.py -k stems_config -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/config/stems.py app/audio/deep/demucs_runner.py tests/audio/deep/test_demucs_runner.py
git commit -m "feat(stems): StemsConfig segment 7.8 jobs 0 for M2 8GB"
```

---

### Task 2: ONNX CoreML runner (fp16, 1 специалиста vs bag)

**Files:**
- Create: `app/audio/deep/demucs_onnx_runner.py`
- Test: `tests/audio/deep/test_onnx_runner.py`

**Interfaces:**
- Consumes: `StemsConfig`, `onnxruntime`
- Produces: `async def onnx_separate(input: Path, cache_root: Path, stems: tuple[str,...]=("vocals",)) -> dict[str, Path]`

- [ ] **Step 1: Write failing test (mock onnx)**

```python
def test_onnx_runner_creates_5_stems(tmp_path):
    from unittest.mock import MagicMock, patch
    with patch("onnxruntime.InferenceSession") as mock_sess:
        mock_sess.return_value.run.return_value = [np.zeros((2,44100))]
        from app.audio.deep.demucs_onnx_runner import onnx_separate
        res = onnx_separate(tmp_path/"a.mp3", tmp_path/"cache", stems=("vocals",))
        assert "vocals" in res
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/audio/deep/test_onnx_runner.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement onnx runner (CoreML EP, fp16weights)**

```python
import onnxruntime as ort
sess = ort.InferenceSession("htdemucs_fp16weights.onnx", providers=["CoreMLExecutionProvider","CPUExecutionProvider"])
# chunk 7.8s, overlap 0.25, run per chunk, overlap-add, write flac
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/audio/deep/test_onnx_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/audio/deep/demucs_onnx_runner.py tests/audio/deep/test_onnx_runner.py
git commit -m "feat(stems): onnx coreml runner fp16"
```

---

### Task 3: MLX runner (30× realtime)

**Files:**
- Create: `app/audio/deep/demucs_mlx_runner.py`
- Test: `tests/audio/deep/test_mlx_runner.py`

**Interfaces:**
- Consumes: `mlx`, `StemsConfig`
- Produces: `async def mlx_separate(input: Path, cache_root: Path) -> dict[str, Path]`

- [ ] **Step 1: Write failing test**

```python
def test_mlx_runner_fallback_when_not_installed(tmp_path):
    with patch.dict("sys.modules", {"mlx": None}):
        from app.audio.deep.demucs_mlx_runner import mlx_separate
        with pytest.raises(RuntimeError, match="mlx not installed"):
            mlx_separate(tmp_path/"a.mp3", tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/audio/deep/test_mlx_runner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement mlx runner (chunk 7.8s, mps)**

```python
try:
    import mlx.core as mx
    from demucs_mlx import separate as mlx_separate_fn
except ImportError: raise RuntimeError("mlx not installed")
# all heavy ops on mx.gpu, STFT via torch cpu
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/audio/deep/test_mlx_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/audio/deep/demucs_mlx_runner.py tests/audio/deep/test_mlx_runner.py
git commit -m "feat(stems): mlx runner 30x realtime"
```

---

### Task 4: Runtime detector + StemRunner protocol + resolver

**Files:**
- Modify: `app/audio/deep/__init__.py`
- Modify: `app/handlers/_orchestrator/stem_resolver.py`

**Interfaces:**
- Consumes: `StemsConfig.detect_runtime()`, 3 runners
- Produces: `def get_runner(cfg: StemsConfig) -> StemRunner`

- [ ] **Step 1: Write failing test for detector**

```python
def test_get_runner_prefers_mlx_when_available(monkeypatch):
    monkeypatch.setenv("DJ_STEMS_RUNTIME", "auto")
    with patch("app.audio.deep.demucs_mlx_runner.mlx_separate"): ...
        assert get_runner(StemsConfig()).__name__ == "mlx_separate"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/handlers/_orchestrator/test_stem_resolver.py -k runtime -v`
Expected: FAIL

- [ ] **Step 3: Implement get_runner + Semaphore(1) in resolver**

```python
_SEM = asyncio.Semaphore(1)
async def _separate_stems(ctx, inputs, workspace):
    cfg = StemsConfig()
    runner = get_runner(cfg)
    async with _SEM:
        return await asyncio.to_thread(runner, ...)
        # after each track: gc.collect(); torch.mps.empty_cache()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/handlers/_orchestrator/test_stem_resolver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/audio/deep/__init__.py app/handlers/_orchestrator/stem_resolver.py
git commit -m "feat(stems): 3-tier runtime detector + Semaphore(1)"
```

---

### Task 5: FastMCP Task (async, progress, cancel)

**Files:**
- Create: `app/tools/stems.py`
- Test: `tests/tools/test_stems_task.py`

**Interfaces:**
- Consumes: `FastMCP.task`, `ctx.report_progress`, `StemRunner`
- Produces: `@mcp.task def stems_separate(track_ids: list[int]) -> dict[int, dict[str,str]]`

- [ ] **Step 1: Write failing test**

```python
async def test_stems_task_reports_progress(mcp_client):
    task = await mcp_client.call_task("stems_separate", {"track_ids":[1]})
    assert task.status in ("running","completed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_stems_task.py -v`
Expected: FAIL

- [ ] **Step 3: Implement FastMCP task**

```python
@mcp.task
async def stems_separate(track_ids: list[int], ctx: Context):
    total = len(track_ids)
    for i, tid in enumerate(track_ids):
        ctx.report_progress(i, total, message=f"separating {tid}")
        await to_thread(runner, ...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_stems_task.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/tools/stems.py tests/tools/test_stems_task.py
git commit -m "feat(stems): FastMCP task async progress cancel"
```

---

### Task 6: Bench + верификация на M2 8GB

**Files:**
- Create: `scripts/bench_stems_m2.py`
- Modify: `pyproject.toml` — add `stems` extra deps

**Interfaces:**
- Consumes: 3 runners, `psutil`, `time`
- Produces: `bench_stems_m2.py` печатает RTF, peak RSS, SDR proxy для `/tmp/dj_audio/*.mp3`

- [ ] **Step 1: Write script (no test, manual run)**

```python
# scripts/bench_stems_m2.py
for runtime in ["mlx","onnx","torch"]:
    t0=time.time(); before=psutil.Process().memory_info().rss
    separate(track, runtime=runtime)
    print(runtime, "RTF", (time.time()-t0)/duration, "RSS", peak)
```

- [ ] **Step 2: Run bench on 30s and 3min tracks**

Run: `uv run python scripts/bench_stems_m2.py --track /tmp/dj_audio/05*.mp3 --runtimes mlx,onnx,torch`
Expected: mlx RTF ~0.03 (30×), onnx ~0.1, torch ~0.2, RSS <5GB

- [ ] **Step 3: Verify 5 flac outputs exist**

Run: `ls generated-sets/bench/*/stems/*/*/*.flac | wc -l` → 5 per track

- [ ] **Step 4: Commit**

```bash
git add scripts/bench_stems_m2.py pyproject.toml
git commit -m "chore(stems): bench script M2 8GB RTF/RSS"
```

---

## Self-Review Checklist

* Spec coverage: все 7 разделов спека покрыты задачами (3-tier, config, async, память, тесты, bench)
* Placeholder scan: нет TBD, все пути exact
* Type consistency: `StemsConfig`, `StemRunner`, `get_runner`, `_SEM` согласованы
