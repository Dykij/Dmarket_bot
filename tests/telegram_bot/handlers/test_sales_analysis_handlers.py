"""Tests for sales_analysis_handlers module.

Covers handle_sales_analysis, handle_arbitrage_with_sales,
handle_liquidity_analysis, handle_sales_volume_stats, and utility functions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.handlers.sales_analysis_handlers import (
    GAMES,
    get_liquidity_emoji,
    handle_arbitrage_with_sales,
    handle_liquidity_analysis,
    handle_sales_analysis,
    handle_sales_volume_stats,
)
from src.utils.exceptions import APIError

# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_update(
    text: str | None = None,
    has_message: bool = True,
) -> MagicMock:
    """Create a mock Update object."""
    update = MagicMock()
    if has_message:
        update.message = MagicMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
    else:
        update.message = None
    return update


def create_mock_context(
    user_data: dict | None = None,
) -> MagicMock:
    """Create a mock ContextTypes.DEFAULT_TYPE object."""
    context = MagicMock()
    context.user_data = user_data
    return context


# =============================================================================
# Tests for GAMES constant
# =============================================================================


class TestGamesConstant:
    """Tests for GAMES constant."""

    def test_games_contains_csgo(self) -> None:
        """Test GAMES contains CS2 entry."""
        assert "csgo" in GAMES
        assert GAMES["csgo"] == "CS2"

    def test_games_contains_dota2(self) -> None:
        """Test GAMES contains Dota 2 entry."""
        assert "dota2" in GAMES
        assert GAMES["dota2"] == "Dota 2"

    def test_games_contains_tf2(self) -> None:
        """Test GAMES contains TF2 entry."""
        assert "tf2" in GAMES
        assert GAMES["tf2"] == "Team Fortress 2"

    def test_games_contains_rust(self) -> None:
        """Test GAMES contains Rust entry."""
        assert "rust" in GAMES
        assert GAMES["rust"] == "Rust"


# =============================================================================
# Tests for get_liquidity_emoji
# =============================================================================


class TestGetLiquidityEmoji:
    """Tests for get_liquidity_emoji function."""

    @pytest.mark.parametrize(
        ("score", "expected"),
        (
            (100, "💎"),
            (90, "💎"),
            (80, "💎"),
            (79, "💧"),
            (70, "💧"),
            (60, "💧"),
            (59, "💦"),
            (50, "💦"),
            (40, "💦"),
            (39, "🌊"),
            (30, "🌊"),
            (20, "🌊"),
            (19, "❄️"),
            (10, "❄️"),
            (0, "❄️"),
        ),
    )
    def test_liquidity_emoji_for_score(self, score: float, expected: str) -> None:
        """Test liquidity emoji for various scores."""
        assert get_liquidity_emoji(score) == expected

    def test_very_high_liquidity_score(self) -> None:
        """Test emoji for very high liquidity score."""
        assert get_liquidity_emoji(100) == "💎"

    def test_very_low_liquidity_score(self) -> None:
        """Test emoji for very low liquidity score."""
        assert get_liquidity_emoji(0) == "❄️"


# =============================================================================
# Tests for handle_sales_analysis
# =============================================================================


class TestHandleSalesAnalysis:
    """Tests for handle_sales_analysis function."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_message(self) -> None:
        """Test returns early when update has no message."""
        update = create_mock_update(has_message=False)
        context = create_mock_context()

        await handle_sales_analysis(update, context)

        # No exception should be raised

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_text(self) -> None:
        """Test returns early when message has no text."""
        update = create_mock_update(text=None)
        context = create_mock_context()

        await handle_sales_analysis(update, context)

        # Should not call reply_text for error
        # (returns early before that check)

    @pytest.mark.asyncio()
    async def test_shows_error_without_item_name(self) -> None:
        """Test shows error when no item name is provided."""
        update = create_mock_update(text="/sales_analysis")
        context = create_mock_context()

        await handle_sales_analysis(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Необходимо указать название предмета" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_successful_analysis(self) -> None:
        """Test successful sales analysis."""
        update = create_mock_update(text="/sales_analysis AWP | Asiimov")
        context = create_mock_context()

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        mock_analysis = {
            "average_price": 100.0,
            "sales_count": 50,
            "trend": "up",
        }

        with (
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.analyze_sales_history",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.format_sales_analysis",
                return_value="Formatted analysis",
            ),
        ):
            await handle_sales_analysis(update, context)

        mock_reply.edit_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handles_api_error(self) -> None:
        """Test handles APIError gracefully."""
        update = create_mock_update(text="/sales_analysis AWP | Asiimov")
        context = create_mock_context()

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with patch(
            "src.telegram_bot.handlers.sales_analysis_handlers.analyze_sales_history",
            new_callable=AsyncMock,
            side_effect=APIError("API Error", 500),
        ):
            await handle_sales_analysis(update, context)

        mock_reply.edit_text.assert_called_once()
        call_args = mock_reply.edit_text.call_args
        # Text can be in args[0] or kwargs["text"]
        error_text = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
        assert "Ошибка" in error_text

    @pytest.mark.asyncio()
    async def test_handles_generic_exception(self) -> None:
        """Test handles generic exception gracefully."""
        update = create_mock_update(text="/sales_analysis AWP | Asiimov")
        context = create_mock_context()

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with patch(
            "src.telegram_bot.handlers.sales_analysis_handlers.analyze_sales_history",
            new_callable=AsyncMock,
            side_effect=ValueError("Unexpected error"),
        ):
            await handle_sales_analysis(update, context)

        mock_reply.edit_text.assert_called_once()
        call_args = mock_reply.edit_text.call_args
        # Text can be in args[0] or kwargs["text"]
        error_text = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
        assert "Произошла ошибка" in error_text


