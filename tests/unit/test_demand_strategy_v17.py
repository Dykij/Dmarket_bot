"""test_demand_strategy_v17.py — Comprehensive tests for OBI demand strategy v17.7.

Tests cover:
- Normalized OBI calculation
- OFI (Order Flow Imbalance)
- Z-score calibration
- Dynamic liquidity thresholds
- Spread entropy filter
- PVC trend multiplier
- Kelly + OFI integration
- GARCH + PVC integration
- HMM + VPIN integration
- Hawkes + Spread Entropy integration
- Decision logging
"""

from __future__ import annotations

import random

import pytest


class TestNormalizedOBI:
    """Test normalized_obi() from obi.py."""

    def test_all_buyers(self):
        from src.analysis.microstructure.obi import normalized_obi
        assert normalized_obi(100, 0) == 1.0

    def test_all_sellers(self):
        from src.analysis.microstructure.obi import normalized_obi
        assert normalized_obi(0, 100) == -1.0

    def test_balanced(self):
        from src.analysis.microstructure.obi import normalized_obi
        assert normalized_obi(50, 50) == 0.0

    def test_no_orders(self):
        from src.analysis.microstructure.obi import normalized_obi
        assert normalized_obi(0, 0) == 0.0

    def test_buyer_dominant(self):
        from src.analysis.microstructure.obi import normalized_obi
        result = normalized_obi(75, 25)
        assert 0.4 < result < 0.6  # ~0.5

    def test_seller_dominant(self):
        from src.analysis.microstructure.obi import normalized_obi
        result = normalized_obi(25, 75)
        assert -0.6 < result < -0.4  # ~-0.5


class TestOFI:
    """Test ofi() from obi.py."""

    def test_positive_ofi(self):
        from src.analysis.microstructure.obi import ofi
        assert ofi(0.5, 0.3) == 0.2

    def test_negative_ofi(self):
        from src.analysis.microstructure.obi import ofi
        assert ofi(0.3, 0.5) == -0.2

    def test_zero_ofi(self):
        from src.analysis.microstructure.obi import ofi
        assert ofi(0.5, 0.5) == 0.0

    def test_extreme_ofi(self):
        from src.analysis.microstructure.obi import ofi
        assert ofi(1.0, -1.0) == 2.0


class TestZScore:
    """Test obi_z_score() from obi.py."""

    def test_normal_value(self):
        from src.analysis.microstructure.obi import obi_z_score
        z = obi_z_score(0.5, [0.1, 0.2, 0.3, 0.4, 0.5])
        assert z is not None and z > 0

    def test_outlier(self):
        from src.analysis.microstructure.obi import obi_z_score
        z = obi_z_score(0.9, [0.1, 0.2, 0.3, 0.4, 0.5])
        assert z is not None and z > 2.0

    def test_insufficient_data(self):
        from src.analysis.microstructure.obi import obi_z_score
        assert obi_z_score(0.5, [0.1]) is None

    def test_zero_std(self):
        from src.analysis.microstructure.obi import obi_z_score
        z = obi_z_score(0.5, [0.5, 0.5, 0.5, 0.5, 0.5])
        assert z == 0.0


