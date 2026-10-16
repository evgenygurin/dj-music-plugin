"""Паттерн Стратегия — семейство взаимозаменяемых алгоритмов."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Context:
    def __init__(self, strategy: Strategy) -> None:
        self._strategy = strategy

    @property
    def strategy(self) -> Strategy:
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: Strategy) -> None:
        self._strategy = strategy

    def do_some_business_logic(self) -> list[str]:
        result = self._strategy.do_algorithm(["a", "b", "c", "d", "e"])
        return result


class Strategy(ABC):
    @abstractmethod
    def do_algorithm(self, data: list[str]) -> list[str]:
        pass


class ConcreteStrategyA(Strategy):
    def do_algorithm(self, data: list[str]) -> list[str]:
        return sorted(data)


class ConcreteStrategyB(Strategy):
    def do_algorithm(self, data: list[str]) -> list[str]:
        return list(reversed(sorted(data)))
