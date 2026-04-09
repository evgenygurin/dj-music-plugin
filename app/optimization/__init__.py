"""Set optimization domain — GA, greedy, fitness functions."""

from app.optimization.fitness import compute_fitness
from app.optimization.genetic import GeneticAlgorithm
from app.optimization.greedy import GreedyChainBuilder
from app.optimization.protocol import OptimizerStrategy
from app.optimization.result import OptimizationResult

__all__ = [
    "GeneticAlgorithm",
    "GreedyChainBuilder",
    "OptimizationResult",
    "OptimizerStrategy",
    "compute_fitness",
]
