"""
strategy_selector.py — Dynamic strategy selection (v14.5).

Auto-switches between MarketMaker and CrossMarket strategies
based on real-time market conditions:
  - High volatility → MarketMaker (spread-based, safer)
  - Low volatility + CS2Cap available → CrossMarket (arbitrage)
  - Night/Weekend → Conservative (wider spreads, smaller sizes)
  - Event active → Caution (higher margin thresholds)

Used by SnipingLoop to select the active strategy each cycle.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("StrategySelector")


class StrategySelector:
    """Selects the best trading strategy based on current market conditions."""

    def __init__(self):
        self._current_strategy: str = "MarketMaker"
        self._switch_count: int = 0
        self._last_switch_cycle: int = 0

    @property
    def active_strategy(self) -> str:
        return self._current_strategy

    def select(
        self,
        cycle: int,
        cs2cap_ok: bool,
        avg_spread_pct: float = 0.0,
        avg_volatility: float = 0.0,
        is_weekend: bool = False,
        is_night: bool = False,
        event_active: bool = False,
        drawdown_pct: float = 0.0,
    ) -> str:
        """
        Select the best strategy for this cycle.

        Returns one of: "MarketMaker", "CrossMarket", "Conservative"
        """
        # Prevent rapid switching — minimum 20 cycles between changes
        if self._switch_count > 0 and cycle - self._last_switch_cycle < 20:
            return self._current_strategy

        # Drawdown protection: force conservative
        if drawdown_pct >= 5.0:
            self._set_strategy("MarketMaker", cycle, "drawdown_protection")
            return self._current_strategy

        # Event active: force MarketMaker (caution mode)
        if event_active:
            self._set_strategy("MarketMaker", cycle, "event_caution")
            return self._current_strategy

        # Night/Weekend: conservative sizing
        if is_night or is_weekend:
            self._set_strategy("MarketMaker", cycle, "low_liquidity_period")
            return self._current_strategy

        # CS2Cap available + low vol → CrossMarket (arbitrage mode)
        if cs2cap_ok and avg_volatility < 0.30:
            self._set_strategy("CrossMarket", cycle, "low_vol_arbitrage")
            return self._current_strategy

        # High spread → CrossMarket (more profit potential)
        if cs2cap_ok and avg_spread_pct > 8.0:
            self._set_strategy("CrossMarket", cycle, "high_spread")
            return self._current_strategy

        # Default: MarketMaker (safe spread-based)
        self._set_strategy("MarketMaker", cycle, "default")
        return self._current_strategy

    def _set_strategy(self, new: str, cycle: int, reason: str) -> None:
        if new != self._current_strategy:
            self._current_strategy = new
            self._switch_count += 1
            self._last_switch_cycle = cycle
            logger.info(
                f"[Strategy] switched to {new} (cycle {cycle}, reason: {reason})"
            )

    def get_sizing_multiplier(self) -> float:
        """Return position sizing multiplier based on current strategy."""
        multipliers = {
            "MarketMaker": 1.0,
            "CrossMarket": 0.75,   # cross-market has more unknowns
            "Conservative": 0.50,
        }
        return multipliers.get(self._current_strategy, 1.0)

    def get_state(self) -> dict:
        return {
            "active_strategy": self._current_strategy,
            "switch_count": self._switch_count,
            "last_switch_cycle": self._last_switch_cycle,
        }


# Singleton instance
strategy_selector = StrategySelector()
