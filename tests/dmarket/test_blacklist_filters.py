"""Tests for blacklist_filters module.

Blacklist is an OBLIGATORY filter - items matching blacklist are NEVER purchased.
This protects agAlgonst unprofitable trades.
"""


from src.dmarket.blacklist_filters import (
    BLACKLIST_KEYWORDS,
    PATTERN_KEYWORDS,
    ItemBlacklistFilter,
    ItemLiquidityFilter,
    ItemQualityFilter,
)


class TestBlacklistKeywords:
    """Tests for BLACKLIST_KEYWORDS configuration."""

    def test_blacklist_keywords_not_empty(self):
        """Verify blacklist has keywords defined."""
        assert len(BLACKLIST_KEYWORDS) > 0

    def test_souvenir_in_blacklist(self):
        """Verify 'souvenir' is blacklisted (low liquidity)."""
        assert any("souvenir" in kw.lower() for kw in BLACKLIST_KEYWORDS)

    def test_sticker_in_blacklist(self):
        """Verify stickers are blacklisted (low profit)."""
        assert any("sticker" in kw.lower() for kw in BLACKLIST_KEYWORDS)

    def test_graffiti_in_blacklist(self):
        """Verify graffiti is blacklisted."""
        assert any("graffiti" in kw.lower() for kw in BLACKLIST_KEYWORDS)

    def test_music_kit_in_blacklist(self):
        """Verify music kits are blacklisted (niche market)."""
        assert any("music kit" in kw.lower() for kw in BLACKLIST_KEYWORDS)

    def test_patch_in_blacklist(self):
        """Verify patches are blacklisted."""
        assert any("patch" in kw.lower() for kw in BLACKLIST_KEYWORDS)


class TestPatternKeywords:
    """Tests for PATTERN_KEYWORDS configuration."""

    def test_pattern_keywords_not_empty(self):
        """Verify pattern keywords are defined."""
        assert len(PATTERN_KEYWORDS) > 0

    def test_katowice_2014_in_patterns(self):
        """Verify Katowice 2014 stickers are flagged (extreme prices)."""
        assert any("katowice" in kw.lower() for kw in PATTERN_KEYWORDS)

    def test_ibuypower_in_patterns(self):
        """Verify iBUYPOWER is flagged (price manipulation risk)."""
        assert any("ibuypower" in kw.lower() for kw in PATTERN_KEYWORDS)

    def test_titan_holo_in_patterns(self):
        """Verify Titan Holo is flagged."""
        assert any("titan" in kw.lower() for kw in PATTERN_KEYWORDS)


