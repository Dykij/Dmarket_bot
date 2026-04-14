"""
Trade Execution Gate.

Deterministic validator between Mathematical Target Sniping logic and the DMarket API.
The gate enforces:
    1. Schema compliance (TradeDecision).
    2. Price floor/ceiling from price_validator.py.
    3. Maximum allowed position size.
    4. Item name sanitization.

The gate re-validates ALL prices against price_validator.py constants.
"""

from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from src.price_validator import (
    MIN_PRICE_USD,
    MAX_PRICE_USD,
    PriceValidationError,
    validate_price,
)


class TradeAction(str, Enum):
    """Allowed trade actions."""
    BUY = "BUY"
    SELL = "SELL"
    SKIP = "SKIP"


class TradeDecision(BaseModel):
    """
    Pydantic schema for structured trade execution.
    """
    action: TradeAction = Field(
        description="The recommended action: BUY, SELL, or SKIP"
    )
    skin_name: str = Field(
        min_length=1,
        max_length=256,
        description="Full item name from DMarket"
    )
    price_usd: float = Field(
        gt=0,
        description="Proposed execution price in USD"
    )

    @field_validator("price_usd")
    @classmethod
    def price_must_be_in_safe_range(cls, v: float) -> float:
        """Enforce price floor/ceiling from price_validator.py."""
        if v < MIN_PRICE_USD:
            raise ValueError(
                f"Price ${v:.4f} below safety floor ${MIN_PRICE_USD:.2f}"
            )
        if v > MAX_PRICE_USD:
            raise ValueError(
                f"Price ${v:.2f} above safety ceiling ${MAX_PRICE_USD:,.0f}"
            )
        return v


class GateViolation(Exception):
    """Raised when the Trade Gate blocks a decision."""
    pass


class TradeExecutionGate:
    """
    Deterministic validator between output and the DMarket API.

    This is the ONLY path from mathematical recommendation to a real trade.
    
    Parameters
    ----------
    max_position_usd : float
        Maximum USD per single trade (default $50.00).
    """

    def __init__(
        self,
        max_position_usd: float = 50.00,
    ):
        self.max_position_usd = max_position_usd

    def evaluate(self, decision: TradeDecision) -> tuple[bool, str]:
        """
        Evaluate a parsed TradeDecision against safety rules.

        Returns
        -------
        (approved, reason) : tuple[bool, str]
            approved: True if the trade is safe to execute.
            reason: Human-readable explanation.
        """
        if decision.action == TradeAction.SKIP:
            return True, "Action is SKIP — no execution needed."

        if decision.price_usd > self.max_position_usd:
            return False, (
                f"Price ${decision.price_usd:.2f} exceeds max position "
                f"${self.max_position_usd:.2f}. Trade blocked."
            )

        try:
            validate_price(decision.price_usd, label=decision.skin_name)
        except PriceValidationError as e:
            return False, f"Price re-validation failed: {e}"

        if any(ord(c) < 32 for c in decision.skin_name):
            return False, "Item name contains control characters. Blocked."

        return True, (
            f"✅ APPROVED: {decision.action.value} '{decision.skin_name}' "
            f"at ${decision.price_usd:.2f}"
        )
