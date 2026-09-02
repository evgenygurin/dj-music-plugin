# Liebing N-Deck Toolkit — Highly Parameterizable Instruments

**Date:** 2026-09-03
**Status:** draft for review
**Base research:** `docs/research/2026-09-03-chris-liebing-deep-research.md` (180+ источников, 3 exa high, context7 FastMCP 3.2.4)
**Decks:** N ∈ [2..12], deck = role/layer, not track. One LOW owner invariant.

## Goal

Набор из ~15 узких MCP-инструментов вместо одного монолита «собери сет». Каждый инструмент делает одну вещь, максимально параметризуем (все 83 поля `track_audio_features_computed` доступны), работает на любом N (2,4,6,12) без ветвлений `if N==2`. Данные — максимум из БД без прослушивания; слух — финальная верификация.

Покрыть логику Chris Liebing: отбор по функции (тело/фрагмент/ритм/атмосфера), стена звука из слоёв, один LOW, длинные 32–64 тактовые blends, энергия волнами (не дропами), Sync освобождает внимание.

## Non-Goals

- Не новый алгоритм разделения (остаётся `demucs htdemucs` 4-stem).
- Не замена `sequence_optimize` GA — расширяем `transition_score_pool`.
- Не требовать прослушивания для скоринга; не хардкодить 2/6 дек.
- Не ломать `fastmcp>=3.2.4,<3.4` / `pyproject.toml:26`.

## Architecture — deck-agnostic N

```
Analyzer (read-only 83 fields) → Curator (filters+preset) → Scorer (S=Σ w·S)
→ Planner (phrase/layer/energy, N) → Optimizer (GA/greedy/constructive)
→ Renderer (beatgrid/stems/mixdown N-канальный, SEM=1) → Validator (grid/diagnose/flow)
```

Каждый инструмент — `@mcp.tool` с `BaseModel` параметрами (`Annotated[Field(ge/le, description)]`) и `BaseModel` выходом → FastMCP auto `outputSchema` + `structuredContent` + `content` (`docs/servers/tools.mdx` 3.2.4). Версионирование через `version` param (`docs/servers/versioning.mdx`).

Роли для любого N:

| Роль | Спектр | Когда вводить | LOW |
|------|--------|---------------|-----|
| FOUNDATION | full | всегда 1 | владелец |
| INCOMING | full, LOW kill до swap | 1–8 такты | вырезан |
| PERCUSSION | high-pass | 1–8 | нет |
| TEXTURE | band-pass | 1–8 | нет |
| VOICE | mid | если есть место | нет |
| BRIDGE/SPARE | любой | запас | нет |

N=2: [FOUNDATION, INCOMING]
N=4: + [PERCUSSION, TEXTURE]
N=6: + [VOICE, BRIDGE]
N=12: дубли ролей с другими тембрами.

Инвариант: **в любой момент ровно один канал владеет LOW** (фильтр + fader).

## Data — 83 поля `track_audio_features_computed`

`supabase: track_audio_features_computed` — 83 колонки (см. `SELECT column_name FROM information_schema.columns WHERE table_name='track_audio_features_computed'`):

- `bpm, bpm_confidence, bpm_stability, variable_tempo, audio_bpm, beatport_bpm, bpm_histogram_*`
- `integrated_lufs, short_term_lufs_mean, momentary_max, rms_dbfs, true_peak_db, crest_factor_db, loudness_range_lu, energy_* (7 bands + ratios), energy_mean/max/std/slope`
- `spectral_centroid_hz, rolloff_85/95, flatness, flux_mean/std, slope, contrast, spectral_complexity_mean`
- `key_code, key_confidence, atonality, hnr_db, chroma_entropy, hp_ratio, kick_prominence, onset_rate, pulse_clarity`
- `mfcc_vector, tonnetz_vector, tempogram_ratio_vector, beat_loudness_band_ratio, dissonance_mean, dynamic_complexity, pitch_salience_mean`
- `phrase_boundaries_ms, dominant_phrase_bars, first_downbeat_ms`
- `beatport_genre/sub_genre/track_id/confidence/label/release/isrc/duration_ms, audio_key_code/confidence, audio_mood/confidence, bpm_source/key_source/mood_source`
- `analysis_level (L2/L5), mood, danceability`

Все доступны через `entity_list(track_features, filters={field__range/__gte/__lte/__in/__isnull})` — Django-style уже в `app/tools`. `mcc_vector` и т.д. хранятся как `character varying` (сериализованный вектор).

## Instruments — 15 tools, каждый параметризуем

### Analyzer (read-only, без записи)

**`analyze_track_deep(track_id, level=5)`** → `track_features` 73 поля. Использует `essentia`+`librosa`+`openl3` как в `app/audio/analyzers/*`.