class TestItemBlacklistFilter:
    """Tests for ItemBlacklistFilter class."""

    def test_souvenir_item_is_blacklisted(self):
        """Verify souvenir items are blacklisted."""
        filter_ = ItemBlacklistFilter()
        item = {"title": "Souvenir M4A1-S | Knight (Factory New)"}
        assert filter_.is_blacklisted(item) is True

    def test_sticker_item_is_blacklisted(self):
        """Verify sticker items are blacklisted."""
        filter_ = ItemBlacklistFilter()
        item = {"title": "Sticker | NaVi (Holo) | Antwerp 2022"}
        assert filter_.is_blacklisted(item) is True

    def test_graffiti_item_is_blacklisted(self):
        """Verify graffiti items are blacklisted."""
        filter_ = ItemBlacklistFilter()
        item = {"title": "Sealed Graffiti | Noscope (Frog Green)"}
        assert filter_.is_blacklisted(item) is True

    def test_normal_skin_not_blacklisted(self):
        """Verify normal skins are NOT blacklisted."""
        filter_ = ItemBlacklistFilter()
        item = {"title": "AK-47 | Redline (Field-Tested)"}
        assert filter_.is_blacklisted(item) is False

    def test_case_not_blacklisted(self):
        """Verify cases are NOT blacklisted."""
        filter_ = ItemBlacklistFilter()
        item = {"title": "Kilowatt Case"}
        assert filter_.is_blacklisted(item) is False

    def test_keyword_filter_can_be_disabled(self):
        """Verify keyword filter can be disabled."""
        filter_ = ItemBlacklistFilter(enable_keyword_filter=False)
        item = {"title": "Souvenir M4A1-S | Knight (Factory New)"}
        # Without keyword filter, souvenir is not blacklisted by keywords
        # (but could still be blacklisted by other filters)
        assert filter_.is_blacklisted(item) is False

    def test_battle_scarred_low_profit_blacklisted(self):
        """Verify Battle-Scarred items with low profit are blacklisted."""
        filter_ = ItemBlacklistFilter(enable_float_filter=True)
        item = {
            "title": "AWP | Safari Mesh (Battle-Scarred)",
            "profit_percent": 5,  # Low profit
        }
        assert filter_.is_blacklisted(item) is True

    def test_battle_scarred_high_profit_not_blacklisted(self):
        """Verify Battle-Scarred items with high profit are NOT blacklisted."""
        filter_ = ItemBlacklistFilter(enable_float_filter=True)
        item = {
            "title": "AWP | Safari Mesh (Battle-Scarred)",
            "profit_percent": 25,  # High profit
        }
        assert filter_.is_blacklisted(item) is False

    def test_sticker_boosted_price_blacklisted(self):
        """Verify items with boosted sticker price are blacklisted."""
        filter_ = ItemBlacklistFilter(enable_sticker_boost_filter=True)
        item = {
            "title": "AK-47 | Redline (Field-Tested)",
            "extra": {"stickers": [{"name": "Some Sticker"}]},
            "price_is_boosted": True,
        }
        assert filter_.is_blacklisted(item) is True

    def test_pattern_filter_katowice_2014(self):
        """Verify Katowice 2014 items are blacklisted when pattern filter enabled."""
        filter_ = ItemBlacklistFilter(enable_pattern_filter=True)
        item = {"title": "AK-47 | Redline with Katowice 2014 sticker"}
        assert filter_.is_blacklisted(item) is True

    def test_pattern_filter_disabled_by_default(self):
        """Verify pattern filter is disabled by default."""
        filter_ = ItemBlacklistFilter()  # Default: enable_pattern_filter=False
        item = {"title": "AK-47 | Redline with Katowice 2014 sticker"}
        # Without pattern filter, this should not be blacklisted
        assert filter_.is_blacklisted(item) is False

    def test_case_insensitive_matching(self):
        """Verify blacklist matching is case insensitive."""
        filter_ = ItemBlacklistFilter()
        item = {"title": "SOUVENIR M4A1-S | Knight"}
        assert filter_.is_blacklisted(item) is True


class TestItemLiquidityFilter:
    """Tests for ItemLiquidityFilter class."""

    def test_low_sales_not_liquid(self):
        """Verify items with low sales are not liquid."""
        filter_ = ItemLiquidityFilter(min_sales_24h=3)
        item = {
            "title": "Test Item",
            "statistics": {"sales24h": 1},
        }
        assert filter_.is_liquid(item) is False

    def test_high_sales_is_liquid(self):
        """Verify items with high sales are liquid."""
        filter_ = ItemLiquidityFilter(min_sales_24h=3, min_avg_sales_per_day=0.3)
        item = {
            "title": "Test Item",
            "statistics": {"sales24h": 10, "avg_sales_per_day": 5.0},
        }
        assert filter_.is_liquid(item) is True

    def test_overpriced_item_not_liquid(self):
        """Verify overpriced items are not liquid."""
        filter_ = ItemLiquidityFilter(max_overprice_ratio=1.5)
        item = {
            "title": "Test Item",
            "statistics": {"sales24h": 10, "avg_sales_per_day": 5.0},
            "suggestedPrice": {"amount": 1000},
            "price": {"amount": 2000},  # 2x the suggested price
        }
        assert filter_.is_liquid(item) is False

    def test_fAlgorly_priced_item_is_liquid(self):
        """Verify fAlgorly priced items are liquid."""
        filter_ = ItemLiquidityFilter(max_overprice_ratio=1.5)
        item = {
            "title": "Test Item",
            "statistics": {"sales24h": 10, "avg_sales_per_day": 5.0},
            "suggestedPrice": {"amount": 1000},
            "price": {"amount": 1200},  # 1.2x - within threshold
        }
        assert filter_.is_liquid(item) is True


