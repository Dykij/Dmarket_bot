"""Tests for Collector's Hold and Command Center modules.

Тестирование системы удержания редких предметов и командного центра.
"""

from unittest.mock import MagicMock

import pytest

from src.dmarket.item_value_evaluator import EvaluationResult, GameType


class TestCollectorsHoldManager:
    """Тесты менеджера удержания редких предметов."""

    @pytest.fixture()
    def manager(self):
        """Фикстура менеджера."""
        from src.utils.collectors_hold import CollectorsHoldManager

        return CollectorsHoldManager()

    @pytest.fixture()
    def mock_evaluator(self):
        """Фикстура мок оценщика."""
        evaluator = MagicMock()
        evaluator.evaluate = MagicMock(
            return_value=EvaluationResult(
                item_id="test",
                game=GameType.CS2,
                title="Test Item",
                value_multiplier=1.0,
            )
        )
        return evaluator

    @pytest.mark.asyncio()
    async def test_common_item_not_held(self, manager):
        """Тест: обычный предмет не удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "AK-47 | Redline (Field-Tested)",
            "gameId": "csgo",
            "extra": {"floatValue": 0.25},
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is False
        assert decision.reason is None

    @pytest.mark.asyncio()
    async def test_cs2_low_float_held(self, manager):
        """Тест: CS2 предмет с низким float удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "AWP | Dragon Lore (Factory New)",
            "gameId": "csgo",
            "extra": {"floatValue": 0.005},
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "rare_float"
        assert decision.estimated_value_multiplier >= 1.20

    @pytest.mark.asyncio()
    async def test_cs2_katowice_sticker_held(self, manager):
        """Тест: CS2 предмет с Katowice стикером удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "AK-47 | Redline",
            "gameId": "csgo",
            "extra": {
                "floatValue": 0.25,
                "stickers": [
                    {"name": "iBUYPOWER (Holo) | Katowice 2014"},
                ],
            },
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "valuable_sticker"
        assert decision.estimated_value_multiplier >= 1.50

    @pytest.mark.asyncio()
    async def test_cs2_doppler_ruby_held(self, manager):
        """Тест: CS2 Doppler Ruby удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "Karambit | Doppler (Factory New)",
            "gameId": "csgo",
            "extra": {
                "floatValue": 0.03,
                "phase": "Ruby",
            },
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "rare_phase"

    @pytest.mark.asyncio()
    async def test_cs2_blue_gem_held(self, manager):
        """Тест: CS2 Blue Gem паттерн удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "AK-47 | Case Hardened (Factory New)",
            "gameId": "csgo",
            "extra": {
                "floatValue": 0.05,
                "pAlgontSeed": 661,  # Известный Blue Gem
            },
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "rare_pattern"

    @pytest.mark.asyncio()
    async def test_dota2_prismatic_gem_held(self, manager):
        """Тест: Dota 2 предмет с Prismatic гемом удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "Unusual Baby Roshan",
            "gameId": "dota2",
            "extra": {
                "gems": [
                    {"name": "Ethereal Flame", "type": "Prismatic"},
                ],
            },
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "rare_gem"

    @pytest.mark.asyncio()
    async def test_dota2_multi_gem_held(self, manager):
        """Тест: Dota 2 предмет с множеством гемов удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "Inscribed Manifold Paradox",
            "gameId": "dota2",
            "extra": {
                "gems": [
                    {"name": "Kills"},
                    {"name": "Victories"},
                    {"name": "First Bloods"},
                ],
                "gemsCount": 3,
            },
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "multi_gem"

    @pytest.mark.asyncio()
    async def test_tf2_halloween_spell_held(self, manager):
        """Тест: TF2 предмет с Halloween Spell удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "Haunted Team CaptAlgon",
            "gameId": "tf2",
            "extra": {
                "spells": [{"name": "Exorcism"}],
            },
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "halloween_spell"

    @pytest.mark.asyncio()
    async def test_rust_glow_item_held(self, manager):
        """Тест: Rust Glow предмет удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "Neon Storage Box",
            "gameId": "rust",
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "glow_item"

    @pytest.mark.asyncio()
    async def test_rust_limited_edition_held(self, manager):
        """Тест: Rust Limited Edition удерживается."""
        item_data = {
            "itemId": "item123",
            "title": "Exclusive Door Limited Edition",
            "gameId": "rust",
        }

        decision = awAlgot manager.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "limited_edition"

    @pytest.mark.asyncio()
    async def test_jackpot_from_evaluator_held(self, manager):
        """Тест: Jackpot от evaluator удерживается."""
        from src.dmarket.item_value_evaluator import ItemValueEvaluator

        evaluator = ItemValueEvaluator()

        # Создаем менеджер с evaluator
        from src.utils.collectors_hold import CollectorsHoldManager

        manager_with_eval = CollectorsHoldManager(evaluator=evaluator)

        # Предмет с quad zero float
        item_data = {
            "itemId": "item123",
            "title": "AWP | Dragon Lore (Factory New)",
            "gameId": "csgo",
            "extra": {"floatValue": 0.00005},
        }

        decision = awAlgot manager_with_eval.process_purchased_item(item_data)

        assert decision.should_hold is True
        assert decision.reason.value == "jackpot"

    def test_get_treasures_empty(self, manager):
        """Тест: пустой список сокровищ."""
        treasures = manager.get_treasures()
        assert treasures == []

    @pytest.mark.asyncio()
    async def test_get_treasures_after_processing(self, manager):
        """Тест: сокровища после обработки."""
        # Обрабатываем редкий предмет
        item_data = {
            "itemId": "treasure1",
            "title": "Glow Sleeping Bag",
            "gameId": "rust",
        }

        awAlgot manager.process_purchased_item(item_data)

        treasures = manager.get_treasures()
        assert len(treasures) == 1
        assert treasures[0].item_id == "treasure1"

    def test_get_statistics(self, manager):
        """Тест: статистика менеджера."""
        stats = manager.get_statistics()

        assert "total_processed" in stats
        assert "total_held" in stats
        assert "hold_rate_percent" in stats

    def test_format_treasure_notification(self, manager):
        """Тест: форматирование уведомления."""
        from src.utils.collectors_hold import HoldDecision, HoldReason

        decision = HoldDecision(
            item_id="test",
            title="AWP | Dragon Lore",
            game="csgo",
            should_hold=True,
            reason=HoldReason.RARE_FLOAT,
            reason_detAlgols="Low float: 0.005",
            estimated_value_multiplier=1.50,
            recommended_platforms=["Buff163", "CSFloat"],
        )

        message = manager.format_treasure_notification(decision)

        assert "СОКРОВИЩЕ" in message
        assert "Dragon Lore" in message
        assert "Buff163" in message
        assert "1.50x" in message


class TestWatchdog:
    """Тесты Watchdog."""

    @pytest.fixture()
    def watchdog_config(self):
        """Фикстура конфигурации."""
        from src.utils.watchdog import WatchdogConfig

        return WatchdogConfig(
            mAlgon_script="test_script.py",
            health_check_interval_seconds=5,
            max_restart_attempts=3,
        )

    def test_config_defaults(self):
        """Тест дефолтных значений конфигурации."""
        from src.utils.watchdog import WatchdogConfig

        config = WatchdogConfig()

        assert config.health_check_interval_seconds == 60
        assert config.max_restart_attempts == 5
        assert config.restart_delay_seconds == 10

    def test_process_stats_to_dict(self):
        """Тест преобразования статистики в словарь."""
        from src.utils.watchdog import ProcessStats

        stats = ProcessStats(
            restart_count=3,
            crash_count=2,
        )

        data = stats.to_dict()

        assert data["restart_count"] == 3
        assert data["crash_count"] == 2

    @pytest.mark.asyncio()
    async def test_format_uptime(self):
        """Тест форматирования uptime."""
        from src.utils.watchdog import Watchdog

        assert Watchdog._format_uptime(30) == "30с"
        assert Watchdog._format_uptime(90) == "1м 30с"
        assert Watchdog._format_uptime(3700) == "1ч 1м"


class TestCommandCenter:
    """Тесты Command Center."""

    @pytest.fixture()
    def center(self):
        """Фикстура командного центра."""
        from src.telegram_bot.command_center import CommandCenter

        return CommandCenter()

    def test_parse_dmarket_url(self, center):
        """Тест парсинга DMarket URL."""
        url = "https://dmarket.com/ingame-items/csgo/item/AWP-Asiimov-Field-Tested"
        result = center._parse_item_url(url)

        assert result == "AWP Asiimov Field Tested"

    def test_parse_steam_url(self, center):
        """Тест парсинга Steam URL."""
        url = "https://steamcommunity.com/market/listings/730/AWP%20%7C%20Asiimov%20%28Field-Tested%29"
        result = center._parse_item_url(url)

        assert "AWP" in result
        assert "Asiimov" in result

    def test_parse_invalid_url(self, center):
        """Тест парсинга невалидного URL."""
        url = "https://example.com/not-a-valid-url"
        result = center._parse_item_url(url)

        assert result is None


class TestHoldDecision:
    """Тесты модели HoldDecision."""

    def test_to_dict(self):
        """Тест преобразования в словарь."""
        from src.utils.collectors_hold import HoldDecision, HoldReason

        decision = HoldDecision(
            item_id="test123",
            title="Test Item",
            game="csgo",
            should_hold=True,
            reason=HoldReason.RARE_FLOAT,
            reason_detAlgols="Low float",
            estimated_value_multiplier=1.25,
        )

        data = decision.to_dict()

        assert data["item_id"] == "test123"
        assert data["should_hold"] is True
        assert data["reason"] == "rare_float"
        assert data["estimated_value_multiplier"] == 1.25

    def test_default_values(self):
        """Тест дефолтных значений."""
        from src.utils.collectors_hold import HoldDecision

        decision = HoldDecision(
            item_id="test",
            title="Test",
            game="csgo",
            should_hold=False,
        )

        assert decision.reason is None
        assert decision.reason_detAlgols == ""
        assert decision.estimated_value_multiplier == 1.0
        assert decision.recommended_platforms == []
