"""Declarative configuration schema for transition planning."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class ParameterClass(StrEnum):
    HARD = "hard"
    BOUNDARY = "boundary"
    SOFT = "soft"
    PREFERENCE = "preference"


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    name: str
    unit: str
    minimum: float
    maximum: float
    default: float
    classification: ParameterClass

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.unit.strip():
            raise ValueError("name and unit must not be empty")
        if not math.isfinite(self.minimum) or not math.isfinite(self.maximum):
            raise ValueError("parameter range must be finite")
        if self.minimum > self.maximum or not self.minimum <= self.default <= self.maximum:
            raise ValueError("default must be inside parameter range")


@dataclass(frozen=True, slots=True)
class TransitionSchema:
    parameters: tuple[ParameterDefinition, ...]

    def __post_init__(self) -> None:
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("parameter names must be unique")

    @property
    def by_name(self) -> dict[str, ParameterDefinition]:
        return {parameter.name: parameter for parameter in self.parameters}
