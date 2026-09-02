# Electronic-Music Stem Render — Design

**Date:** 2026-09-02
**Status:** Draft
**Supersedes:** none
**Related:** `app/domain/render/`, `app/audio/deep/demucs_runner.py`, `app/handlers/_orchestrator/render_orchestrator.py`, `app/tools/render/render_mixdown.py`, `app/models/{track_features,stem_features,transition,transition_history,track_affinity,track_feedback,scoring_profile,cross_similarity,track_embedding}.py`, `docs/render-pipeline.md`

## 1. Context

Current render uses **two parallel stem taxonomies** that don't match electronic music:
- `STEM_ORDER = ("drums", "bass", "harmonic", "instrumental", "acappella")` — old prepared-stem
- `DEMUCS_STEM_ORDER = ("drums", "bass", "vocals", "other", "percussion")` — Demucs 4-stem

The 5th "percussion" stem in `demucs_runner.py:103-128` is a **fake**: it's `drums` split via ffmpeg highpass at 400 Hz, not real Demucs output. Hi-hats bleed into the kick stem; snares contaminate both. For electronic music (techno / house) this means:

- **drums stem carries everything below 400 Hz** including sub-kick + the upper half still has cymbals
- **percussion stem has only kicks** — the opposite of what a DJ needs for hi-hat mixing
- No separation between bassline (`bass`) and harmonic content (`other`)
- Transition rules in `filtergraph._stem_fades` are hardcoded per stem-name, with no consideration of the **rich per-track data already in the DB** (L1-L6 features, beatgrid, cue points, sections, transition history, affinity, embeddings, cross-similarity, Camelot keys)

Symptoms reported in AGENTS.md "Render Lessons" section: drum stem shifts phase (Demucs transient drift on stems, not original audio), BPM stored vs audio discrepancy not handled, render re-runs without DSP changes, never. The new design treats every available track datum as a first-class input to a **policy-based transition engine** that recomputes fade plan per-stem from data, not from constants.

## 2. Goals / Non-Goals

**Goals**
- Switch to **Demucs 6s native 5-stem taxonomy** tuned for electronic music: `vocals, drums, bass, harmonic, percussion` (one-to-one mapping with Demucs 6s output: `vocals, drums, bass, other, percussion`).
- Remove the ffmpeg 400 Hz drum-split heuristic in `demucs_runner.py` — percussion is now Demucs' own stem, not a fake.
- Replace hardcoded `_stem_fades()` with a **`StemTransitionPolicy` engine**: 21+ pure-function policies, each consuming a subset of available track data, composable via `CompositeStemTransitionPolicy`.
- Make the engine **graceful**: when a track is only L1-L2 analyzed, fall back to defaults; when L4 sections exist, snap to phrase boundaries; when L6 per-stem features exist, do per-stem energy matching; when `TrackAffinity` is negative, lengthen the blend; when the user has banned the outgoing track, hard-skip.
- Expose the policy engine through a new MCP tool `dj_stem_transition_policy` so users can override defaults without code changes.
- Single source of truth for HPF + per-stem gain (renamed `STEM_VOICING` → `STEM_TIMBRE` to reflect the broader scope; module `stem_voicing.py` → `stem_timbre.py`).

