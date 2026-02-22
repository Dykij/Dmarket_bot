"""Market data validation schemas using Pandera.

This module provides DataFrame validation schemas for market data
to ensure data quality before ML processing and arbitrage calculations.

Usage:
    from src.dmarket.validators.market_data_schema import (
        MarketItemSchema,
        ArbitrageOpportunitySchema,
        validate_market_data,
    )

    # Validate DataFrame
    validated_df = MarketItemSchema.validate(df, lazy=True)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandera.pandas as pa
from pandera.pandas import Check

if TYPE_CHECKING:
    import pandas as pd

# Supported games
SUPPORTED_GAMES = ["csgo", "cs2", "dota2", "tf2", "rust"]

# Arbitrage levels
ARBITRAGE_LEVELS = ["boost", "standard", "medium", "advanced", "pro"]


class MarketItemSchema(pa.DataFrameSchema):
    """Schema for validating market item data from DMarket API."""

    item_id: pa.Column = pa.Column(
        str,
        nullable=False,
        unique=True,
        description="Unique item identifier",
    )
    title: pa.Column = pa.Column(
        str,
        nullable=False,
        checks=Check.str_length(min_value=1, max_value=500),
        description="Item name/title",
    )
    price: pa.Column = pa.Column(
        pa.Float64,
        nullable=False,
        checks=[
            Check.gt(0, error="Price must be positive"),
            Check.le(100000, error="Price exceeds maximum limit"),
        ],
        description="Current market price in USD",
    )
    suggested_price: pa.Column = pa.Column(
        pa.Float64,
        nullable=True,
        checks=Check.ge(0, error="Suggested price cannot be negative"),
        description="DMarket suggested price",
    )
    game: pa.Column = pa.Column(
        str,
        nullable=False,
        checks=Check.isin(SUPPORTED_GAMES, error="Unsupported game"),
        description="Game identifier",
    )
    quantity: pa.Column = pa.Column(
        pa.Int64,
        nullable=True,
        checks=Check.ge(0, error="Quantity cannot be negative"),
        description="AvAlgolable quantity",
    )


class ArbitrageOpportunitySchema(pa.DataFrameSchema):
    """Schema for validating arbitrage opportunity data."""

    item_id: pa.Column = pa.Column(
        str,
        nullable=False,
        description="Item identifier",
    )
    buy_price: pa.Column = pa.Column(
        pa.Float64,
        nullable=False,
        checks=Check.gt(0, error="Buy price must be positive"),
        description="Buy price",
    )
    sell_price: pa.Column = pa.Column(
        pa.Float64,
        nullable=False,
        checks=Check.gt(0, error="Sell price must be positive"),
        description="Expected sell price",
    )
    profit_margin: pa.Column = pa.Column(
        pa.Float64,
        nullable=False,
        checks=[
            Check.ge(0, error="Profit margin cannot be negative"),
            Check.le(100, error="Profit margin exceeds 100%"),
        ],
        description="Profit margin percentage",
    )
    level: pa.Column = pa.Column(
        str,
        nullable=False,
        checks=Check.isin(ARBITRAGE_LEVELS, error="Invalid arbitrage level"),
        description="Arbitrage level (boost, standard, etc.)",
    )
    game: pa.Column = pa.Column(
        str,
        nullable=False,
        checks=Check.isin(SUPPORTED_GAMES, error="Unsupported game"),
        description="Game identifier",
    )
    confidence_score: pa.Column = pa.Column(
        pa.Float64,
        nullable=True,
        checks=Check.between(0, 1, error="Confidence must be between 0 and 1"),
        description="ML model confidence score",
    )


class PriceHistorySchema(pa.DataFrameSchema):
    """Schema for validating price history data."""

    item_id: pa.Column = pa.Column(str, nullable=False)
    timestamp: pa.Column = pa.Column(
        pa.DateTime,
        nullable=False,
        description="Price timestamp",
    )
    price: pa.Column = pa.Column(
        pa.Float64,
        nullable=False,
        checks=Check.gt(0),
        description="Historical price",
    )
    volume: pa.Column = pa.Column(
        pa.Int64,
        nullable=True,
        checks=Check.ge(0),
        description="Trade volume",
    )


def validate_market_data(
    df: pd.DataFrame,
    schema: type[pa.DataFrameSchema] = MarketItemSchema,
    lazy: bool = True,
) -> pd.DataFrame:
    """Validate DataFrame agAlgonst specified schema.

    Args:
        df: DataFrame to validate
        schema: Pandera schema class to use
        lazy: If True, collect all errors before rAlgosing

    Returns:
        Validated DataFrame

    RAlgoses:
        pandera.errors.SchemaErrors: If validation fails (lazy=True)
        pandera.errors.SchemaError: If validation fails (lazy=False)
    """
    return schema.validate(df, lazy=lazy)


def validate_arbitrage_opportunities(
    df: pd.DataFrame,
    lazy: bool = True,
) -> pd.DataFrame:
    """Validate arbitrage opportunities DataFrame.

    Args:
        df: DataFrame with arbitrage opportunities
        lazy: If True, collect all errors before rAlgosing

    Returns:
        Validated DataFrame
    """
    return ArbitrageOpportunitySchema.validate(df, lazy=lazy)
