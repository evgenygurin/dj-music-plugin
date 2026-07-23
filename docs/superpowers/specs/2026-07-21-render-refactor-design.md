# Render subsystem refactor (mixdown + beatgrid)

> Дата: 2026-07-21
> Scope: `render_mixdown` + `render_beatgrid` pipelines (mixdown + beatgrid).
> Diagnose (`render_diagnose`), auxiliary MCP builders (`echo_builder`,
> `filter_sweep_builder`, `reverb_builder`, `auto_fix`, `energy_arc_plan`,
> `subgenre_preset`) и весь `app/domain/multi_deck/*` / `app/tools/multi_deck/*`
> **вне scope** — у них отдельный контекст.

## Мотивация

Код рендера сета (~3650 строк) накопил DRY/SRP боли, мёртвый код и слойные
нарушения. Поджанровые фичи и будущие render-режимы требуют расширяемости
через явные seams. Внешний MCP-surface (`@tool`-декораторы, сигнатуры,
описания, теги) **не меняется**. Внутренние интерфейсы свободно
реорганизуются.

Подход: **A** (сбалансированный) —对患者 fix'ит все найденные боли, вводит
`RenderMode` enum + `RenderRequest` Parameter Object как seams для будущих
режимов, без спекулятивных абстракций (Stage pipeline, sum-type RenderPlan).

## Pain points (findings)

- **Dead code (~850 строк)**: `app/domain/render/twelve_deck.py` (466),
  `app/domain/render/multi_deck.py` (178), `app/domain/render/stem_matrix.py`
  (206). Ноль импортов в `app/`/`tests/`. `twelve_deck.py` содержит баги
  (`rubberband=tempo=1.0` всегда, кривая формула `pan`, двойное
  присваивание `track_stems = TrackStems(...)`), `stem_matrix.py` плодит
  собственный `STEM_TYPES` в порядке, рассинхронизированном с
  `models.STEM_ORDER`.
- **DRY**: `RenderPlanBuilder.build_classic` / `build_stem`
  (`plan_builder.py:12-92`) — pass-through к `build_render_plan` /
  `build_stem_render_plan` (`timeline.py:114-258`), которые сами на ~80%
  дублируют 17 kwargs.
- **Long method**: `ClassicGraphBuilder._segment_block`
  (`filtergraph.py:87-212`, ~125 строк). Late-импорты
  `from app.audio.effects.echo_delay import ...` внутри метода + дублирующий
  `from app.audio.effects.filter_sweep import ...`.
- **Layer violation**: `app/audio/render/runner.py` импортирует
  `app.domain.render.filtergraph` (audio → domain). Runner не использует
  librosa/scipy — это доменная command-assembly, не DSP.
- **Fragile dispatch**: `select_strategy(plan)` смотрит
  `plan.stem_segments is not None`; у `RenderPlan` нет явного поля `mode`.
- **Handler-SRP**: `render_mixdown_handler` (169 строк, 16 параметров)
  смешивает subgenre preset, beatgrid-cache, stem-resolve, bar-plan,
  plan-build, job-tracking, run, scan. Pass-through 14 параметров через 3
  слоя (tool → handler → builder → timeline).
- **Magic numbers**: `_MAX_PHASE_MS=120.0`, `_MAX_TRIM_START_S=8.0` в
  `render_beatgrid.py`; `_LP_HZ=150`, `_SR=22050` дублируются в
  `kick_phase.py` / `phase_refine.py` / `diagnostics.py`.
- **Beatgrid JSON schema duplicated**: writer'а (`render_beatgrid_handler`)
  и reader'а (`render_mixdown_handler._load_grid`) оба хардкодят форму
  `{"track_id","trim_start_s","refined_trim_s","gain_db","phase_ms","flags"}`.
- **BarPlanner**: возвращает кортеж `(per_transition, per_body)`; два
  прохода по `inputs`, дублирует `classify_pair` на каждой паре.
- **Stem voicing**: `_STEM_HPF_HZ` (filtergraph.py:35-41) — single source
  для bleed-masking HPF + gain staging растаскан по двум staticmethods
  `_stem_trim_gain_db` и `_stem_chain` c magic числами -7/-3/-2/0.
- `build_preprocess_cmd` (`runner.py:15`) не используется в production,
  только в тесте — мёртвый утилит.

## Целевая структура

