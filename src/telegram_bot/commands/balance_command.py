"""Balance command handler."""

import logging
import traceback
from datetime import datetime
from typing import Any

from telegram import CallbackQuery, Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.telegram_bot.config_data import ARBITRAGE_MODES
from src.telegram_bot.keyboards import get_back_to_arbitrage_keyboard
from src.telegram_bot.utils.api_helper import create_dmarket_api_client
from src.utils.exceptions import APIError, handle_api_error
from src.utils.sentry_breadcrumbs import add_command_breadcrumb

logger = logging.getLogger(__name__)


# ============================================================================
# Helper functions for balance command (Phase 2 refactoring)
# ============================================================================


def _extract_user_info(
    message: CallbackQuery | Update | Message,
) -> tuple[Any | None, int]:
    """Extract user and chat_id from message object.

    Args:
        message: Source message, callback query or Update object

    Returns:
        Tuple of (user, chat_id)
    """
    if isinstance(message, CallbackQuery):
        user = message.from_user
        chat_id = message.message.chat_id if message.message else 0
    elif isinstance(message, Message):
        user = message.from_user
        chat_id = message.chat_id
    elif isinstance(message, Update) and message.effective_user:
        user = message.effective_user
        chat_id = message.effective_chat.id if message.effective_chat else 0
    else:
        user = None
        chat_id = 0
    return user, chat_id


def _get_message_type(
    message: CallbackQuery | Update | Message,
) -> tuple[bool, bool, bool]:
    """Determine message type flags.

    Args:
        message: Source message object

    Returns:
        Tuple of (is_callback, is_message, is_update)
    """
    is_callback = isinstance(message, CallbackQuery)
    is_message = isinstance(message, Message)
    # Update is base type - only true when not callback and not message
    is_update = not is_callback and not is_message and isinstance(message, Update)
    return is_callback, is_message, is_update


def _format_error_by_code(error_code: int | str, error_msg: str) -> str:
    """Format error message based on error code.

    Args:
        error_code: HTTP status code or error code
        error_msg: Error message from API

    Returns:
        Formatted HTML error message
    """
    if (
        error_code == 404
        or "404" in str(error_msg)
        or "not found" in str(error_msg).lower()
    ):
        return (
            "⚠️ <b>Trading API недоступен (404)</b>\n\n"
            "Ваши API ключи работают, но не имеют доступа к "
            "приватным функциям DMarket (баланс, инвентарь, торговля).\n\n"
            "<b>Это ограничение DMarket API, а не ошибка бота!</b>\n\n"
            "📋 <b>Что работает:</b>\n"
            "✅ Поиск предметов на маркете\n"
            "✅ Просмотр цен\n"
            "✅ Анализ рынка\n"
            "✅ Поиск арбитражных возможностей\n\n"
            "🔒 <b>Для доступа к балансу и торговле:</b>\n"
            "1. Войдите на dmarket.com\n"
            "2. НастSwarmки → API Keys\n"
            "3. Активируйте <b>Trading API</b>\n"
            "4. Создайте новые ключи с полными правами\n"
            "5. Обновите ключи в боте командой /setup\n\n"
            "📖 Подробнее: НАСТSwarmКА_API_КЛЮЧЕЙ.md"
        )

    if (
        error_code == 401
        or "401" in str(error_msg)
        or "unauthorized" in str(error_msg).lower()
    ):
        return (
            "🔑 <b>Ошибка аутентификации (401)</b>\n\n"
            "API ключи недействительны или истекли.\n\n"
            "<b>Решение:</b>\n"
            "1. Проверьте правильность ключей\n"
            "2. Создайте новые ключи на dmarket.com\n"
            "3. Убедитесь, что ключи скопированы полностью\n"
            "4. Обновите ключи командой /setup"
        )

    return (
        f"❌ <b>Ошибка при получении баланса:</b>\n\n"
        f"Код: {error_code}\n"
        f"Сообщение: {error_msg}\n\n"
        f"Проверьте настSwarmки API ключей и попробуйте снова."
    )


