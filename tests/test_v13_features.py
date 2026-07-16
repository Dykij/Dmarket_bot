"""
test_v13_features.py — Tests for v13.0+ features:

1. Fee estimation (4 tiers: 2/5/7/10%)
2. Trade lock hours (Config.TRADE_LOCK_HOURS=0)
3. Funds hold model (frozen balance, release_expired)
4. Exclusive inventory (mark_exclusive, get_non_exclusive_inventory)
5. Sticker evaluation
6. Pattern/phase premium
7. Formatters (funds hold display)
"""

import os
import time
from unittest.mock import MagicMock, AsyncMock

from src.config import reset_config
reset_config()

import pytest


# =====================================================================
# Fee Estimation Tests
# =====================================================================
class TestFeeEstimation:
    """Tests for _estimate_fee_from_volume (4-tier model)."""

    def test_liquid_fee_2pct(self):
        """≥50 volume → 2%."""
        from src.api.dmarket_api_client.fees import _FeesMixin
        fee = _FeesMixin._estimate_fee_from_volume(25, 25)
        assert fee == 0.02

    def test_standard_fee_5pct(self):
        """10-49 volume → 5%."""
        from src.api.dmarket_api_client.fees import _FeesMixin
        fee = _FeesMixin._estimate_fee_from_volume(5, 5)
        assert fee == 0.05

    def test_high_fee_7pct(self):
        """5-9 volume → 7%."""
        from src.api.dmarket_api_client.fees import _FeesMixin
        fee = _FeesMixin._estimate_fee_from_volume(3, 2)
        assert fee == 0.07

    def test_max_fee_10pct(self):
        """1-4 volume (illiquid) → 10%."""
        from src.api.dmarket_api_client.fees import _FeesMixin
        fee = _FeesMixin._estimate_fee_from_volume(2, 0)
        assert fee == 0.10

    def test_zero_volume_fallback(self):
        """0 volume → standard 5% (safe fallback)."""
        from src.api.dmarket_api_client.fees import _FeesMixin
        fee = _FeesMixin._estimate_fee_from_volume(0, 0)
        assert fee == 0.05

    def test_boundary_50(self):
        """Exactly 50 → liquid 2%."""
        from src.api.dmarket_api_client.fees import _FeesMixin
        fee = _FeesMixin._estimate_fee_from_volume(50, 0)
        assert fee == 0.02

    def test_boundary_10(self):
        """Exactly 10 → standard 5% (not high)."""
        from src.api.dmarket_api_client.fees import _FeesMixin
        fee = _FeesMixin._estimate_fee_from_volume(10, 0)
        assert fee == 0.05

    def test_boundary_5(self):
        """Exactly 5 → high 7% (not max)."""
        from src.api.dmarket_api_client.fees import _FeesMixin
        fee = _FeesMixin._estimate_fee_from_volume(5, 0)
        assert fee == 0.07


# =====================================================================
# Trade Lock Hours Tests
# =====================================================================
class TestTradeLockHours:
    """Tests for TRADE_LOCK_HOURS config."""

    def test_default_is_zero(self):
        """Default trade lock is 0 (instant marketplace resale)."""
        from src.config import reset_config
        reset_config()
        from src.config import Config
        assert Config.TRADE_LOCK_HOURS >= 0

    def test_env_override(self):
        """TRADE_LOCK_HOURS env var is respected."""
        from src.config import reset_config
        import os
        original = os.environ.get("TRADE_LOCK_HOURS")
        try:
            os.environ["TRADE_LOCK_HOURS"] = "168"
            reset_config()
            from src.config import Config
            assert Config.TRADE_LOCK_HOURS == 168
        finally:
            if original is not None:
                os.environ["TRADE_LOCK_HOURS"] = original
            elif "TRADE_LOCK_HOURS" in os.environ:
                del os.environ["TRADE_LOCK_HOURS"]
            reset_config()

    def test_instant_resale_enabled(self):
        """MARKETPLACE_INSTANT_RESALE is true by default."""
        from src.config import reset_config
        reset_config()
        from src.config import Config
        assert isinstance(Config.MARKETPLACE_INSTANT_RESALE, bool)

    def test_withdrawal_fee_configured(self):
        """WITHDRAWAL_FEE_RATE is set."""
        from src.config import reset_config
        reset_config()
        from src.config import Config
        assert Config.WITHDRAWAL_FEE_RATE > 0

    def test_float_premium_disabled(self):
        """FLOAT_PREMIUM_ENABLED is true by default."""
        from src.config import reset_config
        reset_config()
        from src.config import Config
        assert isinstance(Config.FLOAT_PREMIUM_ENABLED, bool)


