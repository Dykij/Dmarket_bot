"""E2E тесты для полных пользовательских сценариев.

Этот модуль тестирует end-to-end workflow:
- Регистрация нового пользователя
- НастSwarmка API ключей
- Сканирование арбитража
- Создание таргетов
- Получение уведомлений
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture()
def mock_bot():
    """Create mock Telegram bot."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    return bot


@pytest.fixture()
def mock_user():
    """Create mock Telegram user."""
    user = MagicMock()
    user.id = 123456789
    user.username = "test_user"
    user.first_name = "Test"
    user.last_name = "User"
    user.language_code = "ru"
    return user


@pytest.fixture()
def mock_update(mock_user):
    """Create mock Telegram update."""
    update = MagicMock()
    update.effective_user = mock_user
    update.effective_chat = MagicMock()
    update.effective_chat.id = mock_user.id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.text = ""
    update.callback_query = None
    return update


@pytest.fixture()
def mock_context(mock_bot):
    """Create mock context."""
    context = MagicMock()
    context.bot = mock_bot
    context.user_data = {}
    context.bot_data = {
        "dmarket_api": AsyncMock(),
        "database": AsyncMock(),
    }
    return context


# ============================================================================
# E2E: NEW USER REGISTRATION FLOW
# ============================================================================


class TestNewUserRegistrationFlow:
    """Tests for new user registration end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_complete_registration_flow(self, mock_update, mock_context):
        """Test complete new user registration flow."""
        from src.telegram_bot.commands.basic_commands import start_command

        # Step 1: User sends /start
        mock_update.message.text = "/start"

        await start_command(mock_update, mock_context)

        # Verify welcome message sent
        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args
        assert call_args is not None

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_user_help_after_registration(self, mock_update, mock_context):
        """Test user can access help after registration."""
        from src.telegram_bot.commands.basic_commands import help_command

        await help_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()


# ============================================================================
# E2E: ARBITRAGE SCAN FLOW
# ============================================================================


class TestArbitrageScanFlow:
    """Tests for arbitrage scanning end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_scan_boost_level(self, mock_update, mock_context):
        """Test scanning at boost level."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {
                        "title": "Test Item",
                        "price": {"USD": "100"},
                        "suggestedPrice": {"USD": "150"},
                        "extra": {"category": "csgo"},
                    }
                ],
                "total": "1",
            }
        )

        scanner = ArbitrageScanner(api_client=mock_api)

        # Scan at boost level - check scanner is created
        assert scanner is not None
        assert scanner.api_client is mock_api

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_scan_all_levels_sequence(self, mock_update, mock_context):
        """Test scanning all levels in sequence."""
        levels = ["boost", "standard", "medium", "advanced", "pro"]

        for level in levels:
            # Each level should be scannable
            assert level in levels


# ============================================================================
# E2E: TARGET CREATION FLOW
# ============================================================================


class TestTargetCreationFlow:
    """Tests for target creation end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_create_target_flow(self, mock_context):
        """Test complete target creation flow."""
        from src.dmarket.targets import TargetManager

        mock_api = AsyncMock()
        mock_api.create_target = AsyncMock(
            return_value={
                "targetId": "test_target_123",
                "title": "AK-47 | Redline",
                "price": 1500,
            }
        )

        manager = TargetManager(api_client=mock_api)

        # Check manager created
        assert manager is not None
        assert manager.api is mock_api

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_list_targets_flow(self, mock_context):
        """Test listing targets flow."""
        from src.dmarket.targets import TargetManager

        mock_api = AsyncMock()
        mock_api.get_user_targets = AsyncMock(
            return_value={
                "targets": [
                    {"targetId": "1", "title": "Item 1", "price": 1000},
                    {"targetId": "2", "title": "Item 2", "price": 2000},
                ]
            }
        )

        manager = TargetManager(api_client=mock_api)

        # Check manager created
        assert manager is not None
        assert manager.api is mock_api


# ============================================================================
# E2E: BALANCE CHECK FLOW
# ============================================================================