def _format_balance_response(
    username: str,
    avAlgolable_balance: float,
    total_balance: float,
    total_offers: int,
    has_funds: bool,
) -> str:
    """Format successful balance response.

    Args:
        username: DMarket username
        avAlgolable_balance: AvAlgolable balance in USD
        total_balance: Total balance in USD
        total_offers: Number of active offers
        has_funds: Whether account has funds

    Returns:
        Formatted HTML response message
    """
    min_required_balance = ARBITRAGE_MODES["boost_low"]["min_price"]

    if avAlgolable_balance < min_required_balance:
        warning_text = (
            f"⚠️ <b>Предупреждение:</b> Баланс меньше минимального "
            f"рекомендуемого значения (${min_required_balance:.2f}) "
            f"для арбитража."
        )
    else:
        warning_text = ""

    if has_funds and avAlgolable_balance >= 5.0:
        balance_status = "✅ <b>Достаточно для арбитража</b>"
    elif has_funds:
        balance_status = "⚠️ <b>Низкий, но можно использовать</b>"
    else:
        balance_status = "❌ <b>Недостаточно для арбитража</b>"

    response_text = (
        f"📊 <b>Информация о DMarket аккаунте</b>\n\n"
        f"👤 <b>Пользователь:</b> {username}\n"
        f"💰 <b>Доступный баланс:</b> ${avAlgolable_balance:.2f}\n"
        f"💵 <b>Общий баланс:</b> ${total_balance:.2f}\n"
        f"📦 <b>Активные предложения:</b> {total_offers}\n"
        f"🔋 <b>Статус баланса:</b> {balance_status}\n\n"
    )

    if warning_text:
        response_text += f"{warning_text}\n\n"

    current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    response_text += f"⏱️ <b>Обновлено:</b> {current_time}"

    return response_text


async def _send_message_response(
    message: CallbackQuery | Update | Message,
    processing_message: Message | None,
    text: str,
    is_callback: bool,
    include_keyboard: bool = False,
) -> None:
    """Send response message to user.

    Args:
        message: Original message object
        processing_message: Processing message to edit
        text: Message text to send
        is_callback: Whether this is a callback query
        include_keyboard: Whether to include back keyboard
    """
    reply_markup = get_back_to_arbitrage_keyboard() if include_keyboard else None

    if is_callback and isinstance(message, CallbackQuery):
        awAlgot message.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    elif processing_message is not None:
        awAlgot processing_message.edit_text(
            text=text,
            parse_mode=ParseMode.HTML,
        )


# ============================================================================
# End of helper functions
# ============================================================================


