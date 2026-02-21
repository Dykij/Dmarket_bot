from typing import Any
import pandera.pandas as pa
from pandera.typing.pandas import Series
from pydantic import BaseModel, Field, field_validator


class MarketItemSchema(pa.DataFrameModel):
    """Схема для валидации списка предметов с DMarket."""

    item_id: Series[str] = pa.Field(alias="itemId", check_name=True)
    title: Series[str] = pa.Field()
    price: Series[float] = pa.Field(ge=0.0)  # Price must be non-negative
    currency: Series[str] = pa.Field(eq="USD")
    suggested_price: Series[float] = pa.Field(
        alias="suggestedPrice", nullable=True, coerce=True
    )

    class Config:
        strict = True
        coerce = True  # Try to convert types (e.g. str price to float)


# Pydantic-style wrapper for API responses (compatibility layer)


class MarketItem(BaseModel):
    item_id: str = Field(alias="itemId")
    title: str
    price: (
        dict[str, str | int] | float
    )  # DMarket returns weird price structures sometimes
    suggested_price: float | None = Field(default=None, alias="suggestedPrice")

    @field_validator("price", "suggested_price", mode="before")
    @classmethod
    def parse_price(cls, v):
        if isinstance(v, dict) and "USD" in v:
            return float(v["USD"]) / 100
        return v


class MarketItemsResponse(BaseModel):
    objects: list[MarketItem] = []
    cursor: str | None = None


class AggregatedPriceItem(BaseModel):
    title: str
    price: float | dict[str, Any]
    volume: int | None = None


class AggregatedPricesResponse(BaseModel):
    items: list[AggregatedPriceItem] = []
    cursor: str | None = None


class BuyOfferResult(BaseModel):
    offer_id: str
    status: str
    price: float | None = None


class BuyOffersResponse(BaseModel):
    results: list[BuyOfferResult] = []
    total_spent: float = 0.0
    currency: str = "USD"