```
app/
  config/render.py                  RenderSettings (без_dup per-subgenre полей не трогаю)
  domain/render/
    __init__.py                     обновлённый exports
    models.py                       +RenderMode enum, RenderPlan carries mode
    request.py                      NEW: RenderRequest (Parameter Object)
    bar_plan.py                      NEW: BarPlan dataclass + BarPlanner (из bar_planner.py)
    beatgrid.py                      NEW: BeatgridEntry.clamp()/flags()/to_row/from_row, BeatgridLimits
    segments.py                      NEW: SegmentFactory Protocol + Classic/Stem factories
    plan_assembler.py                NEW: RenderPlanner (замена plan_builder.py + build_*_render_plan)
    timeline.py                      place_segments + timeline_windows (упрощён, без build_*_render_plan)
    filtergraph.py                   разложен на меньшие методы + использует STEM_VOICING + ResolvedEffects
    stem_voicing.py                  NEW: единственный источник stem HPF/gain staging
    effects_resolver.py              NEW: EffectPresetResolver + ResolvedEffects value object
    runner.py                        MOVED из app/audio/render (фикс слойности)
    graph.py / stem_graph.py         facades — back-compat (тесты используют)
  audio/render/
    kick_phase.py                    DSP (чистый, no app.domain)
    phase_refine.py                  DSP
    diagnostics.py                   scan_mix + diagnose_mix (out-of-scope логически, рядом)
  handlers/
    render_mixdown.py                ТОНКИЙ (~10 строк): → RenderOrchestrator
    render_beatgrid.py               ТОНКИЙ: → BeatgridProvider.compute
    _orchestrator/
      render_orchestrator.py         RenderOrchestrator: prepare → plan → render → scan
      beatgrid_provider.py           ensure + compute + load (заменяет _load_grid + часть handler'a)
      preset_applier.py              SubgenrePresetApplier
      stem_resolver.py               MOVED из _stem_resolver.py
      render_executor.py             RenderExecutor: RENDER_JOBS + run_render + scan_mix
    render_diagnose.py               (out-of-scope)
  schemas/render.py                  НЕ трогать — MCP surface
  shared/render_jobs.py, render_workspace.py — без изменений
  tools/render/*                     НЕ трогаю @tool-декораторы (MCP surface preserved)
```

Удаляю:
- `app/domain/render/twelve_deck.py`
- `app/domain/render/multi_deck.py`
- `app/domain/render/stem_matrix.py`
- `app/domain/render/plan_builder.py`
- `app/domain/render/bar_planner.py` (→ `bar_plan.py`)
- `app/handlers/_stem_resolver.py` (→ `_orchestrator/stem_resolver.py`)
- `app/audio/render/runner.py` (→ `app/domain/render/runner.py`)
- `build_preprocess_cmd` + `tests/audio/render/test_runner.py::test_build_preprocess_cmd`

## Core data types

### `RenderMode` enum

```python
class RenderMode(str, Enum):
    CLASSIC = "classic"   # single-file 3-band EQ bass-swap
    STEM    = "stem"       # 5 prepared stems multi-deck
```

### `RenderRequest` (Parameter Object)

```python
@dataclass(frozen=True, slots=True)
class RenderRequest:
    version_id: int
    workspace: str
    timestamp: str
    out_name: str | None = None
    transition_bars: int | None = None
    body_bars: int | None = None
    refresh_grid: bool = False
    stem: bool = True
    subgenre: str | None = None
    filter_sweep: str | None = None
    echo: str | None = None
    crossfade_curve_out: str = "tri"
    crossfade_curve_in: str = "exp"
    reverb: str | None = None
    reverb_mix: float = 0.25

    @property
    def mode(self) -> RenderMode:
        return RenderMode.STEM if self.stem else RenderMode.CLASSIC

    @property
    def out_filename(self) -> str:
        return self.out_name or get_settings().render.mix_filename
```

### `BarPlan`

```python
@dataclass(frozen=True, slots=True)
class BarPlan:
    transition_bars: tuple[int, ...]   # length n-1
    body_bars: list[int]                # length n
    def __len__(self) -> int: return len(self.body_bars)
    def transition_for(self, i: int) -> int: return self.transition_bars[i]
    def body_for(self, i: int) -> int: return self.body_bars[i]
```

`BarPlanner.compute` делает один проход по `inputs`, кэшируя
`classify_pair` для каждой пары, возвращает `BarPlan`.

### `BeatgridEntry` (методы + `BeatgridLimits`)

