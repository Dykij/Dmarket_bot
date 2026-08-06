"""
resale_dry.py — DRY-mode helpers for the resale pipeline (simulation only).

Mixed into SnipingLoop via _ResaleMixin (see resale.py).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from typing import Any

from src.config import Config
from src.db.price_history import price_db
from src.utils.fee_utils import get_sell_fee_rate
# P1-1: Lazy import to break core→telegram layer coupling

logger = logging.getLogger("SnipingBot")


def _get_notifier():
    """P1-1: Lazy import notifier to avoid core→telegram coupling at import time."""
    from src.telegram.notifier import notifier
    return notifier


class _ResaleDryMixin:
    """Simulated resale — no real DMarket API calls."""

    client: Any

    def _dry_simulate_sales(self) -> None:
        """DRY: Mark some `listed` items as sold (40% per cycle)."""
        listed = price_db.get_virtual_inventory(status="listed")
        if not listed:
            return
        for it in listed:
            if random.random() < 0.40:
                # Simulate the sale at the listed price minus 5% fee
                sell_price = round((it["sell_price"] or it["buy_price"] * 1.05), 2)
                fee = round(sell_price * get_sell_fee_rate(), 4)
                price_db.record_virtual_sale(int(it["id"]), sell_price, fee)
                # v13.1: Simulate TP funds hold (7 days)
                hold_until = time.time() + 7 * 24 * 3600
                price_db.set_funds_hold(int(it["id"]), hold_until)
                profit = sell_price - (it["buy_price"] or 0) - fee
                logger.info(
                    f"[SIM] SOLD! {it['hash_name']} | "
                    f"Buy: ${it['buy_price']:.2f} → Sell: ${sell_price:.2f} "
                    f"| PnL: ${profit:+.2f}"
                )
                # v12.5: notify + record in risk manager
                # v15.10 FIX: Store task reference to prevent GC before completion
                _task = asyncio.create_task(
                    _get_notifier().sell(
                        title=it["hash_name"],
                        buy_price_usd=float(it["buy_price"] or 0),
                        sell_price_usd=sell_price,
                        profit_usd=profit,
                    )
                )
                self._background_tasks = getattr(self, '_background_tasks', set())
                self._background_tasks.add(_task)
                _task.add_done_callback(self._background_tasks.discard)
                if hasattr(self, "risk"):
                    try:
                        self.risk.record_trade_outcome(
                            pnl_usd=profit,
                            trade_type="sell",
                            item_title=it["hash_name"],
                        )
                    except Exception as e:
                        logger.debug(f"risk.record_trade_outcome (sim sell) failed: {e}")

    async def _dry_list_unlocked(self, items: list[Any], game_id: str) -> None:
        """DRY: Simulate listing unlocked items at buy_price * 1.05."""
        for item in items:
            current_price = item["buy_price"] * 1.05
            buy_price = item["buy_price"]
            target_sell = round(buy_price * 1.05, 2)
            if current_price < target_sell:
                # Market no longer supports our markup — hold off
                continue
            list_price = round(min(current_price * 0.97, current_price - 0.01), 2)
            await price_db.run_in_thread(price_db.mark_listed, int(item["id"]), f"sim-{int(time.time())}-{item['id']}", list_price)  # P2-17: async
            est_profit = round(list_price - buy_price - list_price * 0.05, 2)
            logger.info(
                f"[SIM] LISTED: {item['hash_name']} | "
                f"Buy: ${buy_price:.2f} → Listed: ${list_price:.2f} "
                f"| Est profit: ${est_profit:+.2f}"
            )
