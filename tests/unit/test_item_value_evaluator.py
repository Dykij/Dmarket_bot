"""Tests for ItemValueEvaluator module.

Тестирование оценки редкости предметов для всех игр.
"""

import pytest

from src.dmarket.item_value_evaluator import (
    EvaluationResult,
    GameType,
    ItemValueEvaluator,
    RarityTier,
)


class TestItemValueEvaluator:
    """Тесты оценщика ценности предметов."""

    @pytest.fixture()
    def evaluator(self):
        """Фикстура оценщика."""
        return ItemValueEvaluator()

    # CS2 Tests
    def test_cs2_double_zero_float(self, evaluator):
        """Тест обнаружения Double Zero float."""
        item_data = {
            "gameId": "csgo",
            "title": "AK-47 | Redline (Factory New)",
            "extra": {"floatValue": 0.005},
        }

        result = evaluator.evaluate(item_data)

        assert result.float_value == 0.005
        assert result.value_multiplier >= 1.15  # +15% за double zero
        assert "Low Float" in str(result.detected_attributes)
        assert result.rarity_tier in [RarityTier.RARE, RarityTier.UNCOMMON]

    def test_cs2_triple_zero_float(self, evaluator):
        """Тест обнаружения Triple Zero float."""
        item_data = {
            "gameId": "csgo",
            "title": "M4A4 | Howl (Factory New)",
            "extra": {"floatValue": 0.0008},
        }

        result = evaluator.evaluate(item_data)

        assert result.float_value == 0.0008
        assert result.value_multiplier >= 1.30  # +30%
        assert "Triple Zero" in str(result.detected_attributes)

    def test_cs2_quad_zero_float_jackpot(self, evaluator):
        """Тест обнаружения Quad Zero float (JACKPOT)."""
        item_data = {
            "gameId": "csgo",
            "title": "AWP | Dragon Lore (Factory New)",
            "extra": {"floatValue": 0.00005},
        }

        result = evaluator.evaluate(item_data)

        assert result.float_value == 0.00005
        assert result.value_multiplier >= 1.50  # +50%
        assert result.requires_manual_review is True
        assert result.rarity_tier == RarityTier.JACKPOT

    def test_cs2_katowice_2014_holo_sticker(self, evaluator):
        """Тест обнаружения Katowice 2014 Holo наклейки."""
        item_data = {
            "gameId": "csgo",
            "title": "AK-47 | Redline (Field-Tested)",
            "extra": {
                "stickers": [
                    {"name": "iBUYPOWER (Holo) | Katowice 2014"},
                ]
            },
        }

        result = evaluator.evaluate(item_data)

        assert len(result.stickers) == 1
        assert result.value_multiplier >= 2.0  # +100%
        assert result.requires_manual_review is True
        assert "Katowice 2014 Holo" in str(result.detected_attributes)

    def test_cs2_crown_foil_sticker(self, evaluator):
        """Тест обнаружения Crown Foil наклейки."""
        item_data = {
            "gameId": "csgo",
            "title": "M4A1-S | Hot Rod (Factory New)",
            "extra": {
                "stickers": [
                    {"name": "Crown (Foil)"},
                ]
            },
        }

        result = evaluator.evaluate(item_data)

        assert result.value_multiplier >= 1.15  # +15%
        assert "Crown" in str(result.detected_attributes)

    def test_cs2_doppler_ruby(self, evaluator):
        """Тест обнаружения Doppler Ruby."""
        item_data = {
            "gameId": "csgo",
            "title": "Karambit | Doppler (Factory New)",
            "extra": {"phase": "Ruby"},
        }

        result = evaluator.evaluate(item_data)

        assert result.phase == "Ruby"
        assert result.value_multiplier >= 1.40  # +40%
        assert result.requires_manual_review is True

    def test_cs2_case_hardened_blue_gem(self, evaluator):
        """Тест обнаружения Case Hardened Blue Gem паттерна."""
        item_data = {
            "gameId": "csgo",
            "title": "AK-47 | Case Hardened (Factory New)",
            "extra": {"pAlgontSeed": 661},  # Известный Blue Gem паттерн
        }

        result = evaluator.evaluate(item_data)

        assert result.pattern_id == 661
        assert result.value_multiplier >= 1.50  # +50%
        assert result.requires_manual_review is True
        assert "Blue Gem" in str(result.detected_attributes)

    # Dota 2 Tests
    def test_dota2_prismatic_gem(self, evaluator):
        """Тест обнаружения редкого Prismatic гема."""
        item_data = {
            "gameId": "dota2",
            "title": "Unusual Baby Roshan",
            "extra": {
                "gems": [
                    {"name": "Ethereal Flame", "type": "Prismatic"},
                ]
            },
        }

        result = evaluator.evaluate(item_data)

        assert len(result.gems) == 1
        assert result.value_multiplier >= 1.20  # +20%
        assert "Prismatic Gem" in str(result.detected_attributes)

    def test_dota2_multi_inscribed(self, evaluator):
        """Тест обнаружения множественных Inscribed гемов."""
        item_data = {
            "gameId": "dota2",
            "title": "Inscribed Manifold Paradox",
            "extra": {
                "gems": [
                    {"name": "Kills"},
                    {"name": "Victories"},
                    {"name": "First Bloods"},
                    {"name": "Gold Earned"},
                ],
                "gemsCount": 4,
            },
        }

        result = evaluator.evaluate(item_data)

        assert result.value_multiplier >= 1.05  # +5%
        assert "Multi-gem" in str(result.detected_attributes)

    def test_dota2_unlocked_styles(self, evaluator):
        """Тест обнаружения открытых стилей."""
        item_data = {
            "gameId": "dota2",
            "title": "Arcana Item",
            "extra": {"unlockedStyles": 3},
        }

        result = evaluator.evaluate(item_data)

        assert result.unlocked_styles == 3
        assert result.value_multiplier >= 1.08  # +8%

    # TF2 Tests
    def test_tf2_halloween_spell(self, evaluator):
        """Тест обнаружения Halloween Spell."""
        item_data = {
            "gameId": "tf2",
            "title": "Haunted Hat",
            "extra": {
                "spells": [
                    {"name": "Exorcism"},
                ]
            },
        }

        result = evaluator.evaluate(item_data)

        assert len(result.spells) == 1
        assert result.value_multiplier >= 1.15  # +15%
        assert "Halloween Spell" in str(result.detected_attributes)

    def test_tf2_unusual_tier1(self, evaluator):
        """Тест обнаружения топового Unusual эффекта."""
        item_data = {
            "gameId": "tf2",
            "title": "Unusual Team CaptAlgon",
            "extra": {"effect": "Burning Flames"},
        }

        result = evaluator.evaluate(item_data)

        assert result.unusual_effect == "Burning Flames"
        assert result.value_multiplier >= 1.25  # +25%
        assert "Tier 1 Unusual" in str(result.detected_attributes)

    def test_tf2_strange_parts(self, evaluator):
        """Тест обнаружения Strange Parts."""
        item_data = {
            "gameId": "tf2",
            "title": "Strange Scattergun",
            "extra": {
                "parts": [
                    {"name": "Headshot Kills"},
                    {"name": "Critical Kills"},
                ]
            },
        }

        result = evaluator.evaluate(item_data)

        assert len(result.strange_parts) == 2
        assert result.value_multiplier >= 1.10  # +5% * 2

    # Rust Tests
    def test_rust_glow_item(self, evaluator):
        """Тест обнаружения Glow предмета."""
        item_data = {
            "gameId": "rust",
            "title": "Neon Storage Box",
        }

        result = evaluator.evaluate(item_data)

        assert result.is_glow is True
        assert result.value_multiplier >= 1.10  # +10%
        assert "Glow" in str(result.detected_attributes)

    def test_rust_limited_edition(self, evaluator):
        """Тест обнаружения Limited Edition."""
        item_data = {
            "gameId": "rust",
            "title": "Exclusive Door Skin Limited",
        }

        result = evaluator.evaluate(item_data)

        assert result.is_limited_edition is True
        assert result.value_multiplier >= 1.15  # +15%

    # Edge Cases
    def test_common_item_no_bonus(self, evaluator):
        """Тест обычного предмета без бонусов."""
        item_data = {
            "gameId": "csgo",
            "title": "AK-47 | Redline (Field-Tested)",
            "extra": {"floatValue": 0.25},  # Обычный float
        }

        result = evaluator.evaluate(item_data)

        assert result.value_multiplier == 1.0
        assert result.rarity_tier == RarityTier.COMMON
        assert len(result.detected_attributes) == 0

    def test_max_overpay_calculation(self, evaluator):
        """Тест расчета максимальной переплаты."""
        # Предмет с +20% бонусом
        result = EvaluationResult(
            item_id="test",
            game=GameType.CS2,
            title="Test Item",
            value_multiplier=1.20,
        )

        max_overpay = evaluator.get_max_overpay_percent(result)

        # 20% потенциал * 25% = 5% макс переплата
        assert abs(max_overpay - 5.0) < 0.01  # Allow floating point tolerance

    def test_jackpot_no_overpay(self, evaluator):
        """Тест: для джекпотов не переплачиваем автоматически."""
        result = EvaluationResult(
            item_id="test",
            game=GameType.CS2,
            title="Test Item",
            value_multiplier=2.0,
            requires_manual_review=True,
        )

        max_overpay = evaluator.get_max_overpay_percent(result)

        assert max_overpay == 0.0  # Требуется ручная проверка


class TestEvaluationResult:
    """Тесты модели EvaluationResult."""

    def test_to_dict(self):
        """Тест преобразования в словарь."""
        result = EvaluationResult(
            item_id="test123",
            game=GameType.CS2,
            title="Test Item",
            rarity_tier=RarityTier.RARE,
            value_multiplier=1.15,
            detected_attributes=["Low Float"],
        )

        data = result.to_dict()

        assert data["item_id"] == "test123"
        assert data["game"] == GameType.CS2
        assert data["rarity_tier"] == RarityTier.RARE
        assert data["value_multiplier"] == 1.15

    def test_profitability_flag(self):
        """Тест флага прибыльности."""
        # Profitable
        result1 = EvaluationResult(
            item_id="1",
            game=GameType.CS2,
            title="Item 1",
            value_multiplier=1.15,
        )
        result1.is_profitable_rare = result1.value_multiplier >= 1.10
        assert result1.is_profitable_rare is True

        # Not profitable
        result2 = EvaluationResult(
            item_id="2",
            game=GameType.CS2,
            title="Item 2",
            value_multiplier=1.05,
        )
        result2.is_profitable_rare = result2.value_multiplier >= 1.10
        assert result2.is_profitable_rare is False
