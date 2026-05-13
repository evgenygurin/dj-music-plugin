# Transition System Refactor v2 — ADR + Design Spec

> **Status:** Proposed
> **Дата:** 2026-05-13
> **Автор:** Evgeny + Claude Opus 4.7
> **Контекст:** v1.3.8, post Neural Mix refactor. Этот документ — **следующий шаг** после двух предыдущих research'ей.
>
> **Связанные документы:**
> - [docs/transition-scoring.md](transition-scoring.md) — текущая формула v1.3 (6 компонент + 7 пресетов)
> - [docs/research/2026-04-08-techno-transitions-research.md](research/2026-04-08-techno-transitions-research.md) — академическая база (Kim/Vande Veire/Zehren/Ishizaki)
> - [docs/research/2026-05-13-neural-mix-transitions-deep-dive.md](research/2026-05-13-neural-mix-transitions-deep-dive.md) — глубокий разбор picker + djay Pro AI / Algoriddim
> - [docs/superpowers/plans/2026-05-13-picker-heuristic-refinement.md](superpowers/plans/2026-05-13-picker-heuristic-refinement.md) — Phase 0 (vocal heuristic fix)
> - [docs/audio-pipeline.md](audio-pipeline.md) — 18 analyzers + tiered L1–L4
> - [docs/audio-schema.md](audio-schema.md) — 47 features в БД

---

## TL;DR