**`analyze_loudness_map(track_id, bars=16)`** → `[{bar, low, mid, high, flux}]` (sub-band energy per phrase). `librosa` + `scipy`.

**`analyze_harmonic_profile(track_id, target_keys: list[int]|None)`** → `{S_h per key, chroma, roughness}`. `essentia HPCP + Key(edma) + scipi roughness` (Gebhardt).

**`analyze_groove(track_id)`** → `{onset_density, syncopation, hp_ratio, kick_prominence, groove_score}`.

**`validate_grid(version_id, mix_path) -> GridCheckResult`** — уже есть `render_validate_grid` (`app/tools/render/render_validate_grid.py:44`).

### Curator (отбор, не порядок)

**`curate_by_role(n_decks: int Field(ge=2,le=12), preset: Preset|None, filters: TrackFeatureFilters, limit: int)`**

```python
class TrackFeatureFilters(BaseModel):
    bpm__range: tuple[float,float]|None = Field(None, description="BPM коридор, 8-10 окно")
    integrated_lufs__range: tuple[float,float]|None = Field(None, description="LUFS, 5-6 окно")
    energy_low__gte: float|None = None
    spectral_centroid_hz__lte: float|None = None
    key_code__in: list[int]|None = None
    atonality__eq: bool|None = None
    phrase_boundaries_ms__isnull: bool|None = None
    # ... все 83 поля как Optional[Range|Value|List] с Field(ge/le)
    variable_tempo__eq: bool|None = Field(False, description="исключить дрейфующие")

class Preset(str, Enum):
    liebing_hypnotic = "liebing_hypnotic"  # 126-133, -13..-9 LUFS, low_ratio, spectral_centroid 1800, hp>2.5
    liebing_industrial = "liebing_industrial"
    peak_time = "peak_time"
    custom = "custom"

# preset заполняет дефолты filters, но любой Field в filters переопределяет
```

Preset — не хардкод, а `BaseModel` с дефолтами, переопределяемыми.

**`curate_by_energy_block(track_ids, block_size=3-4)`**, **`find_bridge_tracks(from_id, to_id, max_pitch_pct=4)`** — использует `p=100*(Bt/B0-1)`, `Δs=12·log2(1+p/100)`.

### Scorer (совместимость для N)

**`score_harmonic(a_id, b_id, alpha: float Field(ge=0,le=1)=0.5)`** → `S_h = α·key_distance + (1-α)·roughness` (Faraldo + Gebhardt). `key_distance` — Camelot + `ENHARMONIC_ALIASES`.

**`score_rhythmic(a_id,b_id, max_bpm_delta=10)`** → `S_r = 1 - |ΔBPM|/10 - drift_penalty` (`Δbeats=ΔBPM·t/60`, `t=240·N/BPM`).

**`score_timbral(a_id,b_id, method="openl3"|"mfcc")`** → `cosine(OpenL3)`.

**`score_energy(a_id,b_id)`** → `1 - |ΔLUFS|/6 - |Δsubband|/norm` (Lustig & Tan).

**`score_structure(a_id,b_id, phrase_bars=16)`** → `phrase_align_bonus` (Raveform).

**`score_transition(a_id,b_id, weights: ScoringWeights, components=true)`** — главный:

```python
class ScoringWeights(BaseModel):
    w_harmony: float = Field(0.25, ge=0,le=1)
    w_rhythmic: float = Field(0.25, ge=0,le=1)
    w_timbral: float = Field(0.2, ge=0,le=1)
    w_energy: float = Field(0.15, ge=0,le=1)
    w_structure: float = Field(0.15, ge=0,le=1)
    roughness_vs_camelot: float = Field(0.5, ge=0,le=1, description="α для S_h")
# S = Σ w·S + проверка S_h, нормализация Σw=1
```

Расширяет существующий `transition_score_pool(track_ids, top_k, components, weights)` (`app/tools/compute/transition_score.py`).

### Planner (любое N)

**`plan_phrase(track_id, bars: Literal[8,16,32]=16)`** → `{phrase_times, bar_times, t=240·bars/BPM}`.

**`plan_layer(n_decks: int Field(ge=2,le=12), roles: list[Role] | None)`** → назначение слоёв на N каналов с инвариантом один LOW. `roles` опционален — если `None`, маппит по таблице выше (2→2 роли, 6→6).

**`plan_energy_curve(track_ids, start_pct=0.6, peak_at=0.65)`** → глобальная траектория 60–70%→пик 55–70 мин, блоками 3–4, запас 20–30% (Mixgraph).

**`optimize_sequence(track_ids, algorithm="ga"|"greedy"|"constructive", camelot_mode="soft", energy_arc="peak_time", weights)`** — уже `sequence_optimize`, добавить `weights` passthrough.

### Renderer (N-канальный)

