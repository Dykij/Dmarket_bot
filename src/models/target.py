"""Target model."""
from dataclasses import dataclass


@dataclass
class Target:
    user_id: int
    target_id: str
    game: str
    title: str
    price: float
    amount: int | None = None
    status: str = "active"

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "target_id": self.target_id,
            "game": self.game,
            "title": self.title,
            "price": self.price,
            "amount": self.amount,
            "status": self.status,
        }


@dataclass
class TradingSettings:
    user_id: int
    max_trade_value: float | None = None
    daily_limit: float | None = None
    min_profit_percent: float | None = None
    strategy: str | None = None
    auto_trading_enabled: int = 0

    def to_dict(self) -> dict:
        return {
            "max_trade_value": self.max_trade_value,
            "daily_limit": self.daily_limit,
            "min_profit_percent": self.min_profit_percent,
            "strategy": self.strategy,
            "auto_trading_enabled": bool(self.auto_trading_enabled),
        }
