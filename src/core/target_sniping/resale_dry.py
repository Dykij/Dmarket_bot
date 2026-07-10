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

from src.api.oracle_factory import OracleFactory
from src.db.price_history import price_db
from src.telegram.notifier import notifier

logger = logging.getLogger("SnipingBot")


class _ResaleDryMixin:
    """Simulated resale — no real DMarket API calls."""

    client: Any
    cs2cap_cache: Any

    def _dry_simulate_sales(self) -> None:
        """DRY: Mark some `listed` items as sold (40% per cycle)."""
        listed = price_db.get_virtual_inventory(status="listed")
        if not listed:
            return
        for it in listed:
            if random.random() < 0.40:
                # Simulate the sale at the listed price minus 5% fee
                sell_price = round((it["sell_price"] or it["buy_price"] * 1.05), 2)
                fee = round(sell_price * 0.05, 4)
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
                asyncio.create_task(
                    notifier.sell(
                        title=it["hash_name"],
                        buy_price_usd=float(it["buy_price"] or 0),
                        sell_price_usd=sell_price,
                        profit_usd=profit,
                    )
                )
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
        oracle = OracleFactory.get_oracle(game_id)
        for item in items:
            current_price = 0.0
            if oracle:
                with contextlib.suppress(Exception):
                    current_price = await oracle.get_item_price(item["hash_name"])
            if current_price <= 0:
                current_price = item["buy_price"] * 1.05
            buy_price = item["buy_price"]
            target_sell = round(buy_price * 1.05, 2)
            if current_price < target_sell:
                # Market no longer supports our markup — hold off
                continue
            list_price = round(min(current_price * 0.97, current_price - 0.01), 2)
            price_db.mark_listed(int(item["id"]), dm_offer_id=f"sim-{int(time.time())}-{item['id']}", list_price=list_price)
            est_profit = round(list_price - buy_price - list_price * 0.05, 2)
            logger.info(
                f"[SIM] LISTED: {item['hash_name']} | "
                f"Buy: ${buy_price:.2f} → Listed: ${list_price:.2f} "
                f"| Est profit: ${est_profit:+.2f}"
            )
