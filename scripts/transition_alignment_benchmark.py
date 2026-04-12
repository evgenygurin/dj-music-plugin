"""Template/subgenre transition alignment benchmark (baseline vs aligned).

This benchmark is data-independent and uses deterministic synthetic pools so it
can run in any environment (including CI) without external DB connectivity.

It compares:
1. Baseline ordering (no template/mood guidance)
2. Aligned ordering (template + mood guidance enabled)

Across key templates:
- peak_hour_60
- roller_90
- progressive_120
- closing_60
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dj_music.core.constants import SetTemplate, TechnoSubgenre
from app.entities.audio.features import TrackFeatures
from app.optimization.fitness import template_fitness
from dj_music.services.optimizer import GreedyChainBuilder
from dj_music.services.templates import get_template
from dj_music.services.transition import TransitionScorer
from app.templates.models import SetTemplateDefinition
from dj_music.transition.intent import infer_intent

KEY_TEMPLATES = ("peak_hour_60", "roller_90", "progressive_120", "closing_60")
SAMPLE_SEEDS = (7, 13, 29, 41, 97)


@dataclass
class RunMetrics:
    avg_transition_quality: float
    hard_conflicts: int
    template_fit: float


@dataclass
class Comparison:
    baseline: RunMetrics
    aligned: RunMetrics

    @property
    def conflicts_ok(self) -> bool:
        return self.aligned.hard_conflicts <= self.baseline.hard_conflicts

    @property
    def quality_ok(self) -> bool:
        return self.aligned.avg_transition_quality >= self.baseline.avg_transition_quality

    @property
    def template_fit_ok(self) -> bool:
        return self.aligned.template_fit >= self.baseline.template_fit


def _template_enum(template: SetTemplateDefinition) -> SetTemplate | None:
    try:
        return SetTemplate(template.name)
    except ValueError:
        return None


def _build_pool(
    template_name: str,
    *,
    pool_size: int,
    seed: int,
) -> tuple[
    list[TrackFeatures],
    list[int],
    dict[int, int],
    dict[int, str | None],
    SetTemplateDefinition,
]:
    template = get_template(template_name)
    rng = random.Random(seed)

    all_subgenres = [sg.value for sg in TechnoSubgenre]
    tracks: list[TrackFeatures] = []
    track_ids: list[int] = []
    moods: dict[int, str | None] = {}

    for i in range(pool_size):
        slot = template.slots[i % len(template.slots)]
        # Inject periodic off-template tracks to make optimization non-trivial.
        off_template = (i % 6) == 0

        if off_template:
            bpm = rng.uniform(max(120.0, slot.bpm_min - 10), slot.bpm_max + 10)
            lufs = rng.uniform(slot.energy_lufs - 4.0, slot.energy_lufs + 4.0)
            mood = rng.choice(all_subgenres)
        else:
            bpm = rng.uniform(slot.bpm_min - 2.0, slot.bpm_max + 2.0)
            lufs = rng.uniform(slot.energy_lufs - 1.5, slot.energy_lufs + 1.5)
            mood = (
                slot.target_mood
                if slot.target_mood is not None
                else rng.choice(all_subgenres)
            )

        tid = i + 1
        key_code = (i * 2 + rng.randint(0, 2)) % 24

        tracks.append(
            TrackFeatures(
                bpm=bpm,
                key_code=key_code,
                integrated_lufs=lufs,
                spectral_centroid_hz=rng.uniform(1200.0, 4200.0),
                energy_mean=rng.uniform(0.25, 0.9),
                onset_rate=rng.uniform(2.0, 6.5),
                kick_prominence=rng.uniform(0.25, 0.9),
                mood=mood,
            )
        )
        track_ids.append(tid)
        moods[tid] = mood

    idx_map = {tid: idx for idx, tid in enumerate(track_ids)}
    return tracks, track_ids, idx_map, moods, template


def _evaluate_order(
    order: list[int],
    *,
    tracks: list[TrackFeatures],
    idx_map: dict[int, int],
    moods: dict[int, str | None],
    template: SetTemplateDefinition,
    intent_template: SetTemplate | None,
    scorer: TransitionScorer,
) -> RunMetrics:
    if len(order) < 2:
        return RunMetrics(avg_transition_quality=0.0, hard_conflicts=0, template_fit=0.0)

    soft_scores: list[float] = []
    hard_conflicts = 0
    n = len(order)
    for i in range(n - 1):
        a = tracks[idx_map[order[i]]]
        b = tracks[idx_map[order[i + 1]]]
        position = i / max(1, n - 2)
        energy_delta = (b.integrated_lufs or -8.0) - (a.integrated_lufs or -8.0)
        intent = infer_intent(position, energy_delta, template=intent_template)
        score = scorer.score(a, b, intent=intent)
        if score.hard_reject:
            hard_conflicts += 1
        else:
            soft_scores.append(score.overall)

    avg_quality = sum(soft_scores) / len(soft_scores) if soft_scores else 0.0
    tmpl_fit = template_fitness(tracks, order, idx_map, template, moods)
    return RunMetrics(
        avg_transition_quality=avg_quality,
        hard_conflicts=hard_conflicts,
        template_fit=tmpl_fit,
    )


def _run_comparison(template_name: str, *, pool_size: int, seed: int) -> Comparison:
    tracks, track_ids, idx_map, moods, template = _build_pool(
        template_name,
        pool_size=pool_size,
        seed=seed,
    )
    scorer = TransitionScorer()
    builder = GreedyChainBuilder(scorer)

    baseline = builder.optimize(
        tracks,
        track_ids,
        template=None,
        moods=None,
    )
    aligned = builder.optimize(
        tracks,
        track_ids,
        template=template,
        moods=moods,
    )

    baseline_metrics = _evaluate_order(
        baseline.track_order,
        tracks=tracks,
        idx_map=idx_map,
        moods=moods,
        template=template,
        intent_template=None,
        scorer=scorer,
    )
    aligned_metrics = _evaluate_order(
        aligned.track_order,
        tracks=tracks,
        idx_map=idx_map,
        moods=moods,
        template=template,
        intent_template=_template_enum(template),
        scorer=scorer,
    )
    return Comparison(baseline=baseline_metrics, aligned=aligned_metrics)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _aggregate(comparisons: list[Comparison]) -> Comparison:
    return Comparison(
        baseline=RunMetrics(
            avg_transition_quality=_mean(
                [c.baseline.avg_transition_quality for c in comparisons]
            ),
            hard_conflicts=round(_mean([float(c.baseline.hard_conflicts) for c in comparisons])),
            template_fit=_mean([c.baseline.template_fit for c in comparisons]),
        ),
        aligned=RunMetrics(
            avg_transition_quality=_mean(
                [c.aligned.avg_transition_quality for c in comparisons]
            ),
            hard_conflicts=round(_mean([float(c.aligned.hard_conflicts) for c in comparisons])),
            template_fit=_mean([c.aligned.template_fit for c in comparisons]),
        ),
    )


def _render_table(title: str, rows: list[tuple[str, Comparison]]) -> str:
    lines = [
        f"### {title}",
        "",
        (
            "| Template | Baseline Hard | Aligned Hard | Baseline AvgQ | "
            "Aligned AvgQ | Baseline Fit | Aligned Fit | Verdict |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for template_name, comp in rows:
        verdict = (
            "PASS"
            if (comp.conflicts_ok and comp.quality_ok and comp.template_fit_ok)
            else "CHECK"
        )
        lines.append(
            "| "
            + f"{template_name} | "
            + f"{comp.baseline.hard_conflicts} | "
            + f"{comp.aligned.hard_conflicts} | "
            + f"{comp.baseline.avg_transition_quality:.4f} | "
            + f"{comp.aligned.avg_transition_quality:.4f} | "
            + f"{comp.baseline.template_fit:.4f} | "
            + f"{comp.aligned.template_fit:.4f} | "
            + f"{verdict} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run transition alignment benchmark.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Markdown report path "
            "(default: docs/reports/transition-alignment-benchmark-<date>.md)"
        ),
    )
    parser.add_argument(
        "--sample-pool-size",
        type=int,
        default=48,
        help="Synthetic pool size for sample sweep",
    )
    parser.add_argument(
        "--focused-pool-size",
        type=int,
        default=160,
        help="Synthetic pool size for focused run",
    )
    args = parser.parse_args()

    today = datetime.now(tz=UTC).date().isoformat()
    out_path = args.out or Path(
        f"docs/reports/transition-alignment-benchmark-{today}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sample_rows: list[tuple[str, Comparison]] = []
    focused_rows: list[tuple[str, Comparison]] = []

    for template_name in KEY_TEMPLATES:
        sample_runs = [
            _run_comparison(
                template_name,
                pool_size=args.sample_pool_size,
                seed=seed,
            )
            for seed in SAMPLE_SEEDS
        ]
        sample_rows.append((template_name, _aggregate(sample_runs)))

        focused = _run_comparison(
            template_name,
            pool_size=args.focused_pool_size,
            seed=20260409,
        )
        focused_rows.append((template_name, focused))

    sample_pass = sum(
        1
        for _, comp in sample_rows
        if comp.conflicts_ok and comp.quality_ok and comp.template_fit_ok
    )
    focused_pass = sum(
        1
        for _, comp in focused_rows
        if comp.conflicts_ok and comp.quality_ok and comp.template_fit_ok
    )

    report = "\n".join(
        [
            "# Transition Alignment Benchmark",
            "",
            f"- Date: {today}",
            "- Mode: synthetic deterministic benchmark (baseline vs aligned wiring)",
            f"- Templates: {', '.join(KEY_TEMPLATES)}",
            (
                f"- Sample sweep: {len(SAMPLE_SEEDS)} seeds per template, "
                f"pool_size={args.sample_pool_size}"
            ),
            f"- Focused run: 1 seed per template, pool_size={args.focused_pool_size}",
            "",
            _render_table("Sample Sweep (Aggregated)", sample_rows),
            _render_table("Focused Run", focused_rows),
            "## Acceptance Summary",
            "",
            f"- Sample sweep pass count: {sample_pass}/{len(sample_rows)} templates",
            f"- Focused run pass count: {focused_pass}/{len(focused_rows)} templates",
            "- Acceptance checks per template:",
            "  - `aligned hard_conflicts <= baseline hard_conflicts`",
            "  - `aligned avg_transition_quality >= baseline avg_transition_quality`",
            "  - `aligned template_fit >= baseline template_fit`",
            "",
        ]
    )

    out_path.write_text(report, encoding="utf-8")
    print(f"Report written: {out_path}")


if __name__ == "__main__":
    main()
