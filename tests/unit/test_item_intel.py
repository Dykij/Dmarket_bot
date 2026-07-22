"""Tests for item_intel.py — Enhanced item intelligence."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.core.item_intel import _ItemIntelMixin


def _make_intel():
    """Create a mock with key methods properly wired to real implementations."""
    m = MagicMock(spec=_ItemIntelMixin)
    m.categorize_item = lambda title: _ItemIntelMixin.categorize_item(m, title)
    m.extract_base_skin = staticmethod(_ItemIntelMixin.extract_base_skin)
    m.extract_dmarket_markers = lambda item: _ItemIntelMixin.extract_dmarket_markers(m, item)
    m.get_family_holdings_count = lambda title: _ItemIntelMixin.get_family_holdings_count(m, title)
    m._analytics_engine = None
    return m


class TestCategorizeItem:

    def test_rifle_ak47(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "AK-47 | Redline") == "rifle"

    def test_rifle_awp(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "AWP | Dragon Lore") == "rifle"

    def test_smg_p90(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "P90 | Asiimov") == "smg"

    def test_pistol_deagle(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "Desert Eagle | Blaze") == "pistol"

    def test_knife_star(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "★ Karambit | Doppler") == "knife"

    def test_knife_word(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "Butterfly Knife | Fade") == "knife"

    def test_gloves(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "Sport Gloves | Hedge Maze") == "gloves"

    def test_sticker(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "Sticker | Katowice 2014") == "sticker"

    def test_case(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "Operation Breakout Case") == "case"

    def test_graffiti(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "Graffiti | Skull") == "graffiti"

    def test_other(self):
        assert _ItemIntelMixin.categorize_item(_make_intel(), "Music Kit | High Noon") == "other"

    def test_disabled_returns_other(self):
        with patch("src.core.item_intel.USE_CATEGORY_FILTER", False):
            assert _ItemIntelMixin.categorize_item(_make_intel(), "AK-47 | Redline") == "other"


class TestGetCategoryRiskMultiplier:

    def test_rifle(self):
        assert _ItemIntelMixin.get_category_risk_multiplier(_make_intel(), "AK-47 | Redline") == 1.0

    def test_knife(self):
        assert _ItemIntelMixin.get_category_risk_multiplier(_make_intel(), "★ Karambit") == 0.5

    def test_sticker(self):
        assert _ItemIntelMixin.get_category_risk_multiplier(_make_intel(), "Sticker | Test") == 0.3

    def test_graffiti(self):
        assert _ItemIntelMixin.get_category_risk_multiplier(_make_intel(), "Graffiti | Skull") == 0.0

    def test_case(self):
        assert _ItemIntelMixin.get_category_risk_multiplier(_make_intel(), "Case | Test") == 0.7

    def test_heavy(self):
        assert _ItemIntelMixin.get_category_risk_multiplier(_make_intel(), "MAG-7 | Heat") == 0.85

    def test_smg(self):
        assert _ItemIntelMixin.get_category_risk_multiplier(_make_intel(), "MP9 | Hot Rod") == 0.9

    def test_pistol(self):
        assert _ItemIntelMixin.get_category_risk_multiplier(_make_intel(), "Glock-18 | Fade") == 0.95

    def test_gloves(self):
        assert _ItemIntelMixin.get_category_risk_multiplier(_make_intel(), "Driver Gloves") == 0.5


class TestIsBlockedCategory:

    def test_graffiti_blocked(self):
        assert _ItemIntelMixin.is_blocked_category(_make_intel(), "Graffiti | Skull") is True

    def test_rifle_not_blocked(self):
        assert _ItemIntelMixin.is_blocked_category(_make_intel(), "AK-47 | Redline") is False


class TestExtractBaseSkin:

    def test_with_full_wear(self):
        assert _ItemIntelMixin.extract_base_skin("AK-47 | Redline (Field-Tested)") == "AK-47 | Redline"

    def test_factory_new(self):
        assert _ItemIntelMixin.extract_base_skin("★ Karambit | Doppler (Factory New)") == "★ Karambit | Doppler"

    def test_without_wear(self):
        assert _ItemIntelMixin.extract_base_skin("AK-47 | Redline") == "AK-47 | Redline"

    def test_short_wear(self):
        assert _ItemIntelMixin.extract_base_skin("AK-47 | Redline (FN)") == "AK-47 | Redline"

    def test_no_space_wear(self):
        assert _ItemIntelMixin.extract_base_skin("AK-47 | Redline(FT)") == "AK-47 | Redline"

    def test_minimal_wear(self):
        assert _ItemIntelMixin.extract_base_skin("M4A4 | Asiimov (Minimal Wear)") == "M4A4 | Asiimov"

    def test_battle_scarred(self):
        assert _ItemIntelMixin.extract_base_skin("AK-47 | Case Hardened (Battle-Scarred)") == "AK-47 | Case Hardened"


class TestExtractDMarketMarkers:

    def test_empty_item(self):
        markers = _ItemIntelMixin.extract_dmarket_markers(_make_intel(), {})
        # Empty item still extracts default values from extra/suggestedPrice/instantPrice
        assert markers.get("is_new") is False
        assert markers.get("tag_name") == ""
        assert markers.get("suggested_price_usd") == 0.0

    def test_discount(self):
        markers = _ItemIntelMixin.extract_dmarket_markers(_make_intel(), {"discount": "15"})
        assert markers["discount_pct"] == 15.0

    def test_suggested_price(self):
        markers = _ItemIntelMixin.extract_dmarket_markers(_make_intel(), {"suggestedPrice": {"USD": "1500"}})
        assert markers["suggested_price_usd"] == 15.0

    def test_instant_price(self):
        markers = _ItemIntelMixin.extract_dmarket_markers(_make_intel(), {"instantPrice": {"USD": "2000"}})
        assert markers["instant_price_usd"] == 20.0

    def test_extra_markers(self):
        item = {"extra": {"isNew": True, "tagName": "Best Price", "tradeLock": False, "withdrawable": True}}
        markers = _ItemIntelMixin.extract_dmarket_markers(_make_intel(), item)
        assert markers["is_new"] is True
        assert markers["tag_name"] == "Best Price"
        assert markers["trade_locked"] is False
        assert markers["withdrawable"] is True

    def test_invalid_discount(self):
        markers = _ItemIntelMixin.extract_dmarket_markers(_make_intel(), {"discount": "abc"})
        assert "discount_pct" not in markers


class TestIsDiscountedDeal:

    def test_disabled(self):
        with patch("src.core.item_intel.USE_DISCOUNT_FILTER", False):
            assert _ItemIntelMixin.is_discounted_deal(_make_intel(), {}, 10.0) is False

    def test_high_discount(self):
        item = {"discount": "20"}
        assert _ItemIntelMixin.is_discounted_deal(_make_intel(), item, 10.0) is True

    def test_below_suggested(self):
        item = {"suggestedPrice": {"USD": "2000"}}  # $20 suggested
        assert _ItemIntelMixin.is_discounted_deal(_make_intel(), item, 15.0) is True  # $15 < $20 * 0.9

    def test_best_price_tag(self):
        item = {"extra": {"tagName": "Best Price"}}
        assert _ItemIntelMixin.is_discounted_deal(_make_intel(), item, 10.0) is True

    def test_cheapest_tag(self):
        item = {"extra": {"tagName": "cheapest"}}
        assert _ItemIntelMixin.is_discounted_deal(_make_intel(), item, 10.0) is True

    def test_no_discount(self):
        item = {"discount": "5"}  # below threshold
        assert _ItemIntelMixin.is_discounted_deal(_make_intel(), item, 10.0) is False


class TestGetMarkerBonus:

    def test_disabled(self):
        with patch("src.core.item_intel.USE_DISCOUNT_FILTER", False):
            assert _ItemIntelMixin.get_marker_bonus(_make_intel(), {}) == 1.0

    def test_high_discount_bonus(self):
        item = {"discount": "35"}
        bonus = _ItemIntelMixin.get_marker_bonus(_make_intel(), item)
        assert bonus >= 1.15

    def test_medium_discount_bonus(self):
        item = {"discount": "25"}
        bonus = _ItemIntelMixin.get_marker_bonus(_make_intel(), item)
        assert bonus >= 1.10

    def test_low_discount_bonus(self):
        item = {"discount": "15"}
        bonus = _ItemIntelMixin.get_marker_bonus(_make_intel(), item)
        assert bonus >= 1.05

    def test_new_listing_bonus(self):
        item = {"extra": {"isNew": True}}
        bonus = _ItemIntelMixin.get_marker_bonus(_make_intel(), item)
        assert bonus >= 1.05

    def test_best_price_bonus(self):
        item = {"extra": {"tagName": "best price"}}
        bonus = _ItemIntelMixin.get_marker_bonus(_make_intel(), item)
        assert bonus >= 1.10

    def test_capped_at_130(self):
        item = {"discount": "50", "extra": {"isNew": True, "tagName": "best"}}
        bonus = _ItemIntelMixin.get_marker_bonus(_make_intel(), item)
        assert bonus <= 1.30

    def test_no_markers(self):
        bonus = _ItemIntelMixin.get_marker_bonus(_make_intel(), {})
        assert bonus == 1.0


class TestGetFamilyHoldingsCount:

    def test_disabled(self):
        with patch("src.core.item_intel.USE_CROSS_WEAR_GUARD", False):
            assert _ItemIntelMixin.get_family_holdings_count(_make_intel(), "AK-47 | Redline") == 0

    def test_counts_same_family(self):
        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_virtual_inventory.side_effect = [
                [{"hash_name": "AK-47 | Redline (FT)"}],  # idle
                [{"hash_name": "AK-47 | Redline (MW)"}],  # selling
                [],  # listed
            ]
            count = _ItemIntelMixin.get_family_holdings_count(_make_intel(), "AK-47 | Redline (FN)")
        assert count == 2

    def test_different_family_not_counted(self):
        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_virtual_inventory.side_effect = [
                [{"hash_name": "M4A4 | Asiimov (FT)"}],  # idle
                [],  # selling
                [],  # listed
            ]
            count = _ItemIntelMixin.get_family_holdings_count(_make_intel(), "AK-47 | Redline (FN)")
        assert count == 0


class TestIsFamilySaturated:

    def test_disabled(self):
        with patch("src.core.item_intel.USE_CROSS_WEAR_GUARD", False):
            assert _ItemIntelMixin.is_family_saturated(_make_intel(), "AK-47 | Redline") is False

    def test_saturated(self):
        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_virtual_inventory.side_effect = [
                [{"hash_name": "AK-47 | Redline (FT)"}] * 3,  # idle
                [],  # selling
                [],  # listed
            ]
            assert _ItemIntelMixin.is_family_saturated(_make_intel(), "AK-47 | Redline (FN)", max_family=3) is True

    def test_not_saturated(self):
        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_virtual_inventory.side_effect = [
                [{"hash_name": "AK-47 | Redline (FT)"}],  # idle
                [],  # selling
                [],  # listed
            ]
            assert _ItemIntelMixin.is_family_saturated(_make_intel(), "AK-47 | Redline (FN)", max_family=3) is False


class TestCheckEventRisk:

    def test_safe(self):
        with patch("src.core.event_shield.event_shield") as mock_shield:
            mock_shield.is_category_risky.return_value = False
            assert _ItemIntelMixin.check_event_risk("AK-47 | Redline") is None

    def test_risky(self):
        with patch("src.core.event_shield.event_shield") as mock_shield:
            mock_shield.is_category_risky.return_value = True
            result = _ItemIntelMixin.check_event_risk("Case | Test")
            assert result is not None
            assert "event_shield" in result


class TestGetEventOpportunityMultiplier:

    def test_normal(self):
        with patch("src.core.event_shield.event_shield") as mock_shield:
            mock_shield.is_opportunity_mode.return_value = False
            assert _ItemIntelMixin.get_event_opportunity_multiplier() == 1.0

    def test_opportunity(self):
        with patch("src.core.event_shield.event_shield") as mock_shield:
            mock_shield.is_opportunity_mode.return_value = True
            assert _ItemIntelMixin.get_event_opportunity_multiplier() == 0.70


class TestComputeTechnicalScore:

    def test_ensure_analytics_creates_engine(self):
        """_ensure_analytics creates PriceAnalytics if None (lines 83-85)."""
        m = _make_intel()
        assert m._analytics_engine is None
        with patch("src.analytics.price_analytics.PriceAnalytics") as mock_cls:
            mock_cls.return_value = MagicMock()
            _ItemIntelMixin._ensure_analytics(m)
        assert m._analytics_engine is not None

    def test_ensure_analytics_preserves_existing(self):
        """_ensure_analytics preserves existing engine."""
        m = _make_intel()
        existing = MagicMock()
        m._analytics_engine = existing
        _ItemIntelMixin._ensure_analytics(m)
        assert m._analytics_engine is existing

    def test_insufficient_data_returns_neutral(self):
        """< 15 prices returns neutral score (lines 103-104)."""
        m = _make_intel()
        m._analytics_engine = MagicMock()
        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 5  # only 5
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 10.0)
        assert score == 0.5
        assert desc == "insufficient_data"

    def test_rsi_oversold_boost(self):
        """RSI oversold gives +0.20 boost (lines 120-122)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        rsi = MagicMock()
        rsi.is_oversold = True
        rsi.is_overbought = False
        rsi.value = 20.0
        mock_analysis.rsi = rsi
        mock_analysis.macd = None
        mock_analysis.bollinger = None
        mock_analysis.trend = None
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 10.0)
        assert score > 0.5
        assert "RSI_oversold" in desc

    def test_rsi_overbought_penalty(self):
        """RSI overbought gives -0.15 penalty (lines 123-125)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        rsi = MagicMock()
        rsi.is_oversold = False
        rsi.is_overbought = True
        rsi.value = 80.0
        mock_analysis.rsi = rsi
        mock_analysis.macd = None
        mock_analysis.bollinger = None
        mock_analysis.trend = None
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 10.0)
        assert score < 0.5
        assert "RSI_overbought" in desc

    def test_rsi_neutral(self):
        """RSI neutral shows value (lines 126-127)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        rsi = MagicMock()
        rsi.is_oversold = False
        rsi.is_overbought = False
        rsi.value = 50.0
        mock_analysis.rsi = rsi
        mock_analysis.macd = None
        mock_analysis.bollinger = None
        mock_analysis.trend = None
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 10.0)
        assert score == 0.5
        assert "RSI(50)" in desc

    def test_macd_bullish_boost(self):
        """MACD bullish crossover gives +0.15 (lines 132-134)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        mock_analysis.rsi = None
        macd = MagicMock()
        macd.is_bullish_crossover = True
        macd.is_bearish_crossover = False
        mock_analysis.macd = macd
        mock_analysis.bollinger = None
        mock_analysis.trend = None
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 10.0)
        assert score > 0.5
        assert "MACD_bullish_x" in desc

    def test_macd_bearish_penalty(self):
        """MACD bearish crossover gives -0.15 (lines 135-137)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        mock_analysis.rsi = None
        macd = MagicMock()
        macd.is_bullish_crossover = False
        macd.is_bearish_crossover = True
        mock_analysis.macd = macd
        mock_analysis.bollinger = None
        mock_analysis.trend = None
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 10.0)
        assert score < 0.5
        assert "MACD_bearish_x" in desc

    def test_bollinger_lower_band_boost(self):
        """Price near lower Bollinger band gives +0.15 (lines 143-145)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        mock_analysis.rsi = None
        mock_analysis.macd = None
        bb = MagicMock()
        bb.upper = 15.0
        bb.lower = 8.0
        mock_analysis.bollinger = bb
        mock_analysis.trend = None
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            # current_price=8.0 <= bb.lower * 1.05 = 8.4
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 8.0)
        assert score > 0.5
        assert "BB_lower" in desc

    def test_bollinger_upper_band_penalty(self):
        """Price near upper Bollinger band gives -0.10 (lines 146-148)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        mock_analysis.rsi = None
        mock_analysis.macd = None
        bb = MagicMock()
        bb.upper = 15.0
        bb.lower = 8.0
        mock_analysis.bollinger = bb
        mock_analysis.trend = None
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            # current_price=15.0 >= bb.upper * 0.95 = 14.25
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 15.0)
        assert score < 0.5
        assert "BB_upper" in desc

    def test_trend_bullish_boost(self):
        """Bullish trend gives +0.05 (lines 154-156)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        mock_analysis.rsi = None
        mock_analysis.macd = None
        mock_analysis.bollinger = None
        trend = MagicMock()
        trend.direction = MagicMock()
        mock_analysis.trend = trend
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with (
            patch("src.core.item_intel.price_db") as mock_db,
            patch("src.analytics.price_analytics.Trend") as mock_trend,
        ):
            mock_trend.BULLISH = "bullish"
            mock_trend.BEARISH = "bearish"
            trend.direction = "bullish"
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 10.0)
        assert score > 0.5
        assert "trend_up" in desc

    def test_trend_bearish_penalty(self):
        """Bearish trend gives -0.10 (lines 157-159)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        mock_analysis.rsi = None
        mock_analysis.macd = None
        mock_analysis.bollinger = None
        trend = MagicMock()
        mock_analysis.trend = trend
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with (
            patch("src.core.item_intel.price_db") as mock_db,
            patch("src.analytics.price_analytics.Trend") as mock_trend,
        ):
            mock_trend.BULLISH = "bullish"
            mock_trend.BEARISH = "bearish"
            trend.direction = "bearish"
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 10.0)
        assert score < 0.5
        assert "trend_down" in desc

    def test_no_analysis_data_returns_neutral(self):
        """No RSI/MACD/Bollinger/Trend returns neutral (lines 114-162)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        mock_analysis.rsi = None
        mock_analysis.macd = None
        mock_analysis.bollinger = None
        mock_analysis.trend = None
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with patch("src.core.item_intel.price_db") as mock_db:
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 10.0)
        assert score == 0.5
        assert desc == "no_data"

    def test_score_clamped_0_to_1(self):
        """Score is clamped to [0.0, 1.0] (line 161)."""
        m = _make_intel()
        mock_analysis = MagicMock()
        rsi = MagicMock()
        rsi.is_oversold = True
        rsi.is_overbought = False
        rsi.value = 10.0
        mock_analysis.rsi = rsi
        macd = MagicMock()
        macd.is_bullish_crossover = True
        macd.is_bearish_crossover = False
        mock_analysis.macd = macd
        bb = MagicMock()
        bb.upper = 20.0
        bb.lower = 5.0
        mock_analysis.bollinger = bb
        trend = MagicMock()
        mock_analysis.trend = trend
        m._analytics_engine = MagicMock()
        m._analytics_engine.analyze_item.return_value = mock_analysis

        with (
            patch("src.core.item_intel.price_db") as mock_db,
            patch("src.analytics.price_analytics.Trend") as mock_trend,
        ):
            mock_trend.BULLISH = "bullish"
            trend.direction = "bullish"
            mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
            # price=5.0 near lower BB → +0.15, RSI oversold → +0.20, MACD bullish → +0.15, trend → +0.05
            score, desc = _ItemIntelMixin.compute_technical_score(m, "AK-47", 5.0)
        assert 0.0 <= score <= 1.0
