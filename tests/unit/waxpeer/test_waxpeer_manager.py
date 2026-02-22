"""
Тесты для Waxpeer Manager.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.waxpeer.waxpeer_manager import CS2RareFilters, ListedItem, ListingConfig, WaxpeerManager


class TestCS2RareFilters:
    """Тесты для фильтров редких CS2 скинов."""

    def test_default_filters_initialization(self) -> None:
        """Тест инициализации фильтров по умолчанию."""
        filters = CS2RareFilters()

        assert filters.factory_new_low == 0.01
        assert filters.factory_new_ultra == 0.001
        assert filters.battle_scarred_high == 0.95
        assert "Katowice 2014" in filters.target_sticker_groups
        assert "Ruby" in filters.doppler_phases

    def test_custom_filters(self) -> None:
        """Тест кастомных фильтров."""
        filters = CS2RareFilters(
            factory_new_low=0.02,
            doppler_phases=["Ruby", "Sapphire"],
        )

        assert filters.factory_new_low == 0.02
        assert filters.doppler_phases == ["Ruby", "Sapphire"]


class TestWaxpeerManagerRarityEvaluation:
    """Тесты оценки редкости предметов."""

    @pytest.fixture()
    def manager(self) -> WaxpeerManager:
        """Создание менеджера для тестов."""
        return WaxpeerManager(api_key="test_key")

    def test_evaluate_triple_zero_float(self, manager: WaxpeerManager) -> None:
        """Тест определения Triple Zero флоата."""
        item_data = {
            "title": "AK-47 | Redline (Factory New)",
            "float_value": 0.0008,
        }

        is_rare, reason, markup = manager._evaluate_item_rarity(item_data)

        assert is_rare is True
        assert "Ultra Low Float" in reason
        assert markup == 0.40

    def test_evaluate_double_zero_float(self, manager: WaxpeerManager) -> None:
        """Тест определения Double Zero флоата."""
        item_data = {
            "title": "M4A4 | Howl (Factory New)",
            "float_value": 0.008,
        }

        is_rare, reason, markup = manager._evaluate_item_rarity(item_data)

        assert is_rare is True
        assert "Low Float" in reason
        assert markup == 0.25

    def test_evaluate_blackiimov_float(self, manager: WaxpeerManager) -> None:
        """Тест определения Blackiimov флоата."""
        item_data = {
            "title": "AWP | Asiimov (Battle-Scarred)",
            "float_value": 0.97,
        }

        is_rare, reason, markup = manager._evaluate_item_rarity(item_data)

        assert is_rare is True
        assert "High Float" in reason
        assert markup == 0.20

    def test_evaluate_katowice_2014_holo_sticker(self, manager: WaxpeerManager) -> None:
        """Тест определения Katowice 2014 Holo наклейки."""
        item_data = {
            "title": "AK-47 | Blue Laminate (Factory New)",
            "float_value": 0.05,
            "stickers": [
                {"name": "iBUYPOWER (Holo) | Katowice 2014"},
            ],
        }

        is_rare, reason, markup = manager._evaluate_item_rarity(item_data)

        assert is_rare is True
        assert "JACKPOT" in reason
        assert markup == 0.50

    def test_evaluate_crown_foil_sticker(self, manager: WaxpeerManager) -> None:
        """Тест определения Crown (Foil) наклейки."""
        item_data = {
            "title": "Glock-18 | Fade (Factory New)",
            "float_value": 0.03,
            "stickers": [
                {"name": "Crown (Foil)"},
            ],
        }

        is_rare, reason, markup = manager._evaluate_item_rarity(item_data)

        assert is_rare is True
        assert "Rare Sticker" in reason

    def test_evaluate_ruby_doppler(self, manager: WaxpeerManager) -> None:
        """Тест определения Ruby Doppler."""
        item_data = {
            "title": "★ Karambit | Doppler Ruby (Factory New)",
            "float_value": 0.02,
        }

        is_rare, reason, markup = manager._evaluate_item_rarity(item_data)

        assert is_rare is True
        assert "Premium Doppler: Ruby" in reason
        assert markup == 0.50

    def test_evaluate_phase_2_doppler(self, manager: WaxpeerManager) -> None:
        """Тест определения Phase 2 Doppler."""
        item_data = {
            "title": "★ M9 Bayonet | Doppler Phase 2 (Factory New)",
            "float_value": 0.03,
        }

        is_rare, reason, markup = manager._evaluate_item_rarity(item_data)

        assert is_rare is True
        assert "Phase 2" in reason
        assert markup == 0.15

    def test_evaluate_normal_item(self, manager: WaxpeerManager) -> None:
        """Тест обычного предмета без редких атрибутов."""
        item_data = {
            "title": "P250 | Sand Dune (Field-Tested)",
            "float_value": 0.25,
            "stickers": [],
        }

        is_rare, reason, markup = manager._evaluate_item_rarity(item_data)

        assert is_rare is False
        assert reason is None
        assert markup == 0.0


class TestWaxpeerManagerPriceCalculation:
    """Тесты расчета цены листинга."""

    @pytest.fixture()
    def manager(self) -> WaxpeerManager:
        """Создание менеджера для тестов."""
        config = ListingConfig(
            default_markup_percent=10.0,
            undercut_amount_usd=0.01,
            min_profit_percent=5.0,
        )
        return WaxpeerManager(api_key="test_key", listing_config=config)

    def test_calculate_price_for_normal_item(self, manager: WaxpeerManager) -> None:
        """Тест расчета цены для обычного предмета."""
        buy_price = Decimal("10.00")
        market_price = Decimal("12.00")

        price = manager._calculate_listing_price(
            buy_price=buy_price,
            market_min_price=market_price,
            is_rare=False,
            markup_multiplier=0.0,
        )

        # Должен использовать undercut: $12.00 - $0.01 = $11.99
        assert price == Decimal("11.99")

    def test_calculate_price_respects_min_profit(self, manager: WaxpeerManager) -> None:
        """Тест что цена не опускается ниже минимальной прибыли."""
        buy_price = Decimal("10.00")
        market_price = Decimal("10.00")  # Рынок на уровне покупки

        price = manager._calculate_listing_price(
            buy_price=buy_price,
            market_min_price=market_price,
            is_rare=False,
            markup_multiplier=0.0,
        )

        # Должен использовать markup от покупки: $10.00 * 1.10 = $11.00
        assert price == Decimal("11.00")

    def test_calculate_price_for_rare_item(self, manager: WaxpeerManager) -> None:
        """Тест расчета цены для редкого предмета."""
        buy_price = Decimal("10.00")
        market_price = Decimal("12.00")

        price = manager._calculate_listing_price(
            buy_price=buy_price,
            market_min_price=market_price,
            is_rare=True,
            markup_multiplier=0.30,  # +30%
        )

        # Редкие не undercut: $10.00 * 1.30 = $13.00
        assert price == Decimal("13.00")

    def test_calculate_price_without_market_data(self, manager: WaxpeerManager) -> None:
        """Тест расчета цены без данных о рынке."""
        buy_price = Decimal("10.00")

        price = manager._calculate_listing_price(
            buy_price=buy_price,
            market_min_price=None,
            is_rare=False,
            markup_multiplier=0.0,
        )

        # Использует markup: $10.00 * 1.10 = $11.00
        assert price == Decimal("11.00")


class TestWaxpeerManagerListing:
    """Тесты листинга предметов."""

    @pytest.fixture()
    def manager(self) -> WaxpeerManager:
        """Создание менеджера для тестов."""
        return WaxpeerManager(api_key="test_key")

    @pytest.mark.asyncio()
    async def test_list_cs2_item_tracks_listing(self, manager: WaxpeerManager) -> None:
        """Тест отслеживания выставленного предмета."""
        mock_api_response = {"success": True}

        with patch.object(manager, "_evaluate_item_rarity", return_value=(False, None, 0.0)):
            with patch("src.waxpeer.waxpeer_manager.WaxpeerAPI") as mock_api_class:
                mock_api = AsyncMock()
                mock_api.get_item_price = AsyncMock(return_value=Decimal("12.00"))
                mock_api.list_single_item = AsyncMock(return_value=mock_api_response)
                mock_api.__aenter__ = AsyncMock(return_value=mock_api)
                mock_api.__aexit__ = AsyncMock(return_value=None)
                mock_api_class.return_value = mock_api

                response, price, is_rare, reason = await manager.list_cs2_item(
                    asset_id="asset_123",
                    item_name="AK-47 | Redline (FT)",
                    buy_price=10.00,
                )

        assert "asset_123" in manager._listed_items
        assert manager._total_listed == 1
        tracked = manager._listed_items["asset_123"]
        assert tracked.buy_price == Decimal("10.00")

    @pytest.mark.asyncio()
    async def test_list_rare_item_with_notification(self, manager: WaxpeerManager) -> None:
        """Тест листинга редкого предмета."""
        mock_api_response = {"success": True}
        item_data = {
            "title": "AWP | Dragon Lore (Factory New)",
            "float_value": 0.008,
        }

        with patch("src.waxpeer.waxpeer_manager.WaxpeerAPI") as mock_api_class:
            mock_api = AsyncMock()
            mock_api.get_item_price = AsyncMock(return_value=Decimal("5000.00"))
            mock_api.list_single_item = AsyncMock(return_value=mock_api_response)
            mock_api.__aenter__ = AsyncMock(return_value=mock_api)
            mock_api.__aexit__ = AsyncMock(return_value=None)
            mock_api_class.return_value = mock_api

            response, price, is_rare, reason = await manager.list_cs2_item(
                asset_id="asset_rare",
                item_name="AWP | Dragon Lore (FN)",
                buy_price=4500.00,
                item_data=item_data,
            )

        assert is_rare is True
        assert "Low Float" in reason
        tracked = manager._listed_items["asset_rare"]
        assert tracked.is_rare is True


class TestListedItemDataClass:
    """Тесты для dataclass ListedItem."""

    def test_listed_item_creation(self) -> None:
        """Тест создания ListedItem."""
        from datetime import datetime

        item = ListedItem(
            asset_id="123",
            name="AK-47 | Redline",
            buy_price=Decimal("10.00"),
            list_price=Decimal("11.50"),
            listed_at=datetime.now(),
            is_rare=False,
        )

        assert item.asset_id == "123"
        assert item.buy_price == Decimal("10.00")
        assert item.price_drops == 0
        assert item.is_rare is False
        assert item.rare_reason is None
