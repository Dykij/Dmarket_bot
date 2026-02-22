import os

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from src.dmarket.dmarket_api import DMarketAPI
from src.dmarket.scanner.engine import check_user_balance
from src.telegram_bot.handlers.settings_handlers import get_localized_text
from src.telegram_bot.profiles import get_user_profile
from src.utils.canonical_logging import get_logger
from src.utils.exceptions import APIError

logger = get_logger(__name__)

# Загружаем переменные окружения
load_dotenv()


async def dmarket_status_impl(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status_message=None,
) -> None:
    """Реализация проверки статуса DMarket API.

    Args:
        update (Update): Объект обновления Telegram
        context (CallbackContext): Контекст обработчика
        status_message: Сообщение для обновления статуса (опционально)

    """
    if not update.effective_user or not update.effective_chat:
        return

    # Получаем пользователя и его профиль
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)

    # Отправляем индикатор печатания, если сообщение статуса не предоставлено
    if not status_message and update.message:
        await update.effective_chat.send_action(ChatAction.TYPING)
        checking_msg = get_localized_text(user_id, "checking_api")
        status_message = await update.message.reply_text(checking_msg)

    if not status_message:
        # Если не удалось отправить сообщение, выходим
        return

    # Отображаем индикатор загрузки данных
    await update.effective_chat.send_action(ChatAction.UPLOAD_DOCUMENT)

    # Получаем API ключи из профиля пользователя
    # или из переменных окружения
    public_key = profile.get("api_key", "")
    secret_key = profile.get("api_secret", "")
    auth_source = ""
    if not public_key or not secret_key:
        # При отсутствии ключей в профиле, пробуем переменные окружения
        public_key = os.getenv("DMARKET_PUBLIC_KEY", "")
        secret_key = os.getenv("DMARKET_SECRET_KEY", "")
        auth_source = " <i>(из переменных окружения)</i>"

    auth_status = "❌ <b>Авторизация</b>: ключи API не настроены"
    if public_key and secret_key:
        auth_status = f"✅ <b>Авторизация</b>: настроена{auth_source}"

    api_status = "Неизвестно"
    balance_info = ""

    try:
        async with DMarketAPI(
            public_key=public_key,
            secret_key=secret_key,
            pool_limits=httpx.Limits(max_connections=5),
        ) as api_client:
            # Показываем, что мы работаем с API
            await update.effective_chat.send_action(ChatAction.TYPING)

            # Получаем баланс через улучшенную функцию
            balance_data = await check_user_balance(api_client)

            # Проверка на наличие ошибки
            if balance_data.get("error", False):
                api_status = "⚠️ <b>API</b>: проблема с доступом"
                error_message = balance_data.get(
                    "error_message",
                    "Неизвестная ошибка",
                )

                if (
                    "unauthorized" in error_message.lower()
                    or "token" in error_message.lower()
                ):
                    auth_status = "❌ <b>Авторизация</b>: ошибка авторизации"
                    balance_info = (
                        "<i>Не удалось получить баланс: проверьте ключи API.</i>"
                    )
                else:
                    balance_info = f"<i>Ошибка при запросе баланса:</i> {error_message}"
            else:
                balance = balance_data.get("balance", 0.0)

                api_status = "✅ <b>API доступно</b>"

                if public_key and secret_key:
                    # Форматируем баланс для отображения пользователю
                    balance_status = "✅" if balance > 0 else "⚠️"
                    balance_info = f"{balance_status} <b>Баланс</b>: <code>${balance:.2f} USD</code>"
                else:
                    balance_info = "<i>Баланс недоступен без API ключей.</i>"
    except APIError as e:
        api_status = f"⚠️ <b>Ошибка API</b>: {e.message}"
        if e.status_code == 401:
            auth_status = "❌ <b>Ошибка авторизации</b>: неверные ключи API"
        balance_info = "<i>Не удалось проверить баланс.</i>"
    except Exception as e:
        # Обработка общих исключений
        logger.exception(f"Неожиданная ошибка при проверке статуса: {e!s}")
        api_status = f"⚠️ <b>Неожиданная ошибка</b>: {e!s}"
        balance_info = "<i>Не удалось проверить статус.</i>"

    # Добавляем информацию для устранения проблем
    troubleshooting = ""
    if "ошибка авторизации" in auth_status.lower() or "❌" in auth_status:
        troubleshooting = (
            "\n\n🔧 <b>Для устранения проблемы:</b>\n"
            "1. Проверьте корректность API ключей\n"
            "2. Убедитесь, что ключи не истекли\n"
            "3. Создайте новые ключи API на DMarket, если необходимо"
        )

    # Формируем текст сообщения
    # (не переопределяя переменную status_message!)
    final_text = (
        f"{api_status}\n"
        f"{auth_status}\n"
        f"{balance_info}{troubleshooting}\n\n"
        f"🕒 <i>Последнее обновление: только что</i>"
    )

    # Показываем финальное сообщение с форматированием HTML
    await status_message.edit_text(
        final_text,
        parse_mode=ParseMode.HTML,
    )