class TestItemQualityFilter:
    """Tests for ItemQualityFilter class (combined filter)."""

    def test_filter_removes_blacklisted_items(self):
        """Verify blacklisted items are filtered out."""
        filter_ = ItemQualityFilter()
        items = [
            {"title": "AK-47 | Redline (FT)", "statistics": {"sales24h": 10, "avg_sales_per_day": 5}},
            {"title": "Souvenir AWP | Dragon Lore", "statistics": {"sales24h": 10, "avg_sales_per_day": 5}},
            {"title": "M4A1-S | Hyper Beast (FN)", "statistics": {"sales24h": 10, "avg_sales_per_day": 5}},
        ]

        filtered = filter_.filter_items(items)

        # Souvenir should be filtered out
        assert len(filtered) == 2
        assert all("souvenir" not in item["title"].lower() for item in filtered)

    def test_filter_removes_illiquid_items(self):
        """Verify illiquid items are filtered out."""
        filter_ = ItemQualityFilter()
        items = [
            {"title": "AK-47 | Redline (FT)", "statistics": {"sales24h": 10, "avg_sales_per_day": 5}},
            {"title": "Rare Knife | Pattern", "statistics": {"sales24h": 0, "avg_sales_per_day": 0}},
        ]

        filtered = filter_.filter_items(items)

        # Illiquid item should be filtered out
        assert len(filtered) == 1
        assert filtered[0]["title"] == "AK-47 | Redline (FT)"

    def test_filter_keeps_good_items(self):
        """Verify good items pass through filter."""
        filter_ = ItemQualityFilter()
        items = [
            {"title": "AK-47 | Redline (FT)", "statistics": {"sales24h": 10, "avg_sales_per_day": 5}},
            {"title": "AWP | Asiimov (FT)", "statistics": {"sales24h": 20, "avg_sales_per_day": 8}},
            {"title": "M4A1-S | Hyper Beast (FN)", "statistics": {"sales24h": 15, "avg_sales_per_day": 6}},
        ]

        filtered = filter_.filter_items(items)

        # All good items should pass
        assert len(filtered) == 3

    def test_empty_list_returns_empty(self):
        """Verify empty input returns empty output."""
        filter_ = ItemQualityFilter()
        filtered = filter_.filter_items([])
        assert filtered == []


class TestBlacklistIsObligatory:
    """Tests to verify blacklist is OBLIGATORY (not optional like whitelist)."""

    def test_blacklist_always_filters(self):
        """Verify blacklist always filters items regardless of settings."""
        # Even with all optional filters disabled, keyword filter is enabled by default
        filter_ = ItemBlacklistFilter(
            enable_keyword_filter=True,  # This is the default and MUST stay True
            enable_float_filter=False,
            enable_sticker_boost_filter=False,
            enable_pattern_filter=False,
        )

        # Souvenir MUST be blacklisted
        item = {"title": "Souvenir M4A1-S | Knight"}
        assert filter_.is_blacklisted(item) is True

    def test_blacklist_protects_from_bad_trades(self):
        """Verify blacklist prevents known bad trades."""
        filter_ = ItemBlacklistFilter()

        # All these should be blacklisted - OBLIGATORY protection
        bad_items = [
            {"title": "Souvenir AWP | Dragon Lore"},
            {"title": "Sticker | Team Liquid (Holo)"},
            {"title": "Sealed Graffiti | Crown"},
            {"title": "Music Kit | Darude, Sandstorm"},
            {"title": "Patch | Howling Dawn"},
        ]

        for item in bad_items:
            assert filter_.is_blacklisted(item) is True, f"Should blacklist: {item['title']}"
