"""
Test suite for src.config.Config — the trading engine configuration.

Covers: all mandatory attributes, Balance-Aware v14.4 parameters,
v14.6 value detection layers, Oracle batch settings, liquidity metrics,
and the regression for MAX_FIRST_SALE_AGE_DAYS (2026-06-07 crash fix).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config


class TestConfigMandatoryKeys:
    """Core credentials and game configuration."""

    def test_game_id_is_cs2(self):
        assert Config.GAME_ID == "a8db"

    def test_fee_rate_in_range(self):
        assert 0.01 <= Config.FEE_RATE <= 0.10

    def test_min_spread_pct_positive(self):
        assert Config.MIN_SPREAD_PCT > 0

    def test_scan_interval_positive(self):
        assert Config.SCAN_INTERVAL > 0

    def test_batch_size_positive(self):
        assert Config.BATCH_SIZE > 0


class TestBalanceAwareV14_4:
    """Dynamic balance-aware position sizing parameters."""

    def test_reserve_buffer_positive(self):
        assert Config.BALANCE_RESERVE_USD >= 0

    def test_sniping_floor_positive(self):
        assert Config.MAX_SNIPING_PRICE_FLOOR > 0

    def test_sniping_balance_fraction_in_range(self):
        assert 0 < Config.MAX_SNIPING_PRICE_BALANCE_FRACTION <= 1.0

    def test_kelly_fraction_in_range(self):
        assert 0 < Config.KELLY_FRACTION <= 1.0

    def test_kelly_floor_pct_positive(self):
        assert Config.KELLY_FLOOR_PCT > 0

    def test_lock_aware_liquid_fraction_in_range(self):
        assert 0 < Config.LOCK_AWARE_LIQUID_FRACTION <= 1.0

    def test_capital_velocity_min_in_range(self):
        assert 0 < Config.CAPITAL_VELOCITY_MIN <= 1.0

    def test_drawdown_threshold_in_range(self):
        assert 0 < Config.DRAWDOWN_FREEZE_THRESHOLD < 1.0


class TestLiquidityMetrics:
    """Liquidity and sale-age filter parameters."""

    def test_min_total_sales_positive(self):
        assert Config.MIN_TOTAL_SALES > 0

    def test_min_sales_in_window_positive(self):
        assert Config.MIN_SALES_IN_WINDOW > 0

    def test_first_sale_age_days_present(self):
        """Regression: MAX_FIRST_SALE_AGE_DAYS was missing and crashed every cycle on 2026-06-07."""
        assert hasattr(Config, "MAX_FIRST_SALE_AGE_DAYS")
        assert Config.MAX_FIRST_SALE_AGE_DAYS > 0
        assert Config.MAX_FIRST_SALE_AGE_DAYS <= 365

    def test_last_sale_age_days_present(self):
        assert hasattr(Config, "MAX_LAST_SALE_AGE_DAYS")
        assert Config.MAX_LAST_SALE_AGE_DAYS > 0

    def test_max_open_inventory_present(self):
        assert hasattr(Config, "MAX_OPEN_INVENTORY")
        assert Config.MAX_OPEN_INVENTORY > 0

    def test_bot_version_present(self):
        assert hasattr(Config, "BOT_VERSION")
        assert Config.BOT_VERSION


class TestOracleBatchSettings:
    """Oracle batch and cache parameters."""

    def test_oracle_batch_size_positive(self):
        assert Config.ORACLE_BATCH_SIZE > 0

    def test_oracle_top_k_validate_positive(self):
        assert Config.ORACLE_TOP_K_VALIDATE > 0

    def test_oracle_cache_ttl_positive(self):
        assert Config.ORACLE_CACHE_TTL_SECONDS > 0

    def test_oracle_cache_refresh_top_n_positive(self):
        assert Config.ORACLE_CACHE_REFRESH_TOP_N > 0

    def test_agg_scan_top_n_positive(self):
        assert Config.AGG_SCAN_TOP_N > 0

    def test_listings_fetch_limit_positive(self):
        assert Config.LISTINGS_FETCH_LIMIT > 0


class TestV14_6ValueDetection:
    """v14.6 value detection boolean flags."""

    def test_float_premium_enabled_is_bool(self):
        assert isinstance(Config.FLOAT_PREMIUM_ENABLED, bool)

    def test_pattern_premium_enabled_is_bool(self):
        assert isinstance(Config.PATTERN_PREMIUM_ENABLED, bool)

    def test_sticker_combo_enabled_is_bool(self):
        assert isinstance(Config.STICKER_COMBO_ENABLED, bool)

    def test_seasonal_timing_enabled_is_bool(self):
        assert isinstance(Config.SEASONAL_TIMING_ENABLED, bool)

    def test_filler_tracking_enabled_is_bool(self):
        assert isinstance(Config.FILLER_TRACKING_ENABLED, bool)

    def test_dirty_bs_enabled_is_bool(self):
        assert isinstance(Config.DIRTY_BS_ENABLED, bool)

    def test_round_float_enabled_is_bool(self):
        assert isinstance(Config.ROUND_FLOAT_ENABLED, bool)

    def test_float_date_enabled_is_bool(self):
        assert isinstance(Config.FLOAT_DATE_ENABLED, bool)

    def test_commission_optimizer_enabled_is_bool(self):
        assert isinstance(Config.COMMISSION_OPTIMIZER_ENABLED, bool)


class TestMicrostructureV14:
    """Order book microstructure parameters."""

    def test_obi_enabled_is_bool(self):
        assert isinstance(Config.OBI_ENABLED, bool)

    def test_ofi_enabled_is_bool(self):
        assert isinstance(Config.OFI_ENABLED, bool)

    def test_bait_detection_enabled_is_bool(self):
        assert isinstance(Config.BAIT_DETECTION_ENABLED, bool)

    def test_vwap_filter_enabled_is_bool(self):
        assert isinstance(Config.VWAP_FILTER_ENABLED, bool)

    def test_slippage_gate_enabled_is_bool(self):
        assert isinstance(Config.SLIPPAGE_GATE_ENABLED, bool)

    def test_cvd_enabled_is_bool(self):
        assert isinstance(Config.CVD_ENABLED, bool)

    def test_vpin_enabled_is_bool(self):
        assert isinstance(Config.VPIN_ENABLED, bool)

    def test_adverse_selection_enabled_is_bool(self):
        assert isinstance(Config.ADVERSER_SELECTION_ENABLED, bool)

    def test_composite_score_enabled_is_bool(self):
        assert isinstance(Config.COMPOSITE_SCORE_ENABLED, bool)

    def test_tod_enabled_is_bool(self):
        assert isinstance(Config.TOD_ENABLED, bool)


class TestRiskManagement:
    """Risk management parameters."""

    def test_min_price_usd_positive(self):
        assert Config.MIN_PRICE_USD > 0

    def test_max_price_usd_positive(self):
        assert Config.MAX_PRICE_USD > 0

    def test_max_same_item_holdings_positive(self):
        assert Config.MAX_SAME_ITEM_HOLDINGS > 0

    def test_max_concurrent_positions_positive(self):
        assert Config.MAX_CONCURRENT_POSITIONS > 0

    def test_max_total_inventory_value_positive(self):
        assert Config.MAX_TOTAL_INVENTORY_VALUE > 0

    def test_max_total_inventory_items_positive(self):
        assert Config.MAX_TOTAL_INVENTORY_ITEMS > 0

    def test_dry_run_is_bool(self):
        assert isinstance(Config.DRY_RUN, bool)

    def test_trade_lock_hours_not_negative(self):
        assert Config.TRADE_LOCK_HOURS >= 0


class TestCrossMarket:
    """Cross-market arbitrage parameters."""

    def test_cross_market_enabled_is_bool(self):
        assert isinstance(Config.CROSS_MARKET_ENABLED, bool)

    def test_cross_market_min_edge_pct_positive(self):
        assert Config.CROSS_MARKET_MIN_EDGE_PCT > 0


class TestConfigRefScan:
    """
    Regression test: scan all .py source files for Config.X references
    and verify every referenced attribute exists in Config.
    Prevents runtime AttributeError on undiscovered code paths.
    """

    def test_all_config_refs_resolved(self):
        import re
        import os

        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
        ref_pattern = re.compile(r"Config\.([A-Z_][A-Z0-9_]*)")

        defined = {k for k in dir(Config) if k.isupper() and not callable(getattr(Config, k))}
        missing: dict[str, set[str]] = {}

        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                fpath = os.path.join(root, fn)
                with open(fpath) as fh:
                    for line in fh:
                        for match in ref_pattern.finditer(line):
                            ref = match.group(1)
                            if ref not in defined:
                                rel = os.path.relpath(fpath, src_dir)
                                missing.setdefault(ref, set()).add(rel)

        if missing:
            msg = "\n".join(
                f"Config.{k} missing, referenced in: {', '.join(sorted(v))}"
                for k, v in sorted(missing.items())
            )
            pytest.fail(f"Unresolved Config references found:\n{msg}")


import pytest
print(f"Config trading test suite loaded. {len(Config.__dict__)} attributes defined.")
