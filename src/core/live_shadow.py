"""
live_shadow.py — Live Shadow Trading (v14.5).

Runs a shadow trading engine 24/7 alongside the real bot.
Every cycle, real market data is mirrored into the shadow portfolio,
which simulates trades without spending real DMarket balance.

Features:
  - Background asyncio task, never blocks the main loop
  - Independent shadow.db with full history
  - Monte Carlo batch simulation for statistical significance
  - Real-vs-shadow P&L comparison
  - Exposed via health server for Prometheus and Telegram

Usage:
    from src.core.live_shadow import live_shadow
    live_shadow.start()
    # ... bot runs ...
    live_shadow.feed_cycle(cycle_data)
    live_shadow.stop()
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import statistics
import time
from dataclasses import dataclass
from typing import Any

from src.core.shadow_engine import ShadowEngine

logger = logging.getLogger("LiveShadow")

LIVE_SHADOW_ENABLED = os.getenv("LIVE_SHADOW_ENABLED", "true").lower() == "true"
MONTE_CARLO_RUNS = int(os.getenv("MONTE_CARLO_RUNS", "1000"))
SHADOW_BALANCE = float(os.getenv("SHADOW_BALANCE", "100.0"))


@dataclass
class MonteCarloResult:
    runs: int
    mean_pnl: float
    median_pnl: float
    std_pnl: float
    min_pnl: float
    max_pnl: float
    pnl_5th: float       # 5th percentile (Value at Risk 95%)
    pnl_95th: float      # 95th percentile
    win_rate_mean: float
    profit_probability: float  # % of runs that were profitable
    sharpe_estimate: float
    max_drawdown_mean: float
    distribution: list[float]  # full distribution for histograms


class LiveShadow:
    """Live shadow trading engine running alongside the real bot."""

    def __init__(self):
        self._engine = ShadowEngine(initial_balance=SHADOW_BALANCE)
        self._enabled = LIVE_SHADOW_ENABLED
        self._started = False
        self._total_cycles: int = 0
        self._last_feed: float = 0.0
        self._monte_carlo_task: asyncio.Task | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def engine(self) -> ShadowEngine:
        return self._engine

    @property
    def total_cycles(self) -> int:
        return self._total_cycles

    def start(self) -> None:
        """Enable live shadow tracking."""
        if not self._enabled:
            return
        self._started = True
        logger.info(f"[LiveShadow] Started — initial balance ${SHADOW_BALANCE:.2f}")

    def stop(self) -> None:
        """Stop live shadow tracking."""
        self._started = False
        logger.info(f"[LiveShadow] Stopped after {self._total_cycles} cycles")

    def feed_cycle(
        self,
        *,
        candidates: list[dict[str, Any]],
        agg_prices: dict[str, Any],
        oracle_ok: bool = False,
    ) -> dict[str, Any] | None:
        """
        Feed one trading cycle's data into the shadow engine.
        Called from the main bot loop each cycle.
        Returns shadow cycle summary or None if disabled.
        """
        if not self._enabled or not self._started:
            return None

        self._total_cycles += 1
        self._last_feed = time.time()

        if not candidates and not agg_prices:
            return None

        # Build simple candidates from agg_prices if none provided
        cands = candidates if candidates else self._build_candidates(agg_prices)
        if not cands:
            return None

        try:
            result = self._engine.record_cycle(
                candidates=cands,
                agg_prices=agg_prices,
                oracle_ok=oracle_ok,
                cycle=self._total_cycles,
                max_buys=2,
                max_spend_per_cycle=SHADOW_BALANCE * 0.05,
            )

            if self._total_cycles % 50 == 0:
                summary = self._engine.get_portfolio_summary()
                logger.info(
                    f"[LiveShadow] Cycle {self._total_cycles}: "
                    f"equity=${summary['total_equity']:.2f} "
                    f"PnL=${summary['total_pnl']:+.2f} "
                    f"({summary['total_trades']} trades, "
                    f"WR={summary['win_rate']:.0f}%)"
                )
            return result
        except Exception as e:
            logger.debug(f"[LiveShadow] Cycle feed error: {e}")
            return None

    def get_status(self) -> dict[str, Any]:
        """Get live shadow status for Telegram / health server."""
        if not self._enabled:
            return {"enabled": False}

        summary = self._engine.get_portfolio_summary()
        return {
            "enabled": True,
            "cycles": self._total_cycles,
            "last_feed_seconds_ago": round(time.time() - self._last_feed, 0) if self._last_feed > 0 else -1,
            "initial_balance": round(SHADOW_BALANCE, 2),
            **summary,
        }

    def compare_with_real(self, real_equity: float) -> dict[str, Any]:
        """Compare shadow P&L with real bot P&L."""
        shadow_summary = self._engine.get_portfolio_summary()
        shadow_pnl = shadow_summary["total_pnl"]
        real_pnl = real_equity - SHADOW_BALANCE

        return {
            "shadow_pnl": round(shadow_pnl, 2),
            "real_pnl": round(real_pnl, 2),
            "delta": round(shadow_pnl - real_pnl, 2),
            "shadow_roi": shadow_summary["roi_pct"],
            "real_roi": round((real_pnl / SHADOW_BALANCE) * 100, 1) if SHADOW_BALANCE > 0 else 0,
            "shadow_trades": shadow_summary["total_trades"],
            "shadow_wr": shadow_summary["win_rate"],
        }

    @staticmethod
    def _build_candidates(agg_prices: dict[str, Any]) -> list[dict[str, Any]]:
        cands = []
        for title, agg in list(agg_prices.items())[:20]:
            ask = agg.get("best_ask", 0) or 0
            bid = agg.get("best_bid", 0) or 0
            if ask <= 0:
                continue
            margin = ((bid - ask) / ask * 100) if bid > 0 else 0
            cands.append({
                "title": title,
                "dm_buy_price": ask,
                "best_ask": ask,
                "best_bid": bid,
                "margin_pct": margin,
                "strategy": "CrossMarket" if margin > 3 else "MarketMaker",
            })
        return cands

    # ─────────────────────────────────────────────
    # Monte Carlo
    # ─────────────────────────────────────────────

    async def run_monte_carlo(
        self,
        candidates: list[dict[str, Any]],
        agg_prices: dict[str, Any],
        runs: int = MONTE_CARLO_RUNS,
        cycles: int = 30,
    ) -> MonteCarloResult:
        """
        Run N independent shadow simulations with random price noise.
        Computes full P&L distribution for statistical significance.

        Returns MonteCarloResult with mean, median, VaR, etc.
        """
        if not agg_prices:
            raise ValueError("No agg_prices for Monte Carlo")

        cands = candidates if candidates else self._build_candidates(agg_prices)
        if not cands:
            raise ValueError("No candidates for Monte Carlo")

        pnls: list[float] = []
        win_rates: list[float] = []
        max_dds: list[float] = []

        sem = asyncio.Semaphore(50)  # limit concurrency

        async def _run_one(run_id: int) -> tuple[float, float, float]:
            """Run a single Monte Carlo simulation with random noise."""
            async with sem:
                engine = ShadowEngine(initial_balance=SHADOW_BALANCE)

                # Add random noise to prices (±5% per cycle)
                noisy_agg = {}
                for title, agg in agg_prices.items():
                    noisy = dict(agg)
                    for key in ("best_ask", "best_bid"):
                        val = noisy.get(key, 0) or 0
                        if val > 0:
                            noise = random.normalvariate(0, val * 0.005)  # 0.5% sigma noise
                            noisy[key] = max(0.01, val + noise)
                    noisy_agg[title] = noisy

                for cycle in range(cycles):
                    # Regenerate noise each cycle for realistic volatility
                    for title in noisy_agg:
                        for key in ("best_ask", "best_bid"):
                            val = noisy_agg[title].get(key, 0) or 0
                            if val > 0:
                                noisy_agg[title][key] = max(0.01, val * random.uniform(0.997, 1.003))

                    engine.record_cycle(
                        candidates=cands,
                        agg_prices=noisy_agg,
                        oracle_ok=True,
                        cycle=cycle,
                        max_buys=2,
                        max_spend_per_cycle=SHADOW_BALANCE * 0.03,
                    )

                summary = engine.get_portfolio_summary()
                return (
                    summary["total_pnl"],
                    summary["win_rate"],
                    summary["drawdown_pct"],
                )

        # Run all simulations in parallel batches
        batch_size = 100
        for batch_start in range(0, runs, batch_size):
            batch_end = min(batch_start + batch_size, runs)
            tasks = [_run_one(i) for i in range(batch_start, batch_end)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, tuple):
                    pnls.append(r[0])
                    win_rates.append(r[1])
                    max_dds.append(r[2])

            if batch_start == 0:
                logger.info(
                    f"[MonteCarlo] Running {runs} simulations "
                    f"({cycles} cycles each)..."
                )

        # Compute statistics
        pnls_sorted = sorted(pnls)
        n = len(pnls_sorted)
        mean_pnl = statistics.mean(pnls)
        median_pnl = statistics.median(pnls)
        std_pnl = statistics.stdev(pnls) if n > 1 else 0.0

        return MonteCarloResult(
            runs=n,
            mean_pnl=round(mean_pnl, 2),
            median_pnl=round(median_pnl, 2),
            std_pnl=round(std_pnl, 2),
            min_pnl=round(min(pnls), 2),
            max_pnl=round(max(pnls), 2),
            pnl_5th=round(pnls_sorted[max(0, int(n * 0.05))], 2),
            pnl_95th=round(pnls_sorted[min(n - 1, int(n * 0.95))], 2),
            win_rate_mean=round(statistics.mean(win_rates), 1),
            profit_probability=round(
                sum(1 for p in pnls if p > 0) / max(n, 1) * 100, 1
            ),
            sharpe_estimate=round(mean_pnl / max(std_pnl, 0.01), 2),
            max_drawdown_mean=round(statistics.mean(max_dds), 1),
            distribution=pnls_sorted,
        )

    async def run_monte_carlo_async(self) -> MonteCarloResult | None:
        """Run Monte Carlo asynchronously — can be called from Telegram."""
        if self._monte_carlo_task and not self._monte_carlo_task.done():
            return None  # already running

        # Use last known agg_prices from the main bot
        return None  # will be called from bot context


# Singleton instance
live_shadow = LiveShadow()
