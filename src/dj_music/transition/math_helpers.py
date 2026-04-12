"""Pure math helpers for transition scoring.

Standalone functions extracted from TransitionScorer for reuse
by other modules (e.g., CandidateService).
"""

from __future__ import annotations

import math


def bpm_distance(bpm_a: float, bpm_b: float) -> float:
    """Min BPM distance considering double/half-time."""
    direct = abs(bpm_a - bpm_b)
    double = abs(bpm_a - bpm_b * 2)
    half = abs(bpm_a - bpm_b / 2)
    return min(direct, double, half)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity mapped to [0, 1]."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x**2 for x in a))
    norm_b = math.sqrt(sum(x**2 for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, (dot / (norm_a * norm_b) + 1) / 2))


def correlation(a: list[float], b: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = len(a)
    if n == 0:
        return 0.0
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=False)) / n
    std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a) / n)
    std_b = math.sqrt(sum((y - mean_b) ** 2 for y in b) / n)
    if std_a == 0 or std_b == 0:
        return 0.0
    return cov / (std_a * std_b)