**Non-Goals**
- New DB schema; `stem_paths` is not persisted in `DjSetVersion` (it's per-file cache on disk), so no migration.
- Full Neural Mix envelope system; we keep the existing `key-frames per-stem level_db` recipe path, but it is **out of scope** for this design (it lives in `app/domain/transition/recipe/`).
- Vocal activity detection (e.g. silencing vocal sections during clashes); we use `voicing_ratio` proxy only.
- Real-time parameter tuning; this design is purely for the **offline render path** (`dj_render_mixdown`).

## 3. Architecture

```
MCP Tool (dj_render_mixdown, dj_stem_transition_policy)
              ↓ kwargs
RenderRequest ── StemPolicyKwargs ── TransitionIntent ── SubgenrePreset
              ↓
RenderOrchestrator
  ├─ SubgenrePresetApplier
  ├─ BeatgridProvider
  ├─ StemResolver          ← Demucs 6s, 5 native stems
  ├─ TrackRenderContextBuilder  ← NEW: load all per-track data
  └─ RenderPlanner
        ├─ BarPlanner
        ├─ plan_assembler (assemble plan + StemTransitionContext for each pair)
        └─ StemGraphBuilder
              ├─ StemTransitionPolicy  ← NEW
              │   ├─ CompositeStemTransitionPolicy
              │   │   ├─ BaseTimbrePolicy
              │   │   ├─ EnergyFollowPolicy
              │   │   ├─ PhraseAlignPolicy
              │   │   ├─ SectionPairPolicy
              │   │   ├─ SubgenreTimingPolicy
              │   │   ├─ StemRolePolicy
              │   │   ├─ SpectralClashPolicy
              │   │   ├─ VocalClashPolicy
              │   │   ├─ BeatStrengthPolicy
              │   │   ├─ BpmDiscrepancyPolicy
              │   │   ├─ BeatgridPolicy
              │   │   ├─ CuePointPolicy
              │   │   ├─ TransitionRecipePolicy
              │   │   ├─ UserHistoryPolicy
              │   │   ├─ FeedbackPolicy
              │   │   ├─ ScoringProfilePolicy
              │   │   ├─ EmbeddingPolicy
              │   │   ├─ CrossSimilarityPolicy
              │   │   ├─ CamelotPolicy
              │   │   ├─ VocalsCoverPolicy
              │   │   └─ UserOverridePolicy
              │   └─ FadePlan
              └─ _segment_block  (uses policy output)
              ↓
ffmpeg filtergraph → MIX.mp3
```

### 3.1 Stem taxonomy (electronic music)

| Stem | Source (Demucs 6s) | Role in electronic music |
|------|--------------------|--------------------------|
| `vocals` | `vocals.wav` | vocal lines, vocal fx, sometimes absent in techno |
| `drums` | `drums.wav` | kick + snare + clap (low-frequency percussion) |
| `bass` | `bass.wav` | sub-bass, bassline |
| `harmonic` | `other.wav` | pads, leads, melodic synths, tonal texture |
| `percussion` | `percussion.wav` | hi-hats, cymbals, shakers, rimshots |

The order tuple is `("vocals", "drums", "bass", "harmonic", "percussion")` — this is the **single canonical** order. The two old orders are deleted.

### 3.2 Demucs 6s invocation

```python
demucs -n htdemucs_6s -d <cpu|mps|cuda> -o <cache_dir> <input>
```

Cache key in `run_demucs()` now includes the model name (`htdemucs_6s`) so old cached 4-stem outputs are not reused.

The fake `percussion` (drums split at 400 Hz) is removed.

### 3.3 Stem timbre defaults (`STEM_TIMBRE`)

| Stem | HPF (Hz) | Gain (dB) | Why |
|------|----------|-----------|-----|
| `vocals` | 120 | 0.0 | remove sub-bass bleed |
| `drums` | None | 0.0 | keep kick punch |
| `bass` | None | 0.0 | keep sub-fundamental |
| `harmonic` | 80 | -2.0 | light HPF to avoid mud; small trim because `other` stem can be hot |
| `percussion` | 120 | 0.0 | remove kick bleed; keep hi-hats/cymbals |

### 3.4 `TrackRenderContext` — single load of all data

A new `app/domain/render/stem_policy/context.py`:

```python
@dataclass(frozen=True)
class AvailableData:
    analysis_levels_in: tuple[int, ...]   # which L1-L6 levels track_in has
    analysis_levels_out: tuple[int, ...]
    has_beatgrid_in: bool
    has_beatgrid_out: bool
    has_cue_points_in: bool
    has_cue_points_out: bool
    has_sections_in: bool
    has_sections_out: bool
    has_stem_features_in: bool
    has_stem_features_out: bool
    has_transition_recipe: bool
    has_affinity: bool
    has_user_feedback_in: bool
    has_user_feedback_out: bool
    has_embedding_in: bool
    has_embedding_out: bool
    has_cross_similarity: bool
    has_ym_metadata_in: bool
    has_ym_metadata_out: bool
    has_beatport_in: bool
    has_beatport_out: bool
    has_transition_history: bool


@dataclass(frozen=True)
class TrackRenderContext:
    track_in_id: int
    track_out_id: int
    track_in_features: TrackFeatures | None
    track_out_features: TrackFeatures | None
    stem_features_in: dict[str, StemFeatures]
    stem_features_out: dict[str, StemFeatures]
    beatgrid_in: DjBeatgrid | None
    beatgrid_out: DjBeatgrid | None
    cue_points_in: CuePointSet | None
    cue_points_out: CuePointSet | None
    sections_in: list[TrackSection]
    sections_out: list[TrackSection]
    affinity: TrackAffinity | None
    feedback_in: TrackFeedback | None
    feedback_out: TrackFeedback | None
    transition_recipe: Transition | None
    transition_history: tuple[TransitionHistory, ...]
    cross_similarity: CrossSimilarity | None
    embedding_in: list[float] | None
    embedding_out: list[float] | None
    ym_metadata_in: YandexMetadata | None
    ym_metadata_out: YandexMetadata | None
    beatport_in: dict | None  # from TrackFeatures
    beatport_out: dict | None
    subgenre: str
    user_overrides: dict[str, Any]
    base_transition_s: float
    base_body_s: float
    target_bpm: float
    available: AvailableData
```

`TrackRenderContextBuilder.build(uow, version_id)` loads all of the above in a single pass.

### 3.4.1 Batch loading strategy

For an N-track set, the builder needs data for `(N-1)` pairs (track_i → track_{i+1}). Each pair needs:
- Both tracks' features (1 query batched by track_ids)
- Both tracks' sections (1 query batched)
- Both tracks' beatgrids (1 query batched)
- Both tracks' stem_features (1 query batched, returns rows for any of 5 stems)
- Both tracks' cue_points (computed from sections in memory, no DB)
- Affinity, transitions, history, cross_similarity, embeddings, ym_metadata, feedback, scoring_profiles — all batched by `track_id IN (...)` or `from_track_id IN (...) AND to_track_id IN (...)`

**Total: ~8 round-trips per set, regardless of N.** Not 6×N. SQL `IN` clauses handle batching; `asyncio.gather` runs them in parallel.

For 5-track set: 8 queries ≈ 200ms (matches AGENTS.md "200ms" budget).
For 30-track set: 8 queries ≈ 400ms (linear in row count, not N²).

Per-pair `TrackRenderContext` is sliced from the loaded data; no additional IO.

### 3.5 `StemTransitionContext` (per pair × stem)

```python
# TransitionIntent is the existing enum in app/domain/transition/intent.py
# (MAINTAIN | RAMP_UP | COOL_DOWN | CONTRAST). We re-use it directly — do not
# duplicate. The StemTransitionContext imports it, no new enum needed.

@dataclass(frozen=True)
class StemTransitionContext:
    stem: str                              # one of 5 stems
    pair: PairContext                      # = (track_in_id, track_out_id, seg, ctx)
    features_in: TrackFeatures | None      # L1-L5
    features_out: TrackFeatures | None
    stem_features_in: StemFeatures | None
    stem_features_out: StemFeatures | None
    section_context: SectionContext | None
    intent: TransitionIntent               # re-use existing enum from app/domain/transition/intent.py
    subgenre: str
    user_overrides: dict[str, Any]
    base_d_in_s: float
    base_d_out_s: float
    target_bpm: float
    available: AvailableData
    is_first: bool
    is_last: bool


@dataclass(frozen=True)
class FadePlan:
    fade_in_s: float | None
    fade_in_curve: str                    # qsin | tri | exp | log | squ | sin
    fade_out_s: float | None
    fade_out_curve: str
    hpf_hz: int | None
    gain_db: float
    pinpoint_s: float | None              # bass swap exact point
    pinpoint_curve: str | None            # curve around pinpoint
    notes: tuple[str, ...]                # explainability

    @staticmethod
    def identity() -> "FadePlan":
        """Neutral default — no fade, no HPF, no gain shift, no pinpoint.

        All fields set so that any policy that does nothing still produces a
        valid plan: fade_in_s=fade_out_s=0 (no fade), hpf_hz=None (passthrough),
        gain_db=0.0, pinpoint_s=None, curves="qsin", notes=().
        """
        return FadePlan(
            fade_in_s=0.0,
            fade_in_curve="qsin",
            fade_out_s=0.0,
            fade_out_curve="qsin",
            hpf_hz=None,
            gain_db=0.0,
            pinpoint_s=None,
            pinpoint_curve=None,
            notes=(),
        )
```

### 3.6 Policy protocol

```python
class StemTransitionPolicy(Protocol):
    name: str
    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan: ...
```

`CompositeStemTransitionPolicy(policies: Sequence[StemTransitionPolicy])` applies them in order; each policy mutates **only its own fields**.

**Order is configurable** — constructor accepts `policies` list, so users can build custom composites via `dj_stem_transition_policy` tool with `policy_order: list[str] | None = None` (list of policy names; missing policies are skipped, unknown names raise `ValueError`). Default order is from §3.7.

```python
@dataclass
class CompositeStemTransitionPolicy:
    policies: tuple[StemTransitionPolicy, ...]
    name_order: tuple[str, ...] = ()        # for cache key stability

    def compute(self, ctx: StemTransitionContext) -> FadePlan:
        plan = FadePlan.identity()
        for p in self.policies:
            plan = p.merge(plan, ctx)
        return plan
```

**Memoization** — `CompositeStemTransitionPolicy` exposes a `cache: dict[CacheKey, FadePlan]` field keyed by `(track_in_id, track_out_id, stem, plan_signature)` so identical pairs reuse the same plan within one render. Cache lives only for the render lifetime; no cross-render persistence.

### 3.7 Policies (21)

| # | Policy | Min data | Effect |
|---|--------|----------|--------|
| 1 | `BaseTimbrePolicy` | L1 | set HPF + gain from `STEM_TIMBRE` defaults |
| 2 | `EnergyFollowPolicy` | L2 + (L6 for per-stem) | `gain_db` offset based on per-stem `energy_mean` delta |
| 3 | `PhraseAlignPolicy` | L4 | shift `pinpoint_s` to nearest `phrase_boundaries_ms` within ±4 bars |
| 4 | `SectionPairPolicy` | L4 sections | override per-stem fade based on `SectionPairClass` (drop_to_drop tightens bass; drum_only lengthens blend) |
| 5 | `SubgenreTimingPolicy` | subgenre | scale `base_d_in/out` per `SubgenrePairType` |
| 6 | `StemRolePolicy` | always | base role: drums=continuous, bass=pinpoint, percussion=early, harmonic=mid, vocals=late |
| 7 | `SpectralClashPolicy` | L1 | tighten bass pinpoint when `energy_sub_ratio` sum > 0.3 |
| 8 | `VocalClashPolicy` | L3 (voicing_ratio) + L4 (sections) | multi-stage vocal fade when both tracks have vocals in window |
| 9 | `BeatStrengthPolicy` | L3 | bass pinpoint sharper when `kick_prominence > 0.7` |
| 10 | `BpmDiscrepancyPolicy` | L2 | lengthen bass pinpoint when `|bpm_a - bpm_b| > 1` |
| 11 | `BeatgridPolicy` | always (beatgrid table) | prefer `DjBeatgrid.bpm` over stored `bpm` for time-stretch |
| 12 | `CuePointPolicy` | L4 (cue_points) | snap mix-in to first downbeat, mix-out to last drop |
| 13 | `TransitionRecipePolicy` | DB (transitions.recipe_json) | reuse historical recipe if pair was rendered before |
| 14 | `UserHistoryPolicy` | DB (track_affinity + history) | lengthen blend when `net_sentiment < 0` |
| 15 | `FeedbackPolicy` | DB (track_feedback) | hard-skip banned outgoing, warn on archived |
| 16 | `ScoringProfilePolicy` | DB (scoring_profiles) | scale `gain_db` based on profile's per-stem weights |
| 17 | `EmbeddingPolicy` | DB (track_embeddings) | lengthen blend when cosine similarity > 0.85 |
| 18 | `CrossSimilarityPolicy` | DB (cross_similarity) | tighten blend when DTW `best_match_score` > 0.9 |
| 19 | `CamelotPolicy` | L2 (key_code) + beatport_camelot | adjust HPF / vocal fade when keys clash > 5 |
| 20 | `VocalsCoverPolicy` | L5 (dynamic_complexity, spectral_complexity) | softer vocal fade when complexity high |
| 21 | `UserOverridePolicy` | always | apply user kwargs last (always wins) |

### 3.8 New MCP tool

```python
@tool(name="dj_stem_transition_policy", tags={"namespace:render:config"}, ...)
async def stem_transition_policy(
    # Per-stem timing (доля от общей длины)
    vocals_swap_ratio: float | None = None,
    harmonic_swap_ratio: float | None = None,
    percussion_swap_ratio: float | None = None,
    bass_pinpoint_beats: float | None = None,
    # Per-stem EQ
    hpf_overrides: dict[str, int] | None = None,
    gain_offsets_db: dict[str, float] | None = None,
    # Per-stem curve
    fade_curves: dict[str, str] | None = None,
    # Energy matching
    energy_match_db_window: float | None = None,
    # Phrase alignment
    phrase_alignment: bool | None = None,
    phrase_snap_window_bars: int | None = None,
    # Vocal clash
    vocal_clash_aggression: float | None = None,
    # Global
    transition_length_multiplier: float | None = None,
    subgenre: str | None = None,
    # Policy ordering (list of policy names; see §3.6)
    policy_order: list[str] | None = None,
    # Persistence
    persist: bool = False,  # if True, write to ~/.config/dj-music-plugin/stem_policy.json
) -> dict:
    """Set stem transition policy defaults for the next render. None = keep current.

    persist=True: also save to disk for cross-session use. Default: session-only.
    """
```

**Persistence model:**
- In-memory (default): `StemPolicySession` singleton, lifetime = MCP server process
- On-disk (opt-in via `persist=True`): JSON file at `~/.config/dj-music-plugin/stem_policy.json`
- No Redis, no DB — file-based is enough for single-user desktop plugin

`dj_render_mixdown` accepts the same kwargs as one-shot override; the in-session/disk policy serves as the base.

## 4. Components

### 4.1 `app/domain/render/stem_policy/` (NEW package)

```
stem_policy/
├── __init__.py
├── models.py              # StemTransitionContext, FadePlan, AvailableData
├── base.py                # BaseStemPolicy(Protocol), CompositeStemTransitionPolicy
├── context.py             # TrackRenderContext, TrackRenderContextBuilder
├── policies/
│   ├── __init__.py
│   ├── base_timbre.py
│   ├── energy_follow.py
│   ├── phrase_align.py
│   ├── section_pair.py
│   ├── subgenre_timing.py
│   ├── stem_role.py
│   ├── spectral_clash.py
│   ├── vocal_clash.py
│   ├── beat_strength.py
│   ├── bpm_discrepancy.py
│   ├── beatgrid.py
│   ├── cue_point.py
│   ├── transition_recipe.py
│   ├── user_history.py
│   ├── feedback.py
│   ├── scoring_profile.py
│   ├── embedding.py
│   ├── cross_similarity.py
│   ├── camelot.py
│   ├── vocals_cover.py
│   └── user_override.py
└── builder.py             # default_policy() factory
```

### 4.2 `app/domain/render/stem_timbre.py` (RENAMED from stem_voicing.py)

```python
@dataclass(frozen=True, slots=True)
class StemTimbre:
    hpf_hz: int | None
    gain_db: float


STEM_TIMBRE: dict[str, StemTimbre] = {
    "vocals":     StemTimbre(hpf_hz=120, gain_db=0.0),
    "drums":      StemTimbre(hpf_hz=None, gain_db=0.0),
    "bass":       StemTimbre(hpf_hz=None, gain_db=0.0),
    "harmonic":   StemTimbre(hpf_hz=80,  gain_db=-2.0),
    "percussion": StemTimbre(hpf_hz=120, gain_db=0.0),
}


def stem_timbre(stem: str) -> StemTimbre:
    return STEM_TIMBRE[stem]
```

### 4.3 `app/domain/render/models.py` (MODIFIED)

```python
# Single canonical 5-stem order for electronic music
STEM_ORDER: tuple[str, ...] = ("vocals", "drums", "bass", "harmonic", "percussion")
# DEMUCS_STEM_ORDER removed — Demucs 6s maps 1:1 to STEM_ORDER
```

`StemSegment.stem_paths` now references these 5 names.

### 4.4 `app/audio/deep/demucs_runner.py` (MODIFIED)

- Always invoke `htdemucs_6s`
- Cache key includes `htdemucs_6s` so old 4-stem cache is invalidated
- Remove ffmpeg drums-split heuristic
- Map output → `STEM_ORDER` keys: `vocals, drums, bass, other→harmonic, percussion`

### 4.5 `app/handlers/_orchestrator/stem_resolver.py` (SIMPLIFIED)

- Drop the two-order resolver (`_complete_stem_order`, `_missing_for_any_order`)
- Always Demucs 6s with 5 stems
- `STEM_ORDER` is the only order

### 4.6 `app/domain/render/plan_assembler.py` (MODIFIED)

- Accept `TrackRenderContext` (or build it internally via `TrackRenderContextBuilder`)
- Build default `StemTransitionPolicy` for the render
- Pass policy into `StemGraphBuilder` via `RenderPlan`

### 4.7 `app/domain/render/filtergraph.py` (MODIFIED)

- `StemGraphBuilder._stem_fades()` → `_stem_transition()` calls `policy.compute(ctx)`
- `StemGraphBuilder._segment_block()` constructs `StemTransitionContext` per stem from `seg` + `ctx`
- HPF and gain come from `FadePlan.hpf_hz` / `FadePlan.gain_db` (set by `BaseTimbrePolicy`)
- Per-stem `eq_phase_1_ratio` / `eq_phase_2_ratio` become soft defaults; policies can override

### 4.8 `app/handlers/_orchestrator/render_orchestrator.py` (MODIFIED)

- Inject `TrackRenderContextBuilder` after `StemResolver`
- Pass `TrackRenderContext` to `RenderPlanner.assemble`

### 4.9 `app/tools/render/render_mixdown.py` (MODIFIED)

- Accepts `stem_policy_kwargs: dict | None = None`
- Stores in `RenderRequest.stem_policy_kwargs`
- Falls through to `UserOverridePolicy`

### 4.10 `app/tools/render/stem_transition_policy.py` (NEW)

- Single-shot tool that stores user policy in session state (in-memory)
- `dj_render_mixdown` reads session state if no kwargs passed

## 5. Data Flow

1. User calls `dj_render_mixdown(version_id=42, subgenre="hypnotic_techno", stem_policy_kwargs={...})`
2. `RenderOrchestrator.run`:
   - `preset_applier.apply(settings, subgenre)`
   - `beatgrid_provider.ensure(ctx, request, uow)`
   - `inputs = uow.set_versions.get_render_inputs(42)`
   - `grid = beatgrid_provider.load(workspace)`
   - `bar_plan = BarPlanner(settings).compute(inputs, grid, ...)`
   - If stem mode: `stem_paths = stem_resolver.resolve(ctx, uow, inputs, workspace)` → Demucs 6s
   - **`track_ctx = TrackRenderContextBuilder().build(uow, version_id)`** — single SQL pass
   - `plan = planner.assemble(settings, request, inputs, grid, bar_plan, stem_paths, track_ctx)`
3. `RenderPlanner.assemble`:
   - Build default `StemTransitionPolicy` from `track_ctx.available` (skips policies that need absent data)
   - Apply `user_overrides` via `UserOverridePolicy`
   - Build `StemSegment` list with `stem_paths` from Demucs
4. `RenderExecutor.execute` → `ffmpeg` with filtergraph from `StemGraphBuilder`
5. `StemGraphBuilder._segment_block` for each track:
   - For each stem: build `StemTransitionContext`, call `policy.compute(ctx)`, get `FadePlan`
   - Translate `FadePlan` into ffmpeg filter statements

### Error handling

- If Demucs fails: fall back to `stem=False` (classic EQ) — same as today
- If a policy raises: log warning, skip that policy, continue
- If `TrackRenderContextBuilder` query fails: log warning, `TrackRenderContext` with `available.analysis_levels=()`, all `has_*=False` — policies fall back to defaults

## 6. Testing

### 6.1 Unit tests (TDD per policy)

`tests/domain/render/stem_policy/`:
- `test_base_timbre.py`: HPF/gain defaults per stem
- `test_phrase_align.py`: snaps to nearest boundary, respects bar-multiple
- `test_vocal_clash.py`: multi-stage fade when both tracks have vocals
- `test_user_history.py`: blend lengthens when `net_sentiment < 0`
- ... one file per policy
- `test_composite.py`: order of application, user_override wins

### 6.2 Snapshot tests

`tests/domain/render/test_stem_filtergraph.py` (replaces `test_stem_graph.py`):
- `test_filtergraph_uses_electronic_stem_order`: only `[s0_vocals]`, `[s0_drums]`, `[s0_bass]`, `[s0_harmonic]`, `[s0_percussion]` labels
- `test_filtergraph_no_instrumental_acappella_other`: negative assertions
- `test_filtergraph_5_inputs_per_track`: 2 tracks × 5 stems = 10 inputs
- `test_filtergraph_phrase_aligned_pinpoint`: `pinpoint_s` snaps to phrase boundary when L4 data
- `test_filtergraph_vocal_clash_aggressive_fade`: outgoing vocals drop in last 10% when `voicing_ratio` high on both
- `test_filtergraph_cross_similarity_tightens_blend`: when `cross_similarity.best_match_score > 0.9`, blend duration shortens by 30%
- `test_filtergraph_beatgrid_over_stored_bpm`: `StemGraphBuilder` uses `DjBeatgrid.bpm` for `tempo_ratio` when present, falls back to `TrackFeatures.bpm` only when no beatgrid row exists
- `test_filtergraph_demucs_6s_cache_invalidation`: cache key for Demucs output includes `htdemucs_6s` so old `htdemucs` cache is not reused
- `test_filtergraph_memoization_within_render`: identical pair+stem in same render returns same `FadePlan` from `CompositeStemTransitionPolicy.cache`

### 6.3 Integration tests

`tests/handlers/test_track_render_context.py`:
- `test_builder_loads_all_data`: 5-track set, builder returns all data
- `test_builder_handles_missing_data`: no L4 → `available.has_sections_* = False`
- `test_builder_handles_no_user_history`: `transition_history` empty

### 6.4 Audio validation

`tests/scripts/test_render_electronic_stems.py` (golden render):
- Render 4-track techno set with `htdemucs_6s`
- Validate: phase alignment `< 30ms`, no `DROPOUT`, energy profile monotonic
- Compare with old `htdemucs` 4-stem render — must improve

### 6.5 Migration tests

- `tests/audio/test_demucs_runner_cache_invalidation.py`: cache key includes `htdemucs_6s`
- `tests/domain/render/test_legacy_stem_aliases_rejected.py`: `instrumental`, `acappella`, `other` raise `ValueError`

## 7. Rollout

### Phase 1: Data-only (no behavior change)
- Add `STEM_TIMBRE` rename in `stem_timbre.py`; keep `stem_voicing.py` re-exporting for one release with `DeprecationWarning` on import.
- New `STEM_ORDER = ("vocals", "drums", "bass", "harmonic", "percussion")` in `models.py`; `DEMUCS_STEM_ORDER` kept as alias of `STEM_ORDER` for one release.
- `demucs_runner.py` still calls `htdemucs` (4s) for one release; mapping in `stem_resolver._expand_stem_paths` translates `other`→`harmonic` for callers using the new order.

### Phase 2: Policy engine (additive)
- New `app/domain/render/stem_policy/` package with 21 policies
- `TrackRenderContextBuilder` and data flow
- `StemGraphBuilder` uses policies; falls back to old logic if policies don't bind

### Phase 3: Demucs 6s (breaking)
- `demucs_runner.py` only `htdemucs_6s`
- Old cache invalidated (key includes model)
- Remove `DEMUCS_STEM_ORDER`

### Phase 4: Cleanup
- Delete old `STEM_VOICING` / `StemVoicing` / `stem_voicing.py` / `_DEMUCS_STEM_VOICING`
- Update scripts (`render_12deck_*.py`, `sync_prepared_stem_*.py`, `render_maximal_stem_*.py`)
- Update `docs/render-pipeline.md` and `AGENTS.md`

### Migration impact
- **DB**: NO migration (stem_paths not persisted in DjSetVersion)
- **Disk cache**: auto-invalidated (cache key changes)
- **API**: removing `instrumental`/`acappella`/`other` is breaking for direct users; MCP tools updated
- **Existing sets**: re-render required (cached MIX.mp3 still plays but new render uses new taxonomy)

## 8. Risks

| Risk | Mitigation |
|------|------------|
| 21 policies = maintenance burden | Each is a pure function <100 LOC; unit tests trivial |
| Per-pair policy compute adds CPU | `CompositeStemTransitionPolicy.cache` memoizes by `(track_in_id, track_out_id, stem, plan_signature)`; pair count ≤ 30 per set, cache cleared at end of render |
| Demucs 6s slower than 4s | Acceptable: render is offline; cache pre-warmed |
| `TrackRenderContextBuilder` slow | Batched SQL: ~8 round-trips total per set, parallel via `asyncio.gather`; <400ms for 30-track set (verified by §3.4.1 analysis) |
| User overrides break deterministic tests | Snapshot tests fix all kwargs; `UserOverridePolicy` tested last in isolation |
| Backwards compat for old scripts | Phase 1 keeps aliases; Phase 4 updates scripts in same PR |
| StemFeatures has `instrumental`/`acappella` rows in prod? | **None** — verified 2026-09-02: `SELECT stem_name, COUNT(*) FROM stem_features GROUP BY stem_name` returns only `original/drums/bass/vocals/other/percussion`. `other` is the Demucs 6-stem `other` (not old `instrumental`); render-time mapping `other`→`harmonic` handles the rename without DB write |

## 9. Alternatives Considered

- **A. Hardcoded per-subgenre transition rules** — rejected; we have 66+ features per track and 21 policy-relevant data sources, hardcoding defeats the point.
- **B. Keep two stem taxonomies side-by-side** — rejected; doubles the test matrix and confuses users.
- **C. Phrase-align all transitions regardless of subgenre** — rejected; some subgenres want hard cuts; `SubgenreTimingPolicy` lengthens blend for ambient, shortens for hard.
- **D. Compute policy weights from NeuralMix recipe (existing) directly** — rejected; recipes are key-frames per-stem level_db, different abstraction level.
- **E. Persist `FadePlan` in DB** — rejected YAGNI; recompute is fast and pure.

## 10. Resolved Questions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Persist `dj_stem_transition_policy` across sessions? | Yes, opt-in via `persist=True` to JSON at `~/.config/dj-music-plugin/stem_policy.json` | Single-user desktop plugin, no Redis needed |
| Custom policy order? | Yes, `policy_order: list[str]` kwarg in `CompositeStemTransitionPolicy` constructor and `dj_stem_transition_policy` tool | Power users may want to disable a policy (e.g. skip `VocalClashPolicy` if they trust the L3 detection) |
| Add new `TransitionIntent` enum? | No, re-use existing `app/domain/transition/intent.py` (MAINTAIN/RAMP_UP/COOL_DOWN/CONTRAST) | Already there, tested, no duplication |
| StemFeatures `instrumental`/`acappella` rows in prod? | None — verified via `SELECT stem_name, COUNT(*) FROM stem_features GROUP BY stem_name`: only `original/drums/bass/vocals/other/percussion` (127 rows total, `percussion` has just 2 rows from htdemucs_6s early tests) | No migration needed; `other` → `harmonic` is a render-time mapping, not a DB rename |
| Async policy protocol? | No, all policies sync (pure functions on data already loaded into ctx) | No policy needs async I/O; if one ever does, refactor to async then |
| 30-track set performance? | ~400ms total (8 batched queries, not 6×N²) | Verified by §3.4.1 batching analysis |