# =============================================================================
# Tests for handle_arbitrage_with_sales
# =============================================================================


class TestHandleArbitrageWithSales:
    """Tests for handle_arbitrage_with_sales function."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_message(self) -> None:
        """Test returns early when update has no message."""
        update = create_mock_update(has_message=False)
        context = create_mock_context()

        await handle_arbitrage_with_sales(update, context)

        # No exception should be raised

    @pytest.mark.asyncio()
    async def test_uses_default_game_csgo(self) -> None:
        """Test uses default game csgo when not in user_data."""
        update = create_mock_update(text="/arbitrage_sales")
        context = create_mock_context(user_data=None)

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with (
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.enhanced_arbitrage_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.format_arbitrage_with_sales",
                return_value="Formatted results",
            ),
        ):
            await handle_arbitrage_with_sales(update, context)

        # Should use csgo as default
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_uses_game_from_context(self) -> None:
        """Test uses game from context user_data."""
        update = create_mock_update(text="/arbitrage_sales")
        context = create_mock_context(user_data={"current_game": "dota2"})

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with (
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.enhanced_arbitrage_search",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_search,
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.format_arbitrage_with_sales",
                return_value="Formatted results",
            ),
        ):
            await handle_arbitrage_with_sales(update, context)

        mock_search.assert_called_once_with(game="dota2", min_profit=1.0)

    @pytest.mark.asyncio()
    async def test_handles_api_error(self) -> None:
        """Test handles APIError gracefully."""
        update = create_mock_update(text="/arbitrage_sales")
        context = create_mock_context()

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with patch(
            "src.telegram_bot.handlers.sales_analysis_handlers.enhanced_arbitrage_search",
            new_callable=AsyncMock,
            side_effect=APIError("API Error", 500),
        ):
            await handle_arbitrage_with_sales(update, context)

        mock_reply.edit_text.assert_called_once()
        call_args = mock_reply.edit_text.call_args
        assert "Ошибка" in call_args[0][0]


# =============================================================================
# Tests for handle_liquidity_analysis
# =============================================================================


class TestHandleLiquidityAnalysis:
    """Tests for handle_liquidity_analysis function."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_message(self) -> None:
        """Test returns early when update has no message."""
        update = create_mock_update(has_message=False)
        context = create_mock_context()

        await handle_liquidity_analysis(update, context)

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_text(self) -> None:
        """Test returns early when message has no text."""
        update = create_mock_update(text=None)
        context = create_mock_context()

        await handle_liquidity_analysis(update, context)

    @pytest.mark.asyncio()
    async def test_shows_error_without_item_name(self) -> None:
        """Test shows error when no item name is provided."""
        update = create_mock_update(text="/liquidity")
        context = create_mock_context()

        await handle_liquidity_analysis(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Необходимо указать название предмета" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_successful_analysis(self) -> None:
        """Test successful liquidity analysis."""
        update = create_mock_update(text="/liquidity AWP | Asiimov")
        context = create_mock_context()

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        mock_analysis = {
            "liquidity_score": 75.0,
            "daily_volume": 100,
        }

        with (
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.analyze_item_liquidity",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.format_liquidity_analysis",
                return_value="Formatted analysis",
            ),
        ):
            await handle_liquidity_analysis(update, context)

        mock_reply.edit_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handles_api_error(self) -> None:
        """Test handles APIError gracefully."""
        update = create_mock_update(text="/liquidity AWP | Asiimov")
        context = create_mock_context()

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with patch(
            "src.telegram_bot.handlers.sales_analysis_handlers.analyze_item_liquidity",
            new_callable=AsyncMock,
            side_effect=APIError("API Error", 500),
        ):
            await handle_liquidity_analysis(update, context)

        mock_reply.edit_text.assert_called_once()


