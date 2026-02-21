"""
Refactored notification filters handler with DRY principles.

This module provides handlers for notification filter management with reduced
code duplication and improved readability.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.telegram_bot.filters_manager import get_filters_manager

# Constants
NOTIFY_FILTER = "notify_filter"

SUPPORTED_GAMES = {
    "csgo": "CS:GO",
    "dota2": "Dota 2",
    "tf2": "Team Fortress 2",
    "rust": "Rust",
}

ARBITRAGE_LEVELS = {
    "boost": "🚀 Boost ($0.50-$3)",
    "standard": "📊 Standard ($3-$10)",
    "medium": "💼 Medium ($10-$30)",
    "advanced": "⚡ Advanced ($30-$100)",
    "pro": "👑 Pro ($100+)",
}

NOTIFICATION_TYPES = {
    "arbitrage": "💰 Арбитраж",
    "target_filled": "🎯 Таргеты",
    "price_alert": "📈 Ценовые алерты",
    "market_trend": "📊 Тренды рынка",
}


async def show_games_filter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show games filter selection.

    Args:
        update: Telegram update object
        context: Bot context

    """
    await _show_filter_selection(
        update=update,
        filter_key="games",
        items=SUPPORTED_GAMES,
        title="🎮 *Фильтр по играм*",
        description="Выберите игры для уведомлений:",
        callback_prefix="game",
    )


async def show_levels_filter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show arbitrage levels filter selection.

    Args:
        update: Telegram update object
        context: Bot context

    """
    await _show_filter_selection(
        update=update,
        filter_key="levels",
        items=ARBITRAGE_LEVELS,
        title="📊 *Фильтр по уровням*",
        description="Выберите уровни для уведомлений:",
        callback_prefix="level",
    )


async def show_types_filter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show notification types filter selection.

    Args:
        update: Telegram update object
        context: Bot context

    """
    await _show_filter_selection(
        update=update,
        filter_key="notification_types",
        items=NOTIFICATION_TYPES,
        title="📢 *Фильтр по типам*",
        description="Выберите типы уведомлений:",
        callback_prefix="type",
    )


async def _show_filter_selection(
    update: Update,
    filter_key: str,
    items: dict[str, str],
    title: str,
    description: str,
    callback_prefix: str,
) -> None:
    """Generic handler for showing filter selection UI.

    This function implements DRY principle for all filter handlers.

    Args:
        update: Telegram update object
        filter_key: Key in user filters dict (e.g., 'games', 'levels')
        items: Dict of {code: name} for filter items
        title: Filter title with emoji
        description: Filter description
        callback_prefix: Prefix for callback data (e.g., 'game', 'level')

    """
    query = update.callback_query
    if not query or not update.effective_user:
        return

    await query.answer()

    user_id = update.effective_user.id
    enabled_items = _get_enabled_items(user_id, filter_key)

    message = f"{title}\n\n{description}"
    keyboard = _build_filter_keyboard(
        items=items,
        enabled_items=enabled_items,
        callback_prefix=callback_prefix,
    )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )


def _get_enabled_items(user_id: int, filter_key: str) -> list[str]:
    """Get list of enabled filter items for user.

    Args:
        user_id: Telegram user ID
        filter_key: Filter key in user filters dict

    Returns:
        List of enabled item codes

    """
    filters_manager = get_filters_manager()
    user_filters = filters_manager.get_user_filters(user_id)
    enabled_items_raw = user_filters.get(filter_key, [])

    if not isinstance(enabled_items_raw, list):
        return []

    return enabled_items_raw


def _build_filter_keyboard(
    items: dict[str, str],
    enabled_items: list[str],
    callback_prefix: str,
) -> list[list[InlineKeyboardButton]]:
    """Build inline keyboard for filter selection.

    Args:
        items: Dict of {code: name} for filter items
        enabled_items: List of enabled item codes
        callback_prefix: Prefix for callback data

    Returns:
        List of keyboard button rows

    """
    keyboard = []

    for item_code, item_name in items.items():
        button_text = _get_button_text(item_name, item_code in enabled_items)
        callback_data = f"{NOTIFY_FILTER}_{callback_prefix}_{item_code}"

        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=callback_data)]
        )

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=NOTIFY_FILTER)])

    return keyboard


def _get_button_text(item_name: str, is_enabled: bool) -> str:
    """Get button text with checkbox emoji.

    Args:
        item_name: Display name of the item
        is_enabled: Whether item is enabled

    Returns:
        Button text with checkbox emoji

    """
    checkbox = "✅" if is_enabled else "⬜"
    return f"{checkbox} {item_name}"


class NotificationFilters:
    """Legacy class for backward compatibility with tests."""

    def __init__(self) -> None:
        """Initialize notification filters."""
        self._filters: dict[int, dict[str, any]] = {}

    def _get_default_filters(self) -> dict[str, any]:
        """Get default filter settings.

        Returns:
            Default filter settings

        """
        return {
            "games": list(SUPPORTED_GAMES.keys()),
            "min_profit_percent": 5.0,
            "levels": list(ARBITRAGE_LEVELS.keys()),
            "notification_types": list(NOTIFICATION_TYPES.keys()),
            "enabled": True,
        }

    def get_user_filters(self, user_id: int) -> dict[str, any]:
        """Get filters for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            User's filter settings

        """
        if user_id not in self._filters:
            self._filters[user_id] = self._get_default_filters()
        return self._filters[user_id].copy()

    def update_user_filters(self, user_id: int, new_settings: dict[str, any]) -> None:
        """Update filters for a user.

        Args:
            user_id: Telegram user ID
            new_settings: New filter settings to apply

        """
        if user_id not in self._filters:
            self.get_user_filters(user_id)
        self._filters[user_id].update(new_settings)

    def reset_user_filters(self, user_id: int) -> None:
        """Reset filters for a user to defaults.

        Args:
            user_id: Telegram user ID

        """
        if user_id in self._filters:
            del self._filters[user_id]

    def should_notify(
        self,
        user_id: int,
        game: str,
        profit_percent: float,
        level: str,
        notification_type: str,
    ) -> bool:
        """Check if user should be notified based on filters.

        Args:
            user_id: Telegram user ID
            game: Game code
            profit_percent: Profit percentage
            level: Arbitrage level
            notification_type: Type of notification

        Returns:
            True if user should be notified, False otherwise

        """
        filters = self.get_user_filters(user_id)

        if not filters.get("enabled", True):
            return False

        if notification_type not in filters.get("notification_types", []):
            return False

        if game not in filters.get("games", []):
            return False

        if level not in filters.get("levels", []):
            return False

        return not profit_percent < filters.get("min_profit_percent", 0.0)