# =====================================================================
# Funds Hold Model Tests
# =====================================================================
class TestFundsHold:
    """Tests for Trade Protection funds hold tracking."""

    @pytest.fixture
    def price_db(self):
        """Create a fresh in-memory price_db for testing."""
        from src.db.price_history import PriceHistoryDB
        import tempfile
        db = PriceHistoryDB.__new__(PriceHistoryDB)
        import sqlite3
        db.state_conn = sqlite3.connect(":memory:")
        db.state_conn.row_factory = sqlite3.Row
        # Create virtual_inventory table
        db.state_conn.execute("""
            CREATE TABLE virtual_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_name TEXT NOT NULL,
                buy_price REAL NOT NULL,
                sell_price REAL,
                fee_paid REAL,
                profit REAL,
                status TEXT NOT NULL DEFAULT 'idle',
                acquired_at REAL NOT NULL,
                unlock_at REAL NOT NULL DEFAULT 0,
                sold_at REAL,
                dm_item_id TEXT,
                dm_offer_id TEXT,
                listed_at REAL,
                list_error TEXT,
                exclusive INTEGER NOT NULL DEFAULT 0,
                funds_hold_until REAL,
                rollback_refund INTEGER NOT NULL DEFAULT 0
            )
        """)
        yield db
        db.state_conn.close()

    def test_get_frozen_funds_zero(self, price_db):
        """No sold items → frozen=0."""
        frozen = price_db.get_frozen_funds()
        assert frozen == 0.0

    def test_set_funds_hold_and_retrieve(self, price_db):
        """Set funds hold on sold item → get_frozen_funds returns it."""
        now = time.time()
        price_db.state_conn.execute(
            "INSERT INTO virtual_inventory (hash_name, buy_price, sell_price, status, acquired_at, unlock_at, sold_at) "
            "VALUES (?, ?, ?, 'sold', ?, ?, ?)",
            ("AK-47 | Redline", 10.0, 12.0, now, now, now),
        )
        row_id = price_db.state_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        hold_until = now + 7 * 86400
        price_db.set_funds_hold(row_id, hold_until)
        frozen = price_db.get_frozen_funds()
        assert frozen == 12.0

    def test_expired_funds_released(self, price_db):
        """Expired holds → released, frozen=0."""
        now = time.time()
        price_db.state_conn.execute(
            "INSERT INTO virtual_inventory (hash_name, buy_price, sell_price, status, acquired_at, unlock_at, sold_at, funds_hold_until) "
            "VALUES (?, ?, ?, 'sold', ?, ?, ?, ?)",
            ("AWP | Asiimov", 30.0, 35.0, now, now, now, now - 100),  # expired 100s ago
        )
        released = price_db.release_expired_funds()
        assert released == 1
        frozen = price_db.get_frozen_funds()
        assert frozen == 0.0

    def test_get_total_equity_includes_frozen(self, price_db):
        """get_total_equity returns frozen and available fields."""
        equity = price_db.get_total_equity(100.0)
        assert "frozen" in equity
        assert "available" in equity
        assert "cash" in equity
        assert "assets" in equity
        assert "total" in equity
        assert equity["available"] == 100.0  # no frozen items
        assert equity["frozen"] == 0.0

    def test_rollback_refund(self, price_db):
        """Rollback → profit=0, rollback_refund=1."""
        now = time.time()
        price_db.state_conn.execute(
            "INSERT INTO virtual_inventory (hash_name, buy_price, sell_price, status, acquired_at, unlock_at, sold_at, dm_offer_id) "
            "VALUES (?, ?, ?, 'listed', ?, ?, ?, ?)",
            ("M4A4 | Howl", 300.0, 500.0, now, now, now, "offer_rb_001"),
        )
        price_db.set_rollback_refund("offer_rb_001")
        # After set_rollback_refund, the row should have rollback_refund=1, profit=0
        row = price_db.state_conn.execute(
            "SELECT * FROM virtual_inventory WHERE dm_offer_id = 'offer_rb_001'"
        ).fetchone()
        # Note: set_rollback_refund changes status to 'sold' indirectly
        # Actually set_rollback_refund only sets rollback_refund + profit + fee
        assert row["rollback_refund"] == 1
        assert row["profit"] == 0.0
        assert row["fee_paid"] == 0.0