# =============================================================================
# Tests for handle_sales_volume_stats
# =============================================================================


class TestHandleSalesVolumeStats:
    """Tests for handle_sales_volume_stats function."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_message(self) -> None:
        """Test returns early when update has no message."""
        update = create_mock_update(has_message=False)
        context = create_mock_context()

        await handle_sales_volume_stats(update, context)

    @pytest.mark.asyncio()
    async def test_uses_default_game_csgo(self) -> None:
        """Test uses default game csgo when not in user_data."""
        update = create_mock_update(text="/sales_volume")
        context = create_mock_context(user_data=None)

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with (
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.get_sales_volume_stats",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.format_sales_volume_stats",
                return_value="Formatted stats",
            ),
        ):
            await handle_sales_volume_stats(update, context)

        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_uses_game_from_context(self) -> None:
        """Test uses game from context user_data."""
        update = create_mock_update(text="/sales_volume")
        context = create_mock_context(user_data={"current_game": "rust"})

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with (
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.get_sales_volume_stats",
                new_callable=AsyncMock,
                return_value={},
            ) as mock_stats,
            patch(
                "src.telegram_bot.handlers.sales_analysis_handlers.format_sales_volume_stats",
                return_value="Formatted stats",
            ),
        ):
            await handle_sales_volume_stats(update, context)

        mock_stats.assert_called_once_with(game="rust")

    @pytest.mark.asyncio()
    async def test_handles_api_error(self) -> None:
        """Test handles APIError gracefully."""
        update = create_mock_update(text="/sales_volume")
        context = create_mock_context()

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with patch(
            "src.telegram_bot.handlers.sales_analysis_handlers.get_sales_volume_stats",
            new_callable=AsyncMock,
            side_effect=APIError("API Error", 500),
        ):
            await handle_sales_volume_stats(update, context)

        mock_reply.edit_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handles_generic_exception(self) -> None:
        """Test handles generic exception gracefully."""
        update = create_mock_update(text="/sales_volume")
        context = create_mock_context()

        mock_reply = AsyncMock()
        mock_reply.edit_text = AsyncMock()
        update.message.reply_text.return_value = mock_reply

        with patch(
            "src.telegram_bot.handlers.sales_analysis_handlers.get_sales_volume_stats",
            new_callable=AsyncMock,
            side_effect=ValueError("Unexpected error"),
        ):
            await handle_sales_volume_stats(update, context)

        mock_reply.edit_text.assert_called_once()
