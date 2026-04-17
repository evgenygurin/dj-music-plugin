"""Set optimization domain — GA, greedy, fitness functions."""

from app.v2.domain.optimization.fitness import compute_fitness
from app.v2.domain.optimization.genetic import GeneticAlgorithm
from app.v2.domain.optimization.greedy import GreedyChainBuilder
from app.v2.domain.optimization.protocol import OptimizerStrategy
from app.v2.domain.optimization.result import OptimizationResult

__all__ = [
    "GeneticAlgorithm",
    "GreedyChainBuilder",
    "OptimizationResult",
    "OptimizerStrategy",
    "compute_fitness",
]
