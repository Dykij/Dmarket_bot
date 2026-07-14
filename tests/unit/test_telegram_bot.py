"""
Unit tests for src.telegram.bot — the deprecated legacy Telegram bot.

Focuses on command handler logic and the _admin_only decorator.
Since the module is hard-blocked at import time (RuntimeError unless
ALLOW_LEGACY_TELEGRAM_BOT=1), all tests set that env var.

Coverage:
- _is_admin: admin check logic
- _admin_only decorator: rejects non-admins
- cmd_start: response format
- btn_status: response with bot stats
- cmd_prices: response format
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# =====================================================================
# Module import with legacy bypass
# =====================================================================

@pytest.fixture(autouse=True)
def _allow_legacy_bot(monkeypatch: pytest.MonkeyPatch):
    """Set env var to allow importing the deprecated bot module."""
    monkeypatch.setenv("ALLOW_LEGACY_TELEGRAM_BOT", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "123456789,987654321")


def _import_bot():
    """Import the bot module with legacy bypass active."""
    # Force reimport to pick up env vars
    if "src.telegram.bot" in sys.modules:
        del sys.modules["src.telegram.bot"]
    # Also clear dependencies that may have been imported
    for key in list(sys.modules.keys()):
        if key.startswith("src.telegram.bot"):
            del sys.modules[key]

    import src.telegram.bot as bot_module
    return bot_module


def _make_message(text: str = "/start", user_id: int = 123456789) -> MagicMock:
    """Create a mock aiogram Message object."""
    msg = MagicMock()
    msg.text = text
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    return msg


# =====================================================================
# test_cmd_start
# =====================================================================

class TestCmdStart:
    """Verify /start response."""

    @pytest.mark.asyncio
    async def test_start_returns_welcome_message(self) -> None:
        bot = _import_bot()
        msg = _make_message("/start", user_id=123456789)

        with patch.object(bot, "OracleFactory") as mock_oracle:
            mock_oracle.get_cross_market_oracle.return_value = None
            with patch.object(bot.Config, "DRY_RUN", True):
                await bot.cmd_start(msg)

        msg.answer.assert_called_once()
        call_text = msg.answer.call_args[0][0]
        assert "DMarket Quantitative Engine" in call_text
        assert "SIMULATION" in call_text

    @pytest.mark.asyncio
    async def test_start_shows_live_mode(self) -> None:
        bot = _import_bot()
        msg = _make_message("/start", user_id=123456789)

        with patch.object(bot, "OracleFactory") as mock_oracle:
            mock_oracle.get_cross_market_oracle.return_value = MagicMock()
            with patch.object(bot.Config, "DRY_RUN", False):
                await bot.cmd_start(msg)

        call_text = msg.answer.call_args[0][0]
        assert "LIVE TRADING" in call_text

    @pytest.mark.asyncio
    async def test_start_rejects_non_admin(self) -> None:
        bot = _import_bot()
        msg = _make_message("/start", user_id=999999999)  # not in ADMIN_IDS

        await bot.cmd_start(msg)
        msg.answer.assert_not_called()


# =====================================================================
# test_cmd_status
# =====================================================================

class TestCmdStatus:
    """Verify /status response with bot stats."""

    @pytest.mark.asyncio
    async def test_status_shows_running(self) -> None:
        bot = _import_bot()
        bot.is_running = True
        msg = _make_message("STATUS", user_id=123456789)

        with patch.object(bot, "OracleFactory") as mock_oracle, \
             patch.object(bot, "price_db") as mock_db, \
             patch.object(bot.Config, "DRY_RUN", True), \
             patch.object(bot.Config, "ACTIVE_STRATEGY", "ValueScanner"), \
             patch.object(bot.Config, "MIN_SPREAD_PCT", 7.0), \
             patch.object(bot.Config, "MAX_DAILY_TRADES", 200):

            mock_oracle.get_cross_market_oracle.return_value = None
            # run_in_thread is called 3 times:
            # 1) max_ts_row fetchone → (0,)
            # 2) state_conn.execute(...) → object with .fetchone()
            # 3) daily_trades_row.fetchone → (5,)
            mock_fetch_result = MagicMock()
            mock_fetch_result.fetchone.return_value = (5,)
            mock_db.run_in_thread = AsyncMock(side_effect=[
                (0,),              # call 1: max_ts_row
                mock_fetch_result, # call 2: daily_trades_row (has .fetchone)
                (5,),              # call 3: fetchone() result
            ])

            await bot.btn_status(msg)

        msg.answer.assert_called_once()
        call_text = msg.answer.call_args[0][0]
        assert "RUNNING" in call_text

    @pytest.mark.asyncio
    async def test_status_shows_stopped(self) -> None:
        bot = _import_bot()
        bot.is_running = False
        msg = _make_message("STATUS", user_id=123456789)

        with patch.object(bot, "OracleFactory") as mock_oracle, \
             patch.object(bot, "price_db") as mock_db, \
             patch.object(bot.Config, "DRY_RUN", False), \
             patch.object(bot.Config, "ACTIVE_STRATEGY", "ValueScanner"), \
             patch.object(bot.Config, "MIN_SPREAD_PCT", 7.0), \
             patch.object(bot.Config, "MAX_DAILY_TRADES", 200):

            mock_oracle.get_cross_market_oracle.return_value = MagicMock()
            mock_fetch_result = MagicMock()
            mock_fetch_result.fetchone.return_value = (0,)
            mock_db.run_in_thread = AsyncMock(side_effect=[
                (0,),              # max_ts_row
                mock_fetch_result, # daily_trades_row
                (0,),              # fetchone result
            ])

            await bot.btn_status(msg)

        call_text = msg.answer.call_args[0][0]
        assert "STOPPED" in call_text
        assert "LIVE" in call_text

    @pytest.mark.asyncio
    async def test_status_rejects_non_admin(self) -> None:
        bot = _import_bot()
        msg = _make_message("STATUS", user_id=999999999)

        await bot.btn_status(msg)
        msg.answer.assert_not_called()


# =====================================================================
# test_cmd_prices
# =====================================================================

class TestCmdPrices:
    """Verify /prices response format."""

    @pytest.mark.asyncio
    async def test_prices_with_items(self) -> None:
        bot = _import_bot()
        msg = _make_message("/prices", user_id=123456789)

        mock_api = AsyncMock()
        mock_inv_mgr = MagicMock()
        mock_inv_mgr.check_held_items_prices = AsyncMock(return_value=[
            {"title": "AK-47 | Redline (FT)", "buy_price": 12.50,
             "oracle_price": 15.00, "unrealized_pnl_pct": 20.0},
            {"title": "AWP | Atheris (FT)", "buy_price": 5.00,
             "oracle_price": 4.50, "unrealized_pnl_pct": -10.0},
        ])

        with patch.object(bot, "_get_api_client", return_value=mock_api), \
             patch.object(bot, "InventoryManager", return_value=mock_inv_mgr):

            await bot.cmd_prices(msg)

        msg.answer.assert_called_once()
        call_text = msg.answer.call_args[0][0]
        assert "ORACLE PRICES" in call_text
        assert "AK-47 | Redline (FT)" in call_text
        assert "+20.0%" in call_text

    @pytest.mark.asyncio
    async def test_prices_no_items(self) -> None:
        bot = _import_bot()
        msg = _make_message("/prices", user_id=123456789)

        mock_api = AsyncMock()
        mock_inv_mgr = MagicMock()
        mock_inv_mgr.check_held_items_prices = AsyncMock(return_value=[])

        with patch.object(bot, "_get_api_client", return_value=mock_api), \
             patch.object(bot, "InventoryManager", return_value=mock_inv_mgr):

            await bot.cmd_prices(msg)

        msg.answer.assert_called_once()
        call_text = msg.answer.call_args[0][0]
        assert "No items" in call_text

    @pytest.mark.asyncio
    async def test_prices_rejects_non_admin(self) -> None:
        bot = _import_bot()
        msg = _make_message("/prices", user_id=999999999)

        await bot.cmd_prices(msg)
        msg.answer.assert_not_called()


# =====================================================================
# test_admin_only_decorator
# =====================================================================

class TestAdminOnlyDecorator:
    """Verify non-admin users are rejected."""

    @pytest.mark.asyncio
    async def test_admin_id_allowed(self) -> None:
        bot = _import_bot()
        msg = _make_message("/start", user_id=123456789)  # in ADMIN_IDS

        with patch.object(bot, "OracleFactory") as mock_oracle:
            mock_oracle.get_cross_market_oracle.return_value = None
            with patch.object(bot.Config, "DRY_RUN", True):
                await bot.cmd_start(msg)

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_admin_id_rejected(self) -> None:
        bot = _import_bot()
        msg = _make_message("/start", user_id=111111111)  # NOT in ADMIN_IDS

        await bot.cmd_start(msg)
        msg.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_user_id_rejected(self) -> None:
        bot = _import_bot()
        msg = _make_message("/start", user_id=None)
        msg.from_user = None

        await bot.cmd_start(msg)
        msg.answer.assert_not_called()

    def test_is_admin_true_for_known_id(self) -> None:
        bot = _import_bot()
        assert bot._is_admin(123456789) is True

    def test_is_admin_false_for_unknown_id(self) -> None:
        bot = _import_bot()
        assert bot._is_admin(111111111) is False

    def test_is_admin_false_for_none(self) -> None:
        bot = _import_bot()
        assert bot._is_admin(None) is False

    def test_second_admin_id_works(self) -> None:
        bot = _import_bot()
        assert bot._is_admin(987654321) is True

    @pytest.mark.asyncio
    async def test_btn_help_rejects_non_admin(self) -> None:
        bot = _import_bot()
        msg = _make_message("/help", user_id=999999999)

        await bot.cmd_help(msg)
        msg.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_btn_config_rejects_non_admin(self) -> None:
        bot = _import_bot()
        msg = _make_message("CONFIG", user_id=999999999)

        await bot.btn_config(msg)
        msg.answer.assert_not_called()


# =====================================================================
# test_module_hard_block
# =====================================================================

class TestModuleHardBlock:
    """Verify the module raises RuntimeError without the env var."""

    def test_import_without_env_var_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ALLOW_LEGACY_TELEGRAM_BOT", raising=False)
        # Clear cached module
        if "src.telegram.bot" in sys.modules:
            del sys.modules["src.telegram.bot"]

        with pytest.raises(RuntimeError, match="DEPRECATED"):
            import src.telegram.bot  # noqa: F401

    def test_import_with_env_var_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALLOW_LEGACY_TELEGRAM_BOT", "1")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
        if "src.telegram.bot" in sys.modules:
            del sys.modules["src.telegram.bot"]

        # Should not raise
        import src.telegram.bot  # noqa: F401