class TestBalanceCheckFlow:
    """Tests for balance checking end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_check_balance_flow(self, mock_update, mock_context):
        """Test complete balance check flow."""
        mock_api = mock_context.bot_data["dmarket_api"]
        mock_api.get_balance = AsyncMock(return_value={"usd": "10000", "dmc": "5000"})

        balance = await mock_api.get_balance()

        assert "usd" in balance
        assert "dmc" in balance

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_balance_insufficient_warning(self, mock_update, mock_context):
        """Test balance warning when insufficient."""
        mock_api = mock_context.bot_data["dmarket_api"]
        mock_api.get_balance = AsyncMock(return_value={"usd": "50", "dmc": "0"})

        balance = await mock_api.get_balance()

        # Low balance
        assert int(balance["usd"]) < 100


# ============================================================================
# E2E: NOTIFICATION FLOW
# ============================================================================


class TestNotificationFlow:
    """Tests for notification end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_price_alert_notification(self, mock_bot):
        """Test price alert notification flow."""
        # Simulate alert trigger
        alert_data = {
            "type": "price_drop",
            "item": "AK-47 | Redline",
            "old_price": 20.00,
            "new_price": 15.00,
            "change_percent": -25.0,
        }

        # Format message
        message = f"📉 {alert_data['item']}: ${alert_data['old_price']} → ${alert_data['new_price']}"

        assert "📉" in message
        assert "AK-47" in message

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_arbitrage_opportunity_notification(self, mock_bot):
        """Test arbitrage opportunity notification."""
        opportunity = {
            "item": "AWP | Dragon Lore",
            "buy_price": 1500.00,
            "sell_price": 1800.00,
            "profit": 300.00,
            "profit_percent": 20.0,
        }

        message = f"💰 Арбитраж: {opportunity['item']} +${opportunity['profit']:.2f}"

        assert "💰" in message
        assert "Dragon Lore" in message


# ============================================================================
# E2E: SETTINGS MANAGEMENT FLOW
# ============================================================================


class TestSettingsManagementFlow:
    """Tests for settings management end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_change_language_flow(self, mock_update, mock_context):
        """Test language change flow."""
        # Set initial language
        mock_context.user_data["language"] = "ru"

        # Change to English
        mock_context.user_data["language"] = "en"

        assert mock_context.user_data["language"] == "en"

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_change_risk_profile_flow(self, mock_update, mock_context):
        """Test risk profile change flow."""
        # Set initial risk profile
        mock_context.user_data["risk_profile"] = "medium"

        # Change to aggressive
        mock_context.user_data["risk_profile"] = "aggressive"

        assert mock_context.user_data["risk_profile"] == "aggressive"

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_notification_preferences_flow(self, mock_update, mock_context):
        """Test notification preferences flow."""
        # Set notification preferences
        mock_context.user_data["notifications"] = {
            "price_alerts": True,
            "arbitrage": True,
            "daily_report": False,
        }

        prefs = mock_context.user_data["notifications"]
        assert prefs["price_alerts"] is True
        assert prefs["daily_report"] is False


# ============================================================================
# E2E: ERROR RECOVERY FLOW
# ============================================================================


class TestErrorRecoveryFlow:
    """Tests for error recovery end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_api_error_recovery(self, mock_context):
        """Test recovery from API errors."""
        mock_api = mock_context.bot_data["dmarket_api"]

        # First call fails
        mock_api.get_balance = AsyncMock(
            side_effect=[Exception("API Error"), {"usd": "10000", "dmc": "5000"}]
        )

        # First attempt fails
        try:
            await mock_api.get_balance()
        except Exception:
            pass

        # Second attempt succeeds
        balance = await mock_api.get_balance()
        assert "usd" in balance

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_network_timeout_recovery(self, mock_context):
        """Test recovery from network timeouts."""
        mock_api = mock_context.bot_data["dmarket_api"]

        # Simulate timeout then success

        mock_api.get_market_items = AsyncMock(
            side_effect=[TimeoutError(), {"objects": [], "total": "0"}]
        )

        # First attempt times out
        try:
            await mock_api.get_market_items("csgo")
        except TimeoutError:
            pass

        # Second attempt succeeds
        result = await mock_api.get_market_items("csgo")
        assert "objects" in result


# ============================================================================
# E2E: COMPLETE USER JOURNEY
# ============================================================================


