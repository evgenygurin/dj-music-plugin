---
description: Set optimization — GA, greedy, fitness, algorithm selection, OptimizerStrategy
globs: app/optimization/**/*.py
---

# Set Optimization

Pure domain logic. No I/O, no DB, no async. All in `app/optimization/`.

## Strategy Pattern

Both algorithms implement `OptimizerStrategy` protocol (`app/optimization/protocol.py`):

```python
class OptimizerStrategy(Protocol):
    def optimize(
        self,
        tracks: list[TrackFeatures],
        track_ids: list[int],
        pinned: set[int] | None = None,
        excluded: set[int] | None = None,
        template: SetTemplateDefinition | None = None,
        moods: dict[int, str | None] | None = None,
        on_progress: Callable[[int, float], None] | None = None,
    ) -> OptimizationResult: ...
```

## Algorithm Selection

| Algorithm | Use when | Complexity |
|-----------|---------|-----------|
| `GreedyChainBuilder` | < 30 tracks, quick preview, rebuild | O(n²), deterministic |
| `GeneticAlgorithm` | ≥ 30 tracks, final set | Stochastic, slower, higher quality |

`BuildSetWorkflow` selects automatically based on track count + `algorithm` param from `build_set` tool.

## GeneticAlgorithm (`genetic.py`)

```python
from app.optimization.genetic import GeneticAlgorithm

optimizer = GeneticAlgorithm(scorer=TransitionScorer())
result = optimizer.optimize(tracks, track_ids, template=template, on_progress=cb)
```

All params default to `settings.ga_*` — override only in tests:
- `ga_population_size` (50), `ga_max_generations` (100), `ga_mutation_rate` (0.1)
- `ga_elitism_rate` (0.1), `ga_tournament_size` (5), `ga_convergence_threshold` (20)

Uses 2-opt post-processing on best individual after GA convergence.

## GreedyChainBuilder (`greedy.py`)

```python
from app.optimization.greedy import GreedyChainBuilder

optimizer = GreedyChainBuilder(scorer=TransitionScorer())
result = optimizer.optimize(tracks, track_ids, pinned={42})
```

Greedily picks best opening track (low energy, high BPM compatibility), then best next transition.
`pinned` tracks always appear. `excluded` tracks removed unless also pinned.

## Fitness (`fitness.py`)

`compute_fitness(sequence, features_map, scorer, template)` → `float` [0, 1]
- Scores all consecutive transitions
- Penalizes hard rejects
- Weights by `TransitionIntent` per position (via `infer_intent`)
- Used by both GA (per-individual scoring) and `OptimizationResult.quality_score`

## Adjacency Pre-filter (`candidate_filter.py`)

`build_adjacency(features_map)` — pre-computes which tracks can follow each track (passes hard constraints). Both algorithms use this to prune the search space before optimization.

## OptimizationResult

```python
@dataclass
class OptimizationResult:
    track_order: list[int]  # ordered track IDs
    quality_score: float    # 0–1 fitness
```

## Gotchas

- `excluded` tracks are removed UNLESS also in `pinned` — pinned always wins
- Progress callback signature: `on_progress(generation: int, best_score: float)` — called per GA generation
- GA is non-deterministic — same input yields different order each run. Use `greedy` in reproducible tests
- `playlist_order` fallback (in `BuildSetWorkflow`): when no audio features available — bypasses both optimizers
- `build_adjacency` uses the same hard constraint check as `TransitionScorer` — not a separate filter
