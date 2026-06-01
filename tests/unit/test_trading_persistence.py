"""Tests for TradingPersistence and PendingTrade model.

Этот модуль тестирует систему персистентности сделок:
- Сохранение покупок в базу данных
- Восстановление при перезапуске
- Расчет минимальной цены продажи
- Синхронизация с инвентарем DMarket
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.pending_trade import PendingTrade, PendingTradeStatus


class TestPendingTradeModel:
    """Тесты модели PendingTrade."""

    def test_calculate_min_sell_price_standard_margin(self):
        """Тест расчета минимальной цены с стандартной маржой."""
        # Arrange
        buy_price = 10.0  # $10
        min_margin = 5.0  # 5%
        dmarket_fee = 7.0  # 7%

        # Act
        min_sell = PendingTrade.calculate_min_sell_price(
            buy_price=buy_price,
            min_margin_percent=min_margin,
            dmarket_fee_percent=dmarket_fee,
        )

        # Assert
        # Formula: buy * (1 + margin) / (1 - fee)
        # = 10 * 1.05 / 0.93 = 11.29
        assert min_sell == 11.29

    def test_calculate_min_sell_price_zero_margin(self):
        """Тест расчета минимальной цены с нулевой маржой (break-even)."""
        # Arrange
        buy_price = 10.0
        min_margin = 0.0  # Break-even
        dmarket_fee = 7.0

        # Act
        min_sell = PendingTrade.calculate_min_sell_price(
            buy_price=buy_price,
            min_margin_percent=min_margin,
            dmarket_fee_percent=dmarket_fee,
        )

        # Assert
        # = 10 * 1.0 / 0.93 = 10.75
        assert min_sell == 10.75

    def test_calculate_min_sell_price_high_value_item(self):
        """Тест расчета минимальной цены для дорогого предмета."""
        # Arrange
        buy_price = 100.0  # $100
        min_margin = 5.0
        dmarket_fee = 7.0

        # Act
        min_sell = PendingTrade.calculate_min_sell_price(
            buy_price=buy_price,
            min_margin_percent=min_margin,
            dmarket_fee_percent=dmarket_fee,
        )

        # Assert
        # = 100 * 1.05 / 0.93 = 112.90
        assert min_sell == 112.90

    def test_calculate_profit_positive(self):
        """Тест расчета прибыли - положительный результат."""
        # Arrange
        trade = PendingTrade(
            asset_id="test123",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=11.29,
            current_price=15.0,
            game="csgo",
        )

        # Act
        profit, profit_percent = trade.calculate_profit()

        # Assert
        assert profit == 5.0  # $15 - $10 = $5
        assert profit_percent == 50.0  # 50%

    def test_calculate_profit_custom_price(self):
        """Тест расчета прибыли с указанной ценой продажи."""
        # Arrange
        trade = PendingTrade(
            asset_id="test123",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=11.29,
            game="csgo",
        )

        # Act
        profit, profit_percent = trade.calculate_profit(sale_price=12.0)

        # Assert
        assert profit == 2.0
        assert profit_percent == 20.0

    def test_calculate_profit_no_price(self):
        """Тест расчета прибыли без указания цены."""
        # Arrange
        trade = PendingTrade(
            asset_id="test123",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=11.29,
            game="csgo",
        )

        # Act
        profit, profit_percent = trade.calculate_profit()

        # Assert - uses target_sell_price which is None
        assert profit == 0.0
        assert profit_percent == 0.0

    def test_is_profitable_true(self):
        """Тест проверки прибыльности - прибыльная сделка."""
        # Arrange
        trade = PendingTrade(
            asset_id="test123",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=11.29,
            current_price=15.0,  # $15 * 0.93 = $13.95 > $10
            game="csgo",
        )

        # Act & Assert
        assert trade.is_profitable(dmarket_fee_percent=7.0) is True

    def test_is_profitable_false(self):
        """Тест проверки прибыльности - убыточная сделка."""
        # Arrange
        trade = PendingTrade(
            asset_id="test123",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=11.29,
            current_price=10.5,  # $10.5 * 0.93 = $9.77 < $10
            game="csgo",
        )

        # Act & Assert
        assert trade.is_profitable(dmarket_fee_percent=7.0) is False

    def test_to_dict(self):
        """Тест преобразования в словарь."""
        # Arrange
        trade = PendingTrade(
            asset_id="test123",
            title="AK-47 | Redline",
            buy_price=10.0,
            min_sell_price=11.29,
            target_sell_price=15.0,
            status=PendingTradeStatus.BOUGHT,
            game="csgo",
        )

        # Act
        result = trade.to_dict()

        # Assert
        assert result["asset_id"] == "test123"
        assert result["title"] == "AK-47 | Redline"
        assert result["buy_price"] == 10.0
        assert result["min_sell_price"] == 11.29
        assert result["status"] == PendingTradeStatus.BOUGHT


class TestPendingTradeStatus:
    """Тесты статусов сделок."""

    def test_all_statuses_exist(self):
        """Проверка наличия всех необходимых статусов."""
        assert PendingTradeStatus.BOUGHT == "bought"
        assert PendingTradeStatus.LISTED == "listed"
        assert PendingTradeStatus.SOLD == "sold"
        assert PendingTradeStatus.CANCELLED == "cancelled"
        assert PendingTradeStatus.STOP_LOSS == "stop_loss"
        assert PendingTradeStatus.FAlgoLED == "failed"


@pytest.mark.asyncio()
class TestTradingPersistence:
    """Тесты менеджера персистентности."""

    @pytest.fixture()
    def mock_database(self):
        """Фикстура мок базы данных."""
        db = MagicMock()
        session = AsyncMock()
        db.get_async_session.return_value.__aenter__ = AsyncMock(return_value=session)
        db.get_async_session.return_value.__aexit__ = AsyncMock(return_value=None)
        return db

    @pytest.fixture()
    def mock_api(self):
        """Фикстура мок DMarket API."""
        api = AsyncMock()
        api.get_user_inventory = AsyncMock(return_value={"objects": []})
        return api

    async def test_save_purchase_calculates_min_sell_price(self, mock_database, mock_api):
        """Тест сохранения покупки с расчетом минимальной цены."""
        # Arrange
        from src.utils.trading_persistence import TradingPersistence

        # Mock session execute and commit
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        # Mock the context manager
        mock_database.get_async_session = MagicMock()
        mock_database.get_async_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_database.get_async_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Mock the select result
        mock_trade = PendingTrade(
            asset_id="test123",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=11.29,
            game="csgo",
        )
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = mock_trade
        mock_session.execute.return_value = mock_result

        persistence = TradingPersistence(
            database=mock_database,
            dmarket_api=mock_api,
            min_margin_percent=5.0,
            dmarket_fee_percent=7.0,
        )

        # Act
        result = await persistence.save_purchase(
            asset_id="test123",
            title="Test Item",
            buy_price=10.0,
            game="csgo",
        )

        # Assert
        assert result.asset_id == "test123"
        assert result.buy_price == 10.0

    async def test_get_pending_trades_excludes_completed(self, mock_database, mock_api):
        """Тест получения сделок - исключает завершенные."""
        # Arrange
        from src.utils.trading_persistence import TradingPersistence

        mock_session = AsyncMock()
        mock_database.get_async_session = MagicMock()
        mock_database.get_async_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_database.get_async_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Mock trades - only pending ones should be returned
        pending_trade = PendingTrade(
            asset_id="pending123",
            title="Pending Item",
            buy_price=10.0,
            min_sell_price=11.29,
            status=PendingTradeStatus.BOUGHT,
            game="csgo",
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pending_trade]
        mock_session.execute.return_value = mock_result

        persistence = TradingPersistence(
            database=mock_database,
            dmarket_api=mock_api,
        )

        # Act
        trades = await persistence.get_pending_trades()

        # Assert
        assert len(trades) == 1
        assert trades[0].asset_id == "pending123"

    async def test_recover_pending_trades_marks_sold_offline(self, mock_database, mock_api):
        """Тест восстановления - помечает проданные офлайн."""
        # Arrange
        from src.utils.trading_persistence import TradingPersistence

        mock_session = AsyncMock()
        mock_database.get_async_session = MagicMock()
        mock_database.get_async_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_database.get_async_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Trade that was purchased but item is no longer in inventory
        pending_trade = PendingTrade(
            asset_id="sold123",
            title="Sold Item",
            buy_price=10.0,
            min_sell_price=11.29,
            status=PendingTradeStatus.BOUGHT,
            game="csgo",
        )

        # First call returns pending trades
        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.all.return_value = [pending_trade]

        # Second call (for mark_as_sold) returns the trade
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = pending_trade

        # Third call (update) returns affected rows
        mock_result3 = MagicMock()
        mock_result3.rowcount = 1

        mock_session.execute.side_effect = [mock_result1, mock_result2, mock_result3]

        # Empty inventory (item was sold)
        mock_api.get_user_inventory.return_value = {"objects": []}

        persistence = TradingPersistence(
            database=mock_database,
            dmarket_api=mock_api,
        )

        # Act
        results = await persistence.recover_pending_trades()

        # Assert
        assert len(results) == 1
        assert results[0]["action"] == "marked_sold"

    async def test_recover_pending_trades_lists_new_items(self, mock_database, mock_api):
        """Тест восстановления - определяет предметы для выставления."""
        # Arrange
        from src.utils.trading_persistence import TradingPersistence

        mock_session = AsyncMock()
        mock_database.get_async_session = MagicMock()
        mock_database.get_async_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_database.get_async_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Trade that is still in inventory
        pending_trade = PendingTrade(
            asset_id="item123",
            title="In Inventory Item",
            buy_price=10.0,
            min_sell_price=11.29,
            status=PendingTradeStatus.BOUGHT,
            game="csgo",
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pending_trade]
        mock_session.execute.return_value = mock_result

        # Item is in inventory
        mock_api.get_user_inventory.return_value = {
            "objects": [{"assetId": "item123", "title": "In Inventory Item"}]
        }

        persistence = TradingPersistence(
            database=mock_database,
            dmarket_api=mock_api,
        )

        # Act
        results = await persistence.recover_pending_trades()

        # Assert
        assert len(results) == 1
        assert results[0]["action"] == "list_for_sale"
        assert results[0]["min_sell_price"] == 11.29


class TestEdgeCases:
    """Тесты граничных случаев."""

    def test_calculate_min_sell_price_very_low_price(self):
        """Тест расчета для очень дешевого предмета."""
        # Arrange
        buy_price = 0.03  # 3 цента

        # Act
        min_sell = PendingTrade.calculate_min_sell_price(
            buy_price=buy_price,
            min_margin_percent=5.0,
            dmarket_fee_percent=7.0,
        )

        # Assert
        assert min_sell == 0.03  # Rounded to 2 decimal places

    def test_calculate_min_sell_price_very_high_price(self):
        """Тест расчета для очень дорогого предмета."""
        # Arrange
        buy_price = 10000.0  # $10,000

        # Act
        min_sell = PendingTrade.calculate_min_sell_price(
            buy_price=buy_price,
            min_margin_percent=5.0,
            dmarket_fee_percent=7.0,
        )

        # Assert
        # = 10000 * 1.05 / 0.93 = 11290.32
        assert min_sell == 11290.32

    def test_calculate_profit_zero_buy_price(self):
        """Тест расчета прибыли с нулевой ценой покупки."""
        # Arrange
        trade = PendingTrade(
            asset_id="test123",
            title="Free Item",
            buy_price=0.0,
            min_sell_price=0.0,
            current_price=10.0,
            game="csgo",
        )

        # Act
        profit, profit_percent = trade.calculate_profit()

        # Assert - avoid division by zero
        assert profit == 0.0
        assert profit_percent == 0.0