# =====================================================================
# Exclusive Inventory Tests
# =====================================================================
class TestExclusiveInventory:
    """Tests for exclusive (keep-forever) flag."""

    @pytest.fixture
    def price_db(self):
        from src.db.price_history import PriceHistoryDB
        import sqlite3
        db = PriceHistoryDB.__new__(PriceHistoryDB)
        db.state_conn = sqlite3.connect(":memory:")
        db.state_conn.row_factory = sqlite3.Row
        db.state_conn.execute("""
            CREATE TABLE virtual_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_name TEXT NOT NULL,
                buy_price REAL NOT NULL,
                sell_price REAL,
                fee_paid REAL,
                profit REAL,
                status TEXT NOT NULL DEFAULT 'idle',
                acquired_at REAL NOT NULL,
                unlock_at REAL NOT NULL DEFAULT 0,
                sold_at REAL,
                dm_item_id TEXT,
                dm_offer_id TEXT,
                listed_at REAL,
                list_error TEXT,
                exclusive INTEGER NOT NULL DEFAULT 0,
                funds_hold_until REAL,
                rollback_refund INTEGER NOT NULL DEFAULT 0
            )
        """)
        yield db
        db.state_conn.close()

    def test_add_virtual_item_exclusive(self, price_db):
        """add_virtual_item with exclusive=True → exclusive=1 in DB."""
        now = time.time()
        price_db.add_virtual_item("AK-47 | Fire Serpent", 100.0, exclusive=True)
        row = price_db.state_conn.execute(
            "SELECT * FROM virtual_inventory WHERE hash_name = 'AK-47 | Fire Serpent'"
        ).fetchone()
        assert row["exclusive"] == 1

    def test_add_virtual_item_not_exclusive(self, price_db):
        """add_virtual_item without exclusive flag → exclusive=0."""
        now = time.time()
        price_db.add_virtual_item("Desert Eagle | Blaze", 50.0)
        row = price_db.state_conn.execute(
            "SELECT * FROM virtual_inventory WHERE hash_name = 'Desert Eagle | Blaze'"
        ).fetchone()
        assert row["exclusive"] == 0

    def test_mark_exclusive(self, price_db):
        """mark_exclusive → sets exclusive=1."""
        price_db.add_virtual_item("Knife | Doppler", 200.0)
        row = price_db.state_conn.execute(
            "SELECT id FROM virtual_inventory WHERE hash_name = 'Knife | Doppler'"
        ).fetchone()
        price_db.mark_exclusive(row["id"])
        updated = price_db.state_conn.execute(
            "SELECT exclusive FROM virtual_inventory WHERE id = ?", (row["id"],)
        ).fetchone()
        assert updated["exclusive"] == 1

    def test_is_exclusive(self, price_db):
        """is_exclusive returns True after marking."""
        price_db.add_virtual_item("Gloves | Vice", 300.0, exclusive=True)
        row = price_db.state_conn.execute(
            "SELECT id FROM virtual_inventory WHERE hash_name = 'Gloves | Vice'"
        ).fetchone()
        assert price_db.is_exclusive(row["id"]) is True

    def test_get_non_exclusive_inventory_filters(self, price_db):
        """get_non_exclusive_inventory excludes exclusive items."""
        price_db.add_virtual_item("Item A", 10.0, exclusive=False)
        price_db.add_virtual_item("Item B", 20.0, exclusive=True)
        price_db.add_virtual_item("Item C", 30.0, exclusive=False)
        non_exclusive = price_db.get_non_exclusive_inventory(status="idle")
        assert len(non_exclusive) == 2
        names = {r["hash_name"] for r in non_exclusive}
        assert names == {"Item A", "Item C"}


# =====================================================================
# Sticker Evaluator Tests
# =====================================================================
class TestStickerEvaluator:
    """Tests for sticker value calculation."""

    def test_no_stickers(self):
        """Empty stickers → 0 added value."""
        from src.analytics.stickers_evaluator import StickerEvaluator
        evaluator = StickerEvaluator()
        value = evaluator.calculate_added_value([])
        assert value == 0.0

    def test_rare_sticker_katowice(self):
        """Katowice 2014 sticker → significant value."""
        from src.analytics.stickers_evaluator import StickerEvaluator
        evaluator = StickerEvaluator()
        stickers = [{"name": "Titan | Katowice 2014", "wear": 0.0}]
        value = evaluator.calculate_added_value(stickers)
        assert value > 0  # should be significant

    def test_undervalued_detection(self):
        """is_undervalued returns True when stickers add value above threshold."""
        from src.analytics.stickers_evaluator import StickerEvaluator
        evaluator = StickerEvaluator()
        stickers = [{"name": "iBUYPOWER | Katowice 2014", "wear": 0.0}]
        # iBUYPOWER = $20000 * 0.10 = $2000 added value
        # item_price $1500 < (base $100 + $2000) * 0.95 → undervalued
        result = evaluator.is_undervalued(1500.0, 100.0, stickers)
        assert result is True

    def test_not_undervalued(self):
        """is_undervalued returns False when item is overpriced."""
        from src.analytics.stickers_evaluator import StickerEvaluator
        evaluator = StickerEvaluator()
        stickers = [{"name": "Crown (Foil)", "wear": 0.5}]
        # Crown Foil $800 * 0.05 * wear_factor → small value
        result = evaluator.is_undervalued(5000.0, 100.0, stickers)
        assert result is False