```python
@dataclass(frozen=True, slots=True)
class BeatgridLimits:
    max_phase_ms: float = 120.0
    max_trim_start_s: float = 8.0
    fixed_flag_threshold_ms: float = 40.0
    fixed_flag_gain_db: float = 1.5

    @classmethod
    def from_settings(cls, s: RenderSettings) -> "BeatgridLimits": ...

# к существующему BeatgridEntry добавляю:
def clamp(self, limits: BeatgridLimits) -> BeatgridEntry
def flags(self, limits: BeatgridLimits) -> list[str]   # ["fixed"] or []
def to_row(self) -> dict[str, Any]
@classmethod
def from_row(cls, row: Mapping[str, Any]) -> BeatgridEntry
```

`BeatgridIO`:
`read(workspace) -> list[BeatgridEntry]`, `write(workspace, rows)` —
единственное место `json.loads`/`json.dumps` для `beatgrid.json`;
ссылается на `to_row`/`from_row`. `BeatgridProvider.load workspace)`
оборачивает `BeatgridIO.read` в `dict[int, BeatgridEntry]` (для
orchestrator'a нужны треки по id).

### `RenderPlan` — добавляет `mode`, упрощает `from_settings`

```python
@dataclass(frozen=True, slots=True)
class RenderPlan:
    mode: RenderMode
    # ... rest unchanged
    @classmethod
    def from_settings(cls, settings, request, *, segments, stem_segments=None) -> RenderPlan:
        """Single source settings→plan mapping. Effects/presets из RenderRequest."""
```

`timeline.build_render_plan` / `build_stem_render_plan` — удаляются
(поглощаются `RenderPlanner.assemble`). `place_segments` остаётся как
чистая функция плейсинга (используется и `timeline_windows`).

## RenderPlanner (замена RenderPlanBuilder + build_*_render_plan)

```python
class RenderPlanner:
    _FACTORIES: dict[RenderMode, SegmentFactory] = {
        RenderMode.CLASSIC: ClassicSegmentFactory(),
        RenderMode.STEM:    StemSegmentFactory(),
    }

    def assemble(self, settings, request, inputs, grid, bar_plan, stem_paths) -> RenderPlan:
        factory = self._FACTORIES[request.mode]
        geometries = place_segments(
            inputs, grid,
            target_bpm=settings.target_bpm,
            body_bars=bar_plan.body_bars,
            transition_bars=request.transition_bars or settings.transition_bars,
            per_transition_bars=bar_plan.transition_bars,
            per_body_bars=bar_plan.body_bars,
        )
        segments = factory.build_segments(geometries, inputs, stem_paths, settings, request)
        return RenderPlan.from_settings(
            settings, request,
            segments      = segments if request.mode is RenderMode.CLASSIC else [],
            stem_segments = segments if request.mode is RenderMode.STEM    else None,
        )
```

```python
# app/domain/render/segments.py
class SegmentFactory(Protocol):
    def build_segments(self, geometries, inputs, stem_paths, settings, request) -> list: ...

class ClassicSegmentFactory:
    def build_segments(...) -> list[TrackSegment]: ...

class StemSegmentFactory:
    def build_segments(...) -> list[StemSegment]: ...
```

## Handler decomposition (RenderOrchestrator)

```python
# app/handlers/render_mixdown.py — теперь ~10 строк
async def render_mixdown_handler(*, ctx, uow, version_id, workspace, timestamp, **render_kwargs) -> RenderMixdownResult:
    request = RenderRequest(version_id=version_id, workspace=workspace, timestamp=timestamp, **render_kwargs)
    return await RenderOrchestrator(uow).run(ctx, request)

# app/handlers/_orchestrator/render_orchestrator.py
class RenderOrchestrator:
    def __init__(self, uow, *, preset_applier=None, beatgrid_provider=None,
                 stem_resolver=None, planner=None, executor=None):
        # all defaults None → use production impls
        ...
    async def run(self, ctx, request: RenderRequest) -> RenderMixdownResult:
        settings = get_settings().render
        self._preset.apply(settings, ctx, request.subgenre)
        await self._beatgrid.ensure(ctx, request, self._uow)
        inputs = await self._uow.set_versions.get_render_inputs(request.version_id)
        grid = self._beatgrid.load(request.workspace)
        bar_plan = BarPlanner(settings).compute(inputs, grid,
            transition_override=request.transition_bars,
            body_override=request.body_bars)
        stem_paths = await self._stems.resolve(ctx, self._uow, inputs) \
            if request.mode is RenderMode.STEM else None
        plan = self._planner.assemble(settings, request, inputs, grid, bar_plan, stem_paths)
        return await self._executor.execute(ctx, request, plan)
```

Collaborators (injectable in `__init__`, mock-friendly):
- `SubgenrePresetApplier.apply(settings, ctx, subgenre)`.
- `BeatgridProvider`: `ensure(request, uow)` (mkdir/cache-check/invoke
  `render_beatgrid_handler` if missing) + `load(workspace)` +
  `compute(ctx, uow, version_id, workspace, *, refresh)`.
- `StemResolver` — переезжает из `app/handlers/_stem_resolver.py` без
  изменений в API.
- `RenderPlanner.assemble` — см. выше.
- `RenderExecutor.execute(ctx, request, plan)` — `RENDER_JOBS.start` →
  `run_render` → `scan_mix` → построение `RenderMixdownResult`.

`render_beatgrid_handler` аналогично истончается:

```python
async def render_beatgrid_handler(*, ctx, uow, version_id, workspace, refresh=False) -> RenderBeatgridResult:
    return await BeatgridProvider().compute(ctx, uow, version_id, workspace, refresh=refresh)
```

## Filtergraph / Effects / Stem voxing / Runner

### ClassicGraphBuilder `_segment_block` decomposition

```python
@dataclass(frozen=True, slots=True)
class _FrameContext:
    plan: RenderPlan; i: int; seg: TrackSegment
    length: float; bar_s: float; beat_s: float; low_x: float
    p1: float; p2: float; has_prev: bool; has_next: bool
    curve_out: str; curve_in: str; n: int
    @classmethod
    def from_segment(cls, plan, i, seg) -> _FrameContext: ...

class ClassicGraphBuilder(FilterGraphBuilder):
    def _segment_block(self, plan, i, seg) -> tuple[list[str], str]:
        ctx = _FrameContext.from_segment(plan, i, seg)
        effects = self._effects.resolve(plan)        # injected EffectPresetResolver
        parts: list[str] = [
            self._source_chain(ctx),
            *self._echo_split(ctx, effects.echo),
            *self._band_split(ctx),
            self._fade_high(ctx),
            self._fade_mid(ctx),
            self._fade_low(ctx),
            self._mix_segment(ctx, effects.echo),
        ]
        return parts, f"[m{i}]"
```

Каждый helper-метод 5-15 строк, без late-импортов.

### EffectPresetResolver

```python
@dataclass(frozen=True, slots=True)
class ResolvedEffects:
    echo: EchoPreset | None = None
    sweep: FilterSweepPreset | None = None

class EffectPresetResolver:
    def resolve(self, plan: RenderPlan) -> ResolvedEffects: ...
```

`EchoPreset`/`FilterSweepPreset` — value-objects из существующих
`ECHO_PRESETS`/`FILTER_PRESETS` модулей (без late импорта в filtergraph).

### Stem voicing single source

```python
# app/domain/render/stem_voicing.py
@dataclass(frozen=True, slots=True)
class StemVoicing:
    hpf_hz: int | None
    gain_db: float

STEM_VOICING: dict[str, StemVoicing] = {
    "drums":        StemVoicing(hpf_hz=None, gain_db=0.0),
    "bass":         StemVoicing(hpf_hz=None, gain_db=0.0),
    "harmonic":     StemVoicing(hpf_hz=80,   gain_db=-2.0),
    "instrumental": StemVoicing(hpf_hz=120,  gain_db=-7.0),
    "acappella":    StemVoicing(hpf_hz=120,  gain_db=-3.0),
}
```

`StemGraphBuilder._stem_chain` / `_stem_trim_gain_db` / `_STEM_HPF_HZ`
берут значения из `STEM_VOICING[stem]`.

### Runner relocation + `select_strategy`

`runner.py` переезжает `app/audio/render/` → `app/domain/render/`.
Слойная инверсия исчезает: `app/audio/render/*` больше не зависит от
`app.domain`.

```python
def select_strategy(plan: RenderPlan) -> RenderStrategy:
    return _STRATEGIES[plan.mode]   # dict keyed by enum
```

`ClassicEqStrategy` / `StemMultiDeckStrategy` остаются (Strategy + Template
Method паттерны подтверждены).

`build_preprocess_cmd` + его тест удаляются (мёртвый утилит, без
потребителей > 14 строк + 13 строк теста).

## Migration impact

- `app/domain/render/__init__.py` exports: `RenderPlanBuilder` →
  `RenderPlanner`; `build_render_plan`/`build_stem_render_plan` удаляются;
  добавляются `RenderMode`, `RenderRequest`, `BarPlan`, `BeatgridLimits`,
  `StemVoicing`, `STEM_VOICING`, `ResolvedEffects`, `EffectPresetResolver`.
- `app/audio/render/__init__.py` (если есть) — убрать экспорт `runner`;
  оставить `kick_phase`, `phase_refine`, `diagnostics`.
- Импорты:
  - `from app.audio.render.runner import run_render` →
    `from app.domain.render.runner import run_render`.
  - `from app.handlers._stem_resolver import StemResolver` →
    `from app.handlers._orchestrator.stem_resolver import StemResolver`.
- back-compat alias: оставляю один шим
  `RenderPlanBuilder = RenderPlanner`? — нет; тесты переписаны целиком
  (по явному решению в секции 4).

## Тесты

Существующие ~1337 строк render-тестов:
- `tests/domain/render/test_timeline.py` — 3 теста `build_render_plan(...)`
  переписать на `RenderPlanner.assemble(...)` через `RenderRequest` +
  `RenderSettings`.
- `tests/domain/render/test_stem_graph.py` — без изменений
  (`build_stem_filtergraph` facade сохранён).
- `tests/domain/render/test_graph.py` — без изменений.
- `tests/domain/render/test_models.py` — добавить
  `test_render_plan_carries_mode`;`from_settings` API другой — правлю
  ~1 тест.
- `tests/handlers/test_render_mixdown.py` (422 строки) — patch'ит
  `render_beatgrid_handler`, `run_render`, `scan_mix`, `resolve_preset`
  по тем же коллабораторам; API handler'a идентичен. Минимально добавляю
  `test_orchestrator_invokes_each_collaborator` (mock-assertion порядка
  шагов) и `test_render_request_mode_stem_vs_classic`.
- `tests/handlers/test_render_beatgrid.py` (98 строк) — patch
  `detect_kick_trim`/`refine_phase` тот же. API handler'a не поменялось.
- `tests/audio/render/test_runner.py` (59) — путь импорта `build_ffmpeg_cmd`
  /`run_render`: `app.audio.render.runner` → `app.domain.render.runner`;
  `test_build_preprocess_cmd` удаляется.
- `tests/audio/render/test_kick_phase.py`, `test_phase_refine.py`,
  `test_diagnostics.py`, `test_bass_swap.py`, `test_eq_ritual.py` — без
  изменений (DSP чистый, не тронут).

Новые:
- `tests/domain/render/test_request.py` — `mode`, `out_filename`, frozen.
- `tests/domain/render/test_bar_plan.py` — tuple/list, `transition_for` /
  `body_for`.
- `tests/domain/render/test_plan_assembler.py` — режим-диспечer; сегменты
  верного типа; `RenderMode.CLASSIC` без `stem_paths` ≠ ошибка.
- `tests/domain/render/test_stem_voicing.py` — single source assertions.
- `tests/domain/render/test_effects_resolver.py` — `ResolvedEffects` для
  preset'ов.
- `tests/handlers/_orchestrator/test_render_orchestrator.py` — DI тесты,
  порядок шагов.

## Verification

- `make check` после каждого значимого stage'а (ruff + mypy strict +
  pytest + import-linter).
