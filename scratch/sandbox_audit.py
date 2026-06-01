"""
Sandbox Audit v12.0 — Full Pipeline Test (Intra-Spread Strategy A).

Simulates:
1. Real DMarket API scans (50 items)
2. Aggregated prices fetch
3. Strategy A spread filter
4. Profit calculation
5. Equity report
"""

import asyncio
import logging
import os
import random
from typing import List, Dict, Any

from src.db.price_history import price_db
from src.api.cs2cap_oracle import CS2CapOracle
from src.core.event_shield import event_shield
from src.api.dmarket_api_client import DMarketAPIClient

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("AuditV12")

INITIAL_BALANCE = 44.0  # Real user balance ($43.91)
SIMULATE_LATENCY = True
SIMULATE_ERRORS = 0.05
ITEMS_PER_CYCLE = 50


class SandboxAuditV12:
    def __init__(self):
        self.balance = INITIAL_BALANCE
        self.oracle = CS2CapOracle(api_key=os.getenv("CS2C_API_KEY", ""), tier="free")
        self.client = DMarketAPIClient("pub", "sec")
        self.items_scanned = 0
        self.items_bought = 0
        self.total_profit_potential = 0.0
        self.total_risk = 0.0

    async def simulate_api_call(self, name: str) -> bool:
        if SIMULATE_LATENCY:
            await asyncio.sleep(random.uniform(0.15, 0.4))
        if random.random() < SIMULATE_ERRORS:
            logger.warning(f"[Simulated] API Congestion on {name}.")
            return False
        return True

    async def run_audit(self):
        logger.info("="*60)
        logger.info("SANDBOX AUDIT v12.0 — STRATEGY A + LOW-FEE + FLOAT")
        logger.info("="*60)
        logger.info(f"Initial balance: ${self.balance:.2f}")

        # Bifurcation check
        if not price_db.state_path.exists() or not price_db.history_path.exists():
            logger.error("Bifurcation failed: missing DBs")
            return

        current_multiplier = event_shield.get_margin_multiplier()
        logger.info(f"EventShield multiplier: {current_multiplier}x")

        # Simulate 50-item batch scan
        logger.info(f"Scanning {ITEMS_PER_CYCLE} items on DMarket...")
        mock_titles = [
            f"AK-47 | Redline (Field-Tested) #{i}" for i in range(ITEMS_PER_CYCLE)
        ]

        # Aggregate prices (simulated)
        await asyncio.sleep(0.5)
        agg_prices = {}
        for title in mock_titles:
            base = random.uniform(2.0, 30.0)
            # 30% of items will have a positive spread (5%+)
            if random.random() < 0.3:
                spread_pct = random.uniform(5.0, 25.0)
                best_ask = base
                best_bid = base * (1 + spread_pct / 100.0)
            else:
                best_ask = base
                best_bid = base * 0.99
            agg_prices[title] = {
                "best_ask": best_ask,
                "best_bid": best_bid,
                "ask_count": random.randint(1, 10),
                "bid_count": random.randint(0, 5),
            }
            self.items_scanned += 1

        # Strategy A filter
        opportunities = []
        from src.config import Config
        for title, agg in agg_prices.items():
            if agg["best_bid"] <= 0 or agg["best_ask"] <= 0:
                continue
            if agg["ask_count"] < 1 or agg["bid_count"] < 1:
                continue
            if agg["best_bid"] <= agg["best_ask"] * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0):
                continue

            list_price = round(agg["best_bid"] - Config.INTRA_LIST_DISCOUNT, 2)

            # v12.0 Phase 1.2: Float Premium (simulated)
            float_premium = self._simulate_float_premium()
            if float_premium > 1.0:
                list_price = round(list_price * float_premium, 2)

            buy_price = agg["best_ask"]

            if list_price < buy_price * 1.02:
                continue
            if buy_price > self.balance * (Config.MAX_POSITION_RISK_PCT / 100.0):
                continue
            if buy_price > self.balance:
                continue

            # v12.0 Phase 1.1: Low-Fee filter (simulated: 20% of items are low-fee)
            fee_rate = 0.025 if random.random() < 0.2 else Config.FEE_RATE

            gross_profit = list_price - buy_price
            fee = list_price * fee_rate
            net_profit = gross_profit - fee

            if net_profit > 0:
                opportunities.append({
                    "title": title,
                    "buy_price": buy_price,
                    "list_price": list_price,
                    "spread_pct": ((agg["best_bid"] / buy_price) - 1) * 100,
                    "net_profit": net_profit,
                    "float_premium": float_premium,
                    "fee_rate": fee_rate,
                })

        logger.info(f"Found {len(opportunities)} profitable opportunities (out of {self.items_scanned}).")

        # Sort by profit and buy
        opportunities.sort(key=lambda x: -x["net_profit"])
        for opp in opportunities[:10]:  # Top 10
            if opp["buy_price"] > self.balance:
                continue
            self.balance -= opp["buy_price"]
            self.items_bought += 1
            self.total_risk += opp["buy_price"]
            self.total_profit_potential += opp["net_profit"]
            price_db.add_virtual_item(opp["title"], opp["buy_price"])
            fp_str = f", float {opp['float_premium']:.2f}x" if opp['float_premium'] > 1.0 else ""
            lf_str = f", low-fee {opp['fee_rate']*100:.1f}%" if opp['fee_rate'] < 0.05 else ""
            logger.info(
                f"BUY {opp['title'][:30]} @ ${opp['buy_price']:.2f} → list ${opp['list_price']:.2f} "
                f"(spread {opp['spread_pct']:.1f}%, net ${opp['net_profit']:.2f}{fp_str}{lf_str})"
            )

        logger.info("-" * 60)
        logger.info("AUDIT SUMMARY v12.0:")
        logger.info(f"  Items scanned:    {self.items_scanned}")
        logger.info(f"  Opportunities:    {len(opportunities)}")
        logger.info(f"  Items bought:     {self.items_bought}")
        logger.info(f"  Total risk:       ${self.total_risk:.2f}")
        logger.info(f"  Profit potential: ${self.total_profit_potential:.2f}")
        logger.info(f"  Remaining cash:   ${self.balance:.2f}")
        logger.info(f"  EventShield:      {current_multiplier}x")
        logger.info(f"  Architecture:     Bifurcated SQLite + CS2Cap + Strategy A + Low-Fee + Float")
        logger.info("="*60)

    async def close(self):
        await self.oracle.close()
        await self.client.close()

    @staticmethod
    def _simulate_float_premium() -> float:
        """Simulate a random float value and return the premium multiplier."""
        # Distribution: 5% FN-0, 10% FN, 10% FT-0, 65% MW/FT, 7% WW, 3% BS
        r = random.random()
        if r < 0.05:
            return 1.20  # FN-0
        if r < 0.15:
            return 1.10  # FN
        if r < 0.25:
            return 1.15  # FT-0
        if r < 0.90:
            return 1.00  # MW/FT
        if r < 0.97:
            return 0.95  # WW
        return 0.90  # BS


async def main():
    audit = SandboxAuditV12()
    try:
        await audit.run_audit()
    finally:
        await audit.close()


if __name__ == "__main__":
    asyncio.run(main())
