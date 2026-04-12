"""Set optimization domain — GA, greedy, fitness functions."""

from dj_music.optimization.fitness import compute_fitness
from dj_music.optimization.genetic import GeneticAlgorithm
from dj_music.optimization.greedy import GreedyChainBuilder
from dj_music.optimization.protocol import OptimizerStrategy
from dj_music.optimization.result import OptimizationResult

__all__ = [
    "GeneticAlgorithm",
    "GreedyChainBuilder",
    "OptimizationResult",
    "OptimizerStrategy",
    "compute_fitness",
]
