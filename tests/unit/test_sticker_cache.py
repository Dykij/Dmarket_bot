"""Tests for sticker_cache.py — sticker rejection + premium cache."""

from __future__ import annotations

from src.core.target_sniping.sticker_cache import StickerPremiumCache


class TestShouldRejectByStickers:

    def test_empty_stickers(self):
        cache = StickerPremiumCache()
        assert cache.should_reject_by_stickers([]) is False

    def test_no_stickers(self):
        cache = StickerPremiumCache()
        assert cache.should_reject_by_stickers([]) is False

    def test_luxury_katowice_2014(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "iBUYPOWER | Katowice 2014"}]
        assert cache.should_reject_by_stickers(stickers) is True

    def test_luxury_crown_foil(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Crown (Foil)"}]
        assert cache.should_reject_by_stickers(stickers) is True

    def test_luxury_titan(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Titan | Katowice 2014"}]
        assert cache.should_reject_by_stickers(stickers) is True

    def test_luxury_souvenir_early_major(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Souvenir | Katowice 2014"}]
        assert cache.should_reject_by_stickers(stickers) is True

    def test_luxury_2014_holo(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Fnatic (Holo) 2014"}]
        assert cache.should_reject_by_stickers(stickers) is True

    def test_normal_sticker_passes(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Natus Vincere | Stockholm 2021"}]
        assert cache.should_reject_by_stickers(stickers) is False

    def test_empty_name_skipped(self):
        cache = StickerPremiumCache()
        stickers = [{"name": ""}, {"name": "Normal Sticker"}]
        assert cache.should_reject_by_stickers(stickers) is False

    def test_cache_hit(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "iBUYPOWER | Katowice 2014"}]
        # First call populates cache
        cache.should_reject_by_stickers(stickers)
        # Second call uses cache
        assert cache.should_reject_by_stickers(stickers) is True


class TestCalculatePremiumMultiplier:

    def test_empty_stickers(self):
        cache = StickerPremiumCache()
        assert cache.calculate_premium_multiplier([], 10.0) == 1.0

    def test_luxury_returns_one(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "iBUYPOWER | Katowice 2014"}]
        assert cache.calculate_premium_multiplier(stickers, 10.0) == 1.0

    def test_souvenir_premium(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Souvenir | Copenhagen 2024"}]
        result = cache.calculate_premium_multiplier(stickers, 10.0)
        assert result > 1.0
        assert result <= 1.30

    def test_holo_premium(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Team (Holo) | Antwerp 2022"}]
        result = cache.calculate_premium_multiplier(stickers, 10.0)
        assert result > 1.0

    def test_gold_premium(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Player (Gold) | Rio 2022"}]
        result = cache.calculate_premium_multiplier(stickers, 10.0)
        assert result > 1.0

    def test_4x_combo_bonus(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Team (Holo) | Antwerp 2022"}] * 4
        result = cache.calculate_premium_multiplier(stickers, 10.0)
        # Should have combo bonus
        single = cache.calculate_premium_multiplier([stickers[0]], 10.0)
        assert result > single

    def test_capped_at_130(self):
        cache = StickerPremiumCache()
        # Even with many stickers, cap at 1.30
        stickers = [{"name": "Souvenir | Copenhagen 2024 (Gold)"}] * 4
        result = cache.calculate_premium_multiplier(stickers, 10.0)
        assert result <= 1.30

    def test_no_premium_normal_sticker(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Some Normal Sticker 2023"}]
        result = cache.calculate_premium_multiplier(stickers, 10.0)
        # Year 2023 → +3% minimum
        assert result >= 1.0


class TestGetRankingBoost:

    def test_empty_stickers(self):
        cache = StickerPremiumCache()
        assert cache.get_ranking_boost([]) == 0.0

    def test_luxury_returns_zero(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "iBUYPOWER | Katowice 2014"}]
        assert cache.get_ranking_boost(stickers) == 0.0

    def test_normal_sticker_boost(self):
        cache = StickerPremiumCache()
        stickers = [{"name": "Team (Holo) | Copenhagen 2024"}]
        boost = cache.get_ranking_boost(stickers)
        assert 0.0 < boost <= 1.0

    def test_higher_premium_higher_boost(self):
        cache = StickerPremiumCache()
        basic = [{"name": "Team | Stockholm 2021"}]
        holo = [{"name": "Team (Holo) | Copenhagen 2024"}]
        basic_boost = cache.get_ranking_boost(basic)
        holo_boost = cache.get_ranking_boost(holo)
        assert holo_boost >= basic_boost


class TestCacheManagement:

    def test_clear_cache(self):
        cache = StickerPremiumCache()
        cache._premium_cache["test"] = 0.1
        cache._rejection_cache["test"] = True
        cache.clear_cache()
        assert len(cache._premium_cache) == 0
        assert len(cache._rejection_cache) == 0

    def test_cache_stats(self):
        cache = StickerPremiumCache()
        stats = cache.cache_stats
        assert "premium_entries" in stats
        assert "rejection_entries" in stats
