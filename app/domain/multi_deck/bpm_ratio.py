"""BPM ratio analyzer — polyrhythm and dual-BPM storytelling."""

from __future__ import annotations

import math

from app.domain.multi_deck.models import BpmRatioMatch, BpmRatioResult
from app.repositories.unit_of_work import UnitOfWork

_RATIOS = {
    "3:4": (3, 4, 0.75),
    "2:3": (2, 3, 0.6667),
    "3:2": (3, 2, 1.5),
    "4:3": (4, 3, 1.3333),
    "5:4": (5, 4, 0.8),
    "4:5": (4, 5, 1.25),
    "3:5": (3, 5, 0.6),
    "5:3": (5, 3, 1.6667),
}


def _bars_to_align(num: int, den: int) -> int:
    return math.lcm(num, den)


async def analyze_bpm_ratio(
    uow: UnitOfWork,
    bpm_a: float,
    bpm_range: tuple[float, float] = (40, 200),
    ratios_of_interest: list[str] | None = None,
) -> BpmRatioResult:
    if ratios_of_interest is None:
        ratios_of_interest = list(_RATIOS.keys())

    matches = []
    for label in ratios_of_interest:
        entry = _RATIOS.get(label)
        if entry is None:
            continue
        num, den, ratio = entry

        for candidate in [bpm_a * ratio, bpm_a / ratio]:
            if bpm_range[0] <= candidate <= bpm_range[1]:
                bar_duration_s = 240.0 / bpm_a
                align_bars = _bars_to_align(num, den)
                match = BpmRatioMatch(
                    bpm_b=round(candidate, 2),
                    ratio=round(ratio, 4),
                    ratio_label=label,
                    error_pct=0.0,
                    bars_to_align=align_bars,
                    seconds_to_align=round(align_bars * bar_duration_s, 2),
                )
                matches.append(match)

    return BpmRatioResult(
        bpm_a=bpm_a,
        matches=sorted(matches, key=lambda m: abs(1.0 - m.ratio)),
        library_pairs=[],
    )
