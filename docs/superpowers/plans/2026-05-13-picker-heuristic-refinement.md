# Picker Heuristic Refinement (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить false-positive в `_vocal_active()` где acid/melodic техно-треки (TB-303-style лиды) ошибочно классифицируются как "vocal-active" и приводят к выбору пресета `VOCAL_CUT` вместо подходящего `ECHO_OUT` / `FADE`.

**Architecture:** Минимальное изменение в `app/domain/transition/picker.py` — поднять порог `_VOCAL_PRESENCE_PITCH_SALIENCE` с 0.4 до 0.55 и добавить опциональный третий проверочный фильтр через распределение энергии по `energy_bands` (вокал концентрируется в lowmid+mid = 300-3000 Hz, acid lead — в highmid 3-7 kHz). Сохраняем graceful degradation: если band-data отсутствует, fallback к 2-сигнальной проверке. Никаких изменений в БД, recipe schema или enum'ах пресетов.

**Tech Stack:** Python 3.12, pytest, ruff, mypy (strict). Никаких новых зависимостей.

**Scope boundaries (вне этого плана):**
- FILTER_SWEEP preset — отдельный Phase 2 plan
- `essentia.VoicingDetection()` analyzer — отдельный Phase 2 plan
- demucs stem separation — Phase 3
- Taxonomy canonicalisation (STEM_SUSTAIN/STEM_CUT unification) — Phase 3
- Re-scoring уже persisted transitions — не нужно, новые `entity_create(entity="transition")` автоматически возьмут обновлённую логику

**Spec source:** [`docs/research/2026-05-13-neural-mix-transitions-deep-dive.md`](../../research/2026-05-13-neural-mix-transitions-deep-dive.md) § 7.1 "Краткосрочные".

---

## File Structure

| File | Role | Action |
|---|---|---|
| `app/domain/transition/picker.py` | Pure-Python decision tree (10 funcs, 230 lines). Domain layer — никаких IO/DB. | Modify (~20 lines: 1 new const, rewrite `_vocal_active`, raise existing threshold) |
| `tests/domain/transition/test_picker.py` | pytest, in-memory. Уже имеет `_ok_score()` / `_track()` helpers — переиспользуем. | Modify (~80 lines: 5 новых test cases для acid regression + boundary cases) |
| `docs/transition-scoring.md` | Сводная документация по 6-component scoring + 7 пресетам. | Modify (~25 lines: новый section "Known Limitations: Vocal Detection") |
| `docs/audio-pipeline.md` | Сводная документация по audio analyzer registry. | Modify (~10 lines: уточнить семантику `pitch_salience_mean` в gotchas) |

Каждая задача коммитится отдельно — 4 commits total.

---

## Task 1: Regression test для acid false-positive (TDD red phase)

**Files:**
- Modify: `tests/domain/transition/test_picker.py`

**Rationale:** Сначала фиксируем багу через failing test. Затем (Task 2) исправляем код. Это TDD красная фаза — тест зелёный после Task 2.

- [ ] **Step 1: Прочитать существующий test_picker.py чтобы понять где добавить тест**

Run:
```bash
grep -n "Rule 3:\|def test_vocal\|class TestVocal\|_vocal_active\|VOCAL_CUT\|VOCAL_SUSTAIN" tests/domain/transition/test_picker.py
```

Ожидание: найти существующий блок тестов для правила #3 (`vocal-active A`). Новый regression test добавить **под** существующим блоком vocal-related тестов с явным комментарием-маркером.

- [ ] **Step 2: Добавить регрессионный тест в конец секции vocal-rule тестов**

Найти в `tests/domain/transition/test_picker.py` секцию-разделитель `# ── Rule 3:` (или эквивалент) и добавить **сразу после неё**:

```python
# ── Rule 3 regression: acid-lead false-positive ────────────────────

def test_acid_lead_not_classified_vocal_active() -> None:
    """Acid techno (TB-303-style lead) must NOT trigger vocal-active heuristic.

    Such tracks have high pitch_salience (0.7-0.9) and high spectral_centroid
    (2500-4000 Hz) from the resonant filter peak, but their energy concentrates
    in highmid (3-7 kHz), not lowmid+mid (300-3000 Hz) where vocal formants live.

    Without the midband-ratio filter, picker would route acid → acid pairs to
    VOCAL_CUT instead of the appropriate ECHO_OUT/FADE — see
    docs/research/2026-05-13-neural-mix-transitions-deep-dive.md § 5.3.
    """
    acid_a = _track(
        pitch_salience_mean=0.85,
        spectral_centroid_hz=3200.0,
        # energy_bands order: [sub, low, lowmid, mid, highmid, high]
        # Energy concentrated in highmid (index 4): acid resonance peak.
        energy_bands=[0.05, 0.10, 0.08, 0.07, 0.45, 0.25],
    )
    acid_b = _track(
        pitch_salience_mean=0.78,
        spectral_centroid_hz=2900.0,
        energy_bands=[0.05, 0.10, 0.10, 0.08, 0.42, 0.25],
    )
    score = _ok_score()

    decision = pick_neural_mix(score, acid_a, acid_b)

    assert decision.transition is not NeuralMixTransition.VOCAL_CUT, (
        f"acid pair routed to VOCAL_CUT (false positive). "
        f"Decision: {decision.transition.value}, reason: {decision.reason}"
    )
    assert decision.transition is not NeuralMixTransition.VOCAL_SUSTAIN, (
        "acid pair must not route to VOCAL_SUSTAIN either"
    )
```

- [ ] **Step 3: Запустить тест, убедиться что красный**

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
uv run pytest tests/domain/transition/test_picker.py::test_acid_lead_not_classified_vocal_active -v
```

Expected output:
```text
FAILED ... acid pair routed to VOCAL_CUT (false positive). Decision: vocal_cut, reason: ...
```

Это **подтверждает баг**: текущий picker классифицирует acid-acid как vocal_cut.

- [ ] **Step 4: Commit failing test**

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
git add tests/domain/transition/test_picker.py
git commit -F /tmp/commit-msg-task1.txt
```

Create `/tmp/commit-msg-task1.txt` через Write tool с содержимым:
```bash
test(transition): add acid-lead false-positive regression for vocal_active

Reproduces the case where acid techno tracks with high pitch_salience and
high spectral_centroid (but energy concentrated in highmid, not vocal band)
are mis-classified as vocal-active by the picker — triggering VOCAL_CUT
preset selection for acid → acid transitions.

Test is red; Task 2 (midband-ratio filter + raised pitch_salience threshold)
will make it green.

Spec: docs/research/2026-05-13-neural-mix-transitions-deep-dive.md § 5.3

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task 2: Реализовать midband-ratio фильтр + поднять порог pitch_salience (TDD green phase)

**Files:**
- Modify: `app/domain/transition/picker.py:44-83`

- [ ] **Step 1: Прочитать текущие пороги и `_vocal_active()` чтобы знать точный контекст**

Run:
```bash
sed -n '40,90p' /Users/laptop/dev/dj-music-plugin/app/domain/transition/picker.py
```

Expected: показать константы `_VOCAL_PRESENCE_PITCH_SALIENCE = 0.4`, `_VOCAL_PRESENCE_CENTROID_HZ = 2200.0`, и функцию `_vocal_active()`.

- [ ] **Step 2: Поднять `_VOCAL_PRESENCE_PITCH_SALIENCE` с 0.4 до 0.55**

Edit `app/domain/transition/picker.py`:

```python
# Replace:
_VOCAL_PRESENCE_PITCH_SALIENCE = 0.4
# With:
_VOCAL_PRESENCE_PITCH_SALIENCE = 0.55
```

Замена единственная — `replace_all=false`, exact match.

- [ ] **Step 3: Добавить новую константу `_VOCAL_PRESENCE_MIDBAND_RATIO`**

В `app/domain/transition/picker.py`, после строки `_VOCAL_LOW_PITCH_SALIENCE = 0.3` добавить:

```python
# Replace:
_VOCAL_LOW_PITCH_SALIENCE = 0.3

