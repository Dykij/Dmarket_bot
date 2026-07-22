"""Tests for autonomous_scanner.py — main entry + error handling."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSetupLogging:

    def test_returns_none(self):
        from src.core.autonomous_scanner import setup_logging
        assert setup_logging() is None


class TestFormatProcessStats:

    def test_returns_string(self):
        from src.core.autonomous_scanner import _format_process_stats
        result = _format_process_stats()
        assert isinstance(result, str)

    def test_contains_info(self):
        from src.core.autonomous_scanner import _format_process_stats
        result = _format_process_stats()
        # Either psutil data or fallback
        assert "MB" in result or "unavailable" in result


class TestSendStartupNotification:

    @pytest.mark.asyncio
    async def test_success(self):
        from src.core.autonomous_scanner import _send_startup_notification
        with (
            patch("src.core.autonomous_scanner.Config") as mock_config,
            patch("src.telegram.notifier.notifier") as mock_notifier,
        ):
            mock_config.DRY_RUN = True
            mock_notifier.custom = AsyncMock()
            await _send_startup_notification(["a8db"])
            mock_notifier.custom.assert_called_once()

    @pytest.mark.asyncio
    async def test_dry_run_mode(self):
        from src.core.autonomous_scanner import _send_startup_notification
        with (
            patch("src.core.autonomous_scanner.Config") as mock_config,
            patch("src.telegram.notifier.notifier") as mock_notifier,
        ):
            mock_config.DRY_RUN = True
            mock_notifier.custom = AsyncMock()
            await _send_startup_notification(["a8db"])
            call_args = mock_notifier.custom.call_args[0][0]
            assert "DRY_RUN" in call_args

    @pytest.mark.asyncio
    async def test_live_mode(self):
        from src.core.autonomous_scanner import _send_startup_notification
        with (
            patch("src.core.autonomous_scanner.Config") as mock_config,
            patch("src.telegram.notifier.notifier") as mock_notifier,
        ):
            mock_config.DRY_RUN = False
            mock_notifier.custom = AsyncMock()
            await _send_startup_notification(["a8db"])
            call_args = mock_notifier.custom.call_args[0][0]
            assert "LIVE" in call_args

    @pytest.mark.asyncio
    async def test_notifier_failure_handled(self):
        from src.core.autonomous_scanner import _send_startup_notification
        with (
            patch("src.core.autonomous_scanner.Config") as mock_config,
            patch("src.telegram.notifier.notifier") as mock_notifier,
        ):
            mock_config.DRY_RUN = True
            mock_notifier.custom = AsyncMock(side_effect=Exception("Telegram down"))
            # Should not raise
            await _send_startup_notification(["a8db"])

    @pytest.mark.asyncio
    async def test_includes_game_ids(self):
        from src.core.autonomous_scanner import _send_startup_notification
        with (
            patch("src.core.autonomous_scanner.Config") as mock_config,
            patch("src.telegram.notifier.notifier") as mock_notifier,
        ):
            mock_config.DRY_RUN = True
            mock_notifier.custom = AsyncMock()
            await _send_startup_notification(["a8db", "csgo"])
            call_args = mock_notifier.custom.call_args[0][0]
            assert "a8db" in call_args


class TestModuleLevel:

    def test_base_dir_defined(self):
        from src.core.autonomous_scanner import BASE_DIR
        assert isinstance(BASE_DIR, str)
        assert len(BASE_DIR) > 0

    def test_use_v12_flag(self):
        from src.core.autonomous_scanner import _USE_V12
        assert isinstance(_USE_V12, bool)

    def test_logger_exists(self):
        from src.core.autonomous_scanner import logger
        assert logger is not None
        assert logger.name == "AutonomousScanner"


class TestRunAutonomousScanner:

    @pytest.mark.asyncio
    async def test_cancelled_exits_cleanly(self):
        from src.core.autonomous_scanner import run_autonomous_scanner
        with (
            patch("src.core.autonomous_scanner.load_dotenv"),
            patch("src.core.autonomous_scanner.vault") as mock_vault,
            patch.dict("os.environ", {"DMARKET_PUBLIC_KEY": "test_key"}),
            patch("src.core.autonomous_scanner.os.path.isfile", return_value=True),
            patch("src.core.autonomous_scanner._write_exit_state"),
            patch("src.core.autonomous_scanner.DMarketAPIClient"),
            patch("src.core.autonomous_scanner.InventoryManager"),
            patch("src.core.autonomous_scanner._send_startup_notification", new_callable=AsyncMock),
        ):
            mock_vault.get_dmarket_secret.return_value = "secret"
            with patch("src.core.autonomous_scanner.SnipingLoop") as mock_loop:
                mock_bot = MagicMock()
                mock_bot.target_games = ["a8db"]
                mock_bot.start = AsyncMock(side_effect=asyncio.CancelledError())
                mock_loop.return_value = mock_bot
                # Should return cleanly
                await run_autonomous_scanner()

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_exits(self):
        from src.core.autonomous_scanner import run_autonomous_scanner
        with (
            patch("src.core.autonomous_scanner.load_dotenv"),
            patch("src.core.autonomous_scanner.vault") as mock_vault,
            patch.dict("os.environ", {"DMARKET_PUBLIC_KEY": "test_key"}),
            patch("src.core.autonomous_scanner.os.path.isfile", return_value=True),
            patch("src.core.autonomous_scanner._write_exit_state"),
            patch("src.core.autonomous_scanner.DMarketAPIClient"),
            patch("src.core.autonomous_scanner.InventoryManager"),
            patch("src.core.autonomous_scanner._send_startup_notification", new_callable=AsyncMock),
        ):
            mock_vault.get_dmarket_secret.return_value = "secret"
            with patch("src.core.autonomous_scanner.SnipingLoop") as mock_loop:
                mock_bot = MagicMock()
                mock_bot.target_games = ["a8db"]
                mock_bot.start = AsyncMock(side_effect=KeyboardInterrupt())
                mock_loop.return_value = mock_bot
                await run_autonomous_scanner()

    @pytest.mark.asyncio
    async def test_config_error_calls_fatal_exit(self):
        from src.core.autonomous_scanner import run_autonomous_scanner
        # fatal_exit raises SystemExit to break the while loop
        with (
            patch("src.core.autonomous_scanner.load_dotenv"),
            patch("src.core.autonomous_scanner.vault") as mock_vault,
            patch.dict("os.environ", {"DMARKET_PUBLIC_KEY": ""}),
            patch("src.core.autonomous_scanner.os.path.isfile", return_value=True),
            patch("src.core.autonomous_scanner.fatal_exit", side_effect=SystemExit(2)),
        ):
            mock_vault.get_dmarket_secret.return_value = ""
            with pytest.raises(SystemExit):
                await run_autonomous_scanner()

    @pytest.mark.asyncio
    async def test_auth_error_calls_fatal_exit(self):
        from src.core.autonomous_scanner import run_autonomous_scanner
        from src.risk.fatal_errors import AuthError
        with (
            patch("src.core.autonomous_scanner.load_dotenv"),
            patch("src.core.autonomous_scanner.vault") as mock_vault,
            patch.dict("os.environ", {"DMARKET_PUBLIC_KEY": "test_key"}),
            patch("src.core.autonomous_scanner.os.path.isfile", return_value=True),
            patch("src.core.autonomous_scanner.fatal_exit", side_effect=SystemExit(3)),
            patch("src.core.autonomous_scanner.DMarketAPIClient"),
            patch("src.core.autonomous_scanner.InventoryManager"),
            patch("src.core.autonomous_scanner._send_startup_notification", new_callable=AsyncMock),
        ):
            mock_vault.get_dmarket_secret.return_value = "secret"
            with patch("src.core.autonomous_scanner.SnipingLoop") as mock_loop:
                mock_bot = MagicMock()
                mock_bot.target_games = ["a8db"]
                mock_bot.start = AsyncMock(side_effect=AuthError("bad auth"))
                mock_loop.return_value = mock_bot
                with pytest.raises(SystemExit):
                    await run_autonomous_scanner()

    @pytest.mark.asyncio
    async def test_transient_error_retries_then_exits(self):
        from src.core.autonomous_scanner import run_autonomous_scanner
        call_count = 0

        async def _start():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()
            raise ConnectionError("network blip")

        with (
            patch("src.core.autonomous_scanner.load_dotenv"),
            patch("src.core.autonomous_scanner.vault") as mock_vault,
            patch.dict("os.environ", {"DMARKET_PUBLIC_KEY": "test_key"}),
            patch("src.core.autonomous_scanner.os.path.isfile", return_value=True),
            patch("src.core.autonomous_scanner._write_exit_state"),
            patch("src.core.autonomous_scanner.classify", return_value="TRANSIENT"),
            patch("src.core.autonomous_scanner.asyncio.sleep", new_callable=AsyncMock),
            patch("src.core.autonomous_scanner.DMarketAPIClient"),
            patch("src.core.autonomous_scanner.InventoryManager"),
            patch("src.core.autonomous_scanner._send_startup_notification", new_callable=AsyncMock),
        ):
            mock_vault.get_dmarket_secret.return_value = "secret"
            with patch("src.core.autonomous_scanner.SnipingLoop") as mock_loop:
                mock_bot = MagicMock()
                mock_bot.target_games = ["a8db"]
                mock_bot.start = AsyncMock(side_effect=_start)
                mock_loop.return_value = mock_bot
                await run_autonomous_scanner()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_fatal_error_stops_loop(self):
        from src.core.autonomous_scanner import run_autonomous_scanner
        with (
            patch("src.core.autonomous_scanner.load_dotenv"),
            patch("src.core.autonomous_scanner.vault") as mock_vault,
            patch.dict("os.environ", {"DMARKET_PUBLIC_KEY": "test_key"}),
            patch("src.core.autonomous_scanner.os.path.isfile", return_value=True),
            patch("src.core.autonomous_scanner.classify", return_value="FATAL"),
            patch("src.core.autonomous_scanner.fatal_exit", side_effect=SystemExit(5)),
            patch("src.core.autonomous_scanner.DMarketAPIClient"),
            patch("src.core.autonomous_scanner.InventoryManager"),
            patch("src.core.autonomous_scanner._send_startup_notification", new_callable=AsyncMock),
        ):
            mock_vault.get_dmarket_secret.return_value = "secret"
            with patch("src.core.autonomous_scanner.SnipingLoop") as mock_loop:
                mock_bot = MagicMock()
                mock_bot.target_games = ["a8db"]
                mock_bot.start = AsyncMock(side_effect=RuntimeError("bug"))
                mock_loop.return_value = mock_bot
                with pytest.raises(SystemExit):
                    await run_autonomous_scanner()

    @pytest.mark.asyncio
    async def test_placeholder_keys_raise_config_error(self):
        from src.core.autonomous_scanner import run_autonomous_scanner
        with (
            patch("src.core.autonomous_scanner.load_dotenv"),
            patch("src.core.autonomous_scanner.vault") as mock_vault,
            patch.dict("os.environ", {"DMARKET_PUBLIC_KEY": "ROTATE_ME_xxx"}),
            patch("src.core.autonomous_scanner.os.path.isfile", return_value=True),
            patch("src.core.autonomous_scanner.fatal_exit", side_effect=SystemExit(2)),
        ):
            mock_vault.get_dmarket_secret.return_value = "secret"
            with pytest.raises(SystemExit):
                await run_autonomous_scanner()

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        from src.core.autonomous_scanner import run_autonomous_scanner
        sleep_calls = []

        async def _track_sleep(delay):
            sleep_calls.append(delay)

        call_count = 0

        async def _start():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                raise asyncio.CancelledError()
            raise ConnectionError("network blip")

        with (
            patch("src.core.autonomous_scanner.load_dotenv"),
            patch("src.core.autonomous_scanner.vault") as mock_vault,
            patch.dict("os.environ", {"DMARKET_PUBLIC_KEY": "test_key"}),
            patch("src.core.autonomous_scanner.os.path.isfile", return_value=True),
            patch("src.core.autonomous_scanner._write_exit_state"),
            patch("src.core.autonomous_scanner.classify", return_value="TRANSIENT"),
            patch("src.core.autonomous_scanner.asyncio.sleep", side_effect=_track_sleep),
            patch("src.core.autonomous_scanner.DMarketAPIClient"),
            patch("src.core.autonomous_scanner.InventoryManager"),
            patch("src.core.autonomous_scanner._send_startup_notification", new_callable=AsyncMock),
        ):
            mock_vault.get_dmarket_secret.return_value = "secret"
            with patch("src.core.autonomous_scanner.SnipingLoop") as mock_loop:
                mock_bot = MagicMock()
                mock_bot.target_games = ["a8db"]
                mock_bot.start = AsyncMock(side_effect=_start)
                mock_loop.return_value = mock_bot
                await run_autonomous_scanner()

        # Should have exponential backoff: 5, 10
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == 5
        assert sleep_calls[1] == 10

    @pytest.mark.asyncio
    async def test_successful_cycle_resets_backoff(self):
        """Successful cycle resets retry delay and counter (lines 184-187)."""
        from src.core.autonomous_scanner import run_autonomous_scanner
        call_count = 0

        async def _start():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()
            # First call succeeds (returns normally)

        with (
            patch("src.core.autonomous_scanner.load_dotenv"),
            patch("src.core.autonomous_scanner.vault") as mock_vault,
            patch.dict("os.environ", {"DMARKET_PUBLIC_KEY": "test_key"}),
            patch("src.core.autonomous_scanner.os.path.isfile", return_value=True),
            patch("src.core.autonomous_scanner._write_exit_state"),
            patch("src.core.autonomous_scanner.DMarketAPIClient"),
            patch("src.core.autonomous_scanner.InventoryManager"),
            patch("src.core.autonomous_scanner._send_startup_notification", new_callable=AsyncMock),
        ):
            mock_vault.get_dmarket_secret.return_value = "secret"
            with patch("src.core.autonomous_scanner.SnipingLoop") as mock_loop:
                mock_bot = MagicMock()
                mock_bot.target_games = ["a8db"]
                mock_bot.start = AsyncMock(side_effect=_start)
                mock_loop.return_value = mock_bot
                await run_autonomous_scanner()
        assert call_count == 2

    def test_format_process_stats_fallback(self):
        """psutil unavailable returns fallback string (lines 87-88)."""
        from src.core.autonomous_scanner import _format_process_stats
        with patch("builtins.__import__", side_effect=ImportError("no psutil")):
            result = _format_process_stats()
        assert "unavailable" in result
