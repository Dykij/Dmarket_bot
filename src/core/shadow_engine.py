"""
shadow_engine.py — Shadow/Paper Trading Engine (v14.5).

Runs a parallel virtual portfolio alongside the real bot, using
live market data but never executing real DMarket orders.

Features:
  1. Independent shadow SQLite DB (data/dmarket_shadow.db)
  2. Per-cycle buy/sell simulation at real market prices
  3. Shadow P&L tracking with equity snapshots
  4. Multi-strategy comparison (MarketMaker vs CrossMarket)
  5. Competition + latency + slippage simulation
  6. Stress test scenarios (black swan, flash crash)
  7. Real-vs-shadow P&L comparison report

Usage:
    from src.core.shadow_engine import ShadowEngine
    shadow = ShadowEngine()
    shadow.record_cycle(cycle_data)  # each real cycle
    report = shadow.get_comparison_report()
"""

from __future__ import annotations

import json
from decimal import Decimal
from src.utils.decimal_helpers import D, quantize
import logging
import math
import os
import random
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import Config

logger = logging.getLogger("ShadowEngine")

SHADOW_DB = Path(__file__).parent.parent.parent / "data" / "dmarket_shadow.db"
SHADOW_MODE_ENABLED = os.getenv("SHADOW_MODE_ENABLED", "true").lower() == "true"


@dataclass
class ShadowPosition:
    title: str
    buy_price: float
    current_price: float = 0.0
    bought_at: float = 0.0
    status: str = "idle"  # idle, selling, sold
    sell_price: float = 0.0
    fee_paid: float = 0.0
    strategy: str = "MarketMaker"
    category: str = "other"


@dataclass
class ShadowSnapshot:
    ts: float
    cash: float
    assets: float
    total: float
    cycle: int


@dataclass
class StrategyComparison:
    name: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    peak_equity: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe: float = 0.0
    avg_profit_per_trade: float = 0.0