_HARMONIC_MOTIF_MAX_PITCH_SALIENCE = 0.35
# With:
_VOCAL_LOW_PITCH_SALIENCE = 0.3
_VOCAL_PRESENCE_MIDBAND_RATIO = 0.40

_HARMONIC_MOTIF_MAX_PITCH_SALIENCE = 0.35
```

Назначение константы: минимальная доля энергии в (lowmid + mid) = 300-3000 Hz относительно суммы всех 6 bands. Вокал — 0.40+, acid lead — 0.15-0.25.

- [ ] **Step 4: Переписать `_vocal_active()` с midband fallback**

Edit `app/domain/transition/picker.py` — заменить функцию `_vocal_active`:

```python
# Replace:
def _vocal_active(t: TrackFeatures) -> bool:
    return (
        t.pitch_salience_mean is not None
        and t.spectral_centroid_hz is not None
        and t.pitch_salience_mean > _VOCAL_PRESENCE_PITCH_SALIENCE
        and t.spectral_centroid_hz > _VOCAL_PRESENCE_CENTROID_HZ
    )
# With:
def _vocal_active(t: TrackFeatures) -> bool:
    """Heuristic detection of vocal presence using up to 3 spectral proxies.

    A track is treated as "vocal-active" only when:

    1. ``pitch_salience_mean`` indicates sustained pitched content
       (threshold ``_VOCAL_PRESENCE_PITCH_SALIENCE``).
    2. ``spectral_centroid_hz`` lies in/above the vocal range
       (threshold ``_VOCAL_PRESENCE_CENTROID_HZ``).
    3. *If* per-band energies are available (``energy_bands`` populated with
       6 values), energy in the vocal frequency band
       (lowmid + mid = 300-3000 Hz, indices 2-3) accounts for at least
       ``_VOCAL_PRESENCE_MIDBAND_RATIO`` of total spectral energy.

    The third filter rejects acid-lead false-positives: TB-303-style
    resonant leads share signals (1)+(2) with vocals but concentrate
    their energy in highmid (3-7 kHz), not the formant band. When
    ``energy_bands`` is missing (legacy rows), we fall back to the
    2-signal check to avoid regressing older library entries.
    """
    if t.pitch_salience_mean is None or t.spectral_centroid_hz is None:
        return False
    if t.pitch_salience_mean <= _VOCAL_PRESENCE_PITCH_SALIENCE:
        return False
    if t.spectral_centroid_hz <= _VOCAL_PRESENCE_CENTROID_HZ:
        return False

    # Optional midband-ratio filter — only enforced when band data exists.
    if t.energy_bands is not None and len(t.energy_bands) >= 6:
        total = sum(t.energy_bands)
        if total > 1e-6:
            midband = t.energy_bands[2] + t.energy_bands[3]
            if midband / total < _VOCAL_PRESENCE_MIDBAND_RATIO:
                return False

    return True
```

- [ ] **Step 5: Запустить regression test и убедиться что зелёный**

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
uv run pytest tests/domain/transition/test_picker.py::test_acid_lead_not_classified_vocal_active -v
```

Expected output: `PASSED` — потому что midband (0.08+0.07)/(0.05+0.10+0.08+0.07+0.45+0.25) = 0.15 < 0.40, фильтр режет false-positive.

- [ ] **Step 6: Запустить ВЕСЬ test_picker.py — убедиться что ничего не сломано**

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
uv run pytest tests/domain/transition/test_picker.py -v
```

Expected: все существующие тесты по-прежнему зелёные. Если какие-то падают из-за изменения порога 0.4→0.55 — это значит fixture в тех тестах с граничным значением pitch_salience между 0.4 и 0.55; см. Task 3.

- [ ] **Step 7: Commit fix**

Create `/tmp/commit-msg-task2.txt`:
```bash
fix(transition): reject acid false-positives in vocal_active heuristic

Raise _VOCAL_PRESENCE_PITCH_SALIENCE from 0.4 to 0.55 and add a third
gate _VOCAL_PRESENCE_MIDBAND_RATIO=0.40 on energy_bands distribution.

