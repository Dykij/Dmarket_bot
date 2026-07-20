"""
lock_tracker.py — Advanced Lock Tracking for Trade-Locked Items.

Tracks capital frozen in trade-locked items and provides:
- Forecast of when capital will be unfrozen
- Opportunity cost estimation
- Force-repricing for items locked >48h with unrealized loss
- Capital velocity metrics

Source: ROADMAP_DMARKET2026.md — Advanced Lock Tracking
Complexity: O(N) where N = number of locked items
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("LockTracker")


@dataclass
class LockedItem:
    """A trade-locked inventory item."""
    item_id: int
    hash_name: str
    buy_price: float
    acquired_at: float
    unlock_at: float
    current_value: float = 0.0
    status: str = "idle"

    @property
    def is_locked(self) -> bool:
        return time.time() < self.unlock_at

    @property
    def lock_remaining_hours(self) -> float:
        if not self.is_locked:
            return 0.0
        return (self.unlock_at - time.time()) / 3600.0

    @property
    def lock_age_hours(self) -> float:
        return (time.time() - self.acquired_at) / 3600.0

    @property
    def unrealized_pnl(self) -> float:
        return self.current_value - self.buy_price

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.buy_price <= 0:
            return 0.0
        return (self.current_value - self.buy_price) / self.buy_price * 100

    @property
    def needs_force_reprice(self) -> bool:
        """Check if item should be force-repriced."""
        # Locked >48h AND unrealized loss
        return self.lock_age_hours > 48 and self.unrealized_pnl < 0


@dataclass
class LockReport:
    """Report on locked capital."""
    total_locked_usd: float = 0.0
    locked_item_count: int = 0
    oldest_lock_hours: float = 0.0
    avg_lock_hours: float = 0.0
    items_needing_reprice: int = 0
    opportunity_cost_usd: float = 0.0
    unlock_forecast: dict[str, float] = field(default_factory=dict)
    items: list[LockedItem] = field(default_factory=list)


class LockTracker:
    """
    Advanced lock tracking for trade-locked items.

    Monitors capital frozen in trade-locked items and provides
    actionable insights for capital efficiency.

    Usage:
        tracker = LockTracker(price_db)
        report = tracker.get_report()
        if report.items_needing_reprice > 0:
            # Force reprice items with loss locked >48h
            tracker.force_reprice_lossy_items()
    """

    # Force reprice thresholds
    FORCE_REPRICE_AGE_HOURS: float = 48.0
    FORCE_REPRICE_LOSS_PCT: float = -5.0  # -5% unrealized loss

    # Opportunity cost: annual return we could earn elsewhere
    OPPORTUNITY_COST_ANNUAL_PCT: float = 10.0  # 10% annual

    def __init__(self, price_db: Any) -> None:
        self.price_db = price_db

    def get_locked_items(self) -> list[LockedItem]:
        """Get all currently locked items."""
        try:
            rows = self.price_db.get_virtual_inventory(status="idle", only_unlocked=False)
            now = time.time()
            locked = []
            for row in rows:
                row_dict = dict(row)
                unlock_at = row_dict.get("unlock_at", 0)
                if unlock_at > now:
                    locked.append(LockedItem(
                        item_id=row_dict.get("id", 0),
                        hash_name=row_dict.get("hash_name", "unknown"),
                        buy_price=row_dict.get("buy_price", 0.0),
                        acquired_at=row_dict.get("acquired_at", 0.0),
                        unlock_at=unlock_at,
                        status=row_dict.get("status", "idle"),
                    ))
            return locked
        except Exception as e:
            logger.error(f"[LockTracker] Failed to get locked items: {e}")
            return []

    def get_report(self) -> LockReport:
        """Generate lock tracking report."""
        items = self.get_locked_items()

        if not items:
            return LockReport()

        total_locked = sum(item.buy_price for item in items)
        lock_ages = [item.lock_age_hours for item in items]
        oldest_lock = max(lock_ages) if lock_ages else 0
        avg_lock = sum(lock_ages) / len(lock_ages) if lock_ages else 0

        # Items needing force reprice
        needs_reprice = [item for item in items if item.needs_force_reprice]

        # Opportunity cost: what we could earn if capital was free
        # Simple: locked_value * annual_rate * (locked_hours / 8760)
        opportunity_cost = sum(
            item.buy_price * (self.OPPORTUNITY_COST_ANNUAL_PCT / 100)
            * (item.lock_age_hours / 8760)
            for item in items
        )

        # Unlock forecast: how much unlocks in next 1h, 4h, 24h
        forecast = {"1h": 0.0, "4h": 0.0, "24h": 0.0}
        for item in items:
            hours_until = item.lock_remaining_hours
            if hours_until <= 1:
                forecast["1h"] += item.buy_price
            if hours_until <= 4:
                forecast["4h"] += item.buy_price
            if hours_until <= 24:
                forecast["24h"] += item.buy_price

        return LockReport(
            total_locked_usd=round(total_locked, 2),
            locked_item_count=len(items),
            oldest_lock_hours=round(oldest_lock, 1),
            avg_lock_hours=round(avg_lock, 1),
            items_needing_reprice=len(needs_reprice),
            opportunity_cost_usd=round(opportunity_cost, 2),
            unlock_forecast={k: round(v, 2) for k, v in forecast.items()},
            items=items,
        )

    def get_items_needing_reprice(self) -> list[LockedItem]:
        """Get items that should be force-repriced."""
        items = self.get_locked_items()
        return [item for item in items if item.needs_force_reprice]

    def force_reprice_lossy_items(self, discount_pct: float = 3.0) -> list[dict[str, Any]]:
        """
        Force reprice items locked >48h with unrealized loss.

        Args:
            discount_pct: Additional discount to apply (default 3%).

        Returns:
            List of repriced items with details.
        """
        items = self.get_items_needing_reprice()
        repriced = []

        for item in items:
            try:
                # Calculate new price: current value * (1 - discount)
                new_price = round(item.buy_price * (1 - discount_pct / 100), 2)

                # Update in database
                self.price_db.update_sell_price(item.item_id, new_price)

                repriced.append({
                    "item_id": item.item_id,
                    "hash_name": item.hash_name,
                    "old_price": item.buy_price,
                    "new_price": new_price,
                    "lock_age_hours": round(item.lock_age_hours, 1),
                    "unrealized_loss_pct": round(item.unrealized_pnl_pct, 1),
                })

                logger.info(
                    f"[LockTracker] Force repriced {item.hash_name}: "
                    f"${item.buy_price:.2f} -> ${new_price:.2f} "
                    f"(locked {item.lock_age_hours:.0f}h, "
                    f"loss={item.unrealized_pnl_pct:.1f}%)"
                )
            except Exception as e:
                logger.error(
                    f"[LockTracker] Failed to reprice {item.hash_name}: {e}"
                )

        return repriced

    def get_capital_velocity(self, weekly_sales: float, total_locked: float) -> float:
        """
        Calculate capital velocity: weekly_sales / total_locked.

        Target: >= 0.5 (capital turns over at least once per 2 weeks).
        """
        if total_locked <= 0:
            return 0.0
        return weekly_sales / total_locked

    def get_state(self) -> dict[str, Any]:
        """Get current state for diagnostics."""
        report = self.get_report()
        return {
            "locked_items": report.locked_item_count,
            "total_locked_usd": report.total_locked_usd,
            "oldest_lock_hours": report.oldest_lock_hours,
            "items_needing_reprice": report.items_needing_reprice,
            "opportunity_cost_usd": report.opportunity_cost_usd,
            "unlock_forecast": report.unlock_forecast,
        }


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for LockTracker."""
    from unittest.mock import MagicMock

    now = time.time()

    # Mock price_db with some locked items
    mock_db = MagicMock()
    mock_db.get_virtual_inventory = MagicMock(return_value=[
        {
            "id": 1, "hash_name": "AK-47 | Redline", "buy_price": 15.0,
            "acquired_at": now - 72 * 3600, "unlock_at": now - 24 * 3600,
            "status": "idle",
        },
        {
            "id": 2, "hash_name": "AWP | Asiimov", "buy_price": 30.0,
            "acquired_at": now - 10 * 3600, "unlock_at": now + 14 * 3600,
            "status": "idle",
        },
        {
            "id": 3, "hash_name": "Karambit | Doppler", "buy_price": 200.0,
            "acquired_at": now - 50 * 3600, "unlock_at": now + 2 * 3600,
            "status": "idle",
        },
    ])

    tracker = LockTracker(mock_db)

    # Test report
    report = tracker.get_report()
    print(f"[LockTracker] Locked: {report.locked_item_count} items, "
          f"${report.total_locked_usd:.2f} total")
    print(f"[LockTracker] Oldest: {report.oldest_lock_hours:.1f}h, "
          f"Avg: {report.avg_lock_hours:.1f}h")
    print(f"[LockTracker] Need reprice: {report.items_needing_reprice}")
    print(f"[LockTracker] Opportunity cost: ${report.opportunity_cost_usd:.2f}")
    print(f"[LockTracker] Unlock forecast: {report.unlock_forecast}")

    # Test force reprice
    repriced = tracker.force_reprice_lossy_items(discount_pct=3.0)
    print(f"[LockTracker] Repriced: {len(repriced)} items")

    # Test capital velocity
    velocity = tracker.get_capital_velocity(weekly_sales=50.0, total_locked=100.0)
    print(f"[LockTracker] Capital velocity: {velocity:.2f}")
    assert velocity == 0.5

    print("[LockTracker] Self-check PASSED")


if __name__ == "__main__":
    _demo()
