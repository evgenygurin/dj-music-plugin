"""Backward-compatibility shim — real code lives in app.optimization.

Will be removed in Phase 5 (cleanup).
"""

from app.optimization.fitness import compute_fitness as compute_fitness
from app.optimization.genetic import GeneticAlgorithm as GeneticAlgorithm
from app.optimization.greedy import GreedyChainBuilder as GreedyChainBuilder
from app.optimization.result import OptimizationResult as OptimizationResult
