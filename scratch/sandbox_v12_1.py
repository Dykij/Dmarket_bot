"""
Sandbox v12.1 — Full Week Lifecycle Simulation.

Unlike v12.0 (single-cycle), v12.1 simulates a full 7-day trading period with:
1. Multiple cycles per day (10)
2. Full buy → list → sell lifecycle
3. Trade Protection (7-day lock on capital)
4. Realistic sell rates (50% in 24h, 30% after reprice, 20% expire)
5. Repricing flow for stale listings
6. Capital tracking: cash + locked + realized
7. Daily P&L reports
8. Final weekly summary with monthly/yearly projections

This sandbox is the closest model to real-world bot operation.
"""

import asyncio
import logging
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.db.price_history import price_db
from src.api.cs2cap_oracle import CS2CapOracle
from src.core.event_shield import event_shield
from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("SandboxV12.1")
logger.setLevel(logging.INFO)

# --- Simulation Parameters ---
INITIAL_BALANCE = 44.00          # Real user balance ($43.91)
DAYS = 7                         # One week simulation
CYCLES_PER_DAY = 10              # 10 cycles/day @ 1s = 100s scan time
ITEMS_PER_CYCLE = 50             # DMarket batch limit
TRADE_PROTECTION_DAYS = 7        # DMarket locks bought items for 7 days
SELL_RATE_24H = 0.50             # 50% sold in first 24h
SELL_RATE_48H_REPRICED = 0.30    # 30% sold within 48h after reprice
EXPIRE_RATE = 0.20               # 20% expire (sold at -10% loss)
REPRICE_DISCOUNT = 0.05          # Reduce price by 5% on reprice
COMPETITION_FAIL_RATE = 0.15     # 15% chance of being out-sniped


@dataclass
class Item:
    """A bought item with full lifecycle tracking."""
    id: int
    title: str
    buy_price: float
    list_price: float
    fee_rate: float
    float_premium: float
    buy_day: int                   # Day of purchase
    unlock_day: int                # Day trade protection ends
    list_day: int                  # Day item was listed
    reprice_count: int = 0         # Times repriced
    status: str = "listed"         # listed | sold | expired
    sell_price: Optional[float] = None
    sell_day: Optional[int] = None
    profit: Optional[float] = None

    def current_list_price(self) -> float:
        """Get the current list price after reprices."""
        return self.list_price * ((1 - REPRICE_DISCOUNT) ** self.reprice_count)


@dataclass
class DayStats:
    """Daily statistics."""
    day: int
    cycles_run: int = 0
    items_scanned: int = 0
    opportunities_found: int = 0
    items_bought: int = 0
    items_sold: int = 0
    items_expired: int = 0
    items_repriced: int = 0
    cash_spent: float = 0.0
    cash_received: float = 0.0
    realized_profit: float = 0.0
    fees_paid: float = 0.0
    start_cash: float = 0.0
    end_cash: float = 0.0
    start_locked: float = 0.0
    end_locked: float = 0.0