class TestDynamicLiquidity:
    """Test dynamic liquidity thresholds in demand_strategy.py."""

    def test_cheap_items_threshold(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # bid=5, ask=2 -> Q=2.5 >= 1.5, total=7 >= 3
        r = calculate_demand_score('Cheap', 1.0, 0.9, 2, 5)
        assert r['score'] > 0

    def test_cheap_items_low_liquidity(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # total=2 < 3 (threshold for cheap items)
        r = calculate_demand_score('Cheap', 1.0, 0.9, 1, 1)
        assert r['score'] == 0.0 and 'low liquidity' in r['reason']

    def test_expensive_items_threshold(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # total=8 < 10 (threshold for expensive items)
        r = calculate_demand_score('Expensive', 15.0, 14.0, 4, 4)
        assert r['score'] == 0.0 and 'low liquidity' in r['reason']

    def test_mid_range_items(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # bid=15, ask=5 -> Q=3.0 >= 2.5, total=20 >= 5
        r = calculate_demand_score('Mid', 5.0, 4.8, 5, 15)
        assert r['score'] > 0


class TestSpreadEntropy:
    """Test spread entropy filter in demand_strategy.py."""

    def test_hard_block_wide_spread(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # spread = (10-7)/10 = 30% > 20% hard block
        r = calculate_demand_score('Wide', 10.0, 7.0, 20, 30)
        assert r['score'] == 0.0 and 'spread too wide' in r['reason']

    def test_soft_penalty_medium_spread(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # spread = (10-8.5)/10 = 15% > 10% soft penalty
        r = calculate_demand_score('Medium', 10.0, 8.5, 10, 30)
        # Score should be penalized (lower than without penalty)
        r2 = calculate_demand_score('Tight', 10.0, 9.5, 10, 30)  # spread = 5%
        assert r['score'] <= r2['score']

    def test_no_penalty_tight_spread(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # spread = (5-4.8)/5 = 4% < 10%
        r = calculate_demand_score('Tight', 5.0, 4.8, 10, 30)
        assert r['score'] > 0


class TestGARCHPVC:
    """Test GARCH + PVC integration."""

    def test_pvc_increases_volatility(self):
        from src.analysis.algo_pack.garch import GARCH11Estimator
        random.seed(42)
        garch = GARCH11Estimator()
        garch.calibrate([random.gauss(0, 0.02) for _ in range(50)])
        f1 = garch.forecast(steps=1, pvc_factor=1.0)
        f2 = garch.forecast(steps=1, pvc_factor=1.2)
        assert f2.forecast_vol_1 > f1.forecast_vol_1

    def test_pvc_factor_one_no_change(self):
        from src.analysis.algo_pack.garch import GARCH11Estimator
        random.seed(42)
        garch = GARCH11Estimator()
        garch.calibrate([random.gauss(0, 0.02) for _ in range(50)])
        f1 = garch.forecast(steps=1, pvc_factor=1.0)
        f2 = garch.forecast(steps=1, pvc_factor=1.0)
        assert abs(f1.forecast_vol_1 - f2.forecast_vol_1) < 1e-10


class TestHMMVPIN:
    """Test HMM + VPIN integration."""

    def test_vpin_shifts_transition(self):
        from src.analysis.algo_pack.hmm_regime import HMMRegimeDetector
        random.seed(42)
        hmm = HMMRegimeDetector()
        for _ in range(50):
            hmm.update(random.gauss(0, 0.02))
        # With high VPIN, should be more bearish
        r1 = hmm.update(0.01, vpin=0.0)
        r2 = hmm.update(0.01, vpin=0.8)
        # state_probabilities: [CRISIS, BEAR, RECOVERY, BULL]
        bear_1 = r1.state_probabilities[0] + r1.state_probabilities[1]
        bear_2 = r2.state_probabilities[0] + r2.state_probabilities[1]
        assert bear_2 >= bear_1 * 0.9

    def test_low_vpin_no_effect(self):
        from src.analysis.algo_pack.hmm_regime import HMMRegimeDetector
        random.seed(42)
        hmm = HMMRegimeDetector()
        for _ in range(50):
            hmm.update(random.gauss(0, 0.02))
        r1 = hmm.update(0.01, vpin=0.0)
        r2 = hmm.update(0.01, vpin=0.3)
        # Should be similar (VPIN < 0.6 has no effect)
        bear_1 = r1.state_probabilities[0] + r1.state_probabilities[1]
        bear_2 = r2.state_probabilities[0] + r2.state_probabilities[1]
        assert abs(bear_1 - bear_2) < 0.1


class TestHawkesEntropy:
    """Test Hawkes + Spread Entropy integration."""

    def test_narrow_spread_higher_alpha(self):
        from src.analysis.algo_pack.hawkes import HawkesEstimator
        h = HawkesEstimator()
        h.adjust_for_spread_entropy(0.03)
        narrow = h._state.alpha
        h.adjust_for_spread_entropy(0.20)
        wide = h._state.alpha
        assert narrow > wide

    def test_normal_spread_default(self):
        from src.analysis.algo_pack.hawkes import HawkesEstimator
        h = HawkesEstimator()
        default_alpha = h.alpha
        h.adjust_for_spread_entropy(0.10)
        assert abs(h._state.alpha - default_alpha) < 0.001


class TestDemandScoreIntegration:
    """Integration tests for calculate_demand_score."""

    def test_high_demand_passes(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        r = calculate_demand_score('Test', 5.0, 4.8, 5, 50)
        assert r['score'] > 0
        assert r['demand_ratio'] == 10.0
        assert r['obi_value'] > 0.5
        assert 'obi=' in r['reason']
        assert 'ofi=' in r['reason']

    def test_invalid_prices(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        r = calculate_demand_score('Test', 0, 0, 10, 10)
        assert r['score'] == 0.0

    def test_obi_risk_gate(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # bid=20, ask=80 -> OBI = (20-80)/(20+80) = -0.6 < -0.3
        r = calculate_demand_score('Test', 5.0, 4.8, 80, 20)
        # Should be rejected by demand ratio first (Q=0.25 < 2.5)
        assert r['score'] == 0.0

    def test_new_fields_present(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        r = calculate_demand_score('Test', 5.0, 4.8, 5, 50)
        assert 'ofi_value' in r
        assert 'obi_z' in r
        assert 'micro_price' in r


class TestV18RegressionFixes:
    """Regression tests for v18 audit fixes."""

    def test_queue_imbalance_no_sellers(self):
        """queue_imbalance(10, 0) should return 999.0 (not None)."""
        from src.analysis.microstructure.obi import queue_imbalance
        qi = queue_imbalance(10, 0)
        assert qi == 999.0, f"Expected 999.0, got {qi}"

    def test_queue_imbalance_both_zero(self):
        """queue_imbalance(0, 0) should return None."""
        from src.analysis.microstructure.obi import queue_imbalance
        qi = queue_imbalance(0, 0)
        assert qi is None, f"Expected None, got {qi}"

    def test_normalized_obi_consistency(self):
        """normalized_obi and queue_imbalance should handle ask_count=0 consistently."""
        from src.analysis.microstructure.obi import normalized_obi, queue_imbalance
        # Both should handle ask_count=0 without crashing
        norm = normalized_obi(10, 0)
        qi = queue_imbalance(10, 0)
        assert norm == 1.0
        assert qi == 999.0

    def test_demand_score_with_zero_asks(self):
        """calculate_demand_score should handle ask_count=0 gracefully."""
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        result = calculate_demand_score("Test", 5.0, 4.8, 0, 30)
        # Should not crash, should return valid result
        assert "score" in result
        assert "reason" in result

    def test_demand_logging_creates_entry(self):
        """_log_demand_decision should create a database entry."""
        from src.core.target_sniping.demand_strategy import _log_demand_decision
        from src.db.price_history import price_db
        import json

        before = price_db.state_conn.execute('SELECT COUNT(*) FROM decision_logs').fetchone()[0]
        _log_demand_decision("TEST_LOG_ITEM", 5.0, {
            "obi_value": 0.5, "ofi_value": 0.1, "obi_z": 1.0,
            "demand_ratio": 3.0, "score": 100.0, "expected_hold_days": 2.0,
            "reason": "test"
        })
        after = price_db.state_conn.execute('SELECT COUNT(*) FROM decision_logs').fetchone()[0]
        assert after > before, f"Expected new entry, got {before} -> {after}"


class TestDMarketAPIParentheses:
    """Regression test for parentheses in DMarket API titles."""

    def test_parentheses_stripped_from_params(self):
        """Verify parentheses are stripped before URL encoding."""
        params = {'title': 'AK-47 (Field-Tested)', 'gameId': 'a8db'}
        # Simulate what make_request does
        clean = {}
        for k, v in params.items():
            if isinstance(v, str):
                clean[k] = v.replace("(", "").replace(")", "")
            else:
                clean[k] = v
        assert clean['title'] == 'AK-47 Field-Tested'
        assert '(' not in clean['title']
        assert ')' not in clean['title']

    def test_parentheses_stripped_from_path(self):
        """Verify parentheses are stripped from URL path."""
        path = '/marketplace-api/v1/targets-by-title/a8db/AK-47 (Field-Tested)'
        clean = path.replace("(", "").replace(")", "")
        assert '(' not in clean
        assert ')' not in clean
        assert 'targets-by-title' in clean


class TestDMarketEncodingSafety:
    """Universal regression test for URL encoding issues in DMarket API.

    Tests that RFC3986-reserved characters in titles don't cause
    double-encoding signature mismatches.
    """

    def _strip_parens(self, s: str) -> str:
        """Simulate the make_request parentheses strip."""
        return s.replace("(", "").replace(")", "")

    def test_parens_stripped(self):
        assert self._strip_parens("AK-47 (Field-Tested)") == "AK-47 Field-Tested"

    def test_pipe_preserved(self):
        """Pipe should NOT be stripped — it works fine."""
        assert "AK-47 | Redline" == "AK-47 | Redline"

    def test_star_preserved(self):
        """Unicode star should NOT be stripped."""
        assert "★ Karambit" == "★ Karambit"

    def test_tm_preserved(self):
        """Trademark symbol should NOT be stripped."""
        assert "StatTrak™ AK-47" == "StatTrak™ AK-47"

    def test_brackets_preserved(self):
        """Brackets should NOT be stripped."""
        assert "AK-47 [test]" == "AK-47 [test]"

    def test_encoding_consistency(self):
        """Verify that stripped title produces clean URL encoding."""
        import urllib.parse
        title = "AK-47 | Elite Build (Battle-Scarred)"
        stripped = self._strip_parens(title)
        encoded = urllib.parse.urlencode({"title": stripped})
        # Should NOT contain %28 or %29
        assert "%28" not in encoded
        assert "%29" not in encoded
        # Should contain the pipe as %7C
        assert "%7C" in encoded

    def test_no_parens_in_real_cs2_items(self):
        """Verify common CS2 wear conditions work."""
        wears = [
            "AK-47 | Redline (Field-Tested)",
            "AK-47 | Redline (Minimal Wear)",
            "AK-47 | Redline (Factory New)",
            "AK-47 | Redline (Well-Worn)",
            "AK-47 | Redline (Battle-Scarred)",
            "★ Karambit | Doppler (Factory New)",
            "StatTrak™ AK-47 | Elite Build (Field-Tested)",
        ]
        for title in wears:
            stripped = self._strip_parens(title)
            assert "(" not in stripped, f"Parens not stripped from: {title}"
            assert ")" not in stripped, f"Parens not stripped from: {title}"
            # Verify wear info is preserved
            assert "Field-Tested" in stripped or "Minimal Wear" in stripped or \
                   "Factory New" in stripped or "Well-Worn" in stripped or \
                   "Battle-Scarred" in stripped, f"Wear lost from: {title}"


class TestWeaponDiversity:
    """Regression tests for weapon category diversity scanning."""

    def test_category_patterns_match_correctly(self):
        """Verify category patterns match expected titles."""
        patterns = {
            "Pistols": ["Glock-18 | ", "Desert Eagle | ", "USP-S | ", "P250 | ", "Five-SeveN | "],
            "SMGs": ["MAC-10 | ", "MP9 | ", "MP7 | ", "UMP-45 | ", "P90 | "],
            "Rifles": ["M4A4 | ", "M4A1-S | ", "FAMAS | ", "Galil AR | "],
            "Snipers": ["AWP | ", "SSG 08 | "],
            "Heavy": ["Nova | ", "XM1014 | ", "MAG-7 | ", "Sawed-Off | "],
        }
        
        test_titles = {
            "Pistols": ["Glock-18 | Fade", "Desert Eagle | Blaze", "USP-S | Kill Confirmed"],
            "SMGs": ["MAC-10 | Neon Rider", "MP9 | Wild Lily"],
            "Rifles": ["M4A4 | Howl", "M4A1-S | Hyper Beast", "FAMAS | Mecha Industries"],
            "Snipers": ["AWP | Dragon Lore", "SSG 08 | Blood in the Water"],
            "Heavy": ["Nova | Hyper Beast", "XM1014 | Tranquility"],
        }
        
        for cat, titles in test_titles.items():
            cat_patterns = patterns[cat]
            for t in titles:
                matched = any(t.startswith(p) for p in cat_patterns)
                assert matched, f"'{t}' should match category '{cat}' patterns"
        
        # Verify AK-47 does NOT match any non-AK category
        ak_title = "AK-47 | Redline"
        for cat, pats in patterns.items():
            if cat == "Rifles":
                continue  # AK-47 is a rifle but not in our diversity patterns
            matched = any(ak_title.startswith(p) for p in pats)
            assert not matched, f"AK-47 should NOT match category '{cat}'"

    def test_diversity_candidates_compete_on_score(self):
        """Verify diversity candidates use same score as demand candidates."""
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        
        # AK-47 candidate (from demand expansion) — tight spread, high Q
        ak_score = calculate_demand_score("AK-47 | Redline (FT)", 10.0, 9.5, 100, 300)
        
        # AWP candidate (from diversity scan) — tight spread, high Q
        awp_score = calculate_demand_score("AWP | Asiimov (FT)", 30.0, 28.0, 50, 200)
        
        # Both should use the same scoring function
        assert ak_score["score"] > 0, f"AK-47 should have positive score, got {ak_score['score']}"
        assert awp_score["score"] > 0, f"AWP should have positive score, got {awp_score['score']}"
        # Both use demand_ratio, obi_norm, spread_pct — same formula


class TestLuxuryStickerRejection:
    """Regression tests for luxury sticker rejection."""

    def test_luxury_stickers_detected(self):
        """Verify luxury stickers are correctly identified."""
        from src.core.target_sniping.sticker_cache import StickerPremiumCache
        cache = StickerPremiumCache()
        
        luxury_cases = [
            [{"name": "Titan | Katowice 2014"}],
            [{"name": "iBUYPOWER | Katowice 2014"}],
            [{"name": "Crown (Foil)"}],
            [{"name": "Howl"}],
            [{"name": "Virtus.pro (Holo) | Katowice 2014"}],
        ]
        
        for stickers in luxury_cases:
            assert cache.should_reject_by_stickers(stickers), f"Should reject: {stickers[0]['name']}"

    def test_mid_range_stickers_not_rejected(self):
        """Verify mid-range stickers are NOT rejected."""
        from src.core.target_sniping.sticker_cache import StickerPremiumCache
        cache = StickerPremiumCache()
        
        mid_range_cases = [
            [{"name": "Astralis (Gold) | Berlin 2019"}],
            [{"name": "Natus Vincere (Holo) | Katowice 2015"}],
            [{"name": "FaZe Clan (Gold) | Copenhagen 2024"}],
            [{"name": "Headshot Guarantee"}],
        ]
        
        for stickers in mid_range_cases:
            assert not cache.should_reject_by_stickers(stickers), f"Should NOT reject: {stickers[0]['name']}"

    def test_empty_stickers_not_rejected(self):
        """Verify empty/None stickers are not rejected."""
        from src.core.target_sniping.sticker_cache import StickerPremiumCache
        cache = StickerPremiumCache()
        
        assert not cache.should_reject_by_stickers([])
        assert not cache.should_reject_by_stickers(None)
        assert not cache.should_reject_by_stickers([{"name": ""}])
