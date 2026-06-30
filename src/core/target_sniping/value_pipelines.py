"""
value_pipelines.py — Value Detection Scanner for DMarket skins (v14.9).

This module implements a DUAL-SIGNAL pipeline for the bot's strategy
as described in README.md: Value Detection Scanner + Spread Sniping.

Primary Signal — VALUE:
  Buy when estimated sell price (base on rarity) > ask * (1 + fee + min_margin).
  This is the core of the "buy cheap, sell at premium" strategy.
  Uses float, pattern, sticker, and phase premiums.

Secondary Signal — SPREAD:
  Fallback to intra-DMarket spread (best_bid > best_ask * margin).
  This catches liquid items with natural bid-ask spreads.

The mix between Value and Spread is tunable via `Config.VALUE_SIGNAL_WEIGHT`.

Author: DMarket Bot
Version: 14.9
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config import Config
from src.db.price_history import price_db
from src.utils.decimal_helpers import D, quantize
from src.core.target_sniping.pricing import (
    get_float_premium,
    get_pattern_premium,
)

logger = logging.getLogger("SnipingBot")


def calculate_value_premium(
    attrs: Dict[str, Any],
    stickers: List[Dict[str, Any]],
) -> Decimal:
    """
    Calculate total rarity/value premium for an item based on:
    - Float premium (rare floats)
    - Pattern/phase premium (Ruby, Sapphire, Blue Gem, etc.)
    - Sticker value premium

    Returns a multiplier (e.g., 1.0 = no premium, 1.25 = 25% premium).
    """
    # Float premium
    float_mult = D(get_float_premium(attrs))

    # Pattern/phase premium
    pattern_mult = D(get_pattern_premium(attrs))

    # Sticker premium (simplified: $ amount per sticker)
    sticker_mult = D("1.0")
    if stickers and Config.STICKER_COMBO_ENABLED:
        # Simple sticker combo: 4 same stickers = +100%
        # Count stickers and unique sticker counts
        from collections import Counter
        names = [s.get("name", "") for s in stickers if s.get("name")]
        if names:
            most_common = Counter(names).most_common(1)[0][1]
            if most_common >= 4:
                sticker_mult = D("2.0")  # +100%
            elif most_common == 3:
                sticker_mult = D("1.5")  # +50%
            elif most_common == 2:
                sticker_mult = D("1.2")  # +20%

    # Use the maximum of all premiums (they're multiplicative, but we want
    # the dominant one as the primary driver)
    return max(float_mult, pattern_mult, sticker_mult, D("1.0"))


def estimate_fair_sell_price(
    base_ask: Decimal,
    cs2cap_ask: Decimal,
    premium_mult: Decimal,
) -> Decimal:
    """
    Estimate the expected sell price for an item based on:
    - Base ask price (what we would pay)
    - CS2Cap reference price (market floor)
    - Premium multiplier from rarity

    We todo: want to sell at min(CS2Cap ask * premium, but also above cost + fees).
    """
    # Fair value with premium applied to CS2Cap reference
    fair_value = cs2cap_ask * premium_mult
    # Or use base ask + premium (whichever is higher)
    fair_value = max(fair_value, base_ask * premium_mult)
    return quantize(fair_value)


def evaluate_value_signal(
    title: str,
    base_price: Decimal,
    cs2cap_ask: Decimal,
    attrs: Dict[str, Any],
    stickers: List[Dict[str, Any]],
    fee_rate: Decimal,
) -> Optional[Dict[str, Any]]:
    """
    Evaluate the VALUE signal for a candidate item.

    Returns a dict with buy decision or None if the item doesn't pass.
    """
    if not Config.VALUE_SCAN_ENABLED:
        return None

    if cs2cap_ask <= 0:
        return None

    # Calculate rarity premium
    premium_mult = calculate_value_premium(attrs, stickers)
    if premium_mult <= 1 and not Config.VALUE_SCAN_MIN_PREMIUM > 1:
        # No rarity detected and we're not forcing value-only mode
        return None

    # Calculate estimated sell price with premium
    est_sell = estimate_fair_sell_price(base_price, cs2cap_ask, premium_mult)

    # Must sell at profit after fees
    required_sell = base_price * (Decimal(1) + fee_rate + Config.WITHDRAWAL_FEE_RATE + Config.VALUE_SCAN_MIN_PROFIT_PCT / Decimal(100))

    if est_sell <= required_sell:
        return None

    # Also require a minimum absolute profit so it's worth our time
    min_profit_usd = Config.VALUE_SCAN_MIN_PROFIT_USD
    if (est_sell - base_price) < min_profit_usd:
        return None

    # Passed value signal
    estimated_profit = est_sell - base_price
    estimated_roi = (estimated_profit / base_price) * Decimal(100) if base_price > 0 else D("0")

    is_sandbox = Config.DRY_RUN
    if is_sandbox:
        price_db.log_decision(
            title,
            "pass_value",
            "Value signal — rarity-based",
            f"base=${base_price:.2f} fair=${cs2cap_ask:.2f} "
            f"premium={premium_mult:.2f}x est_sell=${est_sell:.2f} "
            f"profit=${estimated_profit:.2f} ({estimated_roi:.1f}%)",
        )

    return {
        "signal_type": "value",
        "premium_mult": premium_mult,
        "est_sell_price": est_sell,
        "est_profit": estimated_profit,
        "est_roi_pct": estimated_roi,
        "pass": True,
    }


def evaluate_spread_signal(
    title: str,
    base_price: Decimal,
    best_bid: Decimal,
    best_ask: Decimal,
    fee_rate: Decimal,
    current_margin: Decimal,
) -> Optional[Dict[str, Any]]:
    """
    Evaluate the SPREAD signal (traditional intra-market spread).
    Returns dict or None.
    """
    if best_bid <= 0 or best_ask <= 0:
        return None

    spread_ratio = (best_bid - best_ask) / best_ask if best_ask > 0 else D("0")
    required = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE + current_margin

    if spread_ratio < required:
        return None

    est_sell = best_bid - Config.INTRA_LIST_DISCOUNT
    is_sandbox = Config.DRY_RUN
    if is_sandbox:
        price_db.log_decision(
            title,
            "pass_spread",
            "Spread signal — intra-market",
            f"base=${base_price:.2f} spread={float(spread_ratio):.1%}",
        )

    return {
        "signal_type": "spread",
        "spread_ratio": spread_ratio,
        "est_sell_price": quantize(est_sell),
        "pass": True,
    }


def evaluate_combined_signal(
    title: str,
    item: Dict[str, Any],
    cs2cap_ask: Decimal,
    best_bid: Decimal,
    best_ask: Decimal,
    fee_rate: Decimal,
    current_margin: Decimal,
) -> Optional[Dict[str, Any]]:
    """
    Main entry point: evaluate BOTH value and spread signals.

    Priority:
      1. If value signal passes -> return value-based buy signal
      2. If spread signal passes -> return spread-based buy signal
      3. Otherwise -> None

    This allows the bot to find both:
      a) Undervalued rare items (value scanner mode)
      b) Liquid items with natural spread (HFT mode)
    """
    base_price = D(int(item.get("price", {}).get("USD", 0))) / Decimal(100)
    if base_price <= 0:
        return None
    
    # Extract attributes
    attrs_list = item.get("attributes", []) or []
    attrs = {a.get("name"): a.get("value") for a in attrs_list}
    stickers = item.get("stickers", []) or []

    # --- Try PRIMARY signal: VALUE ---
    value_result = evaluate_value_signal(
        title=title,
        base_price=base_price,
        cs2cap_ask=cs2cap_ask,
        attrs=attrs,
        stickers=stickers,
        fee_rate=fee_rate,
    )
    if value_result is not None:
        value_result["base_price"] = base_price
        value_result["list_price"] = value_result["est_sell_price"]
        return value_result

    # --- Try SECONDARY signal: SPREAD ---
    spread_result = evaluate_spread_signal(
        title=title,
        base_price=base_price,
        best_bid=best_bid,
        best_ask=best_ask,
        fee_rate=fee_rate,
        current_margin=current_margin,
    )
    if spread_result is not None:
        spread_result["base_price"] = base_price
        spread_result["list_price"] = spread_result["est_sell_price"]
        return spread_result

    return None
