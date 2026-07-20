"""
filter.py — Per-item candidate evaluation.

Mixin with the heavy filter loop (originally inline in run_cycle).
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.api.exceptions import RateLimitException
from src.config import Config
from src.core.sandbox_scenarios import scenario_engine
from src.core.target_sniping.filter_evaluator import _FilterEvaluatorMixin
from src.core.target_sniping.microstructure_pipeline import run_microstructure_pipeline
from src.core.target_sniping.ranking import rank_candidates_by_spread
from src.core.target_sniping.validations import (
    check_bait_detection,
    compute_microstructure_scores,
    evaluate_cross_market_arb,
    evaluate_fee_slippage_tod,
)
from src.db.price_history import price_db
from src.risk.price_validator import (
    PriceValidationError,
    validate_volatility,
)

logger = logging.getLogger("SnipingBot")


class _FilterMixin(_FilterEvaluatorMixin):
    """Per-item candidate evaluation (filter loop)."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any  # DMarketAPIClient
    buy_budget: float
    liquidity: Any  # LiquidityManager
    _diag_cycle_id: int

    def _skip_if_locked(self, item_id: str, title: str) -> bool: ...  # type: ignore[empty-body]
    def _calculate_float_premium(self, attrs: dict[str, Any]) -> float: ...  # type: ignore[empty-body]
    @staticmethod
    def is_dirty_bs(attrs: dict[str, Any]) -> bool: ...  # type: ignore[empty-body]

    # v12.7: Per-cycle oracle price cache (P1-5).
    # Avoids duplicate HTTP calls for the same title within a single cycle.
    # Cleared at the start of each run_cycle via _clear_oracle_cache().
    _oracle_price_cache: dict[str, float]

    def _ensure_oracle_cache(self) -> None:
        if not hasattr(self, '_oracle_price_cache') or not isinstance(self._oracle_price_cache, dict):
            object.__setattr__(self, '_oracle_price_cache', {})

    def _clear_oracle_cache(self) -> None:
        """Clear the per-cycle oracle price cache. Called at start of run_cycle."""
        self._ensure_oracle_cache()
        self._oracle_price_cache.clear()

    @staticmethod
    def _rank_candidates_by_spread(
        items: list[dict[str, Any]],
        agg_prices: dict[str, dict[str, Any]],
        max_price_usd: float | None = None,
    ) -> list[tuple[str, float]]:
        return rank_candidates_by_spread(items, agg_prices, max_price_usd)

    async def _evaluate_candidate(
        self,
        *,
        item: dict[str, Any],
        game_id: str,
        oracle: Any,
        agg_prices: dict[str, dict[str, Any]],
        bulk_fees: dict[str, float],
        current_balance: float,
        current_margin: float,
        cs_snapshots: dict[str, Any] | None = None,
        cs_bids: dict[str, Any] | None = None,
        saturation_counts: dict[str, int] | None = None,
        effective_balance: float | None = None,
        dynamic_max_price: float | None = None,
    ) -> dict[str, Any] | None:
        """
        Evaluate a single market item and return a buy payload, or None.

        Returns a dict {buy_offer, title, item_id, base_price, list_price,
        best_bid, best_ask} if the item passes all filters; None otherwise.

        cs_snapshots: optional dict {title: PriceSnapshot} pre-populated by the
        caller via a single oracle /prices/batch call. When supplied, the
        oracle validation step here is a dict lookup (free) instead of a
        per-item HTTP call. Falls back to per-item oracle.get_item_price
        only if the title is missing from the snapshots (selective mode miss).
        """

        title = item.get("title", "")
        item_id = item.get("itemId")
        base_price_cents = int(item.get("price", {}).get("USD", 0))
        base_price = base_price_cents / 100.0

        if not title or not item_id or base_price <= 0:
            return None

        if price_db.has_target_been_placed(item_id):
            return None

        # v12.2 Phase 2.1: Skip if asset is reverted or trade_protected
        if self._skip_if_locked(item_id, title):
            return None

        if base_price < Config.MIN_PRICE_USD:
            return None

        # --- v14.0 Bait/Spoof Detection ---
        bait_result = check_bait_detection(title, base_price)
        if not bait_result["pass"]:
            return None

        if base_price > self.buy_budget or base_price > current_balance:
            return None

        # v14.4: Dynamic snipe price cap (Half Kelly based on effective balance)
        # Balances $43 → max $5.00 floor. $500 → max $50. $2000 → max $200.
        _dyn_max = dynamic_max_price or Config.MAX_SNIPING_PRICE_USD
        if base_price > _dyn_max:
            if os.getenv("DRY_RUN", "true").lower() == "true":
                price_db.log_decision(
                    title,
                    "skip",
                    "Above balance-aware cap",
                    f"${base_price:.2f} > ${_dyn_max:.2f} "
                    f"(eff_balance={effective_balance or current_balance:.2f})",
                )
            return None

        # v14.9: Drawdown freeze + daily loss gate (pre-trade risk check)
        # This is the CRITICAL safety gate: blocks buys during drawdown freeze,
        # daily loss limit, consecutive loss streak, and pump-blacklist.
        if hasattr(self, "risk") and self.risk is not None:
            risk_check = self.risk.pre_trade_check(
                proposed_size_usd=base_price,
                current_equity_usd=current_balance,
                game_id=game_id,
                item_title=title,
            )
            if not risk_check.allowed:
                if Config.DRY_RUN:
                    price_db.log_decision(
                        title, "skip", "Risk blocked",
                        risk_check.reason,
                    )
                return None

        # v14.4: Fractional Kelly position sizing
        # Kelly formula: f* = win_rate - (1 - win_rate) / win_loss_ratio
        # Half Kelly = 0.5 * f* (reduced drawdown, same growth direction)
        # v15.8: Bayesian win rate + EWMA volatility adjustment
        kelly_risk_pct = float(Config.MAX_POSITION_RISK_PCT)
        if Config.KELLY_ENABLED and hasattr(self, "risk") and self.risk is not None:
            try:
                risk_state = self.risk.get_state()
                wr = getattr(risk_state, "win_rate", 0.55) or 0.55
                wlr = getattr(risk_state, "win_loss_ratio", 1.5) or 1.5
                win_rate = max(0.30, min(0.80, wr))
                win_loss_ratio = max(1.0, wlr)

                # v15.8: Try Bayesian Kelly with EWMA volatility adjustment
                try:
                    from src.analysis.algo_pack.bayesian_stats import BetaDistribution
                    from src.analysis.algo_pack.ewma import adaptive_kelly_fraction

                    # Build Beta distribution from risk state
                    total_wins = getattr(risk_state, "total_wins", 0) or 0
                    total_losses = getattr(risk_state, "total_losses", 0) or 0
                    beta_dist = BetaDistribution(alpha=2.0 + total_wins, beta=2.0 + total_losses)

                    # Get price history for volatility estimation
                    price_hist = price_db.get_recent_prices(title, days=7)
                    prices = [p for p, _ in price_hist] if price_hist else []

                    # Adaptive Kelly: Bayesian win rate + EWMA volatility
                    kelly_f = adaptive_kelly_fraction(
                        win_rate=beta_dist.mean,
                        win_loss_ratio=win_loss_ratio,
                        prices=prices,
                        base_fraction=float(Config.KELLY_FRACTION),
                    )
                    kelly_risk_pct = max(
                        float(Config.KELLY_FLOOR_PCT),
                        kelly_f * 100.0,
                    )
                except Exception:
                    # Fallback to standard Kelly (consistent with Bayesian path)
                    kelly_f = win_rate - (1.0 - win_rate) / win_loss_ratio
                    kelly_f = max(0.0, min(0.25, kelly_f))  # Clamp same as adaptive_kelly_fraction
                    kelly_risk_pct = max(
                        float(Config.KELLY_FLOOR_PCT),
                        kelly_f * 100.0 * float(Config.KELLY_FRACTION),
                    )

                # Cap by the hard position limit and the dynamic item price cap
                kelly_risk_pct = min(kelly_risk_pct, float(Config.MAX_POSITION_RISK_PCT))
            except Exception as e:
                # Kelly sizing failed — use CONSERVATIVE fallback (half-cap)
                # to avoid over-sizing when risk state is unavailable.
                logger.warning(f"[KELLY] Risk state unavailable, using half-cap fallback: {e}")
                kelly_risk_pct = float(Config.MAX_POSITION_RISK_PCT) * 0.5
        max_risk_price = (effective_balance or current_balance) * (kelly_risk_pct / 100.0)
        max_risk_price = min(max_risk_price, dynamic_max_price or Config.MAX_SNIPING_PRICE_USD)
        if base_price > max_risk_price:
            return None

        # Per-cycle diag (one log per cycle)
        if not hasattr(self, "_diag_cycle_id") or self._diag_cycle_id != getattr(self, "_cur_cycle", -1):
            self._diag_cycle_id = getattr(self, "_cur_cycle", -1)
            agg_keys = list(agg_prices.keys())[:3] if agg_prices else []
            cs_keys = list((cs_snapshots or {}).keys())[:3]
            cs_bid_keys = list((cs_bids or {}).keys())[:3]
            logger.info(
                f"[DIAG] item={title!r} base=${base_price:.2f} | "
                f"agg_titles={len(agg_prices)} (sample={agg_keys}) | "
                f"cs_snap_titles={len(cs_snapshots or {})} (sample={cs_keys}) | "
                f"cs_bid_titles={len(cs_bids or {})} (sample={cs_bid_keys})"
            )
        # Per-item diag for top-5 candidates (those in cs_snapshots)
        if cs_snapshots and title in cs_snapshots:
            agg_for_this = agg_prices.get(title, {})
            logger.info(
                f"[DIAG-TOP5] {title!r} base=${base_price:.2f} | "
                f"DM_bid=${agg_for_this.get('best_bid', 0):.2f} "
                f"DM_ask=${agg_for_this.get('best_ask', 0):.2f}"
            )

        # --- Strategy A: bid-ask spread analysis (needed by cross-market threshold) ---
        agg = agg_prices.get(title, {})
        best_bid = float(agg.get("best_bid") or 0.0)
        best_ask = float(agg.get("best_ask") or 0.0)
        ask_count = int(agg.get("ask_count") or 0)
        bid_count = int(agg.get("bid_count") or 0)

        # --- v15.7: Microstructure pipeline (extracted from inline checks) ---
        # v15.9: Fetch price_history early for Hawkes, Bollinger, DEMA, MACD, Hurst
        _early_history = price_db.get_recent_prices(title, days=14)
        _early_prices = [p for p, _ in _early_history] if _early_history else []
        ms_result = run_microstructure_pipeline(
            title=title,
            base_price=base_price,
            best_ask=best_ask,
            best_bid=best_bid,
            ask_count=ask_count,
            bid_count=bid_count,
            sales_cache=getattr(self, '_sales_cache', None),
            prev_agg_prices=getattr(self, '_prev_agg_prices', None),
            dom_listings=getattr(self, '_dom_cache', {}).get(title, []),
            price_history=_early_prices if _early_prices else None,
        )
        if not ms_result.passed:
            if Config.DRY_RUN:
                price_db.log_decision(title, "skip", "Microstructure", ms_result.reason)
            return None
        vwap_signal_val = ms_result.vwap_signal
        cvd_val = ms_result.cvd
        vpin_val = ms_result.vpin
        trade_records = ms_result.trade_records

        # --- Strategy C: cross-market arb (oracle provider bids) ---
        cross_market = evaluate_cross_market_arb(title, best_ask, cs_bids)
        cross_market_provider = cross_market["provider"]
        cross_market_bid = cross_market["bid"]

        if not self.liquidity.can_spend(base_price, game_id, current_balance):
            return None

        if price_db.is_crashing(title):
            return None

        # v12.2 Phase 2.4: Multi-level liquidity verification
        if Config.USE_LIQUIDITY_FILTER and cross_market_provider is None:
            liquidity = price_db.get_liquidity_metrics(title)
            if not liquidity["is_liquid"]:
                is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
                if is_sandbox:
                    price_db.log_decision(
                        title,
                        "skip",
                        "Low liquidity",
                        f"{liquidity['reason']} (sales={liquidity['total_sales']})",
                    )
                return None

        # v12.2 Phase 2.3: Wash trading detection (trimmed mean)
        if (
            Config.WASH_TRADING_DETECTION
            and cross_market_provider is None
            and not price_db.detect_wash_trading(
                title,
                days=14,
                boost_pct=Config.TRIMMED_MEAN_BOOST_PCT,
                max_outliers=Config.TRIMMED_MEAN_MAX_OUTLIERS,
            )
        ):
            is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
            if is_sandbox:
                price_db.log_decision(
                    title,
                    "skip",
                    "Wash trading detected",
                    "Raw mean >> trimmed mean — price inflated by anomalies",
                )
            return None

        # v15.9: Reuse early price history fetch (avoid duplicate DB call)
        history = _early_history
        prices_only = _early_prices
        # Skip volatility validation if we have a strong cross-market signal.
        if prices_only and cross_market_provider is None:
            try:
                validate_volatility(prices_only)
            except PriceValidationError:
                return None

        if best_ask <= 0 or best_bid <= 0:
            return None
        if ask_count < 1 or bid_count < 1:
            return None  # No real demand
        if (ask_count + bid_count) < Config.MIN_BID_ASK_COUNT:
            return None  # Too thin order book

        # v14.6: Seasonal timing — dynamically adjust spread threshold
        effective_min_spread = Config.INTRA_MIN_SPREAD_PCT
        if Config.SEASONAL_TIMING_ENABLED:
            try:
                from src.analysis.seasonal import get_timing_multiplier
                timing_mult = get_timing_multiplier()
                effective_min_spread *= timing_mult
            except Exception:
                pass  # non-fatal

        # Oracle validation (Phase 1: selective, top-K via batch).
        # In selective mode the caller pre-fetches oracle snapshots for the
        # top-K candidates and passes them in cs_snapshots. We do a dict
        # lookup here (free) instead of a per-item HTTP call.
        # v12.7: Also check per-cycle cache to avoid duplicate HTTP calls (P1-5).
        is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
        cs_price = 0.0
        cs_snap = (cs_snapshots or {}).get(title)
        if cs_snap is not None and getattr(cs_snap, "has_data", False):
            cs_price = cs_snap.min_price
            if is_sandbox:
                cs_price *= scenario_engine.get_price_modifier()
        elif title in self._oracle_price_cache:
            # v12.7: Per-cycle cache hit — avoid HTTP call (P1-5).
            cs_price = self._oracle_price_cache[title]
            if is_sandbox:
                cs_price *= scenario_engine.get_price_modifier()
        else:
            # Title not in the pre-fetched snapshots (not in top-K) or
            # selective mode is off — fall back to per-item call.
            try:
                cs_price = await oracle.get_item_price(title)
                # v12.7: Cache the result for this cycle (P1-5).
                if cs_price > 0:
                    self._oracle_price_cache[title] = cs_price
                if is_sandbox:
                    cs_price *= scenario_engine.get_price_modifier()
            except (RateLimitException, Exception) as e:
                if isinstance(e, RateLimitException) or "429" in str(e):
                    logger.error(f"Oracle rate limited during {game_id} scan.")
                    self.empty_page_count = 5
                    return None
                raise e

        # Spread / opportunity gate.
        # Intra-DMarket spread arbitrage is rare because bid < ask on normal
        # markets. Also allow cross-market underpriced items: DMarket ask is
        # cheaper than the oracle lowest ask, so we can buy on DMarket and
        # resell at the oracle reference price.
        has_intra_spread = best_bid > best_ask * (1 + effective_min_spread / 100.0)
        has_cross_market = cross_market_provider is not None

        required_margin = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE + (Config.MIN_SPREAD_PCT / 100.0)
        has_oracle_discount = (
            cs_price > 0
            and base_price < cs_price * (1 - required_margin)
        )

        # v14.8.1: DMarket-internal underpriced check. Only call last-sales
        # when no other edge exists, to respect rate limits.
        has_dmarket_underpriced = False
        dm_underpriced_ref = 0.0
        if not (has_intra_spread or has_cross_market or has_oracle_discount):
            try:
                from src.core.target_sniping.underpriced import is_dmarket_underpriced
                up = await is_dmarket_underpriced(
                    self.client, game_id, title, base_price, fee_rate=bulk_fees.get(item_id, Config.FEE_RATE)
                )
                if up.get("underpriced"):
                    has_dmarket_underpriced = True
                    dm_underpriced_ref = up.get("reference_price", 0.0)
                    if is_sandbox:
                        price_db.log_decision(
                            title, "pass", "DMarket underpriced vs sales",
                            f"base={base_price:.2f} ref={dm_underpriced_ref:.2f} margin={up.get('margin_pct', 0):.1f}%"
                        )
            except Exception as e:
                logger.debug(f"DMarket underpriced check failed for {title}: {e}")

        if not (has_intra_spread or has_cross_market or has_oracle_discount or has_dmarket_underpriced):
            if is_sandbox:
                price_db.log_decision(
                    title,
                    "skip",
                    "No spread or cross-market edge",
                    f"bid={best_bid:.2f} ask={best_ask:.2f} "
                    f"dm_ask={base_price:.2f} cs_ask={cs_price:.2f} "
                    f"need_margin={required_margin:.1%}",
                )
            return None

        # Oracle reference: ensure oracle price is not way below our buy
        # (this would mean the item is genuinely overvalued on DMarket)
        if cs_price > 0 and base_price > cs_price * 1.5:
            # DMarket price is 50%+ above BUFF163 — likely overpriced, skip
            if is_sandbox:
                price_db.log_decision(
                    title,
                    "skip",
                    "DMarket overpriced vs BUFF163",
                    f"DM=${base_price} BUFF=${cs_price}",
                )
            return None

        # Calculate profit: list at best_bid - 0.01, but use oracle ask or
        # cross-market bid as reference when available.
        cs_ask_price = 0.0
        cs_snap = (cs_snapshots or {}).get(title)
        if cs_snap is not None and getattr(cs_snap, "has_data", False):
            cs_ask_price = cs_snap.min_price

        # Base list price: prefer oracle reference. For cross-market
        # underpriced items best_bid may be below our buy price, so listing
        # at best_bid - 0.01 would guarantee a loss.
        list_price = round(best_bid - Config.INTRA_LIST_DISCOUNT, 2)

        # Use oracle lowest ask as list price reference when available
        if cs_ask_price > 0:
            # Don't list above oracle ask — compete with cheapest marketplace
            cs_list_price = round(cs_ask_price * 0.97, 2)
            # For cross-market buys, always use the oracle reference if it
            # covers our cost. Otherwise keep the higher of the two prices.
            min_profitable = base_price * (1 + required_margin)
            if base_price > best_bid or cs_list_price > list_price:
                list_price = max(cs_list_price, min_profitable)
            else:
                list_price = max(list_price, min_profitable)

        # Cross-market bid override (highest bid across all marketplaces)
        if cross_market_provider and cross_market_bid > best_bid:
            list_price = round(
                min(cross_market_bid * 0.97, cross_market_bid - Config.INTRA_LIST_DISCOUNT),
                2,
            )

        # =================================================================
        # v14.6: Value Detection Layers (TA Site Analysis)
        # =================================================================
        # Parse attributes once for all detectors
        attrs_list = item.get("attributes", [])
        attrs = {a.get("name"): a.get("value") for a in attrs_list}
        is_rare = False  # auto-detect rare items for exclusive flag

        # --- Layer 1: Float Premium (enhanced: dirty BS, round float, float dates) ---
        float_premium = 1.0
        if Config.FLOAT_PREMIUM_ENABLED:
            float_premium = self._calculate_float_premium(attrs)
            if float_premium > 1.0:
                list_price = round(list_price * float_premium, 2)
                if is_sandbox:
                    logger.debug(f"[FLOAT] {title}: premium {float_premium:.2f}x → list=${list_price:.2f}")
                is_rare = float_premium >= 1.20

        # --- Layer 1b: Dirty BS bonus (float > 0.95, appearance-changing skins) ---
        if Config.DIRTY_BS_ENABLED and not is_rare:
            try:
                if self.is_dirty_bs(attrs):
                    list_price = round(list_price * 1.10, 2)
                    if is_sandbox:
                        logger.info(f"[DIRTY-BS] {title}: dirty BS premium 1.10x → list=${list_price:.2f}")
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"[DIRTY-BS] {title}: detection failed: {e}")

        # --- Layer 2: Filler demand multiplier ---
        if Config.FILLER_TRACKING_ENABLED:
            try:
                from src.analytics.filler_tracker import get_filler_multiplier
                filler_mult = get_filler_multiplier(title)
                if filler_mult > 1.0:
                    list_price = round(list_price * filler_mult, 2)
                    if is_sandbox:
                        logger.debug(f"[FILLER] {title}: demand multiplier {filler_mult:.2f}x → list=${list_price:.2f}")
            except (ImportError, KeyError, TypeError) as e:
                logger.debug(f"[FILLER] {title}: lookup failed: {e}")

        # --- Layer 3: Pattern/Phase/Paint Premium (Doppler, Blue Gem, Fire & Ice, etc.) ---
        pattern_premium = 1.0
        if Config.PATTERN_PREMIUM_ENABLED:
            try:
                if hasattr(self, "_calculate_pattern_premium"):
                    pattern_premium = self._calculate_pattern_premium(attrs)
                    if pattern_premium > 1.0:
                        list_price = round(list_price * pattern_premium, 2)
                        if is_sandbox:
                            logger.info(
                                f"[PATTERN] {title}: premium {pattern_premium:.2f}x "
                                f"(phase={attrs.get('phase', '?')} seed={attrs.get('paintSeed', '?')}) "
                                f"→ list=${list_price:.2f}"
                            )
                        is_rare = True
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"[PATTERN] {title}: premium calc failed: {e}")

        # --- Layer 4: Sticker Value + Combo Premium ---
        item_stickers = item.get("stickers", [])
        sticker_value = 0.0
        if item_stickers and hasattr(self, "stickers"):
            try:
                sticker_value = self.stickers.calculate_added_value(item_stickers)
                if sticker_value > 1.0:
                    # Add sticker value to list price (market pays extra for stickered items)
                    list_price = round(list_price + sticker_value * 0.5, 2)
                    if is_sandbox:
                        logger.info(
                            f"[STICKER] {title}: value ${sticker_value:.2f} "
                            f"(applied 50% = ${sticker_value*0.5:.2f}) → list=${list_price:.2f}"
                        )
                if sticker_value > 2.0:
                    is_rare = True
                    if is_sandbox:
                        logger.info(f"[RARE] {title}: sticker value ${sticker_value:.2f} → exclusive keep")
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"[STICKER] {title}: value calc failed: {e}")

        # --- Layer 5: Float-date bonus ---
        if Config.FLOAT_DATE_ENABLED and not is_rare:
            try:
                from src.core.target_sniping.pricing import _is_float_date
                float_str = attrs.get("floatPartValue", "")
                if float_str:
                    if _is_float_date(float(float_str)):
                        list_price = round(list_price * 1.08, 2)
                        if is_sandbox:
                            logger.info(f"[FLOAT-DATE] {title}: date float → 1.08x → list=${list_price:.2f}")
            except (ValueError, TypeError, ImportError) as e:
                logger.debug(f"[FLOAT-DATE] {title}: detection failed: {e}")

        if list_price < base_price * 1.02:
            # Less than 2% gross — too thin after fees
            return None

        # v12.0 Phase 1.1: Low-Fee Filter (prefer low-fee items)
        # v12.2 Phase 2.2: Use bulk fee instead of per-item API call
        # v14.8.1: Use reduced fee from low-fee scan if available.
        fee_rate = bulk_fees.get(item_id, 0.05)
        low_fee_override = item.get("_low_fee_rate")
        if low_fee_override is not None and low_fee_override < fee_rate:
            fee_rate = low_fee_override
        if fee_rate == 0.05:
            # Fall back to per-item call only if bulk missed this item
            fee_rate = await self.client.get_item_fee(game_id, item_id, base_price_cents)
        cached_low_fee = price_db.get_low_fee_rate(title)
        if cached_low_fee is not None and cached_low_fee < fee_rate:
            # Use the lower cached rate (it might differ slightly from dynamic)
            fee_rate = min(fee_rate, cached_low_fee)

        fee_result = evaluate_fee_slippage_tod(
            title=title,
            base_price=base_price,
            best_ask=best_ask,
            best_bid=best_bid,
            ask_count=ask_count,
            bid_count=bid_count,
            fee_rate=fee_rate,
            current_margin=current_margin,
            list_price=list_price,
            is_sandbox=is_sandbox,
            cs_ask_price=cs_ask_price,
        )
        if not fee_result["pass"]:
            return None

        # v12.7: Inventory saturation check (P2-4).
        # Limits concentration risk: max N units of same hash_name.
        # Uses Config.MAX_SAME_ITEM_HOLDINGS (env-configurable, default 3).
        # v12.8: Uses pre-computed saturation_counts (O(1) lookup) when available,
        # avoiding N separate DB calls for each candidate in the parallel loop.
        if saturation_counts is not None:
            held_count = saturation_counts.get(title, 0)
        else:
            held_count = len(
                [
                    x
                    for x in price_db.get_virtual_inventory(status="idle", only_unlocked=False)
                    if x["hash_name"] == title
                ]
            )
        if held_count >= Config.MAX_SAME_ITEM_HOLDINGS:
            if is_sandbox:
                price_db.record_missed_opportunity(
                    title, base_price, list_price, f"Saturation Limit ({held_count})"
                )
            else:
                logger.debug(
                    f"[SATURATION] {title}: already holding {held_count} units, "
                    f"max={Config.MAX_SAME_ITEM_HOLDINGS}. Skipping."
                )
            return None

        # v14.4: Lock-aware inventory cap — prevent over-concentration during trade-lock
        # At $43 with $5 items: max ~6 simultaneous holdings (80% liquid fraction)
        if Config.LOCK_AWARE_CAP_ENABLED:
            _eff_bal = effective_balance or current_balance
            total_locked = price_db.get_virtual_inventory_locked_value()
            liquid_remaining = _eff_bal * Config.LOCK_AWARE_LIQUID_FRACTION
            if total_locked + base_price > liquid_remaining:
                if is_sandbox:
                    price_db.record_missed_opportunity(
                        title, base_price, list_price,
                        f"Lock-Aware Cap (locked=${total_locked:.2f} + "
                        f"${base_price:.2f} > ${liquid_remaining:.2f} liquid)"
                    )
                else:
                    logger.debug(
                        f"[LOCK-CAP] {title}: ${total_locked:.2f} locked + "
                        f"${base_price:.2f} exceeds ${liquid_remaining:.2f} liquid buffer. Skipping."
                    )
                return None

        if is_sandbox and base_price > current_balance:
            price_db.record_missed_opportunity(
                title, base_price, list_price, "Insufficient Balance"
            )

        # --- v14.3 Composite Score ---
        if Config.STRICT_MICROSTRUCTURE_FILTERS:
            micro = compute_microstructure_scores(
                title=title,
                best_ask=best_ask,
                best_bid=best_bid,
                ask_count=ask_count,
                bid_count=bid_count,
                trade_records=trade_records,
                vwap_signal_val=vwap_signal_val,
                cvd_val=cvd_val,
                vpin_val=vpin_val,
                adverse_pass=True,
                vol_regime=ms_result.vol_regime,
                prev_agg_prices=getattr(self, '_prev_agg_prices', None),
                # v15.9: New algorithm signals from microstructure pipeline
                hawkes_activity=ms_result.hawkes_activity,
                bollinger_squeeze=ms_result.bollinger_squeeze,
                bollinger_pctb=ms_result.bollinger_pctb,
                dema_crossover=ms_result.dema_crossover,
                macd_signal_val=ms_result.macd_signal,
                hurst_exponent=ms_result.hurst_exponent,
            )
            micro["composite_score"]
            micro["components"]

        # --- Decide: instant buy vs target ---
        # For intra-spread strategy, we typically instant-buy
        # (the spread exists right now, may not in 5 minutes)
        buy_offer = {
            "offerId": item_id,
            "price": {"amount": str(int(base_price * 100)), "currency": "USD"},
        }
        return {
            "buy_offer": buy_offer,
            "title": title,
            "item_id": item_id,
            "base_price": base_price,
            "list_price": list_price,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "strategy": (
                "dmarket_underpriced" if has_dmarket_underpriced
                else ("cross_market" if cross_market_provider else "intra_spread")
            ),
            "target_platform": cross_market_provider or "dmarket",
            "dm_underpriced_ref": dm_underpriced_ref,
            "is_rare": is_rare,
        }
