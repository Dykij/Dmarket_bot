"""
MarketMaker — оболочка стратегии, остаток после чистки мёртвого кода (2026-11-19).

Живое использование: ``resale_pipeline`` создаёт ``MarketMaker()`` только ради
``calculate_turnover_penalty()`` из BaseStrategy. Прежняя логика
``evaluate_opportunity`` (спред-маркет-мейкинг) не вызывалась из живого контура
и удалена. Метод оставлен заглушкой, потому что он абстрактный в BaseStrategy:
без него ``MarketMaker()`` не создаётся.
"""

from typing import Any

from src.strategies.base import BaseStrategy


class MarketMaker(BaseStrategy):
    def __init__(self):
        super().__init__("MarketMaker")

    def evaluate_opportunity(self, market_data: dict[str, Any]) -> dict[str, Any]:
        """Заглушка: стратегия не торгует (абстрактный метод BaseStrategy)."""
        return {"action": "none"}