Acid leads (TB-303 resonance) share pitch_salience + centroid signals
with vocals but concentrate energy in highmid (3-7 kHz), not the
300-3000 Hz formant band. Without the midband filter, hypnotic/acid
roller sets routed almost every transition to VOCAL_CUT.

Fallback path (no energy_bands) keeps legacy rows working with the
2-signal check.

Spec: docs/research/2026-05-13-neural-mix-transitions-deep-dive.md § 7.1.A

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/domain/transition/picker.py
git commit -F /tmp/commit-msg-task2.txt
```

---

## Task 3: Дополнительные boundary tests (positive + edge cases)

**Files:**
- Modify: `tests/domain/transition/test_picker.py`

**Rationale:** Зафиксировать что (a) реальные вокальные треки остаются классифицированными как vocal-active; (b) граничные значения и legacy rows (без `energy_bands`) деградируют корректно.

- [ ] **Step 1: Добавить positive-case test — вокал распознаётся**

В `tests/domain/transition/test_picker.py`, в той же секции `# ── Rule 3 regression`, **после** `test_acid_lead_not_classified_vocal_active`, добавить:

```python
def test_real_vocal_track_classified_vocal_active() -> None:
    """Positive case: vocal track with concentrated midband energy passes the heuristic.

    Lead vocal has pitch_salience > 0.55, centroid in vocal range (2-3 kHz),
    AND energy concentrated in lowmid+mid = 300-3000 Hz (formant band).
    """
    vocal_a = _track(
        pitch_salience_mean=0.70,
        spectral_centroid_hz=2500.0,
        # Energy concentrated in lowmid+mid: typical vocal formant distribution.
        energy_bands=[0.05, 0.10, 0.25, 0.30, 0.20, 0.10],
    )
    vocal_b = _track(
        pitch_salience_mean=0.65,
        spectral_centroid_hz=2400.0,
        energy_bands=[0.05, 0.10, 0.28, 0.27, 0.20, 0.10],
    )
    score = _ok_score()

    decision = pick_neural_mix(score, vocal_a, vocal_b)

    assert decision.transition is NeuralMixTransition.VOCAL_CUT, (
        f"two vocal-active tracks should still route to VOCAL_CUT "
        f"(rule 3). Got: {decision.transition.value}"
    )
```

- [ ] **Step 2: Добавить boundary test — pitch_salience на нижней границе**

После предыдущего теста добавить:

```python
def test_vocal_active_pitch_salience_below_new_threshold() -> None:
    """Track with pitch_salience = 0.54 (just below 0.55 threshold) is NOT vocal-active.

    Guards against regression if the threshold is loosened back toward 0.4.
    """
    boundary = _track(
        pitch_salience_mean=0.54,
        spectral_centroid_hz=3000.0,
        energy_bands=[0.05, 0.10, 0.25, 0.25, 0.25, 0.10],  # vocal-like distribution
    )
    other = _track(
        pitch_salience_mean=0.20,
        spectral_centroid_hz=1800.0,
        energy_bands=[0.10, 0.20, 0.25, 0.25, 0.15, 0.05],
    )
    score = _ok_score()

    decision = pick_neural_mix(score, boundary, other)

    # Rule 3 should NOT fire (pitch_salience below new threshold).
    # Decision falls through to rule 4/6/7 — exact result depends on other
    # signals; we only assert rule 3 didn't trigger.
    assert decision.transition not in {
        NeuralMixTransition.VOCAL_CUT,
        NeuralMixTransition.VOCAL_SUSTAIN,
    }, (
        f"pitch_salience 0.54 (below 0.55 threshold) must not trigger rule 3. "
        f"Got: {decision.transition.value}, reason: {decision.reason}"
    )
```

- [ ] **Step 3: Добавить fallback test — legacy row без `energy_bands`**

После предыдущего теста:

