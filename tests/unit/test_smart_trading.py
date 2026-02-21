"""Tests for SteamSalesProtector and ShadowListingManager.

Тестирование защиты от распродаж и умного ценообразования.
"""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from src.dmarket.steam_sales_protector import (
    ProtectorConfig,
    SaleEvent,
    SaleMode,
    SaleType,
    SteamSalesProtector,
)


class TestSaleEvent:
    """Тесты модели SaleEvent."""

    def test_is_active(self):
        """Тест проверки активности распродажи."""
        event = SaleEvent(
            name="Test Sale",
            sale_type=SaleType.SUMMER,
            start_date=date(2026, 6, 25),
            end_date=date(2026, 7, 9),
        )

        # До начала
        assert event.is_active(date(2026, 6, 20)) is False
        # В начале
        assert event.is_active(date(2026, 6, 25)) is True
        # В середине
        assert event.is_active(date(2026, 7, 1)) is True
        # В конце
        assert event.is_active(date(2026, 7, 9)) is True
        # После
        assert event.is_active(date(2026, 7, 15)) is False

    def test_days_until_start(self):
        """Тест расчета дней до начала."""
        event = SaleEvent(
            name="Test Sale",
            sale_type=SaleType.SUMMER,
            start_date=date(2026, 6, 25),
            end_date=date(2026, 7, 9),
        )

        assert event.days_until_start(date(2026, 6, 20)) == 5
        assert event.days_until_start(date(2026, 6, 25)) == 0
        assert event.days_until_start(date(2026, 6, 28)) == -3  # Уже началась

    def test_days_since_end(self):
        """Тест расчета дней после окончания."""
        event = SaleEvent(
            name="Test Sale",
            sale_type=SaleType.SUMMER,
            start_date=date(2026, 6, 25),
            end_date=date(2026, 7, 9),
        )

        assert event.days_since_end(date(2026, 7, 9)) == 0
        assert event.days_since_end(date(2026, 7, 12)) == 3
        assert event.days_since_end(date(2026, 7, 5)) == -4  # Еще не закончилась

    def test_duration_days(self):
        """Тест расчета длительности."""
        event = SaleEvent(
            name="Test Sale",
            sale_type=SaleType.SUMMER,
            start_date=date(2026, 6, 25),
            end_date=date(2026, 7, 9),
        )

        assert event.duration_days == 15  # 25 июня - 9 июля


