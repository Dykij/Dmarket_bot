"""Tests for trading_notifier module.

Comprehensive tests for TradingNotifier class and helper functions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.trading_notifier import TradingNotifier, buy_with_notifications


class TestTradingNotifier:
    """Tests for TradingNotifier class."""

    @pytest.fixture()
    def mock_api_client(self) -> MagicMock:
        """Create mock API client."""
        client = MagicMock()
        client.buy_item = AsyncMock(
            return_value={"success": True, "orderId": "test-order-123"}
        )
        client.sell_item = AsyncMock(
            return_value={"success": True, "orderId": "sell-order-456"}
        )
        return client

    @pytest.fixture()
    def mock_bot(self) -> MagicMock:
        """Create mock Telegram bot."""
        return MagicMock()

    @pytest.fixture()
    def mock_notification_queue(self) -> MagicMock:
        """Create mock notification queue."""
        return MagicMock()

    @pytest.fixture()
    def notifier(
        self,
        mock_api_client: MagicMock,
        mock_bot: MagicMock,
        mock_notification_queue: MagicMock,
    ) -> TradingNotifier:
        """Create TradingNotifier instance."""
        return TradingNotifier(
            api_client=mock_api_client,
            bot=mock_bot,
            notification_queue=mock_notification_queue,
            user_id=12345,
        )

    def test_init(
        self,
        mock_api_client: MagicMock,
        mock_bot: MagicMock,
        mock_notification_queue: MagicMock,
    ) -> None:
        """Test TradingNotifier initialization."""
        notifier = TradingNotifier(
            api_client=mock_api_client,
            bot=mock_bot,
            notification_queue=mock_notification_queue,
            user_id=12345,
        )

        assert notifier.api == mock_api_client
        assert notifier.bot == mock_bot
        assert notifier.notification_queue == mock_notification_queue
        assert notifier.user_id == 12345

    def test_init_minimal(self, mock_api_client: MagicMock) -> None:
        """Test TradingNotifier initialization with minimal params."""
        notifier = TradingNotifier(api_client=mock_api_client)

        assert notifier.api == mock_api_client
        assert notifier.bot is None
        assert notifier.notification_queue is None
        assert notifier.user_id is None

    def test_create_item_dict(self, notifier: TradingNotifier) -> None:
        """Test creating item dictionary."""
        item = notifier._create_item_dict("AK-47 | Redline", 15.50, "csgo")

        assert item["title"] == "AK-47 | Redline"
        assert item["price"]["USD"] == 1550  # Converted to cents
        assert item["game"] == "csgo"

    def test_create_item_dict_different_game(self, notifier: TradingNotifier) -> None:
        """Test creating item dictionary for different game."""
        item = notifier._create_item_dict("Arcana", 25.00, "dota2")

        assert item["title"] == "Arcana"
        assert item["price"]["USD"] == 2500
        assert item["game"] == "dota2"

    @pytest.mark.asyncio()
    async def test_buy_item_with_notifications_success(
        self, notifier: TradingNotifier, mock_api_client: MagicMock
    ) -> None:
        """Test successful buy with notifications."""
        with (
            patch(
                "src.utils.trading_notifier.send_buy_intent_notification",
                new_callable=AsyncMock,
            ) as mock_intent,
            patch(
                "src.utils.trading_notifier.send_buy_success_notification",
                new_callable=AsyncMock,
            ) as mock_success,
        ):
            result = await notifier.buy_item_with_notifications(
                item_id="item-123",
                item_name="AK-47 | Redline",
                buy_price=15.50,
                sell_price=20.00,
                game="csgo",
                source="arbitrage_scanner",
            )

            assert result["success"] is True
            mock_intent.assert_called_once()
            mock_success.assert_called_once()
            mock_api_client.buy_item.assert_called_once_with(
                item_id="item-123", price=15.50, game="csgo"
            )

    @pytest.mark.asyncio()
    async def test_buy_item_with_notifications_api_failure(
        self, notifier: TradingNotifier, mock_api_client: MagicMock
    ) -> None:
        """Test buy with notifications when API returns failure."""
        mock_api_client.buy_item = AsyncMock(
            return_value={"success": False, "error": "Insufficient balance"}
        )

        with (
            patch(
                "src.utils.trading_notifier.send_buy_intent_notification",
                new_callable=AsyncMock,
            ) as mock_intent,
            patch(
                "src.utils.trading_notifier.send_buy_failed_notification",
                new_callable=AsyncMock,
            ) as mock_failed,
        ):
            result = await notifier.buy_item_with_notifications(
                item_id="item-123",
                item_name="AK-47 | Redline",
                buy_price=15.50,
                sell_price=20.00,
            )

            assert result["success"] is False
            mock_intent.assert_called_once()
            mock_failed.assert_called_once()

    @pytest.mark.asyncio()
    async def test_buy_item_with_notifications_exception(
        self, notifier: TradingNotifier, mock_api_client: MagicMock
    ) -> None:
        """Test buy with notifications when API raises exception."""
        mock_api_client.buy_item = AsyncMock(side_effect=Exception("Network error"))

        with (
            patch(
                "src.utils.trading_notifier.send_buy_intent_notification",
                new_callable=AsyncMock,
            ),
            patch(
                "src.utils.trading_notifier.send_buy_failed_notification",
                new_callable=AsyncMock,
            ) as mock_failed,
        ):
            with pytest.raises(Exception, match="Network error"):
                await notifier.buy_item_with_notifications(
                    item_id="item-123",
                    item_name="AK-47 | Redline",
                    buy_price=15.50,
                    sell_price=20.00,
                )

            mock_failed.assert_called_once()

    @pytest.mark.asyncio()
    async def test_buy_item_without_bot(self, mock_api_client: MagicMock) -> None:
        """Test buy when bot is not configured."""
        notifier = TradingNotifier(api_client=mock_api_client)

        result = await notifier.buy_item_with_notifications(
            item_id="item-123",
            item_name="AK-47 | Redline",
            buy_price=15.50,
            sell_price=20.00,
        )

        assert result["success"] is True
        mock_api_client.buy_item.assert_called_once()

    @pytest.mark.asyncio()
    async def test_sell_item_with_notifications_success(
        self, notifier: TradingNotifier, mock_api_client: MagicMock
    ) -> None:
        """Test successful sell with notifications."""
        with patch(
            "src.utils.trading_notifier.send_sell_success_notification",
            new_callable=AsyncMock,
        ) as mock_success:
            result = await notifier.sell_item_with_notifications(
                item_id="item-123",
                item_name="AK-47 | Redline",
                buy_price=15.50,
                sell_price=20.00,
                game="csgo",
            )

            assert result["success"] is True
            mock_success.assert_called_once()
            mock_api_client.sell_item.assert_called_once_with(
                item_id="item-123", price=20.00, game="csgo"
            )

    @pytest.mark.asyncio()
    async def test_sell_item_with_notifications_failure(
        self, notifier: TradingNotifier, mock_api_client: MagicMock
    ) -> None:
        """Test sell with notifications when API returns failure."""
        mock_api_client.sell_item = AsyncMock(
            return_value={"success": False, "error": "Item not found"}
        )

        result = await notifier.sell_item_with_notifications(
            item_id="item-123",
            item_name="AK-47 | Redline",
            buy_price=15.50,
            sell_price=20.00,
        )

        assert result["success"] is False

    @pytest.mark.asyncio()
    async def test_sell_item_with_notifications_exception(
        self, notifier: TradingNotifier, mock_api_client: MagicMock
    ) -> None:
        """Test sell with notifications when API raises exception."""
        mock_api_client.sell_item = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await notifier.sell_item_with_notifications(
                item_id="item-123",
                item_name="AK-47 | Redline",
                buy_price=15.50,
                sell_price=20.00,
            )

    @pytest.mark.asyncio()
    async def test_sell_item_without_bot(self, mock_api_client: MagicMock) -> None:
        """Test sell when bot is not configured."""
        notifier = TradingNotifier(api_client=mock_api_client)

        result = await notifier.sell_item_with_notifications(
            item_id="item-123",
            item_name="AK-47 | Redline",
            buy_price=15.50,
            sell_price=20.00,
        )

        assert result["success"] is True
        mock_api_client.sell_item.assert_called_once()


class TestBuyWithNotifications:
    """Tests for buy_with_notifications helper function."""

    @pytest.fixture()
    def mock_api_client(self) -> MagicMock:
        """Create mock API client."""
        client = MagicMock()
        client.buy_item = AsyncMock(
            return_value={"success": True, "orderId": "test-order-123"}
        )
        return client

    @pytest.fixture()
    def mock_bot(self) -> MagicMock:
        """Create mock Telegram bot."""
        return MagicMock()

    @pytest.mark.asyncio()
    async def test_buy_with_notifications_success(
        self, mock_api_client: MagicMock, mock_bot: MagicMock
    ) -> None:
        """Test successful buy using helper function."""
        with (
            patch(
                "src.utils.trading_notifier.send_buy_intent_notification",
                new_callable=AsyncMock,
            ),
            patch(
                "src.utils.trading_notifier.send_buy_success_notification",
                new_callable=AsyncMock,
            ),
        ):
            result = await buy_with_notifications(
                api_client=mock_api_client,
                bot=mock_bot,
                user_id=12345,
                item_id="item-123",
                item_name="AK-47 | Redline",
                buy_price=15.50,
                sell_price=20.00,
                game="csgo",
                source="test",
            )

            assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_buy_with_notifications_with_queue(
        self, mock_api_client: MagicMock, mock_bot: MagicMock
    ) -> None:
        """Test buy with notification queue."""
        mock_queue = MagicMock()

        with (
            patch(
                "src.utils.trading_notifier.send_buy_intent_notification",
                new_callable=AsyncMock,
            ),
            patch(
                "src.utils.trading_notifier.send_buy_success_notification",
                new_callable=AsyncMock,
            ),
        ):
            result = await buy_with_notifications(
                api_client=mock_api_client,
                bot=mock_bot,
                user_id=12345,
                item_id="item-123",
                item_name="AK-47 | Redline",
                buy_price=15.50,
                sell_price=20.00,
                notification_queue=mock_queue,
            )

            assert result["success"] is True


class TestTradingNotifierProfitCalculation:
    """Tests for profit calculation in notifications."""

    @pytest.fixture()
    def mock_api_client(self) -> MagicMock:
        """Create mock API client."""
        client = MagicMock()
        client.buy_item = AsyncMock(
            return_value={"success": True, "orderId": "test-order-123"}
        )
        return client

    @pytest.fixture()
    def mock_bot(self) -> MagicMock:
        """Create mock Telegram bot."""
        return MagicMock()

    @pytest.mark.asyncio()
    async def test_profit_calculation_in_notification(
        self, mock_api_client: MagicMock, mock_bot: MagicMock
    ) -> None:
        """Test that profit is correctly calculated in notification."""
        notifier = TradingNotifier(
            api_client=mock_api_client,
            bot=mock_bot,
            user_id=12345,
        )

        with (
            patch(
                "src.utils.trading_notifier.send_buy_intent_notification",
                new_callable=AsyncMock,
            ) as mock_intent,
            patch(
                "src.utils.trading_notifier.send_buy_success_notification",
                new_callable=AsyncMock,
            ),
        ):
            await notifier.buy_item_with_notifications(
                item_id="item-123",
                item_name="Test Item",
                buy_price=10.00,
                sell_price=15.00,  # 15 * 0.93 - 10 = 3.95 profit
                source="test",
            )

            # Check that intent notification was called with profit info in reason
            call_args = mock_intent.call_args
            assert call_args is not None
            reason = call_args.kwargs.get("reason", "")
            assert "Прибыль" in reason or "profit" in reason.lower()