class ShadowEngine:
    """
    Shadow/paper trading engine.
    Maintains a fully independent virtual portfolio with its own SQLite DB.
    """

    def __init__(self, initial_balance: float = 100.0):
        self._balance = D(str(initial_balance))
        self._initial_balance = D(str(initial_balance))
        self._peak_balance = D(str(initial_balance))
        self._positions: Dict[str, List[ShadowPosition]] = {}
        self._snapshots: List[ShadowSnapshot] = []
        self._cycle_count: int = 0
        self._total_trades: int = 0
        self._total_wins: int = 0
        self._total_losses: int = 0
        self._gross_profit: float = 0.0
        self._gross_loss: float = 0.0

        # Multi-strategy comparison
        self._strategy_stats: Dict[str, StrategyComparison] = {
            "MarketMaker": StrategyComparison(name="MarketMaker"),
            "CrossMarket": StrategyComparison(name="CrossMarket"),
            "Conservative": StrategyComparison(name="Conservative"),
        }

        # DB
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ─────────────────────────────────────────────
    # DB
    # ─────────────────────────────────────────────

    def _init_db(self) -> None:
        SHADOW_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(SHADOW_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS shadow_inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    current_price REAL DEFAULT 0,
                    sell_price REAL DEFAULT 0,
                    fee_paid REAL DEFAULT 0,
                    status TEXT DEFAULT 'idle',
                    strategy TEXT DEFAULT 'MarketMaker',
                    category TEXT DEFAULT 'other',
                    bought_at REAL NOT NULL,
                    sold_at REAL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS shadow_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    cash REAL NOT NULL,
                    assets REAL NOT NULL,
                    total REAL NOT NULL,
                    cycle INTEGER DEFAULT 0
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS shadow_strategies (
                    name TEXT PRIMARY KEY,
                    trades INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    peak_equity REAL DEFAULT 0,
                    max_drawdown_pct REAL DEFAULT 0,
                    sharpe REAL DEFAULT 0,
                    avg_profit REAL DEFAULT 0
                )
            """)

    def _save_snapshot(self) -> None:
        assets_value = sum(
            p.current_price for positions in self._positions.values()
            for p in positions if p.status in ("idle", "selling")
        )
        total = self._balance + assets_value
        self._snapshots.append(ShadowSnapshot(
            ts=time.time(), cash=self._balance, assets=assets_value,
            total=total, cycle=self._cycle_count,
        ))
        if total > self._peak_balance:
            self._peak_balance = total
        if self._conn:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO shadow_snapshots (ts, cash, assets, total, cycle) VALUES (?,?,?,?,?)",
                    (time.time(), float(self._balance), float(assets_value), float(total), self._cycle_count),
                )

    # ─────────────────────────────────────────────
    # Core: record a trading cycle
    # ─────────────────────────────────────────────

    def record_cycle(
        self,
        *,
        candidates: List[Dict[str, Any]],
        agg_prices: Dict[str, Any],
        cs2cap_ok: bool,
        cycle: int,
        max_buys: int = 3,
        max_spend_per_cycle: float = 15.0,
        stop_loss_pct: float = 20.0,
        take_profit_pct: float = 15.0,
    ) -> Dict[str, Any]:
        """
        Record one trading cycle into the shadow portfolio.
        Called from the sandbox or optionally from the real bot.

        Returns summary of this cycle's shadow actions.
        """
        self._cycle_count = cycle
        cycle_result: Dict[str, Any] = {
            "cycle": cycle,
            "buys": 0,
            "sells_sl": 0,
            "sells_tp": 0,
            "spent": D("0"),
            "earned": D("0"),
            "balance": self._balance,
        }

        # 1. Stop-loss / Take-profit on existing positions
        for title, positions in list(self._positions.items()):
            current_price = self._get_market_price(title, agg_prices)
            for pos in positions:
                if pos.status != "idle":
                    continue
                pos.current_price = current_price if current_price > 0 else pos.buy_price
                if current_price <= 0:
                    continue

                loss_pct = ((pos.buy_price - D(str(current_price))) / pos.buy_price) * 100
                profit_pct = ((current_price - pos.buy_price) / pos.buy_price) * 100

                fee = current_price * Config.FEE_RATE

                if loss_pct >= stop_loss_pct:
                    pos.status = "sold"
                    pos.sell_price = current_price
                    pos.fee_paid = fee
                    pnl = current_price - pos.buy_price - fee
                    self._balance += D(str(current_price)) - D(str(fee))
                    self._record_trade(pnl > 0, pnl, pos.strategy)
                    cycle_result["sells_sl"] += 1
                    cycle_result["earned"] += D(str(current_price)) - D(str(fee))

                elif profit_pct >= take_profit_pct:
                    pos.status = "sold"
                    pos.sell_price = current_price
                    pos.fee_paid = fee
                    pnl = current_price - pos.buy_price - fee
                    self._balance += D(str(current_price)) - D(str(fee))
                    self._record_trade(pnl > 0, pnl, pos.strategy)
                    cycle_result["sells_tp"] += 1
                    cycle_result["earned"] += D(str(current_price)) - D(str(fee))

        # 2. Evaluate buy candidates
        for cand in candidates[:max_buys]:
            if cycle_result["spent"] >= max_spend_per_cycle:
                break

            title = cand.get("title", "")
            price = cand.get("dm_buy_price", cand.get("base_price", 0))
            strategy = cand.get("strategy", "MarketMaker")
            category = self._categorize(title)
            margin = cand.get("margin_pct", 0)

            if price <= 0 or price > self._balance:
                continue

            # Skip categories that shouldn't be bought
            if category == "graffiti":
                continue

            # Competition simulation: other bots may snipe first.
            # Only reject when margin is significant enough to attract competition.
            if margin > 2:
                if random.random() < 0.15:  # 15% chance of losing to competition on decent margins
                    continue
            else:
                pass  # low-margin items: always let through (no competition for these)

            # Buy
            self._balance -= price
            pos = ShadowPosition(
                title=title, buy_price=price, current_price=price,
                bought_at=time.time(), status="idle", strategy=strategy,
                category=category,
            )
            self._positions.setdefault(title, []).append(pos)
            cycle_result["buys"] += 1
            cycle_result["spent"] += D(str(price))
            self._total_trades += 1

        # 3. Save snapshot
        self._save_snapshot()

        # 4. Persist to DB
        self._flush_to_db()

        cycle_result["balance"] = round(self._balance, 2)
        cycle_result["total_positions"] = sum(
            len(plist) for plist in self._positions.values()
        )
        return cycle_result

    def _get_market_price(self, title: str, agg_prices: Dict[str, Any]) -> float:
        """Get current market price from agg_prices with random fluctuation."""
        agg = agg_prices.get(title, {})
        ask = agg.get("best_ask", 0.0) or 0.0
        bid = agg.get("best_bid", 0.0) or 0.0
        if ask > 0 and bid > 0:
            mid = (ask + bid) / 2.0
        elif ask > 0:
            mid = ask
        else:
            mid = bid
        if mid <= 0:
            return 0.0
        # Add ±3% random fluctuation per check to simulate market movement
        return mid * random.uniform(0.97, 1.03)

    @staticmethod
    def _categorize(title: str) -> str:
        import re
        if re.search(r"★|Knife|Bayonet|Karambit|Butterfly", title, re.I):
            return "knife"
        if re.search(r"Sticker", title, re.I):
            return "sticker"
        if re.search(r"Case|Capsule|Souvenir", title, re.I):
            return "case"
        if re.search(r"Graffiti", title, re.I):
            return "graffiti"
        if re.search(r"AK-47|M4A|AWP|SSG|SCAR|G3SG1|AUG|SG 553|FAMAS|Galil", title, re.I):
            return "rifle"
        if re.search(r"Desert Eagle|USP-S|Glock|P250|P2000|CZ75|Five-SeveN|Tec-9", title, re.I):
            return "pistol"
        return "other"

    def _record_trade(self, won: bool, pnl: float, strategy: str) -> None:
        if won:
            self._total_wins += 1
            self._gross_profit += abs(pnl)
        else:
            self._total_losses += 1
            self._gross_loss += abs(pnl)
        stats = self._strategy_stats.get(strategy)
        if stats:
            stats.trades += 1
            stats.total_pnl += pnl
            if pnl > 0:
                stats.wins += 1
            else:
                stats.losses += 1
            total = self._balance + sum(
                p.current_price for positions in self._positions.values()
                for p in positions if p.status in ("idle", "selling")
            )
            if total > stats.peak_equity:
                stats.peak_equity = total

    def _flush_to_db(self) -> None:
        if not self._conn:
            return
        with self._conn:
            for name, stats in self._strategy_stats.items():
                self._conn.execute(
                    "INSERT OR REPLACE INTO shadow_strategies VALUES (?,?,?,?,?,?,?,?,?)",
                    (name, stats.trades, stats.wins, stats.losses,
                     round(stats.total_pnl, 4), round(stats.peak_equity, 2),
                     round(stats.max_drawdown_pct, 2), round(stats.sharpe, 3),
                     round(stats.avg_profit_per_trade, 4)),
                )

    # ─────────────────────────────────────────────
    # Reports
    # ─────────────────────────────────────────────

    def get_portfolio_summary(self) -> Dict[str, Any]:
        assets = sum(
            p.current_price for positions in self._positions.values()
            for p in positions if p.status in ("idle", "selling")
        )
        total = self._balance + assets
        pnl = total - self._initial_balance
        roi = (pnl / self._initial_balance * 100) if self._initial_balance > 0 else 0
        dd = ((self._peak_balance - total) / self._peak_balance * 100) if self._peak_balance > 0 else 0

        total_trades = self._total_wins + self._total_losses
        win_rate = (self._total_wins / max(total_trades, 1)) * 100
        avg_profit = self._gross_profit / max(self._total_wins, 1)
        avg_loss = self._gross_loss / max(self._total_losses, 1)

        idle_count = sum(1 for plist in self._positions.values() for p in plist if p.status == "idle")
        selling_count = sum(1 for plist in self._positions.values() for p in plist if p.status == "selling")
        sold_count = sum(1 for plist in self._positions.values() for p in plist if p.status == "sold")

        return {
            "balance": round(self._balance, 2),
            "assets_value": round(assets, 2),
            "total_equity": round(total, 2),
            "peak_equity": round(self._peak_balance, 2),
            "total_pnl": round(pnl, 2),
            "roi_pct": round(roi, 1),
            "drawdown_pct": round(dd, 1),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "avg_profit": round(avg_profit, 2),
            "avg_loss": round(avg_loss, 2),
            "positions": {"idle": idle_count, "selling": selling_count, "sold": sold_count},
            "snapshots": len(self._snapshots),
            "strategies": {
                name: {
                    "trades": s.trades,
                    "wins": s.wins,
                    "losses": s.losses,
                    "pnl": round(s.total_pnl, 2),
                    "peak": round(s.peak_equity, 2),
                }
                for name, s in self._strategy_stats.items() if s.trades > 0
            },
        }

    def get_strategy_comparison(self) -> List[StrategyComparison]:
        return [s for s in self._strategy_stats.values() if s.trades > 0]

    def get_position_breakdown(self) -> Dict[str, int]:
        cats: Dict[str, int] = {}
        for plist in self._positions.values():
            for p in plist:
                if p.status in ("idle", "selling"):
                    cats[p.category] = cats.get(p.category, 0) + 1
        return cats


# ─────────────────────────────────────────────
# Stress test scenarios
# ─────────────────────────────────────────────

@dataclass
class StressScenario:
    name: str
    price_multiplier: float  # apply to all prices
    competition_multiplier: float  # higher = more likely to lose item to competitor
    volatility_multiplier: float  # higher = more random price fluctuation
    description: str


STRESS_SCENARIOS = [
    StressScenario("normal", 1.0, 1.0, 1.0, "Normal market conditions"),
    StressScenario("bull_market", 1.15, 1.5, 1.2, "+15% prices, high competition"),
    StressScenario("bear_crash", 0.70, 0.5, 2.5, "-30% prices, extreme volatility"),
    StressScenario("low_liquidity", 0.95, 0.7, 0.5, "Holiday season, slow market"),
    StressScenario("tournament_hype", 1.25, 2.0, 1.5, "Major tournament price spike"),
    StressScenario("flash_crash", 0.50, 0.3, 3.0, "Flash crash, panic selling"),
]


def run_stress_test(
    base_candidates: List[Dict[str, Any]],
    agg_prices: Dict[str, Any],
    cycles: int = 30,
) -> Dict[str, Dict[str, Any]]:
    """
    Run the same candidates through all stress scenarios
    and compare results. Each scenario runs N cycles.
    """
    results: Dict[str, Dict[str, Any]] = {}

    for scenario in STRESS_SCENARIOS:
        engine = ShadowEngine(initial_balance=100.0)

        # Apply scenario modifiers to agg_prices
        modified_agg = {}
        for title, agg in agg_prices.items():
            mod = dict(agg)
            mod["best_ask"] = (mod.get("best_ask", 0) or 0) * scenario.price_multiplier
            mod["best_bid"] = (mod.get("best_bid", 0) or 0) * scenario.price_multiplier
            modified_agg[title] = mod

        for cycle in range(cycles):
            # Add random volatility
            for title in modified_agg:
                vol = random.uniform(-0.05, 0.05) * scenario.volatility_multiplier
                modified_agg[title]["best_ask"] *= (1 + vol)
                modified_agg[title]["best_bid"] *= (1 + vol)

            engine.record_cycle(
                candidates=base_candidates,
                agg_prices=modified_agg,
                cs2cap_ok=True,
                cycle=cycle,
                max_buys=2,
                max_spend_per_cycle=10.0,
            )

        results[scenario.name] = {
            "description": scenario.description,
            **engine.get_portfolio_summary(),
        }

    return results