```python
def test_vocal_active_fallback_without_energy_bands() -> None:
    """Legacy rows without energy_bands must still work via 2-signal fallback.

    Older L1/L2 features may have pitch_salience + centroid but missing
    energy_bands (the column was added later in the pipeline). The midband
    gate must degrade gracefully and not reject these rows.
    """
    legacy_vocal = _track(
        pitch_salience_mean=0.65,
        spectral_centroid_hz=2400.0,
        energy_bands=None,  # legacy: no band breakdown
    )
    other_vocal = _track(
        pitch_salience_mean=0.60,
        spectral_centroid_hz=2500.0,
        energy_bands=None,
    )
    score = _ok_score()

    decision = pick_neural_mix(score, legacy_vocal, other_vocal)

    # Both pass 2-signal check → rule 3 fires → VOCAL_CUT (both vocal-active).
    assert decision.transition is NeuralMixTransition.VOCAL_CUT, (
        f"legacy 2-signal vocal pair must still route to VOCAL_CUT. "
        f"Got: {decision.transition.value}"
    )
```

- [ ] **Step 4: Добавить degenerate test — malformed `energy_bands` (короче 6 элементов)**

После предыдущего теста:

```python
def test_vocal_active_handles_short_energy_bands() -> None:
    """Malformed energy_bands (fewer than 6 elements) falls back to 2-signal check.

    Defensive: if a future pipeline change produces incomplete bands,
    picker must not crash with IndexError.
    """
    weird = _track(
        pitch_salience_mean=0.70,
        spectral_centroid_hz=2600.0,
        energy_bands=[0.5, 0.5],  # only 2 bands instead of 6
    )
    other = _track(
        pitch_salience_mean=0.65,
        spectral_centroid_hz=2400.0,
        energy_bands=None,
    )
    score = _ok_score()

    # Must not raise.
    decision = pick_neural_mix(score, weird, other)

    # Both treated as vocal-active via 2-signal fallback (len check guards midband).
    assert decision.transition is NeuralMixTransition.VOCAL_CUT
```

- [ ] **Step 5: Запустить весь файл test_picker.py — все 4 новых теста плюс существующие**

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
uv run pytest tests/domain/transition/test_picker.py -v
```

Expected: все тесты PASS. Если test_real_vocal_track_classified_vocal_active падает с decision != VOCAL_CUT — посмотри что score.energy низкий (< 0.85 у _ok_score) и попадает в rule 5 (DRUM_CUT). Решение: в score `_ok_score()` энергия 0.85 ниже порога RAMP_UP, не должно срабатывать. Если падает — проверить что `_energy_delta_lufs(vocal_a, vocal_b)` not None и не > 2.0; для vocal_a и vocal_b в тесте integrated_lufs не задан, _energy_delta_lufs вернёт None → rule 5 не firе → продолжает к default. Должно работать.

- [ ] **Step 6: Запустить полный test suite модуля — убедиться что нет ломки соседних тестов**

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
uv run pytest tests/domain/transition/ -v
```

Expected: все тесты в `tests/domain/transition/` зелёные.

Если падают существующие тесты (например `test_picker.py::test_vocal_active_routes_to_vocal_cut` использовал pitch_salience=0.5 и centroid > 2200) — это значит fixture попадает в новый "deadzone" 0.5-0.55. Fix: повысить pitch_salience в fixture с 0.5 до 0.7 + добавить energy_bands с midband ≥ 0.40. **Не понижай порог обратно** — fixtures должны отражать новый контракт.

- [ ] **Step 7: Commit edge-case coverage**

Create `/tmp/commit-msg-task3.txt`:
```bash
test(transition): cover boundary cases for vocal_active heuristic

Adds 4 regression tests around the new _vocal_active gate:

- positive case: real vocal track (concentrated midband energy) still routes
  to VOCAL_CUT for two vocal-active tracks
- boundary: pitch_salience=0.54 (below new 0.55 threshold) does not fire
  rule 3, falls through to rule 4/6/7
- legacy fallback: rows with energy_bands=None work via 2-signal check
- defensive: malformed energy_bands (len<6) does not raise IndexError

Together with test_acid_lead_not_classified_vocal_active these pin down
the heuristic contract for future modifications.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
git add tests/domain/transition/test_picker.py
git commit -F /tmp/commit-msg-task3.txt
```

---

## Task 4: Обновить документацию — Known Limitations + clarification

**Files:**
- Modify: `docs/transition-scoring.md`
- Modify: `docs/audio-pipeline.md`

