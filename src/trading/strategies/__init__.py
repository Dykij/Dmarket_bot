"""Strategy Factory module."""

from typing import Type

from src.trading.strategies.base import BaseStrategy
from src.trading.strategies.cs2 import CS2Strategy
from src.trading.strategies.dota2 import Dota2Strategy
from src.trading.strategies.rust import RustStrategy
from src.trading.strategies.tf2 import TF2Strategy


class StrategyFactory:
    """Factory for creating game-specific trading strategies."""

    _strategies: dict[str, Type[BaseStrategy]] = {
        "csgo": CS2Strategy,
        "cs2": CS2Strategy,  # Alias
        "dota2": Dota2Strategy,
        "rust": RustStrategy,
        "tf2": TF2Strategy,
    }

    @classmethod
    def get_strategy(cls, game_id: str) -> BaseStrategy:
        """Get strategy instance for the specified game."""
        strategy_class = cls._strategies.get(game_id.lower())

        if not strategy_class:
            raise ValueError(f"No strategy found for game: {game_id}")

        return strategy_class()