1. **Текущая формула v1.3 — добротный baseline, но имеет три структурные проблемы:**
   (а) `scorer.score(section_context=...)` **молча игнорирует** `section_context` ([scorer.py:75](../app/domain/transition/scorer.py#L75) — `del section_context`); вся section-awareness живёт только в picker'е, не в score'е, поэтому `overall` остаётся context-free;
   (б) **фразовая структура не моделируется**, хотя `phrase_boundaries_ms` и `dominant_phrase_bars` уже **есть** в `track_audio_features_computed` (см. [models/track_features.py:127-128](../app/models/track_features.py#L127)) — но никто их не читает;
   (в) `transition_persist_handler` ([handlers/transition_persist.py:148](../app/handlers/transition_persist.py#L148)) вызывает `scorer.score(feat_a, feat_b)` **без** `section_context` / `intent` / `subgenre_pair`, так что и picker, и build_recipe работают на пустом контексте — даже когда данные доступны.

2. **Decision: Score v2 = 8 компонент (добавляем `S_phrase` + `S_structure`) + section-aware overlay в scorer'е + sequence-cost penalty. Phasing — 7 фаз, каждая отдельный PR.**

3. **Не делаем end-to-end ML.** DJtransGAN ([Chen et al. ICASSP 2022](https://arxiv.org/abs/2110.06525)) и подобные дают компетитивные результаты в listening tests, но не дают controllable, debuggable, per-pair scoring — а MCP-интерфейс плагина в принципе строится вокруг **prom-able scoring**. Mosaikbox ([Sowula & Knees ISMIR 2024](https://repositum.tuwien.at/handle/20.500.12708/212628)) подтверждает: hybrid rule-based + structural detection остаётся SOTA в 2024-2025.

4. **Хорошая новость:** ~85% инфраструктуры уже на месте. Phrase boundaries вычисляются ([phrase.py](../app/audio/analyzers/phrase.py)), section-pair primitive есть ([section_context.py](../app/domain/transition/section_context.py)), даже `SubgenrePairType` пробрасывается через picker. Рефакторинг — это **wiring + extension**, не переписывание.

5. **Плохая новость:** существующая документация местами описывает функции, **которых нет в коде**. `score_set_transitions` и `build_section_context` упомянуты в [docs/transition-scoring.md § Runtime Wiring](transition-scoring.md), но `grep` по `app/` их не находит. Это документация-как-намерение, не документация-как-факт. Доку синхронизируем в Phase 7.

---

## 1. Context

### 1.1 Что мы строим

dj-music-plugin — MCP-сервер для управления DJ techno-библиотекой и построения оптимизированных сетов. Один из ключевых выходов — **persisted transition recipes**: для каждой пары `(track_a, track_b)` plugin хранит (i) numerical score (6 компонент + overall), (ii) выбранный Neural Mix preset (один из 7), (iii) полностью материализованный `NeuralMixRecipe` (stem-keyframe envelope), который DJ-tool может проиграть детерминированно.

### 1.2 Что уже сделано

v1.3.x закрыло:

- Neural Mix paradigm: 6-component score → stem-aware (drums/bass/harmonic/vocals — те же 4 стема что у djay Pro 5 / AudioShake)
- 7 пресетов с per-preset stem envelopes (FADE / ECHO_OUT / VOCAL_SUSTAIN / HARMONIC_SUSTAIN / DRUM_SWAP / VOCAL_CUT / DRUM_CUT)
- Picker с decision tree на 7 правил
- Recipe-engine с JSON-сериализацией и round-trip в БД (`transitions.transition_recipe_json`)
- Per-intent weight модификаторы (MAINTAIN / RAMP_UP / COOL_DOWN / CONTRAST)
- Bulk-scorer с numpy parity ([bulk_scorer.py](../app/domain/transition/bulk_scorer.py)) для GA pre-populate

### 1.3 Что мы НЕ закрыли (и об этом этот документ)

| # | Проблема | Источник | Затронутые компоненты |
|---|---|---|---|
| 1 | `section_context` принимается scorer'ом, но **выкинут**: `del section_context` | [scorer.py:75](../app/domain/transition/scorer.py#L75) | scorer.py, score.py |
| 2 | Фразовая структура (16/32-bar boundaries) **не моделируется** в scoring, хотя данные есть в БД | [phrase.py](../app/audio/analyzers/phrase.py), [models/track_features.py:127-128](../app/models/track_features.py#L127) | scorer.py, schemas, weights.py |
| 3 | `entity_create(transition)` handler не пробрасывает context | [transition_persist.py:148](../app/handlers/transition_persist.py#L148) | transition_persist.py, schemas/transition.py |
| 4 | Drum-only релаксация только в picker, не в score — `overall` для outro→intro пары завышает penalty по harmonic | [picker.py:179-196](../app/domain/transition/picker.py#L179) | scorer.py |
| 5 | Camelot dominates: harmonic=40% cam, bass=65% cam — для percussive техно overweighted (см. Bibbó ISMIR 2022) | [neural_mix.py:218-289](../app/domain/transition/neural_mix.py#L218) | neural_mix.py, weights.py |
| 6 | `CONTRAST` intent определён в [intent.py:42-49](../app/domain/transition/intent.py#L42), но `infer_intent` **никогда** его не возвращает | [intent.py:71-96](../app/domain/transition/intent.py#L71) | intent.py |
| 7 | Sequence-cost отсутствует: GA выбирает 3 ECHO_OUT'а подряд если pair-score высокий | [domain/optimization/](../app/domain/optimization/) | optimization/fitness.py |
| 8 | Hard-reject Camelot `>= 5` слишком строгий для атональных / drum-only пар | [hard_constraints.py:56-60](../app/domain/transition/hard_constraints.py#L56) | hard_constraints.py |
| 9 | Bass clash оценивается через camelot+band ratio, без явной low-band conflict detection | [neural_mix.py:218](../app/domain/transition/neural_mix.py#L218) | neural_mix.py |
| 10 | Energy slope bonus бинарный (one bit), не gradient | [components/energy.py:46-51](../app/domain/transition/components/energy.py#L46) | components/energy.py |
| 11 | Vocal detection — 3-сигнальная эвристика, не реальная (Phase 0 уже патчит acid false-positive) | [picker.py:78-113](../app/domain/transition/picker.py#L78) | picker.py |
| 12 | Документация и код разъехались — `score_set_transitions`, `build_section_context` упомянуты в docs, но не существуют | [transition-scoring.md § Runtime Wiring](transition-scoring.md) | docs/ |

### 1.4 Что собирается DJ-индустрия в 2024-2026

| Продукт | Что нового | Релевантно для нас |
|---|---|---|
| **djay Pro AI 5.3 (2025)** | AudioShake 4-stem + Neural Mix Crossfaders (per-stem FX) + новые Automix пресеты (Dissolve / Riser / Echo). Multi-stem FX 2-4 stem switching. | Подтверждает: 4-стем split — индустриальный стандарт. Наши 4 NeuralMixStem'а 1:1 совпадают. Новые пресеты Dissolve/Riser/Echo пересекаются с нашими ECHO_OUT, и намекают на отсутствующий FILTER_SWEEP/RISER. |
| **Rekordbox 7 (2024+)** | **AI vocal detection прямо на waveform** + Phrase Analysis с mood (low/mid/high) + Intelligent Cue Creation (учится на ваших ручных cue points). | Vocal detection в Rekordbox — отдельный ML-классификатор, не эвристика. Наш Phase 0 fix + Phase 7 demucs идут в эту же сторону. Phrase Analysis + mood → структурная разметка треков — это то, что у нас уже есть через `track_sections` + `phrase_boundaries_ms`, но не используется. |
| **Serato Stems Pro 3.0** | 4-stem precomputed (создаёт 4 версии трека на диске для слабого железа), pad FX per stem. | Подтверждает: precompute > realtime для DJ workloads. Наш L4 demucs path должен быть precompute, не realtime. |
| **Mixxx 2.5.4 (Dec 2025)** + **GSoC 2025** | Mixxx двигает Demucs v4 (HT) в ONNX для realtime stems. < 0.1 dB SDR difference между Python и ONNX. | Open-source benchmark: realtime HT-Demucs стал жизнеспособен. Наш L4 path можно делать на pretrained checkpoints без своего train loop'а. |
| **Mosaikbox** (ISMIR 2024, [Sowula & Knees](https://repositum.tuwien.at/handle/20.500.12708/212628)) | "Rule-based stem modification + precise beat-grid estimation" — **прямой аналог** нашей архитектуры (rule-based scorer + Neural Mix recipes). Удаляют incompatible stems на transition. | Подтверждение: hybrid (rules + structural detection + stem suppression) — SOTA в 2024. Не end-to-end ML. |
| **EDMFormer** (2025, [arXiv:2603.08759](https://arxiv.org/html/2603.08759)) | Transformer-based EDM-specific MSA. Существующие MSA-модели плохи на EDM (built around lyrical/harmonic similarity); EDMFormer берёт **energy / rhythm / timbre** изменения как primary boundary signals. | Подтверждает наш приоритет energy/rhythm/timbre над harmonic для техно. Можно использовать как L4 структурный аналайзер. |
| **DJtransGAN** (ICASSP 2022, [Chen et al.](https://arxiv.org/abs/2110.06525)) | Differentiable EQ + fader, trained против discriminator на livetracklist mixes. | **Не наш путь.** GAN-подход даёт competitive listening test scores, но не даёт controllable scoring per pair — а у нас весь plugin построен на этом. Сохраним как future ablation reference. |
| **allin1** ([mir-aidj](https://github.com/mir-aidj/all-in-one)) | Beats + downbeats + segments + labels одним Python API. Покрывает то что у нас сейчас собрано из madmom + librosa + custom phrase analyzer. | Кандидат на замену 3 наших analyzer'ов одним. Phase 7 evaluation. |

---

## 2. Forces

Перед тем как принимать решение — что **обязательно** в дизайне:

1. **MCP-first.** Любой score должен быть промптируемым: LLM должна уметь спросить "почему именно этот score?" — поэтому компоненты остаются inspectable, не одно ML-число.
2. **Backwards compat в API.** `TransitionScore` shape — публичный (panel, REST, persisted DB). Добавлять поля можно, переименовывать — нет. Public field names `drums/bass/harmonics/vocals` остаются ([score.py:43-56](../app/domain/transition/score.py#L43)).
3. **DB-friendly.** `transitions.transition_recipe_json` — JSON, расширяется. `transitions.*_score` колонки — добавлять можно через migration, ронять — нельзя (для legacy rows).
4. **Bulk parity.** Любая фича в scalar `TransitionScorer` должна иметь vector equivalent в `BulkTransitionScorer` под parity test ([test_bulk_scorer_parity.py](../tests/domain/transition/test_bulk_scorer_parity.py)).
5. **Deterministic.** Никакого ML-inference внутри scoring loop — GA вызывает scorer 100K+ раз на сет. Все ML — precompute → feature column.
6. **No new DB tables (если возможно).** 17 dead-таблиц всё ещё ждут drop'а ([CLAUDE.md § DB состояние](../CLAUDE.md)). Новые поля кладём в существующий `track_audio_features_computed` или `transitions`.
7. **Phase'д migration.** Каждая фаза — отдельный PR с зелёным `make check`. Никаких big-bang.

---

## 3. Current state — диагноз

### 3.1 Формула v1.3 ([weights.py:22-29](../app/domain/transition/weights.py#L22))

```text
overall = 0.20·S_bpm + 0.15·S_energy
        + 0.20·S_drums + 0.15·S_bass + 0.15·S_harmonics + 0.15·S_vocals
```

Hard-reject если:
- `bpm_distance > 10` (с double/half awareness)
- `camelot_distance >= 5`
- `|lufs_a - lufs_b| > 6.0`

### 3.2 Где формула молча врёт

#### А. `section_context` принимается, но игнорируется

[scorer.py:69-82](../app/domain/transition/scorer.py#L69):

```python
def score(self, from_t, to_t, *, intent=None, section_context=None):
    """...section_context is currently accepted but unused..."""
    del section_context  # reserved for future per-section weight overrides
    ...
```

Picker ([picker.py:179-196](../app/domain/transition/picker.py#L179)) использует `section_context.is_drum_only_pair` для выбора preset'а — но **сам score остаётся пессимистичным** для outro→intro пары, потому что harmonic / vocals компоненты считают полные треки и penalty за key mismatch / vocal absence остаётся.

Это значит: GA получает `overall = 0.60` для отличной outro→intro пары (где harmonic match не важен), и сортирует её ниже пары с одинаковыми ключами, но мидддл-секциями (где гармоническая совместимость **действительно** matters).

#### B. Phrase grids уже посчитаны, но не используются

[track_features.py:127-128](../app/models/track_features.py#L127):

```python
phrase_boundaries_ms: Mapped[str | None] = mapped_column(String(2000), nullable=True)
dominant_phrase_bars: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
```

Эти поля заполняет [PhraseAnalyzer](../app/audio/analyzers/phrase.py) (agglomerative clustering на bar-level chroma → находит доминирующую длину фразы: 8, 16, или 32 бара). **Нигде** в `app/domain/transition/` нет импорта `phrase_boundaries_ms` или `dominant_phrase_bars`.

Профессиональный DJ-канон ([DJ TechTools](https://djtechtools.com/2009/01/26/phrasing-the-perfect-mix/), [Native Instruments](https://blog.native-instruments.com/phrase-mixing/)):

> "All transitions phrase-locked. Standard techno: 4 beat = 1 bar, 8 bar = 1 phrase, 4 phrase = 1 section. Mix-in / mix-out **must** land on phrase boundary."

Наш scorer не знает разницы между парой `(8-bar phrase, 16-bar phrase)` и парой `(16-bar phrase, 16-bar phrase)`. Первая — гарантированный phase clash на каждой 16-й бочке; вторая — perfectly aligned.

#### C. Handler выбрасывает контекст

[transition_persist.py:148](../app/handlers/transition_persist.py#L148):

```python
score = scorer.score(feat_a, feat_b)
recipe = _build_recipe_or_none(score, feat_a, feat_b)
```

Никаких kwargs. `section_context=None`, `subgenre_pair=None`, `intent=None`. Это работает в текущем `del section_context` режиме, но если мы починим scorer — handler всё равно не передаст контекст. Phase 1 должна включать wiring handler'а.

#### D. Score выпадает в `set_version_build`, не в `entity_create(transition)`

Документация [docs/transition-scoring.md § Runtime Wiring](transition-scoring.md) утверждает что `set_version_build_handler` использует `build_section_context`. **Grep `build_section_context` по `app/` возвращает 0 файлов.** Документация фантомная.

Реально section-context resolution не существует — он описан как намерение. Phase 2 должна создать его.

### 3.3 Где компоненты переоценены/недооценены

Веса 0.20 / 0.15 / 0.20 / 0.15 / 0.15 / 0.15 ([weights.py:22-29](../app/domain/transition/weights.py#L22)) пришли из [docs/research/2026-04-08 § 4.4](research/2026-04-08-techno-transitions-research.md), где было сказано: "поднять spectral до 0.20". Но post-Neural Mix refactor `spectral` стал `bass`, `groove` стал `drums`, `harmonic` остался harmonic, `timbral` стал vocals — и при этом веса остались **прежней редакции**, теперь они моделируют не то что задумывалось.

Конкретно (см. также Kim et al. ISMIR 2020, MFCC analysis):

| Component | Текущий вес | Что реально мерит | Литература говорит | Действие |
|---|---|---|---|---|
| `bpm` | 0.20 | Tempo lock | Critical (Kim, Ishizaki) | Оставить, но добавить phrase-coherent BPM term |
| `energy` | 0.15 | LUFS direction + LRA + crest | Critical, **узкое** выравнивание | Расширить — short-term LUFS на mix-region |
| `drums` | 0.20 | BPM lock (50%) + kick (25%) + onset (15%) + beat-loudness (10%) | Critical для percussion-driven (Vande Veire) | Оставить, но S_bpm здесь дублирует top-level S_bpm — это double-counting |
| `bass` | 0.15 | Camelot (65%) + bass band (20%) + BPM (15%) | Bass clash — #1 mud cause | **Понизить вес Camelot до 0.40, добавить explicit low-band conflict gate** |
| `harmonics` | 0.15 | Camelot (40%) + Tonnetz (20%) + MFCC (20%) + spectral contrast (10%) + dissonance penalty | **Camelot overweighted** для percussive (Bibbó ISMIR 2022) | **Tonnetz cosine → primary**, Camelot → tiebreaker; HNR-gate выносим из формулы в pre-check |
| `vocals` | 0.15 | Centroid (40%) + chroma entropy (30%) + pitch salience (30%) | Heuristic, proxy not real | **Gate-it-out** когда обе стороны non-vocal (вместо неинформативного 0.5) |

### 3.4 Что лишнее

- `infer_intent` ([intent.py:71-96](../app/domain/transition/intent.py#L71)) **никогда** не возвращает `CONTRAST` — все веса в `INTENT_WEIGHT_MODIFIERS[CONTRAST]` ([intent.py:42-49](../app/domain/transition/intent.py#L42)) **dead code**. Либо реализуем, либо удаляем.
- `_peak_start` из `_TEMPLATE_PHASE_TABLE` извлекается, но не используется ([intent.py:84-85](../app/domain/transition/intent.py#L84-L85)).
- `BulkTransitionScorer.neural_best_overall_bulk` ([bulk_scorer.py:589-612](../app/domain/transition/bulk_scorer.py#L589)) — "currently here for parity testing — may be promoted later". Либо promote, либо delete (YAGNI).

### 3.5 Что лишнее в архитектуре пресетов

Из [docs/research/2026-05-13 § 6.2](research/2026-05-13-neural-mix-transitions-deep-dive.md):

- `VOCAL_SUSTAIN` ≡ `HARMONIC_SUSTAIN` структурно (отличаются только target stem)
- `VOCAL_CUT` ≡ `DRUM_CUT` структурно (отличаются только target stem)

Этот таксономический overlap мы НЕ трогаем в Phase 1-6 — он работает. Phase 7 (long-term) обсуждает unification в `STEM_SUSTAIN(target)` / `STEM_CUT(target)`, но это БД-миграция enum'а `transitions.fx_type` и переписывание builders.

---

## 4. Options considered

### Option A — Status quo

Оставить v1.3 как есть, добавить только Phase 0 picker fix.

**Pro:** zero risk, zero work.
**Contra:** четыре концептуальных бага (`del section_context`, no phrase, no handler context, dead CONTRAST) останутся как технический долг. Domain layer документирует функции которые не существуют.

→ **Отвергнуто.** User явно попросил рефакторинг.

### Option B — Patch picker only

Сделать только то что в [Phase 1 plan](superpowers/plans/2026-05-13-picker-heuristic-refinement.md): vocal heuristic + midband filter.

**Pro:** один PR, ~2 часа работы, фиксит самый видимый bug (acid → VOCAL_CUT).
**Contra:** не трогает scorer, не моделирует фразы, не починят section-aware overlap. Это **необходимо, но недостаточно**.

→ **Отвергнуто как самодостаточное решение.** Phase 0 остаётся как первый шаг, но это лишь pre-requisite.

### Option C — Score v2 phased refactor *(THIS PROPOSAL)*

8-component score + section-aware overlay в scorer + phrase scoring + sequence cost + corrected hard constraints + handler context wiring. **7 фаз, каждая отдельный PR.**

**Pro:**
- Закрывает все 12 проблем из §1.3
- Каждая фаза independently mergeable + зелёный make check
- Veterinary compatible с persisted DB rows (добавляем nullable columns)
- Bulk parity test guards drift

**Contra:**
- ~4-6 недель календарного времени (если делать без давления)
- Требует recalibration на ground truth corpus после каждой фазы

→ **Принято.** Деталь — §5.

### Option D — End-to-end ML (DJtransGAN-style)

Заменить весь rule-based scorer на trained model (DJtransGAN / differentiable EQ-fader / latent embeddings).

**Pro:** state-of-the-art listening test scores (Chen 2022).
**Contra:**
- Не controllable, не promptable, не debuggable — нельзя ответить LLM "почему score=0.42"
- Требует train dataset (livetracklist crawl или ручная разметка) — у нас его нет
- Mode collapse, deterministic stem suppression невозможно
- Не интегрируется с recipe engine — выход модели = audio, не envelope keyframes
- Mosaikbox (ISMIR 2024) **подтверждает** что hybrid rule-based + structural detection — SOTA на 2024

→ **Отвергнуто.** Сохраняем как future research направление, но не в roadmap'е.

---

## 5. Decision — Score v2

### 5.1 Новая формула (high-level)

```text
overall = w_bpm · S_bpm + w_energy · S_energy
        + w_drums · S_drums + w_bass · S_bass
        + w_harmonics · S_harmonics + w_vocals · S_vocals
        + w_phrase · S_phrase            ← NEW
        + w_structure · S_structure      ← NEW
```

Веса нормализованы на 1.0; per-intent + per-section-pair модификаторы применяются мультипликативно поверх базовых.

### 5.2 Базовые веса v2

| Component | v1.3 | v2 base | Δ | Обоснование |
|---|---:|---:|---:|---|
| `bpm` | 0.20 | 0.18 | -0.02 | Слегка ниже — теперь часть BPM-сигнала покрывается через `S_phrase` (phrase coherence) и `S_drums` (BPM lock на drums-stem) |
| `energy` | 0.15 | 0.13 | -0.02 | Аналогично — slope-alignment теперь continuous, но общий weight чуть ниже |
| `drums` | 0.20 | 0.18 | -0.02 | Слегка ниже — BPM double-count убран |
| `bass` | 0.15 | 0.13 | -0.02 | Bass-clash gate вынесен из weighted-sum в hard-check |
| `harmonics` | 0.15 | 0.12 | -0.03 | Tonnetz → primary; Camelot weight внутри `S_harmonics` падает с 0.40 до 0.25 |
| `vocals` | 0.15 | 0.10 | -0.05 | Когда обе стороны non-vocal — gate-out (вес = 0); active weight выше |
| `phrase` | — | 0.10 | +0.10 | **NEW.** Phrase-grid coherence (dominant_phrase_bars match + downbeat alignment) |
| `structure` | — | 0.06 | +0.06 | **NEW.** Структурно-семантическая совместимость (outro→intro > middle→middle > drop→intro) |
| **Σ** | 1.00 | 1.00 | 0 | |

> **Калибровочный protocol:** до коммита каждой фазы — run `tests/domain/transition/test_calibration.py` (new test) на ground-truth corpus (Phase 6 deliverable) и убедиться что mean `overall` не сдвинулся > 0.05 без объяснения.

### 5.3 Section-aware overlay (move drum-only relaxation в scorer)

Расширяем [SectionContext](../app/domain/transition/section_context.py) с binary `is_drum_only_pair` до **5-классовой типологии**:

```python
class SectionPairClass(StrEnum):
    DRUM_ONLY    = "drum_only"     # both sides INTRO/OUTRO/SUSTAIN/AMBIENT
    DROP_TO_DROP = "drop_to_drop"  # both sides DROP/PEAK
    BREAKDOWN_OUT = "breakdown_out" # A=BREAKDOWN/VALLEY, B=INTRO/RISE
    BUILDUP_IN   = "buildup_in"    # A=BUILD/RISE, B=DROP/PEAK
    GENERIC      = "generic"       # everything else
```

Каждый класс получает **multiplicative weight overlay**:

| Pair class | drums | bass | harmonics | vocals | phrase | structure |
|---|---:|---:|---:|---:|---:|---:|
| DRUM_ONLY | ×1.30 | ×0.70 | ×0.40 | ×0.30 | ×1.30 | ×1.50 |
| DROP_TO_DROP | ×1.20 | ×1.20 | ×0.80 | ×0.80 | ×1.10 | ×1.30 |
| BREAKDOWN_OUT | ×0.80 | ×0.80 | ×1.40 | ×1.20 | ×0.90 | ×1.20 |
| BUILDUP_IN | ×1.10 | ×0.90 | ×1.10 | ×1.00 | ×1.20 | ×1.40 |
| GENERIC | ×1.00 | ×1.00 | ×1.00 | ×1.00 | ×1.00 | ×1.00 |

После применения — renormalize в сумму 1.0 (см. [section_context.py](../app/domain/transition/section_context.py) extension в §6.3).

**Rationale per class** (см. также [docs/research/2026-04-08 § 1.1-1.3](research/2026-04-08-techno-transitions-research.md)):

- **DRUM_ONLY** — оба окна percussion-only; harmonic clash минимален → drop harmonic weight. Phrase + structure важны (это вся идея intro→outro mixable region).
- **DROP_TO_DROP** — peak-to-peak; harmonic clash можно прятать через intensity, drums/bass — критичны (kicks должны align'иться).
- **BREAKDOWN_OUT** — A в melodic breakdown, B в drum intro; harmonic preservation выходит на первый план (мелодия должна довести), drums ослабляются (новый kick войдёт позже).
- **BUILDUP_IN** — A нарастает (riser/build), B обрушивает drop; phrase + structure dominate, harmonic второстепенен.
- **GENERIC** — fallback, никакого modifier'а.

### 5.4 `S_phrase` — phrase coherence (NEW)

Использует уже-вычисленные `dominant_phrase_bars` и `phrase_boundaries_ms` из БД.

```text
S_phrase = 0.40 · phrase_length_match
         + 0.40 · phrase_grid_align
         + 0.20 · phrase_count_in_mix_region
```

где:

- **phrase_length_match** — `1.0 if dom_phrase_bars_a == dom_phrase_bars_b else 0.5 if |Δ| == 8 bars else 0.0`
- **phrase_grid_align** — насколько mix-out point у A и mix-in point у B попадают на 16-бар boundary
  - если есть `mix_out_point_ms` / `mix_in_point_ms` в DB, использовать; иначе fallback на section start/end
  - формула: `1.0 - min(1.0, beat_offset_ms / (bar_ms / 2))`, где `bar_ms = 60_000 / bpm * 4`
- **phrase_count_in_mix_region** — сколько целых фраз умещается в mix region (target 2-4)
  - `1.0 if 2 <= count <= 4 else 1.0 - 0.2 * |count - 3|`

Compute cost: O(1) lookup + ~10 арифметических операций. Стабильный numpy bulk path.

### 5.5 `S_structure` — section-type compatibility (NEW)

Категориальный score из табличного lookup'а на парах `(SectionType_A_out, SectionType_B_in)`:

| A section ↓ \ B section → | INTRO | RISE | BUILD | DROP | PEAK | BREAKDOWN | OUTRO | SUSTAIN |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **OUTRO** | **1.00** | 0.95 | 0.80 | 0.70 | 0.60 | 0.75 | 0.90 | 0.85 |
| **SUSTAIN** | 0.95 | 0.90 | 0.75 | 0.65 | 0.55 | 0.70 | 0.85 | **1.00** |
| **AMBIENT** | 0.90 | 0.85 | 0.65 | 0.50 | 0.40 | 0.75 | 0.85 | 0.95 |
| **DROP/PEAK** | 0.60 | 0.65 | 0.85 | **1.00** | 0.95 | 0.70 | 0.55 | 0.65 |
| **BREAKDOWN** | 0.85 | 0.90 | 0.95 | 0.80 | 0.70 | 0.85 | 0.75 | 0.80 |
| **BUILD/RISE** | 0.70 | 0.75 | 0.85 | 0.95 | **1.00** | 0.65 | 0.60 | 0.65 |
| **VALLEY** | 0.85 | 0.90 | 0.80 | 0.70 | 0.60 | 0.85 | 0.80 | 0.85 |
| **INTRO** | 0.75 | 0.80 | 0.85 | 0.85 | 0.75 | 0.70 | 0.65 | 0.70 |

Bold diagonal = идеальный case (OUTRO→INTRO, SUSTAIN→SUSTAIN, DROP→DROP, BUILD→PEAK). Table — initial calibration, fine-tuned per ground-truth corpus в Phase 6.

Compute cost: 2D lookup. Стабильный numpy bulk path.

### 5.6 Harmonic v2 — Tonnetz primary

Текущий [score_harmonic_compat](../app/domain/transition/neural_mix.py#L248) использует Camelot как 40%-доминирующий сигнал. Меняем на:

```text
S_harmonics_v2 = 0.40 · tonnetz_cosine          # was 0.20
               + 0.25 · camelot_tiebreaker      # was 0.40
               + 0.20 · mfcc_cosine             # was 0.20 (unchanged)
               + 0.10 · spectral_contrast_prox  # was 0.10 (unchanged)
               + 0.05 · dissonance_inv_proxy    # was binary penalty
```

`camelot_tiebreaker` — это **flat 1.0 для dist ≤ 1, и continuous lookup только когда tonnetz_cosine < 0.4** (ambiguous case).

`dissonance_inv_proxy = max(0.0, 1.0 - 0.5*(diss_a + diss_b))` — было binary `-0.15` если оба > 0.4; теперь continuous.

**Atonal gate:** если оба трека `atonality=True`, мы **полностью** уходим из harmonic-based scoring — `S_harmonics_v2 = 0.85` (neutral preset) и weight убирается из суммы. Это правильный response — у атональных техно треков нет harmonic relationship чтобы её сохранять.

### 5.7 Bass clash explicit gate

Добавляем pre-check в [hard_constraints.py](../app/domain/transition/hard_constraints.py):

```python
def check_bass_clash(from_t, to_t, settings) -> str | None:
    """Returns None if OK, or rejection reason if bass conflict detected.

    Не hard-reject, а сигнальный warning который понижает S_bass.
    Hard-reject только на extreme clash.
    """
    if from_t.energy_sub is None or to_t.energy_sub is None:
        return None
    if from_t.energy_low is None or to_t.energy_low is None:
        return None
    if from_t.key_code is None or to_t.key_code is None:
        return None

    # Both tracks have prominent bass (>0.20 of total energy in sub+low)
    sub_low_a = from_t.energy_sub + from_t.energy_low
    sub_low_b = to_t.energy_sub + to_t.energy_low
    if sub_low_a < 0.20 or sub_low_b < 0.20:
        return None  # at least one bass-light — no clash risk

    # Camelot distance >= 3 (different roots, not just modal swap)
    if camelot_distance(from_t.key_code, to_t.key_code) < 3:
        return None  # same/adjacent root — bass overlap is OK

    # Hard clash: prominent bass, different roots, different modes
    return f"bass clash risk: both bass-heavy (sub+low {sub_low_a:.2f}/{sub_low_b:.2f}) with non-adjacent keys"
```

Если warning сработал → `S_bass *= 0.5` (post-compute multiplier). Не hard-reject — DJ может это починить через filter sweep / bass kill.

### 5.8 Energy v2 — continuous slope + short-term LUFS

[components/energy.py](../app/domain/transition/components/energy.py) сейчас:

1. Gauss на `delta_lufs` (preferred rise +0.5 LUFS)
2. LRA penalty (binary threshold)
3. Crest penalty (binary threshold)
4. Slope bonus (binary: same sign)

v2:

1. Gauss на `delta_lufs` — keep
2. LRA penalty — **continuous**: `penalty = max(0, lra_diff - threshold) / threshold * penalty_max`
3. Crest penalty — **continuous** аналогично
4. Slope bonus — **gradient**: `bonus = min(1.0, |slope_a| · |slope_b| / 0.5²) · sign_match`
5. **Short-term LUFS** на mix region (NEW) — `short_term_lufs_mean` уже есть в БД ([audio-schema.md:75](audio-schema.md#L75)), но не используется. Добавляем доп. член:
   ```
   short_term_score = exp(-(short_term_b - short_term_a - PREFERRED_RISE)² / 2σ²)
   ```
   и взвешиваем `0.6 · integrated_score + 0.4 · short_term_score`. Mix region matters больше чем track-mean.

### 5.9 Sequence cost (NEW, в optimization, не в scorer)

Добавляем в [app/domain/optimization/fitness.py](../app/domain/optimization/fitness.py) post-processing penalty:

```python
# В fitness function, после расчёта pairwise scores:
for i in range(2, len(track_order)):
    if last_3_transitions_all_same_preset:
        sequence_penalty += 0.05  # 5% штраф за монотонность
    if last_2_transitions_both_hard_reject:
        sequence_penalty += 0.10
```

Это не часть `TransitionScore` — это часть оптимизатора сета. `S_phrase` уже моделирует pair-level coherence; sequence cost моделирует set-level coherence.

### 5.10 Hard constraints v2

| Constraint | v1.3 | v2 | Why |
|---|---|---|---|
| BPM diff | > 10 → reject | > 10 → reject (unchanged) | Calibrated against Kim ISMIR 2020 + Pioneer DJ ±6% pitch |
| Camelot dist | ≥ 5 → reject | ≥ 6 → reject for tonal pairs; **no reject** for atonal pairs | Atonal techno (kicks + texture pads, no clear key center) валит на разнице 5-6, но фактически совместимо |
| Energy gap | > 6 LUFS → reject | > 6 LUFS → reject (unchanged) | Phase cancellation, PA-compression threshold |
| Bass clash | — | warning (post-compute `S_bass *= 0.5`) | NEW; see §5.7 |

### 5.11 Picker v2 — внести declarative recipe table

[picker.py](../app/domain/transition/picker.py) сейчас — императивный 7-уровневый if/elif. После Phase 0 patch и роста до 8-9 правил это станет нечитаемым.

Замена — declarative rule table:

```python
PICKER_RULES: list[PickerRule] = [
    PickerRule(
        name="hard_reject_rescue",
        condition=lambda score, fa, fb, ctx: score.hard_reject,
        decision=PickerDecision(NeuralMixTransition.ECHO_OUT, 0.55, "hard reject"),
        priority=1,
    ),
    PickerRule(
        name="drum_only_swap",
        condition=lambda score, fa, fb, ctx: (
            ctx.section_pair == SectionPairClass.DRUM_ONLY
            and score.drums > 0.85
        ),
        decision=PickerDecision(NeuralMixTransition.DRUM_SWAP, 0.92, "..."),
        priority=2,
    ),
    # ...
    PickerRule(
        name="filter_sweep_acid",
        condition=lambda score, fa, fb, ctx: (
            ctx.subgenre_pair in {SubgenrePairType.ACID_PAIR, SubgenrePairType.HYPNOTIC_PAIR}
            and score.bass < 0.5
        ),
        decision=PickerDecision(NeuralMixTransition.FILTER_SWEEP, 0.80, "..."),  # NEW preset
        priority=8,
    ),
    # default fallback at priority=99
]
```

Преимущества: testable, introspectable, addable без касания decision-функции, легко рендерить в panel (`local://transition/.../picker_trace`).

> **FILTER_SWEEP preset** — отдельный enum value добавляется в `NeuralMixTransition` + builder в [builders.py](../app/domain/transition/builders.py). Это **8-й preset** к существующим 7. Соответствует "Filter" preset'у djay Pro 5 ([Algoriddim Automix settings](https://help.algoriddim.com/user-manual/djay-pro-windows/settings/automix)).

### 5.12 `infer_intent` v2 — wire up `CONTRAST`

Текущий ([intent.py:71-96](../app/domain/transition/intent.py#L71)) — 4-факторная классификация по `set_position` и `energy_delta_lufs`, но возвращает 3 из 4 enum-значений. `CONTRAST` defined but never produced.

Добавляем:

```python
def infer_intent(set_position, energy_delta_lufs, *, template=None, last_intent=None) -> TransitionIntent:
    # ... existing RAMP_UP / COOL_DOWN / MAINTAIN logic ...

    # NEW: CONTRAST когда два MAINTAIN'а подряд + position в peak_zone
    if last_intent == TransitionIntent.MAINTAIN and peak_start < set_position < peak_end:
        if abs(energy_delta_lufs) < 0.5:  # static energy — нужен variety
            return TransitionIntent.CONTRAST

    return TransitionIntent.MAINTAIN
```

`last_intent` приходит из GA state (set position cursor). Adds stateful intent — но minor change в interface.

---

## 6. Detailed design (контракты + миграции)

### 6.1 New columns в `track_audio_features_computed`

**Не нужны.** Все нужные поля уже есть:

- `phrase_boundaries_ms`, `dominant_phrase_bars` ([track_features.py:127-128](../app/models/track_features.py#L127))
- `short_term_lufs_mean` ([audio-schema.md:75](audio-schema.md#L75))
- `energy_sub`, `energy_low`, ... ([audio-schema.md:80-86](audio-schema.md#L80))

### 6.2 New columns в `transitions`

```sql
ALTER TABLE transitions ADD COLUMN phrase_score REAL CHECK (phrase_score BETWEEN 0 AND 1);
ALTER TABLE transitions ADD COLUMN structure_score REAL CHECK (structure_score BETWEEN 0 AND 1);
ALTER TABLE transitions ADD COLUMN section_pair_class TEXT;  -- nullable, enum value
```

Все nullable. Legacy rows остаются работоспособными.

### 6.3 `SectionContext` extension

```python
@dataclass(frozen=True)
class SectionContext:
    from_section: SectionType | None
    to_section: SectionType | None

    @cached_property
    def section_pair_class(self) -> SectionPairClass:
        if self.from_section is None or self.to_section is None:
            return SectionPairClass.GENERIC
        # Reuse existing _DRUM_ONLY_SECTIONS frozenset
        if self.from_section in _DRUM_ONLY_SECTIONS and self.to_section in _DRUM_ONLY_SECTIONS:
            return SectionPairClass.DRUM_ONLY
        if self.from_section in _DROP_SECTIONS and self.to_section in _DROP_SECTIONS:
            return SectionPairClass.DROP_TO_DROP
        if self.from_section == SectionType.BREAKDOWN and self.to_section in {SectionType.INTRO, SectionType.RISE}:
            return SectionPairClass.BREAKDOWN_OUT
        if self.from_section in {SectionType.BUILD, SectionType.RISE} and self.to_section in {SectionType.DROP, SectionType.PEAK}:
            return SectionPairClass.BUILDUP_IN
        return SectionPairClass.GENERIC

    @property
    def is_drum_only_pair(self) -> bool:
        """Kept for backwards compat — wraps section_pair_class."""
        return self.section_pair_class == SectionPairClass.DRUM_ONLY
```

Старый property `is_drum_only_pair` остаётся — кейлы в picker не сломаются.

### 6.4 `TransitionScore` extension

```python
@dataclass
class TransitionScore:
    # v1.3 fields — unchanged for backwards compat
    bpm: float = 0.0
    energy: float = 0.0
    drums: float = 0.0
    bass: float = 0.0
    harmonics: float = 0.0
    vocals: float = 0.0
    overall: float = 0.0
    hard_reject: bool = False
    reject_reason: str | None = None
    best_transition: NeuralMixTransition | None = None

    # v2 NEW (all default 0.0 / None — legacy callers unaffected)
    phrase: float = 0.0
    structure: float = 0.0
    section_pair_class: str | None = None  # SectionPairClass.value or None
    bass_clash_warning: str | None = None
```

Public field rename: ничего не переименовываем. Только добавление.

### 6.5 `TransitionScorer.score()` signature — без breaking changes

```python
def score(
    self,
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    intent: TransitionIntent | None = None,
    section_context: SectionContext | None = None,
    subgenre_pair: SubgenrePairType | None = None,  # NEW kwarg, optional
) -> TransitionScore:
    """v2: section_context теперь реально используется."""
    # удаляем `del section_context`
    # передаём в _compute_score
```

### 6.6 `transition_persist_handler` — wire context

```python
async def transition_persist_handler(ctx, uow, data, scorer):
    # ... existing feature loading ...

    # NEW: resolve context if provided
    section_context = None
    subgenre_pair = None
    if data.get("section_context"):
        section_context = SectionContext.from_dict(data["section_context"])
    if data.get("mood_a") and data.get("mood_b"):
        subgenre_pair = classify_pair(data["mood_a"], data["mood_b"])

    intent = TransitionIntent(data["intent"]) if data.get("intent") else None

    score = scorer.score(
        feat_a, feat_b,
        intent=intent,
        section_context=section_context,
        subgenre_pair=subgenre_pair,
    )
    recipe = _build_recipe_or_none(
        score, feat_a, feat_b,
        section_context=section_context,
        subgenre_pair=subgenre_pair,
        intent=intent,
    )
    # ... rest ...
```

Schema `TransitionCreate` ([schemas/transition.py](../app/schemas/transition.py)) — добавить новые optional поля:

```python
class TransitionCreate(BaseModel):
    from_track_id: int
    to_track_id: int
    persist: bool = True
    scoring_profile: str | None = None
    # NEW
    intent: Literal["maintain", "ramp_up", "cool_down", "contrast"] | None = None
    section_context: SectionContextDTO | None = None  # {from_section, to_section}
    mood_a: str | None = None
    mood_b: str | None = None
```

### 6.7 Bulk scorer parity

`BulkTransitionScorer.score_pairs_bulk` ([bulk_scorer.py:618](../app/domain/transition/bulk_scorer.py#L618)) сейчас не принимает section/subgenre. Добавляем:

```python
def score_pairs_bulk(
    fa: FeatureArrays,
    pairs: Sequence[tuple[int, int]],
    intents: Iterable[TransitionIntent],
    *,
    section_contexts: Sequence[SectionContext | None] | None = None,  # NEW, length == len(pairs)
    subgenre_pairs: Sequence[SubgenrePairType | None] | None = None,  # NEW
) -> dict[tuple[int, int, str], float]:
    # ...
```

Parity test ([test_bulk_scorer_parity.py](../tests/domain/transition/test_bulk_scorer_parity.py)) расширяется: каждый scalar `scorer.score(...)` call параметризуется тем же section_context / subgenre_pair что и bulk path.

### 6.8 Performance budget

Текущий scalar path: ~80 µs / pair (per `tests/domain/transition/test_scorer_benchmark.py`).
v2 добавляет:
- `S_phrase`: ~5 µs (table lookup + arithmetic)
- `S_structure`: ~1 µs (2D table lookup)
- Section overlay: ~3 µs (mult + renormalize)
- Bass clash gate: ~2 µs

→ Бюджет: **+15 µs / pair**. На 540K pruned pairs (см. [transition-scoring.md § Pruning](transition-scoring.md)) — +8s wall-clock. Acceptable.

Bulk path: те же добавления векторизуются — overhead < 10ms per N=10K pool.

---

## 7. Migration plan — 7 phases, 7 PRs

Каждая фаза — отдельный branch + PR + green `make check` + zero behaviour regression on existing tests. Изменения веса между фазами могут двигать `overall` value, поэтому каждая фаза имеет **calibration anchor** — test fixture с эталонной парой треков и допустимым delta range.

### Phase 0 — Picker vocal heuristic (✓ уже в коде)

→ план: [docs/superpowers/plans/2026-05-13-picker-heuristic-refinement.md](superpowers/plans/2026-05-13-picker-heuristic-refinement.md)

**Статус:** код уже содержит fix — [picker.py:48-51](../app/domain/transition/picker.py#L48) показывает `_VOCAL_PRESENCE_PITCH_SALIENCE = 0.55` и `_VOCAL_PRESENCE_MIDBAND_RATIO = 0.40`. Plan document описывает работу как pending, но реально она исполнена. Остаётся только формально закрыть план (PR, теги).

**Что было сделано:** raise `_VOCAL_PRESENCE_PITCH_SALIENCE` 0.4 → 0.55, добавлен `_VOCAL_PRESENCE_MIDBAND_RATIO = 0.40` третьим сигналом.
**Гарантия:** acid техно больше не routes в VOCAL_CUT.

### Phase 1 — Wire section_context в scorer (1 PR)

**Что:** убрать `del section_context` из [scorer.py:75](../app/domain/transition/scorer.py#L75). Добавить `section_pair_class` property в `SectionContext`. Применить базовый overlay (`drum_only` → multiplicative weight shift, как в v1.3 picker, но в scorer'е).

**Затрагивает:** scorer.py, section_context.py, score.py (новое поле `section_pair_class`).

**Тесты:**
- `test_scorer_with_drum_only_context_relaxes_harmonic` — outro→intro pair с key dist=3 теперь имеет higher overall чем v1.3 baseline
- `test_scorer_without_context_unchanged` — нет section_context → ровно v1.3 поведение (regression guard)
- Parity test: bulk_scorer применяет тот же overlay

**Calibration:** 5 эталонных пар (drum_only / drop_to_drop / breakdown_out / buildup_in / generic) — snapshot expected `overall` values.

### Phase 2 — Phrase scoring (1 PR)

**Что:** добавить `S_phrase` ([scorer.py](../app/domain/transition/scorer.py) + новый компонент `components/phrase.py`). Прочитать `phrase_boundaries_ms` + `dominant_phrase_bars` из DB row → expose в `TrackFeatures.from_db`.

**Затрагивает:** components/phrase.py (new), scorer.py, weights.py, schemas, shared/features.py.

**DB migration:** `ALTER TABLE transitions ADD COLUMN phrase_score REAL` + parser в `transition_persist`.

**Тесты:**
- Synthetic features с одинаковым `dominant_phrase_bars = 16` → `S_phrase ≈ 1.0`
- Mismatched (8 vs 32) → `S_phrase ≈ 0.0`
- Phrase grid alignment to ±100ms off → near-1.0

**Calibration:** sample of 10 known-good pairs from existing sets, verify phrase score correlates with mix quality rating.

### Phase 3 — Structure scoring + section pair classification (1 PR)

**Что:** добавить `S_structure` с `_SECTION_PAIR_SCORE` 8x8 table. Расширить SectionContext до 5-классовой типологии. Применить per-class overlay из §5.3.

**Затрагивает:** section_context.py, scorer.py, weights.py, schemas, transitions schema.

**DB migration:** `ALTER TABLE transitions ADD COLUMN structure_score REAL, section_pair_class TEXT`.

**Тесты:**
- OUTRO→INTRO pair → `S_structure ≈ 1.0`
- DROP→OUTRO pair → `S_structure ≈ 0.55`
- Unknown section → `S_structure = 0.7` (neutral fallback)
- Pair class transitions: drum_only weighting kicks in only when both sides drum-only

**Calibration:** 8x8 table values fine-tuned to maximize correlation with hand-labeled ground truth.

### Phase 4 — Harmonic v2 (Tonnetz primary) + bass clash gate (1 PR)

**Что:** [§5.6](#56-harmonic-v2--tonnetz-primary) + [§5.7](#57-bass-clash-explicit-gate).

**Затрагивает:** neural_mix.py (`score_harmonic_compat` rewrite), hard_constraints.py (new `check_bass_clash`), weights.py.

**Backwards compat:** `S_harmonics` field name unchanged, public range unchanged [0, 1].

**Тесты:**
- Atonal pair → `S_harmonics ≈ 0.85` neutral
- Tonal pair with high Tonnetz cos but Camelot dist=2 → `S_harmonics > 0.7` (Tonnetz drives)
- Bass-heavy pair, keys 2 apart → `S_bass *= 0.5` warning surfaces

**Calibration:** before/after on 50 pairs from existing sets. Mean shift should be < 0.05.

### Phase 5 — Energy v2 + intent v2 (`CONTRAST`) (1 PR)

**Что:** [§5.8](#58-energy-v2--continuous-slope--short-term-lufs) + [§5.12](#512-infer_intent-v2--wire-up-contrast).

**Затрагивает:** components/energy.py, intent.py.

**Тесты:**
- Two static energy tracks in peak zone after MAINTAIN → `infer_intent → CONTRAST`
- Slope alignment gradient: |slope_a| · |slope_b| close to 0.5 → max bonus

### Phase 6 — Sequence cost in optimizer + picker rule-table (1 PR)

**Что:** [§5.9](#59-sequence-cost-new-в-optimization-не-в-scorer) + [§5.11](#511-picker-v2--внести-declarative-recipe-table).

**Затрагивает:** app/domain/optimization/fitness.py (sequence_penalty), picker.py (declarative rules), tests.

**FILTER_SWEEP preset:** Phase 6 also adds the 8th NeuralMixTransition enum value + builder. Picker rule for acid/hypnotic subgenre → FILTER_SWEEP when bass clash.

**Тесты:**
- Sequence with 3 ECHO_OUT in a row → fitness penalty applied
- ACID_PAIR + bass=0.4 → FILTER_SWEEP selected, recipe materializes filter envelope

### Phase 7 — Long-term (separate roadmap)

Не в этом PR-цепочке, отдельный плановый цикл:

- **L4 demucs stem precompute** — `vocal_stem_energy`, `drum_stem_energy`, `bass_stem_energy`, `harmonic_stem_energy` as features в `track_audio_features_computed`. Replace `_vocal_active` heuristic в picker'е с real `vocal_stem_energy > 0.05`. ~30 sec / track on CPU, ~5-7 sec on GPU. Stage L4 как "extra extra" (требует `[stems]` extra + 100MB model download).
- **Taxonomy unification** — `VOCAL_SUSTAIN/HARMONIC_SUSTAIN` → `STEM_SUSTAIN(target)`; `VOCAL_CUT/DRUM_CUT` → `STEM_CUT(target)`. DB migration of `transitions.fx_type` enum.
- **allin1 evaluation** — replace separate beat/downbeat/phrase analyzers with `allin1` end-to-end model, evaluate against current MIR pipeline on 100-track sample.
- **EDMFormer evaluation** — replace `StructureAnalyzer` (current section detection) с EDMFormer pretrained checkpoint, measure F1 on hand-labeled set of 50 techno tracks.
- **Documentation sync** — переписать [docs/transition-scoring.md § Runtime Wiring](transition-scoring.md) под Phase 1-6 actuals. Удалить ссылки на `score_set_transitions` / `build_section_context` (фантомные).

---

## 8. Risks

| Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|
| Calibration drift между фазами — `overall` смещается, GA выбирает другие сеты | High | Medium | Calibration anchors per phase + golden set comparison; rollback flag `transition_v2_enabled: false` в config |
| Bulk scorer parity ломается при добавлении phrase/structure scoring | Medium | High | Parity test расширяется в Phase 2, Phase 3 — обязательное условие merge |
| `phrase_boundaries_ms` reliable не для всех треков (некоторые имеют `[]` или None) | High | Low | `S_phrase` gracefully degrades к 0.5 (neutral) при missing data, как уже делает scorer для других missing fields |
| `transitions.fx_type` column добавление нового enum value (FILTER_SWEEP) сломает legacy reader | Low | Medium | FILTER_SWEEP не CHECK-constraint enum (это TEXT в SQLite / VARCHAR в PG) — adding value не migration-breaking |
| Section data low-quality для треков с <70 sections (intro/outro могут быть mis-detected) | Medium | Low | `S_structure` defaults to 0.7 (neutral) when section type unavailable |
| `entity_create(transition)` callers не обновятся под новый signature (новые kwargs) | Low | Low | Все новые kwargs optional с default=None — backwards compat |
| Документация в [docs/transition-scoring.md](transition-scoring.md) описывает несуществующее (`score_set_transitions`) — readers тратят время | High (already true) | Low | Phase 7 explicit doc sync; meanwhile add WARNING note в head of docs/transition-scoring.md |
| GA performance падает от +15µs/pair × 540K pairs | Low | Medium | +8s wall-clock measured; для критичных workloads — `use_processes=True` оффсетит |

---

## 9. Open questions

1. **Ground-truth corpus для calibration.** У нас нет официального "best DJ set" dataset. Откуда брать `transition_quality_rating` ∈ [0, 1] на пары? Варианты:
   - Manual rating пилотных 100 пар (1-2 часа DJ-времени)
   - Использовать `track_feedback` table (пользователь явно ставит "yes/no" на transitions) — но эта таблица сейчас почти пустая
   - Bootstrapped: запустить v1.3 на all-pairs, отсортировать, ручная аудит-выборка топ-20 и bottom-20

2. **Section overlay multipliers ×1.30, ×0.70 etc. — откуда числа?** Сейчас они educated guess из DJ practice papers. Реально надо bench-fitting на ground truth (см. #1).

3. **`bass_clash_warning` — surface в panel UI?** Сейчас оно живёт как поле в `TransitionScore.bass_clash_warning: str | None`. Panel может рендерить как чип "⚠ bass clash risk". Решение об UX откладывается.

4. **`CONTRAST` intent stateful через `last_intent` — это правильный design?** Альтернатива — stateless `S_variety` компонент. State делает scorer less pure. Можно вместо этого сделать sequence-level fitness penalty (как в §5.9). **Предлагаю:** убрать stateful CONTRAST из scorer, оставить как fitness-level concept.

5. **L4 demucs precompute — стоит ли свеч?** 23,768 tracks × 30 сек CPU = 200 часов. Только под active sets (10-50 треков за раз) — реалистично. Phase 7 evaluation должен ответить на cost/benefit.

6. **Removal of dead `CONTRAST` weights vs keeping for forward-compat?** Если в #4 решаем убрать stateful CONTRAST, dead код всё равно остаётся в `INTENT_WEIGHT_MODIFIERS`. Cleanup в Phase 5.

---

## 10. Appendix A — полные числовые таблицы

### A.1 v2 weights per intent (после section overlay = ×1.0 / GENERIC)

| Component | MAINTAIN | RAMP_UP | COOL_DOWN | CONTRAST† |
|---|---:|---:|---:|---:|
| bpm | 0.20 | 0.16 | 0.15 | 0.12 |
| energy | 0.13 | 0.22 | 0.20 | 0.15 |
| drums | 0.18 | 0.05 | 0.05 | 0.12 |
| bass | 0.13 | 0.08 | 0.13 | 0.18 |
| harmonics | 0.13 | 0.20 | 0.18 | 0.10 |
| vocals | 0.08 | 0.08 | 0.10 | 0.15 |
| **phrase** | 0.10 | 0.15 | 0.13 | 0.10 |
| **structure** | 0.05 | 0.06 | 0.06 | 0.08 |
| **Σ** | 1.00 | 1.00 | 1.00 | 1.00 |

† CONTRAST остаётся для future use; phase 6 решит, оставлять ли stateful flow или вынести как sequence-level concern.

### A.2 Section pair overlay (multiplicative, до renormalize)

| Pair class | drums | bass | harmonics | vocals | phrase | structure | bpm | energy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DRUM_ONLY | 1.30 | 0.70 | 0.40 | 0.30 | 1.30 | 1.50 | 1.10 | 0.95 |
| DROP_TO_DROP | 1.20 | 1.20 | 0.80 | 0.80 | 1.10 | 1.30 | 1.05 | 1.10 |
| BREAKDOWN_OUT | 0.80 | 0.80 | 1.40 | 1.20 | 0.90 | 1.20 | 0.95 | 1.05 |
| BUILDUP_IN | 1.10 | 0.90 | 1.10 | 1.00 | 1.20 | 1.40 | 1.00 | 1.15 |
| GENERIC | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

После умножения — `weight[k] = base_weight[k] * overlay[k]` затем нормализация в сумму 1.0.

### A.3 Updated hard constraints v2

| Constraint | Threshold | Setting key | Notes |
|---|---|---|---|
| BPM diff (with double/half awareness) | > 10 | `transition.hard_reject_bpm_diff` | unchanged |
| Camelot distance — tonal pair | ≥ 6 | `transition.hard_reject_camelot_dist_tonal` (new) | raised from 5 |
| Camelot distance — atonal pair | no reject | — | atonality=True on both sides → skip |
| Energy gap | > 6.0 LUFS | `transition.hard_reject_energy_gap_lufs` | unchanged |
| Bass clash | warning only | `transition.bass_clash_penalty` (new, default 0.5) | post-score multiplier on `S_bass` |

---

## 11. Appendix B — что значат метрики для DJ

> Эта секция для не-программистов из команды (если такие будут читать) — кратко переводит формулу обратно на язык DJ practice.

| Component | Что DJ услышит, когда score высокий | Что услышит при низком |
|---|---|---|
| `S_bpm` | Биты совпадают, sync кнопка работает чисто, можно блендить 32 бара | Один трек "плывёт" против другого, kicks разъезжаются |
| `S_energy` | Громкость не прыгает на переходе, mix остаётся в груве | Один трек "проседает" или прыгает на 4 dB вверх |
| `S_drums` | Кики совпадают по тону, ритм-секции встают друг на друга | Два разных кика хлюпают, два разных hat'a гремят сверху |
| `S_bass` | Бас одной партии красиво подменяется другим на downbeat'е | Mud в low-end, phase cancellation, пропадает kick |
| `S_harmonics` | Pad'ы и leads звучат гармонично (или оба атональны и не мешают) | Минор + мажор клэшат, вокальная мелодия конфликтует с pad'ом |
| `S_vocals` | Один вокал держится, второй мягко входит, либо обоих нет | Два вокала наезжают друг на друга, или вокал клэшит с лидом |
| `S_phrase` (NEW) | Mix идёт на 16-бар фразовой границе, downbeat'ы align'ятся | Mix съезжает на 2-3 бара, ощущение "off-grid" |
| `S_structure` (NEW) | OUTRO→INTRO, всё logical — DJ-friendly intro/outro как и задумывали продюсеры | DROP→OUTRO, peak умирает на полпути |

`overall` — взвешенная сумма; для разных интентов (RAMP_UP / COOL_DOWN) веса смещаются — DJ играющий warm-up больше слушает `S_energy` и `S_structure`, а peak-time DJ слушает `S_drums` и `S_bass`.

---

## 12. Sources

### Academic

- Kim et al., *A Computational Analysis of Real-World DJ Mixes*, ISMIR 2020 — [archives.ismir.net/ismir2020/paper/000352.pdf](https://archives.ismir.net/ismir2020/paper/000352.pdf)
- Sowula & Knees, *Mosaikbox: Improving Fully Automatic DJ Mixing Through Rule-Based Stem Modification and Precise Beat-Grid Estimation*, ISMIR 2024 — [repositum.tuwien.at](https://repositum.tuwien.at/handle/20.500.12708/212628)
- Vande Veire & De Bie, *From Raw Audio to a Seamless Mix: Drum and Bass Auto-DJ*, JASMP 2018 — [link.springer.com](https://link.springer.com/article/10.1186/s13636-018-0134-8)
- Zehren et al., *Automatic Detection of Cue Points*, CMJ 46(3) 2022 — [direct.mit.edu/comj](https://direct.mit.edu/comj/article/46/3/67/117159/Automatic-Detection-of-Cue-Points-for-the)
- Bibbó & Faraldo, *A New Compatibility Measure for Harmonic EDM Mixing*, ISMIR 2022 LBD
- Chen et al., *Automatic DJ Transitions with Differentiable Audio Effects and GANs*, ICASSP 2022 — [arXiv:2110.06525](https://arxiv.org/abs/2110.06525)
- Ishizaki et al., *Full-Automatic DJ Mixing System with Optimal Tempo Adjustment*, ISMIR 2009
- Davies et al., *AutoMashUpper*, ISMIR 2013
- *EDMFormer: Genre-Specific Self-Supervised Learning for Music Structure Segmentation*, 2025 — [arXiv:2603.08759](https://arxiv.org/html/2603.08759)
- Défossez et al., *Hybrid Transformers for Music Source Separation*, 2022 — [arXiv:2211.08553](https://arxiv.org/abs/2211.08553)

### Industry / SOTA tools

- [Algoriddim djay Pro Neural Mix Overview](https://help.algoriddim.com/user-manual/djay-pro-mac/neural-mix/overview)
- [Algoriddim djay 5.3 update — Crossfaders & multi-stem FX](https://musictech.com/news/gear/algoriddim-free-dj-software-djay-pro-ai-automix-and-neural-mix/)
- [Algoriddim Automix settings — preset list](https://help.algoriddim.com/user-manual/djay-pro-windows/settings/automix)
- [AudioShake × Algoriddim Neural Mix collaboration](https://www.audioshake.ai/post/algoriddim-djaypro-neural-mix)
- [Rekordbox 7 overview](https://rekordbox.com/en/feature/overview/) — AI vocal detection, Phrase Analysis, Intelligent Cue Creation
- [Rekordbox 7 — ClubReady DJ School Guide 2025](https://www.clubreadydjschool.com/tribe-talk/dj-gear-and-software/rekordbox-7-the-ultimate-guide-for-djs-in-2025/)
- [Serato Stems Pro 3.0 — pad FX per stem](https://serato.com/dj/pro)
- [Mixxx 2.5.4 release](https://mixxx.org/news/2025-12-14-mixxx-2_5_4-released/)
- [Mixxx GSoC 2025 — Demucs v4 ONNX integration](https://mixxx.org/news/2025-10-27-gsoc2025-demucs-to-onnx-dhunstack/)
- [allin1 — All-In-One Music Structure Analyzer](https://github.com/mir-aidj/all-in-one)
- [demucs (FAIR)](https://github.com/facebookresearch/demucs)
- [madmom — RNN downbeat tracking](https://madmom.readthedocs.io/en/v0.16/modules/features/downbeats.html)
- [MSAF — Music Structure Analysis Framework](https://github.com/urinieto/msaf)

### DJ practice

- [DJ TechTools — Phrasing The Perfect Mix](https://djtechtools.com/2009/01/26/phrasing-the-perfect-mix/)
- [Native Instruments — Phrase Mixing](https://blog.native-instruments.com/phrase-mixing/)
- [Universe of Tracks — Techno Track Structure](https://universeoftracks.com/the-ultimate-guide-to-techno-track-structure/)
- [DJ.Studio — EQ Mixing](https://dj.studio/blog/dj-eqmixing)
- [Crossfader — Mix Like A Techno DJ](https://wearecrossfader.co.uk/blog/mix-like-a-techno-dj-3-ways-to-mix-techno/)
- [Mixed In Key — Harmonic Mixing Guide](https://mixedinkey.com/harmonic-mixing-guide/)
- [Pheek — Bass Line and Low-End Mixing](https://audioservices.studio/blog/bass-line-and-low-end-mixing-tips)

### Internal (project)

- [docs/transition-scoring.md](transition-scoring.md) — v1.3 формула, 7 пресетов, Camelot, recipe engine
- [docs/research/2026-04-08-techno-transitions-research.md](research/2026-04-08-techno-transitions-research.md) — академическая база
- [docs/research/2026-05-13-neural-mix-transitions-deep-dive.md](research/2026-05-13-neural-mix-transitions-deep-dive.md) — picker deep dive
- [docs/superpowers/plans/2026-05-13-picker-heuristic-refinement.md](superpowers/plans/2026-05-13-picker-heuristic-refinement.md) — Phase 0 spec
- [docs/audio-pipeline.md](audio-pipeline.md) — 18 analyzers, tiered L1-L4
- [docs/audio-schema.md](audio-schema.md) — 47 features
- [docs/domain-glossary.md](domain-glossary.md) — DJ терминология