- Per-step `gitnexus impact({target, direction:"upstream"})` перед правкой
  любого публичного символа: `RenderPlanBuilder`, `build_render_plan`,
  `build_stem_render_plan`, `RenderPlan.from_settings`, `select_strategy`,
  `run_render`, `render_mixdown_handler`, `render_beatgrid_handler`,
  `_stem_resolver.StemResolver`.
- Per-commit `gitnexus detect_changes` финально (compare `main`).
- import-linter assertion: `app.audio.render` не импортирует
  `app.domain` (новый проверяемый инвариант после relocation).

## Non-goals (YAGNI)

- Stage pipeline (Chain of Responsibility) — нет необходимости, текущих
  шагов orchestrator'а хватает.
- Sum-type `RenderPlan = ClassicPlan | StemPlan` — режимы разделяют
  95% полей, discriminated union усложнит consumers.
- Plugin registry режимов — хватит dict `RenderMode → SegmentFactory`.
- Refactoring `RenderSettings` duplicated per-subgenre полей — отдельный
  scope (трогает `BarPlanner._config_bar_override` и subgenre-rules).
- Diagnose subsystem (`diagnose_mix`, `auto_fix`) — вне scope.
- Multi-deck/12-deck domain (`app/domain/multi_deck/*`) — отдельный
  контекст, не трогаю.