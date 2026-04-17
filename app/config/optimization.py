"""Set optimization algorithm settings (GA + greedy)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OptimizationSettings(BaseSettings):
    """Genetic algorithm knobs."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_GA_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    population_size: int = Field(default=50, ge=10, le=500)
    max_generations: int = Field(default=100, ge=10, le=1000)
    mutation_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    elitism_rate: float = Field(default=0.1, ge=0.0, le=0.5)
    tournament_size: int = Field(default=5, ge=2, le=20)
    convergence_threshold: int = Field(default=20, ge=5, le=200)
    two_opt_iterations: int = Field(default=50, ge=0, le=500)
