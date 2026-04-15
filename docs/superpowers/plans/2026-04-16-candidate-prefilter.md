# Candidate Pre-Filter для Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Предварительная фильтрация кандидатов по hard constraints перед transition scoring, чтобы сократить O(n²) до O(n × k) в greedy и улучшить GA-инициализацию.

**Architecture:** Новый модуль `app/optimization/candidate_filter.py` предвычисляет adjacency list (граф совместимости) — для каждого трека список допустимых следующих треков по критериям BPM ±10, Camelot dist < 5, LUFS gap ≤ 6. Greedy и GA-инициализация используют этот граф вместо full-scan. Scorer вызывается только для отфильтрованных пар.

**Tech Stack:** Python 3.12, `app.transition.math_helpers.bpm_distance`, `app.camelot.wheel.camelot_distance`, `app.config.settings`, `app.entities.audio.features.TrackFeatures`

---

## File Map

| Файл | Действие | Ответственность |
|------|----------|-----------------|
| `app/optimization/candidate_filter.py` | **Create** | Предвычисление adjacency list по hard constraints |
| `app/optimization/greedy.py` | **Modify** | Использовать adjacency list в inner loop |
| `app/optimization/genetic.py` | **Modify** | Graph-aware инициализация популяции |
| `tests/test_optimization/test_candidate_filter.py` | **Create** | Тесты фильтра |
| `tests/test_optimization/test_greedy.py` | **Modify** | Тест что greedy использует фильтр |

---

### Task 1: candidate_filter.py — ядро

**Files:**
- Create: `app/optimization/candidate_filter.py`
- Test: `tests/test_optimization/test_candidate_filter.py`

- [ ] **Step 1: Написать failing тест**

```python
# tests/test_optimization/test_candidate_filter.py
from app.entities.audio.features import TrackFeatures
from app.optimization.candidate_filter import build_adjacency

def _feat(bpm: float | None, key_code: int | None, lufs: float | None) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, key_code=key_code, integrated_lufs=lufs)

def test_bpm_hard_reject():
    """Треки с BPM diff > 10 не попадают в adjacency list."""
    features = {1: _feat(120.0, 0, -10.0), 2: _feat(135.0, 0, -10.0)}
    graph = build_adjacency(features)
    assert 2 not in graph[1]
    assert 1 not in graph[2]

def test_camelot_hard_reject():
    """Треки с Camelot distance >= 5 не попадают в adjacency list."""
    # key_code=0 (1A), key_code=10 (6A) — distance=5
    features = {1: _feat(130.0, 0, -10.0), 2: _feat(130.0, 10, -10.0)}
    graph = build_adjacency(features)
    assert 2 not in graph[1]

def test_lufs_hard_reject():
    """Треки с LUFS gap > 6 не попадают в adjacency list."""
    features = {1: _feat(130.0, 0, -10.0), 2: _feat(130.0, 0, -17.5)}
    graph = build_adjacency(features)
    assert 2 not in graph[1]

def test_valid_pair_passes():
    """Совместимая пара присутствует в обоих направлениях."""
    features = {1: _feat(130.0, 0, -10.0), 2: _feat(132.0, 1, -11.0)}
    graph = build_adjacency(features)
    assert 2 in graph[1]
    assert 1 in graph[2]

def test_none_features_fallback():
    """Трек без BPM/key/LUFS не отфильтровывается (fallback — пропустить)."""
    features = {1: _feat(None, None, None), 2: _feat(130.0, 0, -10.0)}
    graph = build_adjacency(features)
    # Без данных нельзя применить hard constraint — трек остаётся кандидатом
    assert 2 in graph[1]
    assert 1 in graph[2]

def test_self_not_in_adjacency():
    """Трек не является кандидатом сам для себя."""
    features = {1: _feat(130.0, 0, -10.0)}
    graph = build_adjacency(features)
    assert 1 not in graph[1]

def test_returns_all_ids_as_keys():
    """Каждый track_id присутствует как ключ даже если кандидатов нет."""
    features = {1: _feat(120.0, 0, -10.0), 2: _feat(140.0, 10, -20.0)}
    graph = build_adjacency(features)
    assert 1 in graph
    assert 2 in graph
```

