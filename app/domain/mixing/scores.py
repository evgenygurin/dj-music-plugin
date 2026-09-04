"""Decomposable musical score dimensions and deterministic ranking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DimensionScore:
    name: str
    value: float
    weight: float = 1.0
    group: str | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class MusicalScore:
    dimensions: tuple[DimensionScore, ...]
    hard_rejected: bool = False

    def dimension(self, name: str) -> DimensionScore:
        return next(item for item in self.dimensions if item.name == name)

    def grouped_value(self, group: str) -> float:
        values = [item.value for item in self.dimensions if item.group == group]
        return sum(values) / len(values) if values else 0.0

    def spectral_contribution(self) -> float:
        items = [item for item in self.dimensions if item.group == "spectral"]
        if not items:
            return 0.0
        return self.grouped_value("spectral") * max(item.weight for item in items)

    def total(self) -> float:
        groups: dict[str, list[DimensionScore]] = {}
        total = 0.0
        for item in self.dimensions:
            if item.group is None:
                total += item.value * item.weight
            else:
                groups.setdefault(item.group, []).append(item)
        for items in groups.values():
            value = sum(item.value for item in items) / len(items)
            total += value * max(item.weight for item in items)
        return total


def rank_scores(scores: tuple[tuple[str, MusicalScore], ...]) -> tuple[str, ...]:
    acceptable = ((name, score) for name, score in scores if not score.hard_rejected)
    ranked = sorted(acceptable, key=lambda item: (-item[1].total(), item[0]))
    return tuple(name for name, _ in ranked)