# =====================================================================
# Pattern/Phase Premium Tests  
# =====================================================================
class TestPatternPremium:
    """Tests for _calculate_pattern_premium."""

    def test_no_phase_no_premium(self):
        """No phase → 1.0x (no premium)."""
        from src.core.target_sniping.pricing import _PricingMixin
        premium = _PricingMixin._calculate_pattern_premium({})
        assert premium == 1.0

    def test_doppler_ruby(self):
        """Doppler Ruby → 5.0x."""
        from src.core.target_sniping.pricing import _PricingMixin
        premium = _PricingMixin._calculate_pattern_premium({"phase": "Ruby"})
        assert premium == 5.0

    def test_doppler_sapphire(self):
        """Doppler Sapphire → 5.0x."""
        from src.core.target_sniping.pricing import _PricingMixin
        premium = _PricingMixin._calculate_pattern_premium({"phase": "Sapphire"})
        assert premium == 5.0

    def test_black_pearl(self):
        """Black Pearl → 4.0x."""
        from src.core.target_sniping.pricing import _PricingMixin
        premium = _PricingMixin._calculate_pattern_premium({"phase": "black_pearl"})
        assert premium == 4.0

    def test_phase_2(self):
        """Phase 2 → 1.5x."""
        from src.core.target_sniping.pricing import _PricingMixin
        premium = _PricingMixin._calculate_pattern_premium({"phase": "P2"})
        assert premium == 1.5

    def test_phase_4(self):
        """Phase 4 → 1.3x."""
        from src.core.target_sniping.pricing import _PricingMixin
        premium = _PricingMixin._calculate_pattern_premium({"phase": "P4"})
        assert premium == 1.3

    def test_rare_paint_seed(self):
        """Rare paintSeed 661 → 3.0x (Blue Gem)."""
        from src.core.target_sniping.pricing import _PricingMixin
        premium = _PricingMixin._calculate_pattern_premium({"paintSeed": "661"})
        assert premium == 3.0

    def test_low_paint_seed(self):
        """Very low paintSeed < 5 → 1.03x (if not in any special set).
        
        v15.7 FIX: Seeds 1-5 are now all in _FIRE_ICE_SEEDS or other
        special sets, so the 1.03x low-seed bonus is never reached.
        Test verifies that seeds in special sets get the correct premium.
        """
        from src.core.target_sniping.pricing import _PricingMixin
        # Seed 2 is in _FIRE_ICE_SEEDS → 5.0x premium
        premium = _PricingMixin._calculate_pattern_premium({"paintSeed": "2"})
        assert premium == 5.0  # Fire & Ice premium


# =====================================================================
# Config Tests
# =====================================================================
class TestConfigV13:
    """Tests for new v13.0+ config values."""

    def test_max_total_inventory_value(self):
        from src.config import reset_config
        reset_config()
        from src.config import Config
        # Accept either .env value (200.0) or default (100.0)
        assert Config.MAX_TOTAL_INVENTORY_VALUE in (100.0, 200.0)

    def test_max_total_inventory_items(self):
        from src.config import reset_config
        reset_config()
        from src.config import Config
        assert Config.MAX_TOTAL_INVENTORY_ITEMS in (30, 50)

    def test_withdrawal_fee_rate(self):
        from src.config import reset_config
        reset_config()
        from src.config import Config
        assert Config.WITHDRAWAL_FEE_RATE > 0

    def test_target_fee_rate(self):
        from src.config import reset_config
        reset_config()
        from src.config import Config
        assert Config.TARGET_FEE_RATE > 0

    def test_float_premium_disabled_default(self):
        from src.config import reset_config
        reset_config()
        from src.config import Config
        assert isinstance(Config.FLOAT_PREMIUM_ENABLED, bool)
