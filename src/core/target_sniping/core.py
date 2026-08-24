"""
core.py — The main SnipingLoop orchestrator (v15.1 refactored).

Composes mixins for specific responsibilities:
    _PricingMixin    (float premium, low-fee cache)
    _ResaleMixin     (auto_resale, reprice_unsold_offers)
    _InventoryMixin  (sync_inventory_statuses, skip_if_locked)
    _SandboxMixin    (DRY_RUN helpers: competition, latency, errors)
    _ScannerMixin    (parallel listing fetcher, float/phase scan)
    _FilterMixin     (per-item candidate evaluation)
    _ExecutionMixin  (instant-buy execution)
    CycleOrchestrator (pipeline stage extraction)

Provides the public entry points:
    - SnipingLoop.__init__
    - start             — the main async loop
    - run_cycle         — delegates to CycleOrchestrator pipeline stages
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.analytics.stickers_evaluator import StickerEvaluator
from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config
from src.core.daily_briefing import DailyBriefingScheduler
from src.core.event_shield import event_shield
from src.core.target_sniping.cycle_orchestrator import CycleContext, CycleOrchestrator
from src.core.target_sniping.execution import _ExecutionMixin
from src.core.target_sniping.filter import _FilterMixin
from src.core.target_sniping.inventory import _InventoryMixin
from src.core.target_sniping.pricing import _PricingMixin
from src.core.target_sniping.resale import _ResaleMixin
from src.core.target_sniping.sandbox import _SandboxMixin
from src.core.target_sniping.scanner import _ScannerMixin
from src.core.target_sniping.scheduler import _SchedulerMixin
from src.core.target_sniping.telemetry import _TelemetryMixin
from src.db.price_history import price_db
from src.risk.liquidity_manager import LiquidityManager
# P1-1: Lazy import

logger = logging.getLogger("SnipingBot")


class SnipingLoop(  # type: ignore[misc]
    _SchedulerMixin,
    _TelemetryMixin,
    _PricingMixin,
    _ResaleMixin,
    _InventoryMixin,
    _SandboxMixin,
    _ScannerMixin,
    _FilterMixin,
    _ExecutionMixin,
    CycleOrchestrator,
):
    """
    Main Autonomous Loop for DMarket Sniping & Re-sale (v15.1 Pipeline).
    """

    def __init__(self, client: DMarketAPIClient) -> None:
        self.client = client
        self.stickers = StickerEvaluator()
        self.liquidity = LiquidityManager()
        self.inventory_mgr: Any = None

        self.target_games = [Config.GAME_ID]
        self.deep_scan_counter = 0
        self.buy_budget = Config.MAX_PRICE_USD
        self.running = False
        self.empty_page_count = 0
        self.resale_cycle_limit = 1
        self.reprice_counter = 0

        self._prev_agg_prices: dict[str, Any] = {}
        self._prev_agg_prices_prior: dict[str, Any] = {}
        self._current_agg_prices: dict[str, Any] = {}  # Current cycle's agg_prices for resale
        self._sales_cache: dict[str, Any] = {}
        self._failed_offer_ids: dict[str, float] = {}  # OfferNotFound blacklist {id: ts}
        self._failure_counts: dict[str, int] = {}  # strike counter per offer_id
        self._permanent_failures: set[str] = set()  # 3-strike permanent blacklist

        from src.analytics.self_reflection import self_reflection
        from src.risk.pump_detector import PumpDetector
        from src.risk.risk_manager import RiskManager

        self.self_reflection = self_reflection
        from src.telegram.notifier import notifier as _notifier_inst
        self.pump_detector = PumpDetector(price_db=price_db, notifier=_notifier_inst)

        try:
            restored = self.pump_detector.restore_from_disk()
            if restored > 0:
                logger.info(f"[PumpDetector] restored {restored} blacklist entries")
        except Exception as e:
            logger.warning(f"[PumpDetector] restore failed: {e}")

        self.risk = RiskManager(
            daily_loss_limit_usd=float(os.getenv("MAX_DAILY_LOSS_USD", "10.00")),
            daily_trade_limit=int(os.getenv("MAX_DAILY_TRADES", "200")),
            max_drawdown_pct=float(os.getenv("MAX_DRAWDOWN_PCT", "15.0")),
            soft_halt_drawdown_pct=float(os.getenv("SOFT_HALT_DRAWDOWN_PCT", "5.0")),
            pump_detector=self.pump_detector,
        )

        self.briefing_scheduler: DailyBriefingScheduler | None = None
        self._last_quota_warn: float = 0.0
        self._last_milestone: float = 0.0

    async def get_min_profit_margin(self) -> float:
        """Dynamic margin: base * event multiplier + volatility regime adjustment."""
        base = Config.MIN_SPREAD_PCT
        reflection = self.self_reflection._cached_result
        adjusted = self.self_reflection.get_adjusted_spread(base, reflection)
        vol_adj = await self.self_reflection.get_volatility_regime_adjustment()
        adjusted += vol_adj
        adjusted = max(1.0, adjusted)
        return (adjusted / 100.0) * event_shield.get_margin_multiplier()

    async def run_cycle(self, game_id: str) -> None:
        """
        v15.1: Refactored pipeline — delegates to CycleOrchestrator stages.

        Pipeline:
            1. _stage_prepare    — counters, balance, oracle init
            2. _stage_scan       — aggregated prices + secondary scans
            3. _stage_prefetch   — bulk fees, sales, pump detection
            4. _stage_evaluate   — parallel candidate evaluation
            5. _stage_execute    — instant buys
            6. _stage_postprocess — resale, repricing, telemetry
        """
        ctx = CycleContext(game_id=game_id)
        try:
            ctx = await self._stage_prepare(ctx)

            ctx = await self._stage_scan(ctx)
            # v17.11: Only return early if BOTH agg_prices AND items are empty.
            # If agg_prices exists, demand expansion in _stage_evaluate can still
            # find candidates even when time filter removes all market items.
            if not ctx.agg_prices and not ctx.items:
                self.empty_page_count += 1
                return
            self.empty_page_count = 0

            ctx = await self._stage_prefetch(ctx)
            ctx = await self._stage_evaluate(ctx)
            ctx = await self._stage_execute(ctx)
            await self._stage_postprocess(ctx)

        except Exception as e:
            from src.risk.error_reporter import ErrorReporter
            from src.risk.fatal_errors import classify

            classification = classify(e)
            if classification in ("FATAL", "UNKNOWN"):
                report = ErrorReporter(e, context={
                    "game_id": game_id,
                    "cycle": self.deep_scan_counter,
                    "balance": f"${ctx.current_balance:.2f}",
                    "items": len(ctx.items),
                })
                logger.error(report.format_log())
                raise
            logger.warning(
                f"[CYCLE] Transient error ({classification}) for "
                f"{game_id}: {type(e).__name__}: {e}",
                exc_info=True,
            )
        finally:
            # Persist risk state to SQLite (survives restarts for 24/7 operation)
            # Moved here from cycle_orchestrator to ensure it runs even on exceptions
            try:
                if hasattr(self, 'risk') and self.risk:
                    self.risk.save_state_to_db()
            except Exception:
                pass


if __name__ == "__main__":
    pass