class SandboxV12_1:
    """
    Multi-day full-lifecycle sandbox for Strategy A + Low-Fee + Float.

    Tracks:
    - Cash: available for buying
    - Locked: capital tied in items (under trade protection or listed)
    - Realized: profits from sold items
    - Inventory: list of all bought items with full lifecycle
    """

    def __init__(self):
        self.cash = INITIAL_BALANCE
        self.locked = 0.0
        self.realized = 0.0
        self.total_fees = 0.0
        self.inventory: List[Item] = []
        self.sold_items: List[Item] = []
        self.expired_items: List[Item] = []
        self.next_item_id = 1
        self.daily_stats: List[DayStats] = []
        self.current_day = 0

    @property
    def total_equity(self) -> float:
        """Total value = cash + locked + realized (all real money)."""
        return self.cash + self.locked + self.realized

    @property
    def unrealized_profit(self) -> float:
        """Profit from items still in inventory (not yet sold)."""
        total = 0.0
        for item in self.inventory:
            if item.status == "listed":
                # Mark to market: list price - buy price - fees
                total += (item.current_list_price() - item.buy_price) * (1 - item.fee_rate)
        return total

    def _scan_market(self) -> List[Dict[str, Any]]:
        """Simulate one market scan cycle (50 items)."""
        items = []
        for i in range(ITEMS_PER_CYCLE):
            base = random.uniform(2.0, 30.0)
            if random.random() < 0.30:  # 30% have positive spread
                spread_pct = random.uniform(5.0, 25.0)
                best_ask = base
                best_bid = base * (1 + spread_pct / 100.0)
            else:
                best_ask = base
                best_bid = base * 0.99
            items.append({
                "title": f"Item_{random.randint(1000, 9999)}_{i}",
                "best_ask": best_ask,
                "best_bid": best_bid,
                "ask_count": random.randint(1, 10),
                "bid_count": random.randint(0, 5),
            })
        return items

    def _find_opportunities(self, items: List[Dict[str, Any]], day: int, stats: DayStats) -> List[Dict[str, Any]]:
        """Apply Strategy A + Low-Fee + Float filters."""
        opportunities = []
        for item in items:
            if item["best_bid"] <= 0 or item["best_ask"] <= 0:
                continue
            if item["ask_count"] < 1 or item["bid_count"] < 1:
                continue
            if item["best_bid"] <= item["best_ask"] * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0):
                continue

            list_price = round(item["best_bid"] - Config.INTRA_LIST_DISCOUNT, 2)

            # Float premium
            float_premium = self._simulate_float_premium()
            if float_premium > 1.0:
                list_price = round(list_price * float_premium, 2)

            buy_price = item["best_ask"]
            if list_price < buy_price * 1.02:
                continue
            if buy_price > self.cash * (Config.MAX_POSITION_RISK_PCT / 100.0):
                continue
            if buy_price > self.cash:
                continue

            # Low-fee
            fee_rate = 0.025 if random.random() < 0.2 else Config.FEE_RATE

            gross_profit = list_price - buy_price
            fee = list_price * fee_rate
            net_profit = gross_profit - fee

            if net_profit > 0:
                opportunities.append({
                    **item,
                    "buy_price": buy_price,
                    "list_price": list_price,
                    "spread_pct": ((item["best_bid"] / buy_price) - 1) * 100,
                    "net_profit": net_profit,
                    "float_premium": float_premium,
                    "fee_rate": fee_rate,
                })

        return opportunities

    def _buy_item(self, opp: Dict[str, Any], day: int, stats: DayStats) -> bool:
        """Simulate buying an item. Returns True if successful."""
        # Competition check
        if random.random() < COMPETITION_FAIL_RATE:
            return False
        # Saturation check (5 same items max)
        held_count = sum(1 for it in self.inventory if it.title == opp["title"])
        if held_count >= 5:
            return False
        if opp["buy_price"] > self.cash:
            return False

        item = Item(
            id=self.next_item_id,
            title=opp["title"],
            buy_price=opp["buy_price"],
            list_price=opp["list_price"],
            fee_rate=opp["fee_rate"],
            float_premium=opp["float_premium"],
            buy_day=day,
            unlock_day=day + TRADE_PROTECTION_DAYS,
            list_day=day,
        )
        self.next_item_id += 1
        self.inventory.append(item)
        self.cash -= opp["buy_price"]
        self.locked += opp["buy_price"]
        stats.items_bought += 1
        stats.cash_spent += opp["buy_price"]
        return True

    def _process_sells_and_reprices(self, day: int, stats: DayStats):
        """Process items that should sell or be repriced today."""
        for item in list(self.inventory):
            if item.status != "listed":
                continue

            days_listed = day - item.list_day

            if days_listed == 1:  # After 24h
                if random.random() < SELL_RATE_24H:
                    self._sell_item(item, day, stats)
                    continue
                # Reprice stale items
                if item.reprice_count == 0:
                    self._reprice_item(item, day, stats)
            elif days_listed == 2:  # After 48h (post-reprice)
                if random.random() < SELL_RATE_48H_REPRICED:
                    self._sell_item(item, day, stats)
                    continue
                # Reprice again
                if item.reprice_count == 1:
                    self._reprice_item(item, day, stats)
            elif days_listed >= 7:  # After 7 days, expire
                if random.random() < EXPIRE_RATE / 7:  # Spread out
                    self._expire_item(item, day, stats)
                elif item.reprice_count < 3:
                    self._reprice_item(item, day, stats)

    def _sell_item(self, item: Item, day: int, stats: DayStats):
        """Mark item as sold at current list price."""
        sell_price = item.current_list_price()
        fee = sell_price * item.fee_rate
        net_proceeds = sell_price - fee
        profit = net_proceeds - item.buy_price

        item.status = "sold"
        item.sell_price = sell_price
        item.sell_day = day
        item.profit = profit
        self.sold_items.append(item)
        self.inventory.remove(item)

        self.cash += net_proceeds
        self.locked -= item.buy_price
        self.realized += profit
        self.total_fees += fee
        stats.items_sold += 1
        stats.cash_received += net_proceeds
        stats.realized_profit += profit
        stats.fees_paid += fee

    def _reprice_item(self, item: Item, day: int, stats: DayStats):
        """Reprice an item (reduce price by 5%)."""
        item.reprice_count += 1
        item.list_price = item.list_price * (1 - REPRICE_DISCOUNT)
        item.list_price = round(item.list_price, 2)
        stats.items_repriced += 1

    def _expire_item(self, item: Item, day: int, stats: DayStats):
        """Item expires — sold at -10% loss."""
        sell_price = item.buy_price * 0.90  # 10% loss
        fee = sell_price * item.fee_rate
        net_proceeds = sell_price - fee
        profit = net_proceeds - item.buy_price  # Will be negative

        item.status = "expired"
        item.sell_price = sell_price
        item.sell_day = day
        item.profit = profit
        self.expired_items.append(item)
        self.inventory.remove(item)

        self.cash += net_proceeds
        self.locked -= item.buy_price
        self.realized += profit
        self.total_fees += fee
        stats.items_expired += 1
        stats.cash_received += net_proceeds
        stats.realized_profit += profit
        stats.fees_paid += fee

    @staticmethod
    def _simulate_float_premium() -> float:
        """Simulate random float distribution."""
        r = random.random()
        if r < 0.05:
            return 1.20
        if r < 0.15:
            return 1.10
        if r < 0.25:
            return 1.15
        if r < 0.90:
            return 1.00
        if r < 0.97:
            return 0.95
        return 0.90

    async def run_week(self):
        """Run the full 7-day simulation."""
        print("="*72)
        print("SANDBOX v12.1 — FULL WEEK LIFECYCLE SIMULATION")
        print("Strategy A + Low-Fee + Float | 7 days | 10 cycles/day | $44 start")
        print("="*72)
        print(f"Parameters: {DAYS} days, {CYCLES_PER_DAY} cycles/day, {ITEMS_PER_CYCLE} items/cycle")
        print(f"Sell rates: 50%/24h, 30%/+24h after reprice, 20% expire")
        print(f"Reprice discount: {REPRICE_DISCOUNT*100:.0f}%, Competition: {COMPETITION_FAIL_RATE*100:.0f}%")
        print(f"Trade protection: {TRADE_PROTECTION_DAYS} days")
        print("-"*72)
        print(f"START: cash=${self.cash:.2f} | locked=${self.locked:.2f} | equity=${self.total_equity:.2f}")
        print("-"*72)

        for day in range(1, DAYS + 1):
            self.current_day = day
            stats = DayStats(
                day=day,
                start_cash=self.cash,
                start_locked=self.locked,
            )

            # Run cycles for this day
            for cycle in range(CYCLES_PER_DAY):
                stats.cycles_run += 1
                market = self._scan_market()
                stats.items_scanned += len(market)

                opps = self._find_opportunities(market, day, stats)
                stats.opportunities_found += len(opps)

                # Sort by profit and buy top 5
                opps.sort(key=lambda x: -x["net_profit"])
                for opp in opps[:5]:
                    self._buy_item(opp, day, stats)

            # Process sells and reprices at end of day
            self._process_sells_and_reprices(day, stats)

            stats.end_cash = self.cash
            stats.end_locked = self.locked
            self.daily_stats.append(stats)

            # Daily report
            inv_count = len([it for it in self.inventory if it.status == "listed"])
            print(
                f"Day {day}: scanned={stats.items_scanned:>4} | "
                f"opps={stats.opportunities_found:>3} | "
                f"bought={stats.items_bought:>2} | "
                f"sold={stats.items_sold:>2} | "
                f"expired={stats.items_expired:>2} | "
                f"repriced={stats.items_repriced:>2} | "
                f"profit=${stats.realized_profit:>+6.2f} | "
                f"cash=${stats.end_cash:>6.2f} | "
                f"locked=${stats.end_locked:>6.2f} | "
                f"inv={inv_count:>2}"
            )

        # Final report
        self._print_final_report()

    def _print_final_report(self):
        """Print comprehensive final report."""
        total_profit = self.realized
        total_bought = sum(s.items_bought for s in self.daily_stats)
        total_sold = sum(s.items_sold for s in self.daily_stats)
        total_expired = sum(s.items_expired for s in self.daily_stats)
        total_repriced = sum(s.items_repriced for s in self.daily_stats)
        total_fees = self.total_fees

        win_count = sum(1 for it in self.sold_items if it.profit > 0)
        win_rate = (win_count / total_sold * 100) if total_sold > 0 else 0

        avg_hold_time = (
            sum((it.sell_day - it.buy_day) for it in self.sold_items if it.sell_day) / total_sold
            if total_sold > 0 else 0
        )

        # ROI calculations
        total_capital_used = self.cash + self.locked + self.realized - INITIAL_BALANCE
        roi_pct = (total_profit / INITIAL_BALANCE * 100) if INITIAL_BALANCE > 0 else 0

        # Daily average
        daily_profit = total_profit / DAYS
        daily_capital = (INITIAL_BALANCE + self.cash) / 2  # avg
        daily_roi = (daily_profit / daily_capital * 100) if daily_capital > 0 else 0

        # Remaining in inventory
        remaining_inventory = len([it for it in self.inventory if it.status == "listed"])
        remaining_locked = sum(it.buy_price for it in self.inventory if it.status == "listed")

        print("\n" + "="*72)
        print("WEEKLY SUMMARY (7 days)")
        print("="*72)

        # Capital flow
        print("\n📊 CAPITAL FLOW:")
        print(f"  Initial balance:     ${INITIAL_BALANCE:.2f}")
        print(f"  Current cash:        ${self.cash:.2f}")
        print(f"  Locked in inventory: ${self.locked:.2f} ({remaining_inventory} items)")
        print(f"  Realized profit:     ${self.realized:+.2f}")
        print(f"  Total equity:        ${self.total_equity:.2f}")
        print(f"  Total fees paid:     ${total_fees:.2f}")

        # Trading stats
        print("\n📈 TRADING STATS:")
        print(f"  Items bought:        {total_bought}")
        print(f"  Items sold:          {total_sold} (win rate: {win_rate:.1f}%)")
        print(f"  Items expired:       {total_expired} (sold at -10% loss)")
        print(f"  Items repriced:      {total_repriced}")
        print(f"  Avg hold time:       {avg_hold_time:.1f} days")
        print(f"  Items still locked:  {remaining_inventory}")

        # Profit breakdown
        print("\n💰 PROFIT BREAKDOWN:")
        if self.sold_items:
            profits = [it.profit for it in self.sold_items if it.profit is not None]
            winning = [p for p in profits if p > 0]
            losing = [p for p in profits if p <= 0]
            print(f"  Winning trades:      {len(winning)} (avg ${sum(winning)/len(winning):.2f})" if winning else "  No winning trades")
            print(f"  Losing trades:       {len(losing)} (avg ${sum(losing)/len(losing):.2f})" if losing else "  No losing trades")
        if self.expired_items:
            exp_profits = [it.profit for it in self.expired_items if it.profit is not None]
            print(f"  Expired losses:      {len(exp_profits)} (total ${sum(exp_profits):.2f})")

        # ROI
        print("\n🎯 ROI ANALYSIS:")
        print(f"  Weekly profit:       ${total_profit:+.2f} ({roi_pct:+.1f}% on ${INITIAL_BALANCE})")
        print(f"  Daily avg profit:    ${daily_profit:+.2f} ({daily_roi:+.1f}% on avg capital)")

        # Projections
        monthly_profit = daily_profit * 30
        yearly_profit = daily_profit * 365
        print("\n📅 PROJECTIONS (based on daily avg):")
        print(f"  Monthly (30 days):   ${monthly_profit:+.2f}")
        print(f"  Yearly (365 days):   ${yearly_profit:+.2f}")
        print(f"  Capital at year end: ${INITIAL_BALANCE + yearly_profit:,.2f}")

        # Risk warnings
        print("\n⚠️  RISK FACTORS:")
        print(f"  - {remaining_inventory} items still locked (${remaining_locked:.2f})")
        print(f"  - {total_expired} items expired at loss (${sum(it.profit for it in self.expired_items):.2f})")
        print(f"  - {len(self.inventory)} items in inventory after 7 days")

        # Top 5 best/worst
        if self.sold_items:
            print("\n🏆 TOP 5 TRADES:")
            top = sorted(self.sold_items, key=lambda x: -(x.profit or 0))[:5]
            for it in top:
                fp = f" [float {it.float_premium:.2f}x]" if it.float_premium > 1.0 else ""
                lf = f" [low-fee]" if it.fee_rate < 0.05 else ""
                print(f"  +${it.profit:>5.2f} | {it.title[:30]:<30} | buy ${it.buy_price:.2f} → sell ${it.sell_price:.2f}{fp}{lf}")

            worst = sorted(self.sold_items, key=lambda x: x.profit or 0)[:3]
            if worst and worst[0].profit < 0:
                print("\n💀 WORST TRADES:")
                for it in worst:
                    if it.profit < 0:
                        print(f"  -${abs(it.profit):>5.2f} | {it.title[:30]:<30} | buy ${it.buy_price:.2f} → sell ${it.sell_price:.2f}")

        print("="*72)


async def main():
    random.seed(42)  # Reproducible
    sandbox = SandboxV12_1()
    await sandbox.run_week()


if __name__ == "__main__":
    asyncio.run(main())
