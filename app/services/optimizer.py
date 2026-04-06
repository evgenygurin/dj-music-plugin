"""Backward-compatibility shim — real code lives in app.domain.optimization.

Will be removed in Phase 5 (cleanup).
"""

from app.domain.optimization.fitness import compute_fitness as compute_fitness
from app.domain.optimization.genetic import GeneticAlgorithm as GeneticAlgorithm
from app.domain.optimization.greedy import GreedyChainBuilder as GreedyChainBuilder
from app.domain.optimization.result import OptimizationResult as OptimizationResult
