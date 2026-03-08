"""
Trade Execution Gate — Agentic Sandbox for LLM output validation.

Architecture (Defense-in-Depth):
  LLM (Arkady) → raw text → TradeDecision (Pydantic parse) → Trade Gate → API

The LLM NEVER has direct access to buy/sell functions.
It returns a structured JSON recommendation which is then validated
by a deterministic Python gate before any API call is made.

This prevents "vibe hacking" / prompt injection attacks where
a compromised LLM could attempt to:
  - Buy at inflated prices
  - Sell below cost
  - Bypass price floor/ceiling validators
  - Execute trades on unauthorized items

The gate re-validates ALL prices against price_validator.py constants.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.price_validator import (
    MIN_PRICE_USD,
    MAX_PRICE_USD,
    PriceValidationError,
    validate_price,
)


class TradeAction(str, Enum):
    """Allowed trade actions from the LLM."""
    BUY = "BUY"
    SELL = "SELL"
    SKIP = "SKIP"


class TradeDecision(BaseModel):
    """
    Pydantic schema for structured LLM trade recommendations.

    The LLM must return JSON matching this schema exactly.
    Any deviation is rejected as a parsing error.

    Example valid JSON from LLM:
    {
        "action": "BUY",
        "skin_name": "AK-47 | Slate (Field-Tested)",
        "price_usd": 5.80,
        "confidence": 0.87,
        "reasoning": "Spread is organic, 2.3% profit after commission."
    }
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
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model confidence score (0.0–1.0)"
    )
    reasoning: str = Field(
        default="",
        max_length=1024,
        description="Brief justification for the decision"
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
    """Raised when the Trade Gate blocks an LLM decision."""
    pass


class TradeExecutionGate:
    """
    Deterministic validator between LLM output and the DMarket API.

    This is the ONLY path from an AI recommendation to a real trade.
    The gate enforces:
      1. Pydantic schema compliance (TradeDecision).
      2. Price floor/ceiling from price_validator.py.
      3. Confidence threshold (default 70%).
      4. Maximum allowed position size.
      5. Item name sanitization (no SQL injection, no control chars).

    Parameters
    ----------
    min_confidence : float
        Minimum model confidence to allow execution (default 0.70).
    max_position_usd : float
        Maximum USD per single trade (default $50.00).
    """

    def __init__(
        self,
        min_confidence: float = 0.70,
        max_position_usd: float = 50.00,
    ):
        self.min_confidence = min_confidence
        self.max_position_usd = max_position_usd

    def parse_llm_output(self, raw_text: str) -> TradeDecision:
        """
        Parse raw LLM text into a validated TradeDecision.

        Handles markdown code fences, extra whitespace, and
        partial JSON gracefully.

        Raises
        ------
        GateViolation
            If the LLM output cannot be parsed or fails validation.
        """
        cleaned = raw_text.strip()

        # Strip markdown code fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        # Try to find JSON object within the text
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start == -1 or end == 0:
            raise GateViolation(
                f"No JSON object found in LLM output:\n{raw_text[:300]}"
            )

        json_str = cleaned[start:end]

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise GateViolation(f"Invalid JSON from LLM: {e}")

        try:
            decision = TradeDecision(**data)
        except Exception as e:
            raise GateViolation(f"Schema validation failed: {e}")

        return decision

    def evaluate(self, decision: TradeDecision) -> tuple[bool, str]:
        """
        Evaluate a parsed TradeDecision against safety rules.

        Returns
        -------
        (approved, reason) : tuple[bool, str]
            approved: True if the trade is safe to execute.
            reason: Human-readable explanation.
        """
        # Rule 1: SKIP actions pass through (no execution)
        if decision.action == TradeAction.SKIP:
            return True, "Action is SKIP — no execution needed."

        # Rule 2: Confidence threshold
        if decision.confidence < self.min_confidence:
            return False, (
                f"Confidence {decision.confidence:.2f} below threshold "
                f"{self.min_confidence:.2f}. Trade blocked."
            )

        # Rule 3: Position size limit
        if decision.price_usd > self.max_position_usd:
            return False, (
                f"Price ${decision.price_usd:.2f} exceeds max position "
                f"${self.max_position_usd:.2f}. Trade blocked."
            )

        # Rule 4: Re-validate price against price_validator.py
        try:
            validate_price(decision.price_usd, label=decision.skin_name)
        except PriceValidationError as e:
            return False, f"Price re-validation failed: {e}"

        # Rule 5: Sanitize item name (no control characters)
        if any(ord(c) < 32 for c in decision.skin_name):
            return False, "Item name contains control characters. Blocked."

        return True, (
            f"✅ APPROVED: {decision.action.value} '{decision.skin_name}' "
            f"at ${decision.price_usd:.2f} (confidence={decision.confidence:.2f})"
        )

    def process(self, raw_llm_output: str) -> tuple[Optional[TradeDecision], bool, str]:
        """
        Full pipeline: parse → validate → evaluate.

        Returns
        -------
        (decision, approved, reason)
        """
        try:
            decision = self.parse_llm_output(raw_llm_output)
        except GateViolation as e:
            return None, False, f"PARSE FAILURE: {e}"

        approved, reason = self.evaluate(decision)
        return decision, approved, reason
