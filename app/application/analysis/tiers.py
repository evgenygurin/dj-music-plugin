"""Analysis tiers and memory-safe resource limits."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class AnalysisTier(IntEnum):
    BASIC = 1
    MIX_READY = 2
    DEEP = 3


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    """Upper bounds used to protect constrained development/runtime hosts."""

    max_parallel_analysis: int = 1
    max_stem_jobs: int = 1
    max_deep_candidates: int = 8

    def __post_init__(self) -> None:
        if self.max_parallel_analysis < 1:
            raise ValueError("max_parallel_analysis must be positive")
        if self.max_stem_jobs < 0 or self.max_deep_candidates < 0:
            raise ValueError("resource limits must be non-negative")

    def allows_analysis(self, requested: int) -> bool:
        return 0 <= requested <= self.max_parallel_analysis

    def allows_stem_jobs(self, requested: int) -> bool:
        return 0 <= requested <= self.max_stem_jobs

    def allows_deep_candidates(self, requested: int) -> bool:
        return 0 <= requested <= self.max_deep_candidates