- [ ] **Step 2: Запустить тест — убедиться что FAIL**

```bash
uv run pytest tests/test_optimization/test_candidate_filter.py -v
```

Ожидаем: `ImportError: cannot import name 'build_adjacency'`

- [ ] **Step 3: Реализовать `candidate_filter.py`**

```python
"""Pre-filter track candidates by hard constraints before full transition scoring.

Builds an adjacency list (graph) mapping each track_id to the set of valid
next-track candidates. A pair is valid if it passes all three hard constraints:
BPM diff ≤ threshold, Camelot distance < threshold, LUFS gap ≤ threshold.

When a feature value is None the corresponding constraint is skipped (can't
reject what we can't measure).
"""
from __future__ import annotations

from app.camelot.wheel import camelot_distance
from app.config import settings
from app.entities.audio.features import TrackFeatures
from app.transition.math_helpers import bpm_distance

def build_adjacency(
    features: dict[int, TrackFeatures],
) -> dict[int, set[int]]:
    """Pre-compute valid next-track candidates for each track.

    Args:
        features: Mapping of track_id → TrackFeatures.

    Returns:
        Adjacency list: track_id → set of valid successor track_ids.
        Every track_id from ``features`` appears as a key.
    """
    ids = list(features.keys())
    graph: dict[int, set[int]] = {tid: set() for tid in ids}

    for i, a_id in enumerate(ids):
        feat_a = features[a_id]
        for b_id in ids:
            if b_id == a_id:
                continue
            feat_b = features[b_id]
            if not _passes_hard_constraints(feat_a, feat_b):
                continue
            graph[a_id].add(b_id)

    return graph

def _passes_hard_constraints(a: TrackFeatures, b: TrackFeatures) -> bool:
    """Return True if the pair survives all hard constraints."""
    # BPM
    if a.bpm is not None and b.bpm is not None:
        if bpm_distance(a.bpm, b.bpm) > settings.transition_hard_reject_bpm_diff:
            return False

    # Camelot / key
    if a.key_code is not None and b.key_code is not None:
        if camelot_distance(a.key_code, b.key_code) >= settings.transition_hard_reject_camelot_dist:
            return False

    # LUFS energy gap
    if a.integrated_lufs is not None and b.integrated_lufs is not None:
        if abs(a.integrated_lufs - b.integrated_lufs) > settings.transition_hard_reject_energy_gap:
            return False

    return True
```

- [ ] **Step 4: Запустить тест — убедиться что PASS**

```bash
uv run pytest tests/test_optimization/test_candidate_filter.py -v
```

Ожидаем: все 7 тестов PASS.

- [ ] **Step 5: Lint + typecheck**

```bash
uv run ruff check app/optimization/candidate_filter.py
uv run mypy app/optimization/candidate_filter.py
```

- [ ] **Step 6: Commit**

```bash
git add app/optimization/candidate_filter.py tests/test_optimization/test_candidate_filter.py
git commit -m "feat(optimization): add candidate pre-filter adjacency builder"
```

---

### Task 2: Greedy использует граф совместимости

**Files:**
- Modify: `app/optimization/greedy.py:56-66` (inner loop `while remaining`)
- Test: `tests/test_optimization/test_greedy.py`

- [ ] **Step 1: Написать failing тест**