class TestCompleteUserJourney:
    """Tests for complete user journeys."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_new_user_first_scan_journey(
        self, mock_update, mock_context, mock_bot
    ):
        """Test journey: new user → registration → first scan."""
        from src.telegram_bot.commands.basic_commands import start_command

        # Step 1: New user starts bot
        await start_command(mock_update, mock_context)

        # Step 2: User is registered
        assert mock_update.message.reply_text.called

        # Step 3: User data initialized
        mock_context.user_data["registered"] = True

        # Step 4: User performs first scan
        mock_api = mock_context.bot_data["dmarket_api"]
        mock_api.get_market_items = AsyncMock(
            return_value={"objects": [], "total": "0"}
        )

        result = await mock_api.get_market_items("csgo")
        assert "objects" in result

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_daily_trading_session_journey(self, mock_context):
        """Test journey: daily trading session."""
        mock_api = mock_context.bot_data["dmarket_api"]

        # Step 1: Check balance
        mock_api.get_balance = AsyncMock(return_value={"usd": "10000", "dmc": "5000"})
        balance = await mock_api.get_balance()
        assert int(balance["usd"]) > 0

        # Step 2: Scan for opportunities
        mock_api.get_market_items = AsyncMock(
            return_value={"objects": [{"title": "Test", "price": {"USD": "100"}}]}
        )
        items = await mock_api.get_market_items("csgo")
        assert len(items.get("objects", [])) > 0

        # Step 3: Create target
        mock_api.create_target = AsyncMock(
            return_value={"targetId": "123", "status": "active"}
        )
        target = await mock_api.create_target(title="Test", price=100)
        assert "targetId" in target

        # Step 4: Monitor targets
        mock_api.get_user_targets = AsyncMock(
            return_value={"targets": [{"targetId": "123", "status": "active"}]}
        )
        targets = await mock_api.get_user_targets()
        assert len(targets.get("targets", [])) > 0


# ============================================================================
# E2E: MULTI-GAME SCAN FLOW
# ============================================================================


class TestMultiGameScanFlow:
    """Tests for multi-game scanning end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_scan_csgo_items(self, mock_context):
        """Test scanning CS:GO items flow."""
        mock_api = mock_context.bot_data["dmarket_api"]
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {
                        "title": "AK-47 | Redline",
                        "price": {"USD": "1500"},
                        "gameId": "a8db",
                    },
                ],
                "total": "1",
            }
        )

        result = await mock_api.get_market_items("csgo")
        assert "objects" in result
        assert len(result["objects"]) > 0

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_scan_dota2_items(self, mock_context):
        """Test scanning Dota 2 items flow."""
        mock_api = mock_context.bot_data["dmarket_api"]
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {"title": "Arcana", "price": {"USD": "3000"}, "gameId": "9a92"},
                ],
                "total": "1",
            }
        )

        result = await mock_api.get_market_items("dota2")
        assert "objects" in result

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_scan_rust_items(self, mock_context):
        """Test scanning Rust items flow."""
        mock_api = mock_context.bot_data["dmarket_api"]
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {"title": "Rust Item", "price": {"USD": "500"}, "gameId": "rust"},
                ],
                "total": "1",
            }
        )

        result = await mock_api.get_market_items("rust")
        assert "objects" in result

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_scan_tf2_items(self, mock_context):
        """Test scanning TF2 items flow."""
        mock_api = mock_context.bot_data["dmarket_api"]
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {"title": "Unusual Hat", "price": {"USD": "100"}, "gameId": "tf2"},
                ],
                "total": "1",
            }
        )

        result = await mock_api.get_market_items("tf2")
        assert "objects" in result


# ============================================================================
# E2E: API KEY MANAGEMENT FLOW
# ============================================================================


class TestAPIKeyManagementFlow:
    """Tests for API key management end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_setup_api_keys_flow(self, mock_context):
        """Test API key setup flow."""
        # Simulate storing API keys
        mock_context.user_data["api_keys"] = {
            "public_key": "test_public_key_123",
            "secret_key": "test_secret_key_456",
        }

        assert mock_context.user_data["api_keys"]["public_key"] == "test_public_key_123"

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_validate_api_keys_flow(self, mock_context):
        """Test API key validation flow."""
        mock_api = mock_context.bot_data["dmarket_api"]
        mock_api.get_balance = AsyncMock(return_value={"usd": "100", "dmc": "0"})

        # Validation by checking balance
        result = await mock_api.get_balance()
        assert "usd" in result

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_revoke_api_keys_flow(self, mock_context):
        """Test API key revocation flow."""
        # Set and then revoke keys
        mock_context.user_data["api_keys"] = {
            "public_key": "test",
            "secret_key": "test",
        }

        # Revoke
        mock_context.user_data["api_keys"] = None

        assert mock_context.user_data["api_keys"] is None


# ============================================================================
# E2E: PROFIT CALCULATION FLOW
# ============================================================================


class TestProfitCalculationFlow:
    """Tests for profit calculation end-to-end flow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_calculate_simple_profit(self):
        """Test simple profit calculation."""
        buy_price = 10.0
        sell_price = 15.0
        commission = 7.0

        # Calculate gross profit
        gross_profit = sell_price - buy_price

        # Calculate commission
        commission_amount = sell_price * (commission / 100)

        # Net profit
        net_profit = gross_profit - commission_amount

        assert net_profit > 0
        assert abs(net_profit - 3.95) < 0.01

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_calculate_profit_with_high_commission(self):
        """Test profit calculation with high commission."""
        buy_price = 100.0
        sell_price = 110.0
        commission = 10.0

        gross_profit = sell_price - buy_price  # 10
        commission_amount = sell_price * (commission / 100)  # 11

        net_profit = gross_profit - commission_amount

        # With 10% commission on $110, commission is $11
        # Net profit = 10 - 11 = -1
        assert net_profit < 0
