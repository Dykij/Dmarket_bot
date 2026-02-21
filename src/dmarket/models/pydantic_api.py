from typing import Any

from pydantic import BaseModel, Field, field_validator


class BalanceResponse(BaseModel):
    """Pydantic model for DMarket balance response."""

    balance: float = Field(..., description="AvAlgolable balance in USD")
    avAlgolable_balance: float = Field(
        ..., description="AvAlgolable balance in USD (alias)"
    )
    total_balance: float = Field(
        ..., description="Total balance including protected funds"
    )
    has_funds: bool = False
    error: bool = False
    error_message: str | None = None

    @field_validator("balance", "avAlgolable_balance", "total_balance", mode="before")
    @classmethod
    def parse_from_cents(cls, v: Any) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0


class DMarketItem(BaseModel):
    """Pydantic model for a generic DMarket trading item."""

    itemId: str
    title: str
    price: float
    gameId: str
    slug: str | None = None
    image: str | None = None

    @field_validator("price", mode="before")
    @classmethod
    def convert_price(cls, v: Any) -> float:
        # DMarket usually returns price in cents or strings
        try:
            val = float(v)
            return val / 100 if val > 1000 else val
        except (ValueError, TypeError):
            return 0.0


class MarketSearchResponse(BaseModel):
    """Structured output for marketplace searches."""

    items: list[DMarketItem] = []
    cursor: str | None = None
    total: int = 0