```python
# tests/test_optimization/test_greedy.py
# Добавить в существующий файл или создать новый

from unittest.mock import patch, MagicMock
from app.entities.audio.features import TrackFeatures
from app.optimization.greedy import GreedyChainBuilder
from app.transition.scorer import TransitionScorer

def _feat(bpm: float, key_code: int, lufs: float) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, key_code=key_code, integrated_lufs=lufs)

def test_greedy_skips_hard_rejected_pairs():
    """Greedy не вызывает scorer для пар нарушающих hard constraints (BPM diff > 10)."""
    mock_scorer = MagicMock(spec=TransitionScorer)
    # Трек 1: 120 BPM, трек 2: 135 BPM (diff=15 > 10 → hard reject)
    tracks = [_feat(120.0, 0, -10.0), _feat(135.0, 0, -10.0)]
    track_ids = [1, 2]

    builder = GreedyChainBuilder(mock_scorer)
    result = builder.optimize(tracks, track_ids)

    # scorer.score() не должен вызываться для этой пары (BPM diff > threshold)
    mock_scorer.score.assert_not_called()
    assert set(result.track_order) == {1, 2}

def test_greedy_scores_valid_pairs():
    """Greedy вызывает scorer для пар прошедших pre-filter."""
    mock_result = MagicMock()
    mock_result.hard_reject = False
    mock_result.overall = 0.8

    mock_scorer = MagicMock(spec=TransitionScorer)
    mock_scorer.score.return_value = mock_result

    tracks = [_feat(130.0, 0, -10.0), _feat(132.0, 1, -11.0)]
    track_ids = [1, 2]

    builder = GreedyChainBuilder(mock_scorer)
    result = builder.optimize(tracks, track_ids)

    mock_scorer.score.assert_called()
    assert set(result.track_order) == {1, 2}

def test_greedy_fallback_when_all_filtered():
    """Если все кандидаты отфильтрованы — greedy берёт любой оставшийся (не зависает)."""
    mock_scorer = MagicMock(spec=TransitionScorer)
    # Все треки с BPM diff > 10 друг к другу
    tracks = [_feat(120.0, 0, -10.0), _feat(135.0, 0, -10.0), _feat(150.0, 0, -10.0)]
    track_ids = [1, 2, 3]

    builder = GreedyChainBuilder(mock_scorer)
    result = builder.optimize(tracks, track_ids)

    # Должен вернуть все треки, не зависнуть
    assert len(result.track_order) == 3
    assert set(result.track_order) == {1, 2, 3}
```

- [ ] **Step 2: Запустить — убедиться что FAIL**

```bash
uv run pytest tests/test_optimization/test_greedy.py::test_greedy_skips_hard_rejected_pairs -v
```

Ожидаем: FAIL — scorer вызывается даже для hard-rejected пар.

- [ ] **Step 3: Изменить `greedy.py` — добавить pre-filter**

Найти метод `optimize()` в `app/optimization/greedy.py`. Добавить импорт и предвычисление графа перед основным циклом.

Изменить заголовок файла (импорты):
```python
"""Greedy chain builder — fast O(n^2) heuristic for set optimization."""
from collections.abc import Callable

from app.entities.audio.features import TrackFeatures
from app.optimization.candidate_filter import build_adjacency
from app.optimization.fitness import compute_fitness
from app.optimization.result import OptimizationResult
from app.templates.models import SetTemplateDefinition
from app.transition.scorer import TransitionScorer
```

Изменить метод `optimize()` — вставить после строки `idx_map = ...` и изменить inner loop:

```python
        idx_map = {tid: i for i, tid in enumerate(track_ids)}
        remaining = set(active_ids)

        # Pre-compute adjacency graph (hard-constraint pre-filter)
        features_map = {tid: tracks[idx_map[tid]] for tid in active_ids}
        adjacency = build_adjacency(features_map)
```

Заменить inner loop (был `for candidate in remaining: result = self.scorer.score(...)`):

