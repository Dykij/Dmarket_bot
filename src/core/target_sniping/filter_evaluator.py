"""
filter_evaluator.py — Extracted evaluation stages from filter.py.

v15.1: Breaks the 647-line _evaluate_candidate() into 6 discrete stages.
Each stage is a separate method that can be tested independently.

Stages:
    1. _stage_risk_gates      — validation, bait, balance, Kelly
    2. _stage_microstructure  — OBI, OFI, VWAP, CVD, VPIN
    3. _stage_oracle_resolve  — oracle price + spread gate
    4. _stage_value_layers    — float, pattern, sticker premiums
    5. _stage_fee_and_caps    — fee eval, saturation, lock-aware
    6. _stage_assemble        — composite score + buy payload
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from src.config import Config
from src.db.price_history import price_db

logger = logging.getLogger("SnipingBot")


@dataclass
class EvalContext:
    """Shared state between evaluation stages."""
    title: str = ""
    item_id: str = ""
    base_price: float = 0.0
    base_price_cents: int = 0
    best_bid: float = 0.0
    best_ask: float = 0.0
    ask_count: int = 0
    bid_count: int = 0
    cs_price: float = 0.0
    list_price: float = 0.0
    fee_rate: float = 0.05
    cross_market_provider: str | None = None
    cross_market_bid: float = 0.0
    has_dmarket_underpriced: bool = False
    dm_underpriced_ref: float = 0.0
    is_rare: bool = False
    is_sandbox: bool = False
    effective_min_spread: float = 0.0
    required_margin: float = 0.0
    kelly_risk_pct: float = 0.0
    vwap_signal_val: float = 0.0
    cvd_val: float = 0.0
    vpin_val: float = 0.0
    vol_regime: str = "medium"
    adverse_pass: bool = True
    trade_records: list[dict[str, Any]] | None = None
    attrs: dict[str, Any] | None = None


class _FilterEvaluatorMixin:
    """Extracted evaluation stages for _evaluate_candidate."""

    # Type stubs
    client: Any
    risk: Any
    liquidity: Any
    stickers: Any
    buy_budget: float
    _prev_agg_prices: dict[str, Any]
    _oracle_price_cache: dict[str, float]
    _dom_cache: dict[str, Any]
    _sales_cache: dict[str, Any]

    def _stage_risk_gates(
        self,
        item: dict[str, Any],
        game_id: str,
        current_balance: float,
        effective_balance: float,
        dynamic_max_price: float,
        current_margin: float,
    ) -> EvalContext | None:
        """Stage 1: Pre-trade risk gates. Returns None if rejected."""
        from src.core.target_sniping.validations import check_bait_detection

        ctx = EvalContext()
        ctx.title = item.get("title", "")
        ctx.item_id = item.get("itemId")
        ctx.base_price_cents = int(item.get("price", {}).get("USD", 0))
        ctx.base_price = ctx.base_price_cents / 100.0
        ctx.is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"

        if not ctx.title or not ctx.item_id or ctx.base_price <= 0:
            return None
        if price_db.has_target_been_placed(ctx.item_id):
            return None
        if self._skip_if_locked(ctx.item_id, ctx.title):
            return None
        if ctx.base_price < Config.MIN_PRICE_USD:
            return None

        bait = check_bait_detection(ctx.title, ctx.base_price)
        if not bait["pass"]:
            return None
        if ctx.base_price > self.buy_budget or ctx.base_price > current_balance:
            return None

        _dyn_max = dynamic_max_price or Config.MAX_SNIPING_PRICE_USD
        if ctx.base_price > _dyn_max:
            if ctx.is_sandbox:
                price_db.log_decision(ctx.title, "skip", "Above balance-aware cap",
                    f"${ctx.base_price:.2f} > ${_dyn_max:.2f}")
            return None

        if hasattr(self, "risk") and self.risk is not None:
            risk_check = self.risk.pre_trade_check(
                proposed_size_usd=ctx.base_price,
                current_equity_usd=current_balance,
                game_id=game_id,
                item_title=ctx.title,
            )
            if not risk_check.allowed:
                if Config.DRY_RUN:
                    price_db.log_decision(ctx.title, "skip", "Risk blocked", risk_check.reason)
                return None

        # Kelly sizing
        ctx.kelly_risk_pct = float(Config.MAX_POSITION_RISK_PCT)
        if Config.KELLY_ENABLED and hasattr(self, "risk") and self.risk is not None:
            try:
                risk_state = self.risk.get_state()
                wr = getattr(risk_state, "win_rate", 0.55) or 0.55
                wlr = getattr(risk_state, "win_loss_ratio", 1.5) or 1.5
                win_rate = max(0.30, min(0.80, wr))
                win_loss_ratio = max(1.0, wlr)
                kelly_f = win_rate - (1.0 - win_rate) / win_loss_ratio
                ctx.kelly_risk_pct = max(
                    float(Config.KELLY_FLOOR_PCT),
                    kelly_f * 100.0 * float(Config.KELLY_FRACTION),
                )
                ctx.kelly_risk_pct = min(ctx.kelly_risk_pct, float(Config.MAX_POSITION_RISK_PCT))
            except Exception as e:
                logger.warning(f"[KELLY] Risk state unavailable: {e}")
                ctx.kelly_risk_pct = float(Config.MAX_POSITION_RISK_PCT) * 0.5

        max_risk_price = effective_balance * (ctx.kelly_risk_pct / 100.0)
        max_risk_price = min(max_risk_price, dynamic_max_price or Config.MAX_SNIPING_PRICE_USD)
        if ctx.base_price > max_risk_price:
            return None

        return ctx

    def _stage_microstructure(
        self,
        ctx: EvalContext,
        agg_prices: dict[str, dict[str, Any]],
    ) -> bool:
        """Stage 2: Microstructure filters. Returns False if rejected."""
        from src.core.target_sniping.validations import (
            check_adverse_selection,
            check_cvd_vpin,
            check_obi,
            check_roll_spread,
            check_vol_regime,
            check_vwap_filter,
            evaluate_cross_market_arb,
        )

        agg = agg_prices.get(ctx.title, {})
        ctx.best_bid = float(agg.get("best_bid") or 0.0)
        ctx.best_ask = float(agg.get("best_ask") or 0.0)
        ctx.ask_count = int(agg.get("ask_count") or 0)
        ctx.bid_count = int(agg.get("bid_count") or 0)

        if ctx.best_bid <= 0 or ctx.best_ask <= 0:
            return False
        if ctx.ask_count < 1 or ctx.bid_count < 1:
            return False
        if (ctx.ask_count + ctx.bid_count) < Config.MIN_BID_ASK_COUNT:
            return False

        if Config.STRICT_MICROSTRUCTURE_FILTERS:
            obi = check_obi(ctx.ask_count, ctx.bid_count, ctx.best_ask, ctx.best_bid)
            if not obi["pass"]:
                return False

            if Config.QUEUE_IMBALANCE_ENABLED and ctx.ask_count > 0:
                from src.analysis.microstructure import queue_imbalance
                qi = queue_imbalance(ctx.bid_count, ctx.ask_count)
                if qi is not None and qi < Config.QI_SELL_THRESHOLD:
                    return False

            if Config.OFI_ENABLED and hasattr(self, '_prev_agg_prices'):
                prev = self._prev_agg_prices.get(ctx.title, {})
                if prev:
                    ofi = (ctx.bid_count - (prev.get("bid_count", 0) or 0)) - (ctx.ask_count - (prev.get("ask_count", 0) or 0))
                    if ofi < Config.OFI_SELL_THRESHOLD:
                        return False

            vwap_result = check_vwap_filter(ctx.title, ctx.best_ask, getattr(self, '_sales_cache', None))
            if not vwap_result["pass"]:
                return False
            ctx.vwap_signal_val = vwap_result["signal"]

            cvd_result = check_cvd_vpin(ctx.title, getattr(self, '_sales_cache', None))
            if not cvd_result["pass"]:
                return False
            ctx.cvd_val = cvd_result["cvd"]
            ctx.vpin_val = cvd_result["vpin"]
            ctx.trade_records = cvd_result.get("trade_records", [])

            if ctx.trade_records:
                adverse = check_adverse_selection(ctx.title, ctx.trade_records)
                if not adverse["pass"]:
                    return False
                ctx.adverse_pass = True

                vol = check_vol_regime(ctx.title, ctx.trade_records)
                if not vol["pass"]:
                    return False
                ctx.vol_regime = vol["regime"]

                roll = check_roll_spread(ctx.title, ctx.trade_records, ctx.best_ask)
                if not roll["pass"]:
                    return False

        cross = evaluate_cross_market_arb(ctx.title, ctx.best_ask, None)
        ctx.cross_market_provider = cross.get("provider")
        ctx.cross_market_bid = cross.get("bid", 0.0)

        return True

    async def _stage_oracle_resolve(
        self,
        ctx: EvalContext,
        oracle: Any,
        cs_snapshots: dict[str, Any],
        game_id: str,
    ) -> bool:
        """Stage 3: Oracle resolution + spread gate. Returns False if no edge."""
        from src.api.exceptions import RateLimitException
        from src.core.sandbox_scenarios import scenario_engine

        ctx.effective_min_spread = Config.INTRA_MIN_SPREAD_PCT
        if Config.SEASONAL_TIMING_ENABLED:
            try:
                from src.analysis.seasonal import get_timing_multiplier
                ctx.effective_min_spread *= get_timing_multiplier()
            except Exception:
                pass

        ctx.required_margin = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE + (Config.MIN_SPREAD_PCT / 100.0)

        # Oracle price resolution
        cs_snap = cs_snapshots.get(ctx.title)
        if cs_snap is not None and getattr(cs_snap, "has_data", False):
            ctx.cs_price = cs_snap.min_price
            if ctx.is_sandbox:
                ctx.cs_price *= scenario_engine.get_price_modifier()
        elif ctx.title in self._oracle_price_cache:
            ctx.cs_price = self._oracle_price_cache[ctx.title]
        else:
            try:
                ctx.cs_price = await oracle.get_item_price(ctx.title)
                if ctx.cs_price > 0:
                    self._oracle_price_cache[ctx.title] = ctx.cs_price
            except (RateLimitException, Exception) as e:
                if isinstance(e, RateLimitException) or "429" in str(e):
                    return False
                raise

        # Spread gate
        has_intra = ctx.best_bid > ctx.best_ask * (1 + ctx.effective_min_spread / 100.0)
        has_cross = ctx.cross_market_provider is not None
        has_oracle = ctx.cs_price > 0 and ctx.base_price < ctx.cs_price * (1 - ctx.required_margin)

        if not (has_intra or has_cross or has_oracle):
            try:
                from src.core.target_sniping.underpriced import is_dmarket_underpriced
                up = await is_dmarket_underpriced(self.client, game_id, ctx.title, ctx.base_price, fee_rate=ctx.fee_rate)
                if up.get("underpriced"):
                    ctx.has_dmarket_underpriced = True
                    ctx.dm_underpriced_ref = up.get("reference_price", 0.0)
            except Exception:
                pass

        if not (has_intra or has_cross or has_oracle or ctx.has_dmarket_underpriced):
            return False

        if ctx.cs_price > 0 and ctx.base_price > ctx.cs_price * 1.5:
            return False

        return True

    def _stage_value_layers(self, ctx: EvalContext, item: dict[str, Any]) -> None:
        """Stage 4: Value detection layers (float, pattern, sticker, filler).

        v15.3: Enhanced with ultra-low-float, mid-range sticker combos,
        and extended pattern detection.
        """
        attrs_list = item.get("attributes", [])
        ctx.attrs = {a.get("name"): a.get("value") for a in attrs_list}

        ctx.list_price = round(ctx.best_bid - Config.INTRA_LIST_DISCOUNT, 2)

        cs_snap = getattr(self, '_cs_snapshots_cache', {}).get(ctx.title)
        if cs_snap and getattr(cs_snap, "has_data", False):
            cs_ask = cs_snap.min_price
            cs_list = round(cs_ask * 0.97, 2)
            min_profitable = ctx.base_price * (1 + ctx.required_margin)
            if ctx.base_price > ctx.best_bid or cs_list > ctx.list_price:
                ctx.list_price = max(cs_list, min_profitable)
            else:
                ctx.list_price = max(ctx.list_price, min_profitable)

        if ctx.cross_market_provider and ctx.cross_market_bid > ctx.best_bid:
            ctx.list_price = round(min(ctx.cross_market_bid * 0.97, ctx.cross_market_bid - Config.INTRA_LIST_DISCOUNT), 2)

        # 1. Float premium (v15.3: enhanced with ultra-low-float tiers)
        if Config.FLOAT_PREMIUM_ENABLED:
            fp = self._calculate_float_premium(ctx.attrs or {})
            if fp > 1.0:
                ctx.list_price = round(ctx.list_price * fp, 2)
                ctx.is_rare = fp >= 1.20

        # 2. Pattern premium (v15.3: Tiger Tooth, tri-color, Gamma Doppler)
        if Config.PATTERN_PREMIUM_ENABLED and hasattr(self, "_calculate_pattern_premium"):
            pp = self._calculate_pattern_premium(ctx.attrs or {})
            if pp > 1.0:
                ctx.list_price = round(ctx.list_price * pp, 2)
                ctx.is_rare = True

        # 3. Sticker premium (v15.4: with slot premium and streak detection)
        if hasattr(self, "stickers"):
            try:
                weapon_name = ctx.title.split(" | ")[0] if " | " in ctx.title else ""
                sv = self.stickers.calculate_added_value(
                    item.get("stickers", []),
                    weapon_name=weapon_name,
                )
                if sv > 1.0:
                    ctx.list_price = round(ctx.list_price + sv * 0.5, 2)
                if sv > 2.0:
                    ctx.is_rare = True
            except Exception:
                pass

        # 4. v15.3: Ultra-low-float bonus from CSFloat data
        if ctx.attrs:
            try:
                float_val = float(ctx.attrs.get("floatPartValue", ctx.attrs.get("float_value", 0)))
                if 0 < float_val < 0.001:
                    # Ultra-low-float: additional 20% bonus on top of float premium
                    ctx.list_price = round(ctx.list_price * 1.20, 2)
                    ctx.is_rare = True
                elif 0 < float_val < 0.005:
                    # Very low float: additional 10% bonus
                    ctx.list_price = round(ctx.list_price * 1.10, 2)
            except (ValueError, TypeError):
                pass

        # v15.8: Ternary search for optimal sell price
        # Uses price history to find the discount that maximizes expected profit.
        # Only adjusts UPWARD (never lowers the list_price from value detection).
        try:
            from src.analysis.algo_pack.sell_optimizer import find_optimal_sell_price
            from src.db.price_history import price_db as _pdb
            hist = _pdb.get_recent_prices(ctx.title, days=30)
            if hist and len(hist) >= 10:
                prices = [p for p, _ in hist]
                optimal = find_optimal_sell_price(
                    fair_price=ctx.list_price,
                    cost_price=ctx.base_price,
                    fee_rate=0.05,
                    price_history=prices,
                )
                # Only adjust if the optimal price is HIGHER and reasonable
                if optimal > ctx.list_price and optimal > ctx.base_price * 1.02:
                    ctx.list_price = optimal
        except Exception:
            pass  # fallback to original list_price

    def _stage_fee_and_caps(
        self,
        ctx: EvalContext,
        item: dict[str, Any],
        bulk_fees: dict[str, float],
        saturation_counts: dict[str, int],
        effective_balance: float,
        current_balance: float,
        game_id: str,
    ) -> bool:
        """Stage 5: Fee evaluation + inventory caps. Returns False if rejected."""
        from src.core.target_sniping.validations import evaluate_fee_slippage_tod

        ctx.fee_rate = bulk_fees.get(ctx.item_id, 0.05)
        low_fee = item.get("_low_fee_rate")
        if low_fee is not None and low_fee < ctx.fee_rate:
            ctx.fee_rate = low_fee

        if ctx.list_price < ctx.base_price * 1.02:
            return False

        fee_result = evaluate_fee_slippage_tod(
            title=ctx.title, base_price=ctx.base_price,
            best_ask=ctx.best_ask, best_bid=ctx.best_bid,
            ask_count=ctx.ask_count, bid_count=ctx.bid_count,
            fee_rate=ctx.fee_rate, current_margin=0.0,
            list_price=ctx.list_price, is_sandbox=ctx.is_sandbox,
            cs_ask_price=ctx.cs_price,
        )
        if not fee_result["pass"]:
            return False

        held = saturation_counts.get(ctx.title, 0)
        if held >= Config.MAX_SAME_ITEM_HOLDINGS:
            return False

        if Config.LOCK_AWARE_CAP_ENABLED:
            locked = price_db.get_virtual_inventory_locked_value()
            liquid = effective_balance * Config.LOCK_AWARE_LIQUID_FRACTION
            if locked + ctx.base_price > liquid:
                return False

        return True

    def _stage_assemble(self, ctx: EvalContext, item: dict[str, Any]) -> dict[str, Any]:
        """Stage 6: Assemble buy payload."""
        if Config.STRICT_MICROSTRUCTURE_FILTERS:
            from src.core.target_sniping.validations import compute_microstructure_scores
            compute_microstructure_scores(
                title=ctx.title, best_ask=ctx.best_ask, best_bid=ctx.best_bid,
                ask_count=ctx.ask_count, bid_count=ctx.bid_count,
                trade_records=ctx.trade_records or [],
                vwap_signal_val=ctx.vwap_signal_val,
                cvd_val=ctx.cvd_val, vpin_val=ctx.vpin_val,
                adverse_pass=ctx.adverse_pass, vol_regime=ctx.vol_regime,
                prev_agg_prices=getattr(self, '_prev_agg_prices', None),
            )

        return {
            "buy_offer": {
                "offerId": ctx.item_id,
                "price": {"amount": str(int(ctx.base_price * 100)), "currency": "USD"},
            },
            "title": ctx.title,
            "item_id": ctx.item_id,
            "base_price": ctx.base_price,
            "list_price": ctx.list_price,
            "best_bid": ctx.best_bid,
            "best_ask": ctx.best_ask,
            "strategy": (
                "dmarket_underpriced" if ctx.has_dmarket_underpriced
                else ("cross_market" if ctx.cross_market_provider else "intra_spread")
            ),
            "target_platform": ctx.cross_market_provider or "dmarket",
            "dm_underpriced_ref": ctx.dm_underpriced_ref,
            "is_rare": ctx.is_rare,
        }