class TestSteamSalesProtector:
    """Тесты защитника от распродаж."""

    @pytest.fixture()
    def protector(self):
        """Фикстура защитника."""
        return SteamSalesProtector()

    @pytest.fixture()
    def custom_protector(self):
        """Фикстура защитника с кастомным конфигом."""
        config = ProtectorConfig(
            pre_sale_days=5,
            post_sale_days=2,
            pre_sale_price_reduction=0.03,
            sale_buy_min_discount=0.30,
        )
        return SteamSalesProtector(config=config)

    def test_normal_mode_no_sales(self, protector):
        """Тест нормального режима без распродаж."""
        # Далеко от любых распродаж
        status = protector.get_current_mode(date(2026, 5, 1))

        assert status.mode == SaleMode.NORMAL
        assert status.should_stop_buying is False
        assert status.should_liquidate is False
        assert status.sell_price_modifier == 1.0

    def test_pre_sale_mode(self, protector):
        """Тест режима перед распродажей."""
        # За 2 дня до Summer Sale (25 июня)
        status = protector.get_current_mode(date(2026, 6, 23))

        assert status.mode == SaleMode.PRE_SALE
        assert status.should_stop_buying is True
        assert status.should_liquidate is True
        assert status.sell_price_modifier < 1.0  # Снижение цены

    def test_sale_mode(self, protector):
        """Тест режима во время распродажи."""
        # Во время Summer Sale (1 июля)
        status = protector.get_current_mode(date(2026, 7, 1))

        assert status.mode == SaleMode.SALE
        assert status.should_stop_buying is False
        assert status.should_buy_aggressively is True
        assert status.buy_discount_threshold == 0.25  # 25% минимум

    def test_post_sale_mode(self, protector):
        """Тест режима после распродажи."""
        # Через 2 дня после Summer Sale (11 июля)
        status = protector.get_current_mode(date(2026, 7, 11))

        assert status.mode == SaleMode.POST_SALE
        assert status.should_stop_buying is False
        assert status.sell_price_modifier == 0.98  # 98% от нормы

    def test_should_buy_item_normal(self, protector):
        """Тест решения о покупке в нормальном режиме."""
        # Нормальный режим - покупаем
        can_buy, reason = protector.should_buy_item(
            item_discount_percent=10.0,
            current_date=date(2026, 5, 1),
        )

        assert can_buy is True

    def test_should_buy_item_pre_sale(self, protector):
        """Тест решения о покупке перед распродажей."""
        # Перед распродажей - не покупаем
        can_buy, reason = protector.should_buy_item(
            item_discount_percent=15.0,
            current_date=date(2026, 6, 23),
        )

        assert can_buy is False
        assert "paused" in reason.lower()

    def test_should_buy_item_during_sale_low_discount(self, protector):
        """Тест: во время распродажи не покупаем с маленькой скидкой."""
        # Во время распродажи нужна скидка 25%+
        can_buy, reason = protector.should_buy_item(
            item_discount_percent=15.0,  # Меньше порога
            current_date=date(2026, 7, 1),
        )

        assert can_buy is False
        assert "threshold" in reason.lower()

    def test_should_buy_item_during_sale_high_discount(self, protector):
        """Тест: во время распродажи покупаем с большой скидкой."""
        can_buy, reason = protector.should_buy_item(
            item_discount_percent=30.0,  # Больше порога
            current_date=date(2026, 7, 1),
        )

        assert can_buy is True

    def test_get_active_sale(self, protector):
        """Тест получения активной распродажи."""
        # Во время Summer Sale
        sale = protector.get_active_sale(date(2026, 7, 1))

        assert sale is not None
        assert sale.sale_type == SaleType.SUMMER
        assert "Summer" in sale.name

    def test_get_upcoming_sale(self, protector):
        """Тест получения ближайшей распродажи."""
        # За 10 дней до Summer Sale
        sale = protector.get_upcoming_sale(date(2026, 6, 15), days_ahead=14)

        assert sale is not None
        assert sale.sale_type == SaleType.SUMMER

    def test_get_all_sales(self, protector):
        """Тест получения списка всех распродаж."""
        sales = protector.get_all_sales()

        assert len(sales) >= 6  # Как минимум основные распродажи
        # Проверяем сортировку по дате
        for i in range(len(sales) - 1):
            assert sales[i].start_date <= sales[i + 1].start_date

    def test_add_sale_event(self, protector):
        """Тест добавления пользовательской распродажи."""
        initial_count = len(protector.get_all_sales())

        custom_sale = SaleEvent(
            name="Publisher Sale",
            sale_type=SaleType.PUBLISHER,
            start_date=date(2026, 4, 15),
            end_date=date(2026, 4, 22),
            expected_discount_percent=10.0,
            is_major=False,
        )
        protector.add_sale_event(custom_sale)

        assert len(protector.get_all_sales()) == initial_count + 1

    def test_price_modifiers_normal(self, protector):
        """Тест модификаторов цен в нормальном режиме."""
        modifiers = protector.get_price_modifiers(date(2026, 5, 1))

        assert modifiers["sell_price_modifier"] == 1.0
        assert modifiers["buy_discount_threshold"] == 0.0
        assert modifiers["mode"] == SaleMode.NORMAL

    def test_price_modifiers_pre_sale(self, protector):
        """Тест модификаторов цен перед распродажей."""
        modifiers = protector.get_price_modifiers(date(2026, 6, 23))

        assert modifiers["sell_price_modifier"] == 0.98  # -2%
        assert modifiers["mode"] == SaleMode.PRE_SALE

    def test_format_status_message(self, protector):
        """Тест форматирования сообщения статуса."""
        message = protector.format_status_message(date(2026, 7, 1))

        assert "SALE" in message
        assert "Summer" in message
        assert "AGGRESSIVE" in message

    def test_notification_dates(self, protector):
        """Тест дат уведомлений."""
        notifications = protector.get_next_notification_dates(date(2026, 6, 1))

        assert len(notifications) > 0
        # Первое уведомление должно быть о Summer Sale
        first_date, first_event, days_before = notifications[0]
        assert first_event.sale_type == SaleType.SUMMER

    def test_winter_sale_crosses_year(self, protector):
        """Тест зимней распродажи, пересекающей год."""
        # Зимняя распродажа 2026 идет до 2 января 2027
        status = protector.get_current_mode(date(2027, 1, 1))

        assert status.mode == SaleMode.SALE
        assert status.active_sale.sale_type == SaleType.WINTER


