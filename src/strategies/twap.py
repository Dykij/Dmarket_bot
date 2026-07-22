"""
twap.py — Simplified TWAP (Time-Weighted Average Price) executor.

v15.10: Anti-slippage execution for large orders (qty >= 5).
Splits a large buy order into smaller slices executed over time,
reducing market impact and average execution price.

This is a simplified version — no MPC/Almgren-Chriss optimization,
just clean time-distributed execution with slippage tracking.

Usage:
    twap = TWAPExecutor(dmarket_client)
    result = await twap.execute(item, total_qty=10, time_horizon=timedelta(minutes=10))
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger("SnipingBot")


class SliceStatus(Enum):
    """Status of a single TWAP execution slice."""
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionSlice:
    """One mini-order in the TWAP schedule."""
    slice_id: int
    qty: int
    scheduled_time: datetime
    status: SliceStatus = SliceStatus.PENDING
    execution_price: float = 0.0
    execution_time: datetime | None = None
    slippage_pct: float = 0.0
    error: str | None = None


@dataclass
class TWAPResult:
    """Result of a TWAP execution."""
    success: bool
    total_qty_requested: int
    total_qty_executed: int
    avg_price: float
    total_cost: float
    slippage_pct: float
    slices: list[ExecutionSlice] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def fill_rate(self) -> float:
        if self.total_qty_requested == 0:
            return 0.0
        return self.total_qty_executed / self.total_qty_requested

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "requested": self.total_qty_requested,
            "executed": self.total_qty_executed,
            "fill_rate": round(self.fill_rate, 4),
            "avg_price": round(self.avg_price, 4),
            "total_cost": round(self.total_cost, 4),
            "slippage_pct": round(self.slippage_pct, 4),
            "slices_count": len(self.slices),
            "duration_s": round(self.duration_seconds, 1),
        }


class TWAPExecutor:
    """
    Simplified TWAP executor for DMarket.

    Splits large orders into smaller slices distributed over time.
    Each slice is a separate buy attempt at the current market price.
    """

    def __init__(
        self,
        client: Any,  # DMarketAPIClient
        max_slices: int = 5,
        min_interval_seconds: float = 30.0,
        max_slippage_pct: float = 5.0,
        price_refresh_before_slice: bool = True,
    ):
        self.client = client
        self.max_slices = max_slices
        self.min_interval_seconds = min_interval_seconds
        self.max_slippage_pct = max_slippage_pct
        self.price_refresh = price_refresh_before_slice

    def create_schedule(
        self,
        total_qty: int,
        time_horizon: timedelta,
        start_time: datetime | None = None,
    ) -> list[ExecutionSlice]:
        """
        Create a TWAP execution schedule.

        Distributes total_qty evenly across time_horizon.
        """
        if start_time is None:
            start_time = datetime.utcnow()

        num_slices = min(self.max_slices, max(1, total_qty))
        qty_per_slice = total_qty // num_slices
        remainder = total_qty % num_slices

        interval = time_horizon / num_slices
        # Enforce minimum interval
        if interval.total_seconds() < self.min_interval_seconds:
            interval = timedelta(seconds=self.min_interval_seconds)

        schedule = []
        for i in range(num_slices):
            qty = qty_per_slice + (1 if i < remainder else 0)
            scheduled_time = start_time + interval * i

            schedule.append(ExecutionSlice(
                slice_id=i,
                qty=qty,
                scheduled_time=scheduled_time,
            ))

        return schedule

    async def execute(
        self,
        item: dict[str, Any],
        total_qty: int,
        time_horizon: timedelta = timedelta(minutes=5),
        game_id: str = "a8db",
    ) -> TWAPResult:
        """
        Execute a TWAP order.

        Args:
            item: Item dict with 'title', 'itemId', 'price' keys
            total_qty: Total quantity to buy
            time_horizon: Time to spread execution over
            game_id: DMarket game ID

        Returns:
            TWAPResult with execution details
        """
        start_time = datetime.utcnow()
        title = item.get("title", "")
        try:
            price_obj = item.get("price", {})
            base_price_cents = int(price_obj.get("USD", 0)) if isinstance(price_obj, dict) else 0
        except (TypeError, ValueError):
            base_price_cents = 0
        base_price = base_price_cents / 100.0

        if base_price <= 0:
            logger.error(f"[TWAP] Invalid base_price={base_price} for {title}, aborting")
            return TWAPResult(
                success=False, total_qty_requested=total_qty,
                total_qty_executed=0, avg_price=0, total_cost=0,
                slippage_pct=0, duration_seconds=0,
            )

        schedule = self.create_schedule(total_qty, time_horizon, start_time)
        executed_slices: list[ExecutionSlice] = []
        total_executed = 0
        total_cost = 0.0

        logger.info(
            f"[TWAP] Starting {len(schedule)} slices for {title} "
            f"(qty={total_qty}, horizon={time_horizon})"
        )

        consecutive_failures = 0
        max_consecutive_failures = 2

        for slice_obj in schedule:
            # Wait until scheduled time
            now = datetime.utcnow()
            wait = (slice_obj.scheduled_time - now).total_seconds()
            if wait > 0:
                await asyncio.sleep(wait)

            # Refresh price if configured
            current_price = base_price
            if self.price_refresh:
                try:
                    resp = await self.client.get_market_items_v2(
                        game_id, limit=3, title=title
                    )
                    listings = resp.get("objects", [])
                    if listings:
                        cheapest_cents = min(
                            int(lst.get("price", {}).get("USD", 0))
                            for lst in listings
                        )
                        current_price = cheapest_cents / 100.0
                except Exception as e:
                    logger.warning(
                        f"[TWAP] Price refresh failed for slice "
                        f"{slice_obj.slice_id}: {e}"
                    )

            # Check slippage
            slippage_pct = 0.0
            if base_price > 0:
                slippage_pct = ((current_price - base_price) / base_price) * 100

            if slippage_pct > self.max_slippage_pct:
                slice_obj.status = SliceStatus.SKIPPED
                slice_obj.error = f"Slippage {slippage_pct:.1f}% > {self.max_slippage_pct}%"
                logger.warning(f"[TWAP] Slice {slice_obj.slice_id} skipped: {slice_obj.error}")
                executed_slices.append(slice_obj)
                continue

            # Execute buy using the existing client.buy_items method
            try:
                buy_payload = {
                    "offerId": item.get("itemId", ""),
                    "price": {"amount": str(int(round(current_price * 100))), "currency": "USD"},
                }
                result = await self.client.buy_items([buy_payload])

                if result and isinstance(result, dict) and result.get("status") != "TxFailed":
                    slice_obj.status = SliceStatus.EXECUTED
                    slice_obj.execution_price = current_price
                    slice_obj.execution_time = datetime.utcnow()
                    slice_obj.slippage_pct = slippage_pct
                    total_executed += slice_obj.qty
                    total_cost += current_price * slice_obj.qty

                    logger.info(
                        f"[TWAP] Slice {slice_obj.slice_id}: "
                        f"{slice_obj.qty}x @ ${current_price:.2f} "
                        f"(slip={slippage_pct:.1f}%)"
                    )
                else:
                    slice_obj.status = SliceStatus.FAILED
                    fail_reason = result.get("dmOffersFailReason", {}) if isinstance(result, dict) else {}
                    slice_obj.error = f"Buy failed: {fail_reason.get('code', 'unknown') if fail_reason else 'no result'}"

            except Exception as e:
                slice_obj.status = SliceStatus.FAILED
                safe_error = f"{type(e).__name__}: {str(e)[:200]}"
                slice_obj.error = safe_error
                logger.warning(
                    f"[TWAP] Slice {slice_obj.slice_id} failed: {safe_error}"
                )
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"[TWAP] {consecutive_failures} consecutive failures, "
                        f"aborting remaining slices"
                    )
                    for remaining_idx in range(
                        slice_obj.slice_id + 1, len(schedule)
                    ):
                        schedule[remaining_idx].status = SliceStatus.SKIPPED
                        schedule[remaining_idx].error = (
                            "Aborted: consecutive failure limit reached"
                        )
                    executed_slices.append(slice_obj)
                    break

            executed_slices.append(slice_obj)
            # Reset failure counter on success
            if slice_obj.status == SliceStatus.EXECUTED:
                consecutive_failures = 0

        # Calculate results
        executed_prices = [
            s.execution_price * s.qty
            for s in executed_slices
            if s.status == SliceStatus.EXECUTED and s.execution_price > 0
        ]
        avg_price = sum(executed_prices) / total_executed if total_executed > 0 else 0.0
        overall_slippage = ((avg_price - base_price) / base_price * 100) if base_price > 0 else 0.0
        duration = (datetime.utcnow() - start_time).total_seconds()

        result = TWAPResult(
            success=total_executed == total_qty,
            total_qty_requested=total_qty,
            total_qty_executed=total_executed,
            avg_price=avg_price,
            total_cost=total_cost,
            slippage_pct=overall_slippage,
            slices=executed_slices,
            duration_seconds=duration,
        )

        logger.info(
            f"[TWAP] Complete: {total_executed}/{total_qty} filled, "
            f"avg=${avg_price:.2f}, slip={overall_slippage:.1f}%, "
            f"duration={duration:.0f}s"
        )

        return result
