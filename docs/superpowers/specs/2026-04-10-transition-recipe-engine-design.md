# Transition Recipe Engine — Design Spec

> Phase 1: Расширение системы переходов до 12 типов с детальными stem-level инструкциями для djay Pro AI.

## 1. Проблема

Текущая система рекомендует один из 6 абстрактных стилей перехода (cut, bass_swap_short/long, long_blend, echo_out, filter_sweep) без учёта:
- Целевого DJ софта (djay Pro AI с Neural Mix stems)
- Субжанра пары треков (dub techno vs industrial — кардинально разные переходы)
- Детальных stem-операций (какой stem когда swap'ить)
- Фразовых границ (phrase alignment)
- Vocal/melodic conflict detection

Cheat sheet содержит только "score=0.82, BPM delta, key distance" — бесполезно для реального выступления.

## 2. Решение

Новый слой `TransitionRecipeEngine` между scoring и export. Генерирует `TransitionRecipe` — полные пошаговые инструкции для djay Pro AI.

### Flow

```text
Текущий:
  Score(A,B) → TransitionScore → recommend_style() → "bass_swap_short, 8 bars"

Новый:
  Score(A,B) → TransitionScore ──┐
  TrackFeatures A,B ─────────────┤
  SectionContext ─────────────────┼──→ TransitionRecipeEngine.generate()
  Moods A,B ──────────────────────┤        │
  TransitionIntent ───────────────┘        ▼
                                    TransitionRecipe {
                                      type, bars, djay_fx,
                                      steps[], eq_plan,
                                      warnings, rescue_move
                                    }
```

Scoring (6 компонентов) и GA optimizer НЕ меняются.

## 3. Научная база

- **Kim et al. (ISMIR 2020)**: анализ 1,557 DJ миксов, 20,765 переходов. MFCC similarity — #1 предиктор. Key compatibility статистически незначима (p > 0.1). 86.1% DJs корректируют BPM < 4%. Медиана скачка громкости = 0.59 dB.
- **Mosaikbox (ISMIR 2024, Sowula & Knees)**: rule-based stem modification значительно превосходит end-to-end ML. Удаление несовместимых стемов — ключ к качеству.
- **Zehren et al. (ISMIR 2022/2024)**: switch points определяются energy novelty + bass drum novelty + timbre novelty. >95% совпадают с 16-bar phrase boundaries.
- **Bittner et al. (ISMIR 2017, Spotify)**: sequencing как graph traversal (shortest Hamiltonian path). Key clash не замечается слушателями.

## 4. 12 типов переходов

| # | Тип | djay Pro AI функция | Bars | Когда |
|---|-----|-------------------|------|-------|
| 1 | `CUT` | Hard crossfader | 0 | All scores > 0.85 + drop boundary |
| 2 | `BASS_SWAP_SHORT` | Manual EQ (low swap) | 8 | Good groove, compatible kick |
| 3 | `BASS_SWAP_LONG` | Manual EQ (gradual) | 32 | Moderate compatibility |
| 4 | `EQ_BLEND` | Crossfade + EQ auto | 16 | Compatible groove, similar arrangement |
| 5 | `FILTER_SWEEP` | Crossfader FX: Filter | 16 | Spectral collision or hard reject |
| 6 | `ECHO_OUT` | Crossfader FX: Echo | 8-16 | Energy gap > 3 LUFS |
| 7 | `LONG_BLEND` | Slow crossfade + EQ | 64 | Key drift, ambient/dub |
| 8 | `RISER` | Crossfader FX: Riser | 8 | Energy ramp up, festival moments |
| 9 | `DROP_SWAP` | Hard cut on "one" | 0-4 | Vocal/bass conflict, energy shift |
| 10 | `NEURAL_MIX_BLEND` | Neural Mix stem swap | 16-32 | Key clash + compatible drums |
| 11 | `DISSOLVE` | Crossfader FX: Tremolo | 8-16 | Ambient/dub, gentle transition |
| 12 | `STEMS_CREATIVE` | Neural Mix + effects | 16 | Creative mashup moment |

## 5. Decision Tree

### Input

`TransitionScore` + `TrackFeatures` A,B + `SectionContext` (optional) + `TechnoSubgenre` A,B (optional) + `TransitionIntent` (optional) + `SectionInfo[]` A,B (optional for mix points)

### Субжанр-контекст (pair classification)

```text
AMBIENT_PAIR:  both in {AMBIENT_DUB, DUB_TECHNO}
HARD_PAIR:     both in {INDUSTRIAL, HARD_TECHNO, RAW}
ACID_PAIR:     any is ACID
MELODIC_PAIR:  both in {MELODIC_DEEP, PROGRESSIVE, DETROIT}
HYPNOTIC_PAIR: both in {HYPNOTIC, MINIMAL}
MIXED_PAIR:    everything else
```

### Decision steps (priority order)

**Step 1 — Hard reject (rescue)**
- `hard_reject` → FILTER_SWEEP, 16 bars, djay: Filter, conf 0.60

**Step 2 — Drum-only sections**
- `is_drum_only_pair AND groove > 0.80` → CUT, 0 bars, conf 0.95
- `is_drum_only_pair AND groove > 0.60` → BASS_SWAP_SHORT, 8 bars, conf 0.88
- `is_drum_only_pair` → FILTER_SWEEP, 8 bars, conf 0.75

**Step 3 — Spectral collision**
- `spectral < 0.45` → FILTER_SWEEP, 16 bars, djay: Filter, conf 0.78-0.82

**Step 4 — Key clash with compatible rhythm**
- `harmonic < 0.55 AND groove > 0.70` → NEURAL_MIX_BLEND, 24 bars, djay: Neural Mix, conf 0.80
- `harmonic < 0.55 AND AMBIENT_PAIR` → LONG_BLEND, 64 bars, conf 0.72
- `harmonic < 0.55` → ECHO_OUT, 16 bars, djay: Echo, conf 0.70

**Step 5 — Energy gap**
- `energy < 0.40 AND delta > 0 AND (RAMP_UP or HARD_PAIR)` → RISER, 8 bars, djay: Riser, conf 0.82
- `energy < 0.40 AND delta > 0` → FILTER_SWEEP, 16 bars, conf 0.75
- `energy < 0.40 AND delta ≤ 0 AND AMBIENT_PAIR` → DISSOLVE, 32 bars, conf 0.78
- `energy < 0.40 AND delta ≤ 0` → ECHO_OUT, 16 bars, djay: Echo, conf 0.80

**Step 6 — Subgenre-specific rules**
- `AMBIENT_PAIR` → DISSOLVE, 48 bars, djay: Tremolo, conf 0.85
- `HARD_PAIR AND overall > 0.70` → DROP_SWAP, 4 bars, conf 0.88
- `ACID_PAIR AND spectral > 0.60` → FILTER_SWEEP, 16 bars, djay: Filter, conf 0.85
- `HYPNOTIC_PAIR AND groove > 0.70` → NEURAL_MIX_BLEND, 32 bars, djay: Neural Mix, conf 0.83

**Step 7 — Vocal conflict detection (heuristic)**
- `vocal_likely(A) AND vocal_likely(B)`:
  - `overall > 0.75` → DROP_SWAP, 4 bars, conf 0.80
  - else → NEURAL_MIX_BLEND, 16 bars, conf 0.75
- Vocal heuristic: `pitch_salience_mean > 0.4 AND spectral_centroid_hz > 2500`

**Step 8 — Perfect compatibility**
- `bpm > 0.95 AND harmonic > 0.85 AND groove > 0.75`:
  - `HARD_PAIR` → CUT, 0 bars, conf 0.95
  - `drop boundary` → DROP_SWAP, 0 bars, conf 0.93
  - else → BASS_SWAP_SHORT, 8 bars, conf 0.92

**Steps 9-12 — Graduated fallback**
- `overall > 0.80` → BASS_SWAP_SHORT, 8 bars, conf 0.88
- `overall > 0.65` → EQ_BLEND, 16 bars, conf 0.80-0.82
- `overall > 0.50` → BASS_SWAP_LONG, 32 bars, conf 0.72
- else → FILTER_SWEEP, 16 bars, conf 0.65

### Post-processing

1. **Subgenre bar clamping**: AMBIENT_PAIR → min 32 bars; HARD_PAIR → max 8 bars; HYPNOTIC_PAIR → min 16 bars
2. **Phrase snap**: bars rounded to nearest `dominant_phrase_bars` (typically 8). Uses `phrase_boundaries_ms` from P2 features when available.

## 6. TransitionRecipe Data Model

```python
class TransitionType(StrEnum):
    CUT = "cut"
    BASS_SWAP_SHORT = "bass_swap_short"
    BASS_SWAP_LONG = "bass_swap_long"
    EQ_BLEND = "eq_blend"
    FILTER_SWEEP = "filter_sweep"
    ECHO_OUT = "echo_out"
    LONG_BLEND = "long_blend"
    RISER = "riser"
    DROP_SWAP = "drop_swap"
    NEURAL_MIX_BLEND = "neural_mix_blend"
    DISSOLVE = "dissolve"
    STEMS_CREATIVE = "stems_creative"

class DjayTransition(StrEnum):
    NONE = "none"
    FILTER = "filter"
    ECHO = "echo"
    TREMOLO = "tremolo"
    RISER = "riser"
    NEURAL_MIX = "neural_mix"

class StemAction(StrEnum):
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CUT = "cut"
    SWAP = "swap"
    MUTE = "mute"
    SOLO = "solo"

@dataclass(frozen=True)
class RecipeStep:
    bar: int
    deck: Literal["A", "B", "both"]
    action: str
    stem: str | None = None
    stem_action: StemAction | None = None
    eq_band: str | None = None
    eq_value: float | None = None
    effect: str | None = None
    effect_param: float | None = None

@dataclass(frozen=True)
class EQPlan:
    low: str
    mid: str
    high: str

@dataclass(frozen=True)
class TransitionRecipe:
    transition_type: TransitionType
    bars: int
    djay_transition: DjayTransition
    djay_tempo_adjust: str
    steps: tuple[RecipeStep, ...]
    eq_plan: EQPlan
    mix_in_section: str | None
    mix_out_section: str | None
    phrase_align: bool
    warnings: tuple[str, ...]
    confidence: float
    subgenre_modifier: str | None
    rescue_move: str
```

## 7. Stem Swap Order

Canonical order for all stem-based transitions (based on Mosaikbox research + professional DJ practice):

1. **Drums first** — safest, rhythmically immediate, no harmonic risk
2. **Bass on phrase boundary** — "one" of 8/16 bar phrase, never mid-phrase
3. **Harmonics carefully** — only when key compatible or during breakdown
4. **Vocals last** — or mute entirely if conflict detected

## 8. Step Templates

12 step-generation functions, one per transition type:

| Function | Key steps |
|----------|----------|
| `_steps_cut` | Single step: hard crossfader move on the one |
| `_steps_bass_swap_short` | bar 0: B in (bass killed), bar 4: raise mids, bar 8: SWAP bass, bar 8: kill A |
| `_steps_bass_swap_long` | Same but 32 bars, gradual EQ trade, hidden filter at end |
| `_steps_eq_blend` | Complementary EQ: boost B where A is cut, 16 bar gradual |
| `_steps_filter_sweep` | bar 0: B enters via LPF, gradual open; bar 8: HPF on A; bar 16: full B |
| `_steps_echo_out` | bar 0: echo on A, bar 8: echo tail fades, B enters clean |
| `_steps_long_blend` | 64 bars: very slow crossfade + EQ trade + reverb wash |
| `_steps_riser` | bar 0: HPF both, bar 4: white noise riser, bar 8: drop into B |
| `_steps_drop_swap` | bar 0: cue B drop exactly on A's last beat, hard cut |
| `_steps_neural_mix_blend` | bar 0: B drums via Neural Mix, bar 8: A harmonics fade, bar 16: B harmonics in, bar 24: full B |
| `_steps_dissolve` | Spatial washout: reverb max + tremolo + very slow fade |
| `_steps_stems_creative` | Custom: drums A + melody B mashup, or acapella swap |

## 9. Субжанр-специфичные правила

| Субжанр пары | Длительность | Предпочтительный тип | Нюансы |
|-------------|-------------|---------------------|--------|
| DUB_TECHNO / AMBIENT_DUB | 32-64+ bars | DISSOLVE, LONG_BLEND | Reverb tail = 50% звука. Sidechain kick пробивает через reverb. Never cut. |
| MINIMAL / HYPNOTIC | 16-32 bars | NEURAL_MIX_BLEND, EQ_BLEND | Loop = ключевой инструмент. Repetitive → drums swap first. |
| MELODIC_DEEP / PROGRESSIVE | 16-32 bars | EQ_BLEND, LONG_BLEND | Key match критичен! Мелодии должны гармонировать. |
| PEAK_TIME / DRIVING | 8-16 bars | BASS_SWAP_SHORT, DROP_SWAP | Быстрые. Kick к kick. Минимум overlap. |
| INDUSTRIAL / HARD_TECHNO | 4-8 bars | CUT, DROP_SWAP | Агрессивные, резкие. Filter sweep + hard cut. |
| ACID | 8-16 bars | FILTER_SWEEP | Фильтр перехода имитирует TB-303 sweep. |
| MIXED (разные субжанры) | 16 bars | EQ_BLEND, FILTER_SWEEP | Нейтральный переход, filter masks differences. |

### Community-sourced techniques incorporated

- **"Never play two basslines simultaneously"** — bass swap обязателен в каждом рецепте с overlap > 0 bars
- **"Hidden filter trick"** — HPF both tracks на последних 2 bars → release on the one → impact
- **"Spatial washout"** — reverb max + HPF для ambient/dub
- **"Loop rescue"** — если диссонанс: loop 4 bars + cut mids = стабилизация
- **"Echo on phrase boundary"** — echo tail затухает ровно к началу нового drop

## 10. Интеграция

### Новые файлы

```text
app/transition/recipe.py          — dataclasses (TransitionRecipe, RecipeStep, enums)
app/transition/recipe_engine.py   — TransitionRecipeEngine (decision tree + step builder)
app/transition/subgenre_rules.py  — per-subgenre modifiers (bars, types, stem order)
```

### Изменения в существующих файлах

**`app/transition/style.py`** — добавить `recommend_recipe()` wrapper, backward-compatible. `recommend_style()` остаётся как fallback.

**`app/services/set/scoring.py`** — в `score_set_transitions()` после scoring каждой пары вызывать `recommend_recipe()` и сохранять recipe data в `Transition` model.

**`app/services/set/cheatsheet.py`** — обогатить формат: вместо "score=0.82" → полный recipe box с steps, EQ plan, warnings.

**`app/export/cheatsheet_writer.py`** — аналогично для file export в deliver_set.

**`app/export/models.py`** — расширить `ExportTransition`: `transition_bars`, `djay_transition`, `recipe_steps`, `eq_plan`, `rescue_move`.

**`app/db/models/transition.py`** — 3 nullable колонки:
```sql
ALTER TABLE transitions ADD COLUMN transition_type VARCHAR(30);
ALTER TABLE transitions ADD COLUMN transition_bars INTEGER;
ALTER TABLE transitions ADD COLUMN transition_recipe_json JSONB;
```

### Что НЕ меняется

- `TransitionScorer` и 6 scoring components
- GA/greedy optimizer и fitness function
- Mood classifier
- Panel player (Фаза 3)
- Все MCP tool interfaces (обратно совместимы)
- `recommend_style()` — остаётся, recipe engine вызывается параллельно

## 11. Cheat Sheet формат

### MCP tool (`get_set_cheat_sheet`)

```text
═══════════════════════════════════════════════════════
  DJ SET: Friday Night Peak Hour
  Version: v3 | Score: 0.84 | Tracks: 15 | Template: peak_hour_60
  Software: djay Pro AI | Tempo: Sync+Tempo Blend
═══════════════════════════════════════════════════════

 1. Alignment — Vortex  [134 BPM | 8A | -7.0 LUFS | peak_time]

     ┌── BASS SWAP SHORT · 16 bars ─── djay: Manual EQ ──┐
     │                                                     │
     │  bar 0   B: Start on phrase. Bass killed.           │
     │          B: Hi-hats + perc at -6dB                  │
     │  bar 4   B: Raise mids gradually                    │
     │  bar 8   ★ BASS SWAP on the 1                      │
     │          A: Begin HPF sweep (30%)                   │
     │  bar 12  A: HPF 70%, fade to 50%                   │
     │  bar 14  BOTH: Hidden filter trick (HPF 2 bars)    │
     │  bar 16  B: Full. Release filters. Kill A.         │
     │                                                     │
     │  EQ: low=swap@8 · mid=gradual · high=filter_sweep  │
     │  ⚠ BPM +2 → use Sync+Tempo Blend                  │
     │  🛟 Rescue: filter sweep + hard cut                 │
     │  Score: 0.88 · Confidence: 0.91                    │
     └─────────────────────────────────────────────────────┘

 2. Next Track  [136 BPM | 9A | -8.0 LUFS | acid]
     ...

═══════════════════════════════════════════════════════
  SET ANALYTICS
  Avg score: 0.84 | Conflicts: 0 | Weak (<0.5): 1
  Types: 6× bass_swap, 4× filter, 2× neural_mix, ...
  BPM: 134-142 | Arc: -8 → -5.5 → -7 LUFS
═══════════════════════════════════════════════════════
```

## 12. Тестирование

### Файлы

```text
tests/test_transition/
├── test_recipe_engine.py       — decision tree: ~25 tests, each step
├── test_recipe_steps.py        — step generation per type
├── test_subgenre_rules.py      — bar clamping, type override
├── test_recipe_integration.py  — full pipeline: score → recipe → text
```

### Покрытие

Каждый путь decision tree = минимум 1 тест. Синтетические TrackFeatures, без DB. ~25 unit тестов.

Key test cases:
- Hard reject → FILTER_SWEEP
- Drum-only pair → CUT or BASS_SWAP_SHORT
- Key clash + compatible drums → NEURAL_MIX_BLEND
- Ambient pair → DISSOLVE with bars >= 32
- Hard pair → DROP_SWAP or CUT with bars <= 8
- Vocal conflict → DROP_SWAP or NEURAL_MIX_BLEND
- Perfect match → CUT
- Phrase snap → bars % 8 == 0
- Fallback without features → style-based recipe

## 13. Скоп и границы

### В скопе (Фаза 1)
- TransitionRecipeEngine с 12 типами
- Decision tree на основе scores + features + subgenres
- Step templates для каждого типа
- Субжанр-специфичные модификаторы
- Обогащённый cheat sheet (MCP tool + file export)
- DB миграция (3 nullable колонки)
- ~25 unit тестов

### Вне скопа (будущие фазы)
- **Фаза 2**: GA fitness upgrade (transition_type → fitness weight)
- **Фаза 3**: Panel transition visualizer (timeline UI с stem lanes)
- **Фаза 4**: Real stem separation (L5 analysis с demucs)
- **Фаза 5**: ML-based transition type prediction (train on real DJ sets)

## 14. Риски

| Риск | Митигация |
|------|-----------|
| Vocal heuristic ошибается | Conservative: prefer DROP_SWAP (safe) over blend (risky) |
| Phrase data отсутствует (P2 не проанализирован) | Fallback: default 8-bar phrases |
| Субжанр неизвестен (mood=None) | Fallback: MIXED_PAIR rules |
| Recipe too verbose для Claude context | Cheat sheet = text summary, JSON recipe = full detail |
| djay Pro AI не поддерживает некоторые операции | Recipe = advisory, DJ может адаптировать |

## 15. Источники

1. Kim, T. et al. "A Computational Analysis of Real-World DJ Mixes" (ISMIR 2020)
2. Sowula, R. & Knees, P. "Mosaikbox: Rule-Based Stem Modification" (ISMIR 2024)
3. Zehren, M. et al. "Automatic Detection of Cue Points for DJ Mixing" (CMJ 2022)
4. Bittner, R. et al. "Automatic Playlist Sequencing and Transitions" (ISMIR 2017, Spotify)
5. Williams, A. et al. "Temporal Considerations in DJ Mix IR and Generation" (TIME 2025)
6. Algoriddim djay Pro AI documentation (2026)
7. DJ.Studio Harmonize documentation (2026)
8. Community: r/Beatmatch, r/DJs transition technique threads