class TestShadowListingManager:
    """Тесты менеджера умного ценообразования."""

    @pytest.fixture()
    def mock_api(self):
        """Фикстура мок API."""
        api = AsyncMock()
        api.get_market_items = AsyncMock(return_value={"objects": []})
        return api

    @pytest.mark.asyncio()
    async def test_monopoly_pricing(self, mock_api):
        """Тест ценообразования при монополии."""
        from src.dmarket.shadow_listing import MarketCondition, PricingAction, ShadowListingManager

        # Нет конкурентов
        mock_api.get_market_items.return_value = {"objects": []}

        manager = ShadowListingManager(mock_api)
        analysis = awAlgot manager.analyze_market_depth(
            item_title="Test Item",
            game="csgo",
            our_current_price=10.0,
        )

        assert analysis.market_condition == MarketCondition.MONOPOLY
        assert analysis.recommended_action == PricingAction.RAlgoSE

    @pytest.mark.asyncio()
    async def test_scarcity_pricing(self, mock_api):
        """Тест ценообразования при дефиците."""
        from src.dmarket.shadow_listing import MarketCondition, ShadowListingManager

        # Только 2 конкурента (< 3 = дефицит)
        mock_api.get_market_items.return_value = {
            "objects": [
                {"price": {"USD": 1100}, "suggestedPrice": {"USD": 1200}},
                {"price": {"USD": 1150}},
            ]
        }

        manager = ShadowListingManager(mock_api)
        analysis = awAlgot manager.analyze_market_depth(
            item_title="Test Item",
            game="csgo",
            our_current_price=12.0,
        )

        assert analysis.market_condition == MarketCondition.SCARCITY
        assert analysis.total_offers == 2

    @pytest.mark.asyncio()
    async def test_calculate_optimal_price_with_margin(self, mock_api):
        """Тест расчета оптимальной цены с минимальной маржой."""
        from src.dmarket.shadow_listing import ShadowListingManager

        mock_api.get_market_items.return_value = {"objects": []}

        manager = ShadowListingManager(mock_api)
        price = awAlgot manager.calculate_optimal_price(
            item_title="Test Item",
            buy_price=10.0,
            game="csgo",
        )

        # Должна быть выше цены покупки с маржой
        assert price > 10.0
        # С учетом комиссии 7% и маржи 3%
        min_expected = 10.0 * 1.03 / 0.93
        assert price >= min_expected

    @pytest.mark.asyncio()
    async def test_large_gap_pricing(self, mock_api):
        """Тест ценообразования при большом разрыве цен."""
        from src.dmarket.shadow_listing import PricingAction, ShadowListingManager

        # Большой разрыв между 1 и 2 ценой
        mock_api.get_market_items.return_value = {
            "objects": [
                {"price": {"USD": 1000}},  # $10.00
                {"price": {"USD": 1200}},  # $12.00 (+20% gap)
                {"price": {"USD": 1250}},
                {"price": {"USD": 1300}},
            ]
        }

        manager = ShadowListingManager(mock_api)
        analysis = awAlgot manager.analyze_market_depth(
            item_title="Test Item",
            game="csgo",
            our_current_price=13.0,
        )

        assert analysis.price_gap_percent > 5.0  # Большой разрыв
        assert analysis.recommended_action == PricingAction.UNDERCUT
        # Рекомендуемая цена должна быть около $11.99 (чуть ниже 2-й)
        assert analysis.recommended_price is not None
        assert analysis.recommended_price < 12.0

    def test_manager_statistics(self, mock_api):
        """Тест статистики менеджера."""
        from src.dmarket.shadow_listing import ShadowListingManager

        manager = ShadowListingManager(mock_api)
        stats = manager.get_statistics()

        assert "tracked_items" in stats
        assert "config" in stats
        assert "scarcity_threshold" in stats["config"]