```python
        while remaining:
            # Use pre-filtered candidates; fall back to all remaining if graph gives nothing
            candidates = adjacency.get(current, set()) & remaining
            if not candidates:
                candidates = remaining  # fallback: no valid transitions, take any

            best_tid = None
            best_score = -1.0
            for candidate in candidates:
                result = self.scorer.score(
                    tracks[idx_map[current]],
                    tracks[idx_map[candidate]],
                )
                score = 0.0 if result.hard_reject else result.overall
                if score > best_score:
                    best_score = score
                    best_tid = candidate
            if best_tid is None:
                best_tid = next(iter(remaining))
            order.append(best_tid)
            remaining.remove(best_tid)
            current = best_tid
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_optimization/test_greedy.py -v
```

Ожидаем: все 3 теста PASS.

- [ ] **Step 5: Прогнать полный test suite**

```bash
uv run pytest tests/ -q --tb=short
```

Ожидаем: нет новых падений.

- [ ] **Step 6: Lint + typecheck**

```bash
uv run ruff check app/optimization/greedy.py
uv run mypy app/optimization/greedy.py
```

- [ ] **Step 7: Commit**

```bash
git add app/optimization/greedy.py tests/test_optimization/test_greedy.py
git commit -m "perf(optimization): greedy uses candidate pre-filter, skips hard-rejected pairs"
```

---

### Task 3: GA — graph-aware инициализация популяции

**Files:**
- Modify: `app/optimization/genetic.py` — `optimize()` и `_init_population()`
- Test: `tests/test_optimization/test_genetic.py`

Смысл: вместо полностью случайных перестановок начальная популяция строится как цепочки по adjacency graph. Это даёт GA лучшую стартовую точку — меньше поколений нужно до сходимости.

- [ ] **Step 1: Написать failing тест**

```python
# tests/test_optimization/test_genetic.py
# Добавить в существующий файл

from app.entities.audio.features import TrackFeatures
from app.optimization.genetic import GeneticAlgorithm
from app.transition.scorer import TransitionScorer
from unittest.mock import MagicMock

def _feat(bpm: float, key_code: int, lufs: float) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, key_code=key_code, integrated_lufs=lufs)

def test_ga_stores_adjacency_on_optimize():
    """GA вычисляет adjacency graph при вызове optimize()."""
    mock_score = MagicMock()
    mock_score.hard_reject = False
    mock_score.overall = 0.5
    mock_score.bpm = 0.8
    mock_score.harmonic = 0.7
    mock_score.energy = 0.6
    mock_score.spectral = 0.5
    mock_score.groove = 0.5
    mock_score.timbral = 0.5

    scorer = MagicMock(spec=TransitionScorer)
    scorer.score.return_value = mock_score

    tracks = [_feat(130.0, 0, -10.0), _feat(131.0, 1, -11.0), _feat(132.0, 0, -10.5)]
    track_ids = [1, 2, 3]

    ga = GeneticAlgorithm(scorer, population_size=10, max_generations=5)
    result = ga.optimize(tracks, track_ids)

    assert len(result.track_order) == 3
    assert set(result.track_order) == {1, 2, 3}
    assert result.algorithm == "ga"
```

- [ ] **Step 2: Запустить — убедиться что тест проходит (baseline)**

```bash
uv run pytest tests/test_optimization/test_genetic.py::test_ga_stores_adjacency_on_optimize -v
```

Ожидаем: PASS (тест проверяет поведение, не реализацию — должен пройти сразу).

- [ ] **Step 3: Изменить `genetic.py` — передавать adjacency в `_init_population`**

Добавить импорт в начало файла:
```python
from app.optimization.candidate_filter import build_adjacency
```

В методе `optimize()` после строки `idx_map = {tid: i for i, tid in enumerate(track_ids)}`:
```python
        # Pre-compute adjacency graph for graph-aware population initialization
        features_map = {tid: tracks[idx_map[tid]] for tid in active_ids}
        adjacency = build_adjacency(features_map)
```

Изменить вызов `_init_population`:
```python
        population = self._init_population(active_ids, pinned, adjacency)
```