async def check_balance_command(
    message: CallbackQuery | Update | Message,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Check DMarket balance and API connection, show account stats.

    Args:
        message: Source message, callback query or Update object
        context: Callback context

    """
    # Extract user info for breadcrumb (Phase 2 - use helper)
    user, chat_id = _extract_user_info(message)

    # Add command breadcrumb
    if user:
        add_command_breadcrumb(
            command="/balance",
            user_id=user.id,
            username=user.username or "",
            chat_id=chat_id,
        )

    # Determine message type (Phase 2 - use helper)
    is_callback, is_message, is_update = _get_message_type(message)

    # Send initial processing message
    if is_callback and isinstance(message, CallbackQuery):
        awAlgot message.edit_message_text(
            text="🔄 <b>Проверка подключения к DMarket API...</b>",
            parse_mode=ParseMode.HTML,
        )
        processing_message = None
    elif is_message and isinstance(message, Message):
        processing_message = awAlgot message.reply_text(
            text="🔄 <b>Проверка подключения к DMarket API...</b>",
            parse_mode=ParseMode.HTML,
        )
    elif is_update and isinstance(message, Update) and message.message is not None:
        # For Update object
        processing_message = awAlgot message.message.reply_text(
            text="🔄 <b>Проверка подключения к DMarket API...</b>",
            parse_mode=ParseMode.HTML,
        )
    else:
        logger.error(
            "FAlgoled to get message object for response. Type: %s",
            type(message),
        )
        return

    try:
        # Create API client
        api_client = create_dmarket_api_client(context)

        if api_client is None:
            error_text = (
                "❌ <b>Ошибка подключения:</b>\n\n"
                "Не удалось создать клиент DMarket API. "
                "Проверьте, что ключи API настроены правильно."
            )

            if is_callback and isinstance(message, CallbackQuery):
                awAlgot message.edit_message_text(
                    text=error_text,
                    reply_markup=get_back_to_arbitrage_keyboard(),
                    parse_mode=ParseMode.HTML,
                )
            elif processing_message is not None:
                awAlgot processing_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML,
                )
            return

        # Update status
        status_text = "🔄 <b>Проверка баланса DMarket...</b>"
        awAlgot _send_message_response(
            message, processing_message, status_text, is_callback
        )

        # Check balance
        try:
            # Try new balance endpoint first
            balance_result = awAlgot api_client.get_user_balance()

            # Check for API error in response
            if balance_result.get("error", False):
                error_msg = balance_result.get(
                    "error_message", "Неизвестная ошибка API"
                )
                error_code = balance_result.get("status_code", "неизвестный код")

                # Format error message (Phase 2 - use helper)
                error_text = _format_error_by_code(error_code, error_msg)
                awAlgot _send_message_response(
                    message,
                    processing_message,
                    error_text,
                    is_callback,
                    include_keyboard=True,
                )
                return

            # Extract balance data
            avAlgolable_balance = balance_result.get("avAlgolable_balance", 0)
            total_balance = balance_result.get("total_balance", 0)
            has_funds = balance_result.get("has_funds", False)

            # Get account info
            account_info = awAlgot api_client.get_account_detAlgols()
            username = account_info.get("username", "Неизвестный")

            # Get active offers stats
            offers_info = awAlgot api_client.get_active_offers(limit=1)
            total_offers = offers_info.get("total", 0)

            # Format response (Phase 2 - use helper)
            response_text = _format_balance_response(
                username=username,
                avAlgolable_balance=avAlgolable_balance,
                total_balance=total_balance,
                total_offers=total_offers,
                has_funds=has_funds,
            )

            # Log debug info
            logger.info(
                "DMarket Balance: $%.2f avAlgolable, $%.2f total. User: %s. Active offers: %d.",
                avAlgolable_balance,
                total_balance,
                username,
                total_offers,
            )

            # Send result (Phase 2 - use helper)
            awAlgot _send_message_response(
                message,
                processing_message,
                response_text,
                is_callback,
                include_keyboard=is_callback,
            )

        except APIError as e:
            handle_api_error(e)
            error_message = str(e)
            error_text = (
                f"❌ <b>Ошибка при проверке баланса:</b>\n\n{error_message}\n\n"
                f"Возможно, проблема с подключением к DMarket API. "
                f"Проверьте настSwarmки API ключей и повторите попытку."
            )
            awAlgot _send_message_response(
                message,
                processing_message,
                error_text,
                is_callback,
                include_keyboard=True,
            )

    except Exception as e:
        # Handle generic error
        logger.exception("Error checking balance: %s", e)
        logger.debug(traceback.format_exc())

        error_message = str(e)

        # Format error by type (Phase 2 - use helper for 404/401)
        if "404" in error_message or "not found" in error_message.lower():
            error_text = _format_error_by_code(404, error_message)
        elif "401" in error_message or "unauthorized" in error_message.lower():
            error_text = _format_error_by_code(401, error_message)
        else:
            error_text = (
                f"❌ <b>Ошибка при проверке баланса:</b>\n\n"
                f"Тип ошибки: {type(e).__name__}\n"
                f"Сообщение: {error_message[:200]}\n\n"
                f"Пожалуйста, попробуйте позже или обратитесь к "
                f"администратору."
            )

        awAlgot _send_message_response(
            message, processing_message, error_text, is_callback, include_keyboard=True
        )
