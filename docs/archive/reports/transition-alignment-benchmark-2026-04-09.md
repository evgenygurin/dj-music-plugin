# Transition Alignment Benchmark

- Date: 2026-04-09
- Mode: synthetic deterministic benchmark (baseline vs aligned wiring)
- Templates: peak_hour_60, roller_90, progressive_120, closing_60
- Sample sweep: 5 seeds per template, pool_size=48
- Focused run: 1 seed per template, pool_size=160

### Sample Sweep (Aggregated)

| Template | Baseline Hard | Aligned Hard | Baseline AvgQ | Aligned AvgQ | Baseline Fit | Aligned Fit | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| peak_hour_60 | 2 | 2 | 0.6959 | 0.7012 | 0.8131 | 0.8131 | PASS |
| roller_90 | 1 | 1 | 0.6921 | 0.6945 | 0.8454 | 0.8454 | PASS |
| progressive_120 | 2 | 2 | 0.6821 | 0.6783 | 0.7857 | 0.7857 | CHECK |
| closing_60 | 1 | 1 | 0.6879 | 0.6827 | 0.8277 | 0.8277 | CHECK |

### Focused Run

| Template | Baseline Hard | Aligned Hard | Baseline AvgQ | Aligned AvgQ | Baseline Fit | Aligned Fit | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| peak_hour_60 | 2 | 2 | 0.7390 | 0.7453 | 0.7512 | 0.7512 | PASS |
| roller_90 | 1 | 1 | 0.7399 | 0.7430 | 0.8987 | 0.8987 | PASS |
| progressive_120 | 2 | 2 | 0.7199 | 0.7152 | 0.7393 | 0.7393 | CHECK |
| closing_60 | 1 | 1 | 0.7253 | 0.7201 | 0.8424 | 0.8424 | CHECK |

## Acceptance Summary

- Sample sweep pass count: 2/4 templates
- Focused run pass count: 2/4 templates
- Acceptance checks per template:
  - `aligned hard_conflicts <= baseline hard_conflicts`
  - `aligned avg_transition_quality >= baseline avg_transition_quality`
  - `aligned template_fit >= baseline template_fit`