Изменить сигнатуру и тело `_init_population`:
```python
    def _init_population(
        self,
        track_ids: list[int],
        pinned: set[int],
        adjacency: dict[int, set[int]] | None = None,
    ) -> list[list[int]]:
        """Initialize population: half graph-guided chains, half random shuffles."""
        population: list[list[int]] = []
        half = self.population_size // 2

        # Graph-guided half: build chains following adjacency edges
        if adjacency:
            for _ in range(half):
                chain = _build_chain(track_ids, pinned, adjacency)
                population.append(chain)

        # Random half (or full if no adjacency)
        while len(population) < self.population_size:
            shuffled = list(track_ids)
            random.shuffle(shuffled)
            # Keep pinned in original relative order
            if pinned:
                pinned_positions = [i for i, t in enumerate(shuffled) if t in pinned]
                pinned_ids = [t for t in track_ids if t in pinned]
                for pos, pid in zip(pinned_positions, pinned_ids, strict=False):
                    shuffled[pos] = pid
            population.append(shuffled)

        return population
```

Добавить вспомогательную функцию на уровне модуля (после импортов, перед классом):
```python
def _build_chain(
    track_ids: list[int],
    pinned: set[int],
    adjacency: dict[int, set[int]],
) -> list[int]:
    """Build one chain by following adjacency graph with random tie-breaking."""
    remaining = set(track_ids)
    chain: list[int] = []

    # Start from a random track
    current = random.choice(track_ids)
    chain.append(current)
    remaining.remove(current)

    while remaining:
        neighbors = adjacency.get(current, set()) & remaining
        if neighbors:
            current = random.choice(list(neighbors))
        else:
            # No valid neighbor — pick randomly from remaining
            current = random.choice(list(remaining))
        chain.append(current)
        remaining.remove(current)

    return chain
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_optimization/ -v
```

Ожидаем: все тесты PASS.

- [ ] **Step 5: Полный suite**

```bash
uv run pytest tests/ -q --tb=short
```

- [ ] **Step 6: Lint + typecheck**

```bash
uv run ruff check app/optimization/genetic.py
uv run mypy app/optimization/genetic.py
```

- [ ] **Step 7: Commit**

```bash
git add app/optimization/genetic.py tests/test_optimization/test_genetic.py
git commit -m "perf(optimization): GA uses graph-aware population init from adjacency pre-filter"
```

---

### Task 4: Экспортировать из `__init__.py` и финальная проверка

**Files:**
- Modify: `app/optimization/__init__.py`

- [ ] **Step 1: Добавить в `__init__.py`**

```python
# app/optimization/__init__.py — добавить строку
from app.optimization.candidate_filter import build_adjacency  # noqa: F401
```

- [ ] **Step 2: Полный `make check`**

```bash
make check
```

Ожидаем: lint + typecheck + arch + tests — все зелёные.

- [ ] **Step 3: Быстрый E2E через REST API**

```bash
# Пересобрать сет и проверить что algorithm не None
curl -s -X POST "http://localhost:8000/api/tools/rebuild_set/call" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{"arguments": {"set_id": 25, "algorithm": "greedy", "version_label": "greedy-filtered"}}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d)"
```

- [ ] **Step 4: Финальный commit**

```bash
git add app/optimization/__init__.py
git commit -m "chore(optimization): export build_adjacency from package"
```

---

## Ожидаемый эффект

| Метрика | До | После |
|---|---|---|
| Greedy inner loop итераций (n=500) | 500 × 500 = 250k | 500 × ~75 = 37k (**6.7x меньше**) |
| scorer.score() вызовов на сет | n² | n × k, k ≈ 15% от n |
| GA первое поколение quality | случайная стартовая точка | chain-guided, ближе к оптимуму |
| Генераций до сходимости | 200 (max) | меньше (лучший старт) |

При 22 треках ("Эксклюзив техно") разница незначительна. При 500+ треках из библиотеки — существенная.
