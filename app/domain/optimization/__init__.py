"""Set optimization domain — GA, greedy, fitness functions."""

from app.domain.optimization.fitness import compute_fitness
from app.domain.optimization.genetic import GeneticAlgorithm
from app.domain.optimization.greedy import GreedyChainBuilder
from app.domain.optimization.protocol import OptimizerStrategy
from app.domain.optimization.result import OptimizationResult

__all__ = [
    "GeneticAlgorithm",
    "GreedyChainBuilder",
    "OptimizationResult",
    "OptimizerStrategy",
    "compute_fitness",
]