- [ ] **Step 1: Прочитать текущую структуру `docs/transition-scoring.md`**

Run:
```bash
grep -n "^## \|^### " /Users/laptop/dev/dj-music-plugin/docs/transition-scoring.md
```

Expected: список секций. Новый раздел "Known Limitations" добавляется **сразу перед** "Camelot Wheel" (ASCII схема в конце документа выглядит уместно как референс после ограничений).

- [ ] **Step 2: Добавить раздел "Known Limitations" в `docs/transition-scoring.md`**

Найти строку которая начинается с `## Camelot Wheel` и добавить **перед** ней:

```markdown
## Known Limitations

### Vocal detection without stem separation

Real-time stem separation (`StemSeparator` via demucs/htdemucs) is marked
NOT YET IMPLEMENTED in [`audio-pipeline.md`](audio-pipeline.md). Until it
ships, `_vocal_active(track)` in [`picker.py`](../app/domain/transition/picker.py)
relies on **three spectral proxies** rather than direct voice detection:

1. `pitch_salience_mean > 0.55` — sustained pitched content
2. `spectral_centroid_hz > 2200 Hz` — content in/above the vocal range
3. `(energy_bands[lowmid] + energy_bands[mid]) / sum(energy_bands) > 0.40` —
   energy concentrated in the 300-3000 Hz formant band (when band data
   is available; otherwise falls back to signals 1+2 only)

**Signal #3 is essential.** Without it, acid/melodic techno with TB-303-style
resonant leads (pitch_salience ≈ 0.7-0.9, centroid ≈ 2500-4000 Hz, but
energy concentrated in highmid 3-7 kHz, not lowmid+mid) was mis-classified
as vocal-active, routing the entire picker into rule 3 (VOCAL_CUT /
VOCAL_SUSTAIN) for sets without any actual vocals.

**Even with signal #3 the heuristic is a proxy, not real voice detection.** It
cannot distinguish:

- Lead vocals from sustained synth pads in the same band
- Vocal samples / one-shots from looped synth motifs
- Formant-shifted vocoded synth from clean vocals

When real stem separation lands (Phase 3, see
[`research/2026-05-13-neural-mix-transitions-deep-dive.md`](research/2026-05-13-neural-mix-transitions-deep-dive.md)
§ 7.3.F), the picker will read `vocal_stem_energy` directly instead of these
proxies, and rules 3+4 will become reliable on any genre.

### Other limitations

- **No `FILTER_SWEEP` preset.** Filter-out / filter-in is the signature
  hypnotic-techno move (Kraviz / Klock / Marcel Fengler). Picker currently
  cannot select it; tracked for Phase 2 (`enable_filter_sweep_style`
  config flag).
- **No `LOOP_ROLL` / `STUTTER_FX` / explicit `HARD_CUT`.** All three are
  approximated by `DRUM_CUT` with `bars=1`-like envelopes. Not a fidelity
  issue today, but a taxonomy gap — see Phase 3 plan.
- **Camelot weights are static.** `S_harmonic` weights Camelot at 40%
  regardless of subgenre, but research (ISMIR-aligned) shows key
  compatibility is overweighted for percussive techno where bass tonality
  is ambiguous. Tracked for Phase 2 (per-subgenre scoring profiles).

```

- [ ] **Step 3: Уточнить семантику `pitch_salience_mean` в `docs/audio-pipeline.md` (Gotchas)**

Run:
```bash
grep -n "pitch_salience\|## Gotchas\|## Mood Classifier" /Users/laptop/dev/dj-music-plugin/docs/audio-pipeline.md
```

Найти существующую строку (`Gotchas` section content) которая упоминает `pitch_salience` или, если её нет, добавить в конец секции Gotchas новую bullet.

Edit `docs/audio-pipeline.md` — найти строку `- **PLP confidence**: \`librosa.beat.plp(...).max()\`` (или ближайшую к ней в секции Gotchas) и добавить **сразу после** этой строки:

```markdown
- **`pitch_salience_mean` is a proxy, not vocal detection.** Computed by
  essentia `PitchYin` + harmonic-peak ratio per frame, then averaged. High
  values (0.7-0.9) mean "sustained pitched content" — vocals, melodic
  leads, pads, **and acid TB-303 resonance** all score high. To distinguish
  vocal from synth lead, `picker.py:_vocal_active()` combines pitch_salience
  with `spectral_centroid_hz` AND `energy_bands` distribution — see
  [transition-scoring.md § Known Limitations](transition-scoring.md#known-limitations).
```

- [ ] **Step 4: Запустить markdownlint / docs-related checks (если есть)**

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
ls -la .markdownlint* 2>/dev/null || echo "no markdownlint config"
```

If config exists, also run any project markdown linter. Otherwise — visual review:
```bash
cd /Users/laptop/dev/dj-music-plugin
head -100 docs/transition-scoring.md | grep -A 50 "## Known Limitations"
```

Expected: новый раздел читается без сломанной разметки. Якорные ссылки `#known-limitations` валидны.

- [ ] **Step 5: Commit docs**

Create `/tmp/commit-msg-task4.txt`:
```bash
docs(transition): document vocal-detection heuristic limitations

Adds "Known Limitations" section to transition-scoring.md explaining the
3-signal vocal heuristic (pitch_salience + centroid + midband-ratio), why
each signal matters, and what the proxy cannot distinguish (lead vocals
vs synth pads vs vocoded synth).

Also clarifies pitch_salience_mean semantics in audio-pipeline.md gotchas
to prevent future contributors from using it as a vocal-presence flag.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
git add docs/transition-scoring.md docs/audio-pipeline.md
git commit -F /tmp/commit-msg-task4.txt
```

---

## Task 5: Финальная проверка — full `make check` + manual regen для verification

**Files:** только запуск тестов и manual smoke-test, без code edits.

- [ ] **Step 1: Запустить `make check` (lint + typecheck + arch + test) — должно быть зелёное**

Run:
```bash
cd /Users/laptop/dev/dj-music-plugin
make check
```

Expected output: `ruff check .` PASS, `mypy app/` PASS, `lint-imports` PASS, `pytest` PASS (все 5 новых тестов + существующие).

Если падает на mypy — проверить что аннотации новых helpers согласованы с TrackFeatures (особенно `energy_bands: list[float] | None`).

- [ ] **Step 2: Запустить ручную проверку через MCP `entity_create(entity="transition")` на acid паре**

Open Python REPL или используй существующий MCP tool. Через MCP tool:

```text
mcp__plugin_dj-music_mcp__entity_create(
    entity="transition",
    data={"from_track_id": 173, "to_track_id": 177, "persist": false}
)
```

Expected: поле `transition` в ответе теперь **не** `vocal_cut` (т.к. оба трека из Nina Kraviz сета — acid с energy в highmid). Должно быть `echo_out` (default rule 7) или `harmonic_sustain` (rule 4, если ключи в Camelot dist ≤ 1).

Если по-прежнему `vocal_cut` — проверить `entity_get(track_features, 173).energy_bands` — возможно поле null для этих треков (level=2 features, band data может отсутствовать в L1/L2). Тогда midband-фильтр не сработает (fallback к 2-сигнальной проверке), и acid опять промахнётся. В этом случае нужно повторно проанализировать треки на level≥3 (`entity_update(track_features, id=173, data={"level": 3})`) — но это не часть текущей задачи, документировать как known issue.

- [ ] **Step 3: Записать smoke-result в commit message / PR description**

Если pilot успешен — задокументировать что-то типа:

```text
Manual verification (track pair 173→177, Byakuya→Transmission, acid):
  before: transition=vocal_cut, bars=32
  after:  transition=echo_out, bars=32
```

Если pilot выявил что L2 features не имеют energy_bands — добавить TODO в комментарий к `_vocal_active()` про необходимость L3+ для лучшей точности.

- [ ] **Step 4: Финальный commit (если что-то нужно поправить из step 2)**

Если из step 2 потребовались правки (например уточнение комментария в picker.py) — отдельный commit:

```bash
cd /Users/laptop/dev/dj-music-plugin
git status
# review any uncommitted changes
git add <files>
git commit -F /tmp/commit-msg-task5.txt
```

Иначе — пропустить step 4.

- [ ] **Step 5: Создать PR**

Через `gh pr create` — branch уже должен быть feature/fix branch (НЕ main). Если работа делалась прямо на main:

```bash
cd /Users/laptop/dev/dj-music-plugin
git log --oneline main..HEAD  # должно быть 4 commits (Task 1-4)
```

If 4 commits exist on a feature branch — push and create PR:

```bash
cd /Users/laptop/dev/dj-music-plugin
git push -u origin fix/picker-vocal-heuristic
gh pr create --base main \
  --title "fix(transition): reject acid false-positives in vocal_active heuristic" \
  --body-file /tmp/pr-body.md
```

Create `/tmp/pr-body.md`:
```markdown
## Summary

- Raises `_VOCAL_PRESENCE_PITCH_SALIENCE` from 0.4 → 0.55
- Adds `_VOCAL_PRESENCE_MIDBAND_RATIO = 0.40` gate on `energy_bands` distribution
- Rewrites `_vocal_active()` to use the 3-signal heuristic with graceful fallback for legacy rows
- 5 new tests (1 acid regression + 4 boundary/edge cases)
- Documents the limitation in `transition-scoring.md` and clarifies `pitch_salience_mean` semantics in `audio-pipeline.md`

## Test plan

- [x] `pytest tests/domain/transition/test_picker.py -v` → all green (existing + 5 new tests)
- [x] `make check` → ruff + mypy + lint-imports + pytest all green
- [x] Manual: `entity_create(transition, persist=false)` on Byakuya→Transmission (acid pair) returns `echo_out` instead of `vocal_cut`

## Spec

[docs/research/2026-05-13-neural-mix-transitions-deep-dive.md](docs/research/2026-05-13-neural-mix-transitions-deep-dive.md) § 7.1

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Self-Review Checklist

✓ **Spec coverage:**
- § 7.1.A (raise threshold + midband_ratio helper) → Task 2
- § 7.1.B (regression test for acid) → Task 1
- § 7.1.B+ (boundary/edge tests) → Task 3
- § 7.1.C (docs update) → Task 4
- Final verification → Task 5

✓ **Placeholder scan:** все code blocks содержат exact code (нет "TBD", "implement appropriate", "similar to above").

✓ **Type consistency:**
- `_VOCAL_PRESENCE_PITCH_SALIENCE` (float) — used same way across tasks
- `_VOCAL_PRESENCE_MIDBAND_RATIO` (float) — defined Task 2 step 3, used Task 2 step 4
- `TrackFeatures.energy_bands: list[float] | None` — consistent with `app/shared/features.py:34`
- Test helper signatures `_track(**kwargs)` / `_ok_score(**kwargs)` — match existing test_picker.py contract

✓ **Out-of-scope items explicitly listed** в Scope boundaries header.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Существующие picker tests падают из-за raised threshold | Task 3 step 6 явно проверяет. Fix — повысить pitch_salience в fixtures, **не** понижать порог обратно |
| L2 features в БД не имеют `energy_bands` → midband fallback не сработает | Документировано в Known Limitations; для critical accuracy нужен L3+ analyze |
| Pre-commit hook (`hooks/reload-mcp.sh` через PostToolUse) перезагружает MCP при каждом Edit, замедляет работу | Не блокирующая проблема, hook вернётся ≤1s |
| Поднятие threshold с 0.4 до 0.55 может пропустить *настоящие* вокальные техно треки с pitch_salience 0.45-0.55 | Task 3 step 5 test_real_vocal проверяет positive case с 0.65/0.70. Если позже найдутся false negatives — точечно подстроить с regression test |

---

## Estimated Effort

- Task 1: 10-15 min (write test + commit)
- Task 2: 15-20 min (code change + run + commit)
- Task 3: 20-25 min (4 tests + run full suite + commit)
- Task 4: 15-20 min (docs + lint + commit)
- Task 5: 10-15 min (make check + manual smoke + optional PR)

**Total: ~75-95 min** для experienced engineer.