**`render_beatgrid(version_id, refresh_grid=False)`** — уже есть, `phase_ms` на оригинале `librosa.load(orig.mp3)` (`AGENTS.md §3`), `bpm_measured` для `tempo_ratio`.

**`render_stems(track_ids, runtime="auto")`** — 3-tier `mlx→onnx→torch` (`StemsConfig` 7.8s jobs 0, `app/config/stems.py`), уже `StemsConfig(segment=7.8)`.

**`render_mixdown(version_id, stem=True, transition_bars, body_bars, filter_sweep=None, subgenre="hypnotic_techno")`** — N-канальный `ffmpeg filter_complex: atrim→rubberband(tempo=bpm_measured/target)→highpass/lowpass xsplit 250/4000→afade→amix→firequalizer→alimiter0.85`, `SEM=1` на 8GB (`app/audio/deep/__init__.py:12`). `hypnotic_techno` 48b/40b `phase_1_ratio 0.55`, `dub 64b` — уже в `app/config/render.py`.

**`render_diagnose(version_id), diagnose_flow(mix_path)`** — `true_peak, level_jumps, near_silent, flow` (`pyloudnorm/scipy`).

### Improving (итерация)

**`suggest_replacement(track_id, set_id, position, weights)`** — уже `local://tracks/{id}/suggest_replacement`, расширить `weights`.

**`bench_stems(runtime, clip)`** — уже `scripts/bench_stems_m2.py`.

## Data flow — пример N=4 Liebing

```python
pool = curate_by_role(n_decks=4, preset="liebing_hypnotic",
  filters={"bpm__range":(126,133), "integrated_lufs__range":(-13,-9),
           "spectral_centroid_hz__lte":2400, "variable_tempo__eq":False}, limit=50)
scores = score_transition(track_ids=pool, weights={w_h:0.3,w_r:0.25,w_t:0.2,w_e:0.15,w_s:0.1}, components=true, top_k=3)
layers = plan_layer(n_decks=4, roles=["FOUNDATION","INCOMING","PERCUSSION","TEXTURE"])
phrases = plan_phrase(track_id=pool[0], bars=16)
order = optimize_sequence(track_ids=pool, algorithm="ga", weights=weights)
render_mixdown(version_id=..., transition_bars=32, body_bars=40, stem=True)
validate_grid(version_id)
```

Тот же код с `n_decks=12` даст 12 ролей, формула `t=240·N/BPM` и `+3dB` сумма не меняются.

## Parameterization — как сделать максимально гибко

- Каждый инструмент принимает `filters: TrackFeatureFilters` (70+ Optional) + `preset` + `weights` + `n_decks`. `Field` даёт `description` для LLM, `ge/le` валидацию, `StructuredOutput` для клиента.
- Версионирование инструментов через `version` param (`docs/servers/versioning.mdx`): `curate_by_role v1` (70 полей) → `v2` (83 поля) без лома.
- Ресурсы для чтения: `local://tracks/{id}/features` (все 83 поля), `local://render/{version_id}/grid_check` — не дублировать в параметры.
- Промпты для LLM: `validate_grid_workflow` уже есть, добавить `liebing_set_workflow` с примером N=2/6/12.

## Error handling

- `filters` с `__gte/__lte` на NULL-heavy колонках (`bpm_confidence`, `true_peak_db`) — не фильтровать, NULL проваливает сравнение (уже в `build-set` skill).
- `pitch_salience_mean`/`dynamic_complexity` — только `__isnull` (нет числовых лукапов).
- `BPM Δ>10 hard reject`, `LUFS spread ≤5-6`, `phrase_boundaries_ms` проверять на слух.
- `Sync` экономит внимание на N>2, но beatgrid проверять в 3 точках трека.

## Testing

- Юнит: `TrackFeatureFilters` валидация, `ScoringWeights Σw=1`, `plan_layer(N=2,4,6,12)` один LOW, `score_transition` с `roughness_vs_camelot`.
- Интеграция: `curate_by_role` на 50 треках 126-133, `bench_stems` RTF mlx 0.03 torch 0.20, `render_mixdown` 6 треков 59s mlx.
- Listening test: 30-мин сет на N=2,4,6 одним пулом, сравнить `level_jumps`/`near_silent` + blind Techno Zen.

## Open questions

1. Веса `w_*` — дефолты 0.25/0.25/0.2/0.15/0.15 оставить или сделать пресет-зависимыми (hypnotic: `w_t` выше)?
2. `phrase_boundaries_ms` — хранить как `character varying` (сериализованный JSON) или мигрировать в `JSONB` для `__contains`?
3. Нужен ли `tinytag` скан для 25k библиотеки или достаточно `Mutagen`?

## Next

После approve — `writing-plans` → план с 6-8 задачами (по инструментам), TDD, `docs/superpowers/plans/YYYY-MM-DD-liebing-n-deck-toolkit.md`.
