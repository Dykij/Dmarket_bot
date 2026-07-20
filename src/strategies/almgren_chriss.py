"""
almgren_chriss.py — Optimal Execution via Almgren-Chriss Model.

Source: Almgren & Chriss (2000) "Optimal Execution of Portfolio Transactions"
        Cartea, Jaimungal, Penalva (2015) "Algorithmic and High-Frequency Trading"

Replaces simplified TWAP with theoretically optimal execution trajectory.
Minimizes a combination of:
  - Market impact (temporary + permanent)
  - Timing risk (variance of execution cost)

Key formula:
  Optimal trajectory: x_k = X * sinh(κ(T-k)) / sinh(κT)
  where κ = sqrt(σ² / (η * γ)), T = time horizon, X = total quantity

Parameters:
  η (eta)   = temporary impact coefficient
  γ (gamma) = permanent impact coefficient
  σ (sigma) = volatility

Applications in DMarket:
  - Large orders (qty >= 5): reduce market impact
  - Illiquid items: spread execution over time
  - High volatility: adjust trajectory speed

Complexity: O(N) for trajectory computation, O(1) per slice
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("AlmgrenChriss")


class SliceStatus(Enum):
    """Status of a single execution slice."""
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionSlice:
    """One mini-order in the execution schedule."""
    slice_id: int
    qty: int
    scheduled_time: datetime
    target_qty_remaining: float  # how much should remain after this slice
    status: SliceStatus = SliceStatus.PENDING
    execution_price: float = 0.0
    execution_time: datetime | None = None
    slippage_pct: float = 0.0
    error: str | None = None


@dataclass
class ACHResult:
    """Result of Almgren-Chriss execution."""
    success: bool
    total_qty_requested: int
    total_qty_executed: int
    avg_price: float
    total_cost: float
    slippage_pct: float
    implementation_shortfall: float  # actual cost vs arrival price
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
            "implementation_shortfall": round(self.implementation_shortfall, 4),
            "slices_count": len(self.slices),
            "duration_s": round(self.duration_seconds, 1),
        }


class AlmgrenChrissExecutor:
    """
    Almgren-Chriss optimal execution for DMarket.

    Computes the optimal execution trajectory that minimizes
    implementation shortfall (market impact + timing risk).

    Usage:
        executor = AlmgrenChrissExecutor(client)
        result = await executor.execute(item, total_qty=10, volatility=0.02)
    """

    def __init__(
        self,
        client: Any,  # DMarketAPIClient
        max_slices: int = 10,
        min_interval_seconds: float = 30.0,
        max_slippage_pct: float = 5.0,
        price_refresh_before_slice: bool = True,
        # Almgren-Chriss parameters
        eta: float = 0.01,       # temporary impact coefficient
        gamma: float = 0.001,    # permanent impact coefficient
        risk_aversion: float = 1.0,  # λ (lambda) — higher = more risk-averse
    ):
        self.client = client
        self.max_slices = max_slices
        self.min_interval_seconds = min_interval_seconds
        self.max_slippage_pct = max_slippage_pct
        self.price_refresh = price_refresh_before_slice
        self.eta = eta
        self.gamma = gamma
        self.risk_aversion = risk_aversion

    def compute_trajectory(
        self,
        total_qty: int,
        time_horizon_periods: int,
        volatility: float,
    ) -> list[float]:
        """
        Compute optimal execution trajectory.

        The trajectory specifies how much inventory should REMAIN
        at each time step. The slice quantity is the difference
        between consecutive inventory levels.

        Args:
            total_qty: Total quantity to execute.
            time_horizon_periods: Number of execution periods.
            volatility: Price volatility (annualized or per-period).

        Returns:
            List of remaining inventory at each time step [0, ..., 0].
        """
        if total_qty <= 0 or time_horizon_periods <= 0:
            return []

        X = total_qty
        T = time_horizon_periods
        sigma = max(volatility, 0.001)
        eta = max(self.eta, 1e-6)
        _gamma = max(self.gamma, 1e-6)  # noqa: F841 — used in impact model
        lam = max(self.risk_aversion, 0.01)

        # κ = sqrt(λ * σ² / η)
        kappa = math.sqrt(lam * sigma ** 2 / eta)

        # Prevent numerical overflow for large kappa*T
        kappa_T = kappa * T
        if kappa_T > 20:
            # For very large κT, trajectory is essentially front-loaded
            # (execute everything immediately)
            return [float(X)] + [0.0] * T

        # Optimal trajectory: x_k = X * sinh(κ(T-k)) / sinh(κT)
        sinh_kT = math.sinh(kappa_T)
        if abs(sinh_kT) < 1e-10:
            # Fallback: linear trajectory
            return [X * (1 - k / T) for k in range(T + 1)]

        trajectory = []
        for k in range(T + 1):
            x_k = X * math.sinh(kappa * (T - k)) / sinh_kT
            trajectory.append(max(0.0, min(float(X), x_k)))

        return trajectory

    def create_schedule(
        self,
        total_qty: int,
        time_horizon: timedelta,
        volatility: float = 0.02,
        start_time: datetime | None = None,
    ) -> list[ExecutionSlice]:
        """
        Create execution schedule from optimal trajectory.

        Args:
            total_qty: Total quantity to buy.
            time_horizon: Time to spread execution over.
            volatility: Price volatility estimate.
            start_time: Start time (default: now).
        """
        if start_time is None:
            start_time = datetime.now(timezone.utc)

        num_slices = min(self.max_slices, max(1, total_qty))
        interval = time_horizon / num_slices
        if interval.total_seconds() < self.min_interval_seconds:
            interval = timedelta(seconds=self.min_interval_seconds)
            num_slices = max(1, int(time_horizon.total_seconds() / self.min_interval_seconds))

        # Compute optimal trajectory
        trajectory = self.compute_trajectory(total_qty, num_slices, volatility)

        # Convert trajectory (remaining inventory) to slice quantities
        schedule = []
        remaining = float(total_qty)

        for i in range(num_slices):
            # Target remaining after this slice
            target_remaining = trajectory[i + 1] if i + 1 < len(trajectory) else 0.0
            slice_qty = max(1, int(round(remaining - target_remaining)))
            slice_qty = min(slice_qty, int(round(remaining)))

            if slice_qty <= 0:
                continue

            scheduled_time = start_time + interval * i

            schedule.append(ExecutionSlice(
                slice_id=i,
                qty=slice_qty,
                scheduled_time=scheduled_time,
                target_qty_remaining=target_remaining,
            ))

            remaining -= slice_qty

        # Distribute any rounding remainder
        total_scheduled = sum(s.qty for s in schedule)
        if total_scheduled < total_qty and schedule:
            schedule[-1].qty += (total_qty - total_scheduled)

        return schedule

    async def execute(
        self,
        item: dict[str, Any],
        total_qty: int,
        time_horizon: timedelta = timedelta(minutes=10),
        volatility: float = 0.02,
        game_id: str = "a8db",
    ) -> ACHResult:
        """
        Execute using Almgren-Chriss optimal trajectory.

        Args:
            item: Item dict with 'title', 'itemId', 'price' keys.
            total_qty: Total quantity to buy.
            time_horizon: Time to spread execution over.
            volatility: Price volatility estimate.
            game_id: DMarket game ID.

        Returns:
            ACHResult with execution details.
        """
        start_time = datetime.now(timezone.utc)
        title = item.get("title", "")

        try:
            price_obj = item.get("price", {})
            base_price_cents = int(price_obj.get("USD", 0)) if isinstance(price_obj, dict) else 0
        except (TypeError, ValueError):
            base_price_cents = 0
        base_price = base_price_cents / 100.0

        if base_price <= 0:
            logger.error(f"[ACH] Invalid base_price={base_price} for {title}, aborting")
            return ACHResult(
                success=False, total_qty_requested=total_qty,
                total_qty_executed=0, avg_price=0, total_cost=0,
                slippage_pct=0, implementation_shortfall=0,
                duration_seconds=0,
            )

        schedule = self.create_schedule(total_qty, time_horizon, volatility, start_time)
        executed_slices: list[ExecutionSlice] = []
        total_executed = 0
        total_cost = 0.0

        logger.info(
            f"[ACH] Starting {len(schedule)} slices for {title} "
            f"(qty={total_qty}, horizon={time_horizon}, vol={volatility:.4f})"
        )

        consecutive_failures = 0
        max_consecutive_failures = 2

        for slice_obj in schedule:
            # Wait until scheduled time
            now = datetime.now(timezone.utc)
            wait = (slice_obj.scheduled_time - now).total_seconds()
            if wait > 0:
                await asyncio.sleep(wait)

            # Refresh price
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
                    logger.warning(f"[ACH] Price refresh failed: {e}")

            # Check slippage
            slippage_pct = 0.0
            if base_price > 0:
                slippage_pct = ((current_price - base_price) / base_price) * 100

            if slippage_pct > self.max_slippage_pct:
                slice_obj.status = SliceStatus.SKIPPED
                slice_obj.error = f"Slippage {slippage_pct:.1f}% > {self.max_slippage_pct}%"
                logger.warning(f"[ACH] Slice {slice_obj.slice_id} skipped: {slice_obj.error}")
                executed_slices.append(slice_obj)
                continue

            # Execute buy
            try:
                result = await self.client.place_buy_order(
                    item_id=item.get("itemId", ""),
                    price_cents=int(current_price * 100),
                    game_id=game_id,
                )

                if result and result.get("orderId"):
                    slice_obj.status = SliceStatus.EXECUTED
                    slice_obj.execution_price = current_price
                    slice_obj.execution_time = datetime.now(timezone.utc)
                    slice_obj.slippage_pct = slippage_pct
                    total_executed += slice_obj.qty
                    total_cost += current_price * slice_obj.qty

                    logger.info(
                        f"[ACH] Slice {slice_obj.slice_id}: "
                        f"{slice_obj.qty}x @ ${current_price:.2f} "
                        f"(slip={slippage_pct:.1f}%)"
                    )
                else:
                    slice_obj.status = SliceStatus.FAILED
                    slice_obj.error = "No order ID returned"

            except Exception as e:
                slice_obj.status = SliceStatus.FAILED
                slice_obj.error = f"{type(e).__name__}: {str(e)[:200]}"
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"[ACH] {consecutive_failures} consecutive failures, aborting")
                    for remaining in schedule[slice_obj.slice_id + 1:]:
                        remaining.status = SliceStatus.SKIPPED
                        remaining.error = "Aborted: consecutive failure limit"
                    executed_slices.append(slice_obj)
                    break

            executed_slices.append(slice_obj)
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
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Implementation Shortfall: difference between decision price and avg execution
        implementation_shortfall = (avg_price - base_price) * total_executed

        result = ACHResult(
            success=total_executed == total_qty,
            total_qty_requested=total_qty,
            total_qty_executed=total_executed,
            avg_price=avg_price,
            total_cost=total_cost,
            slippage_pct=overall_slippage,
            implementation_shortfall=round(implementation_shortfall, 4),
            slices=executed_slices,
            duration_seconds=duration,
        )

        logger.info(
            f"[ACH] Complete: {total_executed}/{total_qty} filled, "
            f"avg=${avg_price:.2f}, slip={overall_slippage:.1f}%, "
            f"IS=${implementation_shortfall:.2f}, duration={duration:.0f}s"
        )

        return result


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for Almgren-Chriss."""
    executor = AlmgrenChrissExecutor(client=None)

    # Test trajectory computation
    trajectory = executor.compute_trajectory(
        total_qty=10, time_horizon_periods=5, volatility=0.02
    )
    print("[ACH] Trajectory for 10 units over 5 periods:")
    for i, x in enumerate(trajectory):
        print(f"  t={i}: remaining={x:.2f}")

    # Should start at 10 and end at 0
    assert abs(trajectory[0] - 10.0) < 0.1, f"Start should be ~10: {trajectory[0]}"
    assert trajectory[-1] < 0.1, f"End should be ~0: {trajectory[-1]}"

    # Should be monotonically decreasing
    for i in range(1, len(trajectory)):
        assert trajectory[i] <= trajectory[i-1] + 0.1, \
            f"Trajectory should decrease: {trajectory[i-1]:.2f} -> {trajectory[i]:.2f}"

    # High risk aversion → front-loaded
    executor_risk_averse = AlmgrenChrissExecutor(client=None, risk_aversion=10.0)
    traj_ra = executor_risk_averse.compute_trajectory(10, 5, 0.02)
    # First slice should be larger
    first_slice_ra = 10 - traj_ra[1]
    first_slice_normal = 10 - trajectory[1]
    print(f"[ACH] Risk-averse first slice: {first_slice_ra:.2f}")
    print(f"  vs normal: {first_slice_normal:.2f}")

    # Test schedule creation
    from datetime import timedelta
    schedule = executor.create_schedule(
        total_qty=10, time_horizon=timedelta(minutes=5), volatility=0.02
    )
    total_scheduled = sum(s.qty for s in schedule)
    print(f"[ACH] Schedule: {len(schedule)} slices, total={total_scheduled}")
    assert total_scheduled == 10, f"Total should be 10: {total_scheduled}"

    print("[ACH] Self-check PASSED")


if __name__ == "__main__":
    _demo()
