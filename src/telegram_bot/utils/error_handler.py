"""Модуль обработки ошибок для Telegram бота.

Содержит функции для централизованной обработки ошибок,
логирования исключений и отправки уведомлений пользователям
при возникновении проблем.
"""

import html
import logging
import os
import sys
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from telegram import Bot, Message, Update
from telegram.constants import ParseMode
from telegram.error import (
    BadRequest,
    Forbidden,
    NetworkError,
    RetryAfter,
    TelegramError,
    TimedOut,
)
from telegram.ext import Application, ContextTypes

logger = logging.getLogger(__name__)

# ID администраторов (пользователи, получающие уведомления об ошибках)
ADMIN_IDS: list[int] = []

# Форматы сообщений об ошибках
ERROR_MESSAGE_HTML = """
<b>❌ Произошла ошибка</b>

К сожалению, при выполнении операции произошла ошибка.
Администраторы уведомлены и уже работают над её устранением.

<i>Вы можете попробовать выполнить операцию позднее или обратиться к /help для получения справки.</i>
"""

ERROR_MESSAGE_ADMIN_HTML = """
<b>⚠️ Ошибка в боте</b>

<b>Пользователь:</b> {user_id} (@{username})
<b>Чат:</b> {chat_id}
<b>Сообщение:</b> <code>{message}</code>
<b>Ошибка:</b> <code>{error}</code>

<b>Трассировка:</b>
<pre>{traceback}</pre>
"""

# Хелперы для обработки различных типов ошибок


async def handle_network_error(
    update: Update | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает сетевые ошибки при взаимодействии с Telegram API.

    Args:
        update: Объект обновления (может быть None)
        context: Контекст бота с информацией об ошибке

    """
    error = context.error
    # При сетевой ошибке предлагаем пользователю попробовать позже
    message = "Произошла сетевая ошибка. Пожалуйста, попробуйте позже."

    if isinstance(error, RetryAfter):
        # При превышении лимита запросов указываем время ожидания
        retry_after = error.retry_after
        message = f"Превышен лимит запросов к Telegram API. Пожалуйста, подождите {retry_after} секунд."
        logger.warning(
            "Превышен лимит запросов: %s. Ожидание %s секунд.",
            error,
            retry_after,
        )

    elif isinstance(error, TimedOut):
        message = (
            "Истекло время ожидания ответа от Telegram. Пожалуйста, попробуйте позже."
        )
        logger.warning("Тайм-аут соединения: %s", error)

    elif isinstance(error, NetworkError):
        logger.error("Сетевая ошибка: %s", error)

    # Отправляем сообщение пользователю, если возможно
    if update is not None and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
            )
        except (NetworkError, TelegramError) as e:
            logger.exception(
                "Не удалось отправить сообщение об ошибке пользователю: %s",
                e,
            )


async def retry_last_action(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пытается повторить последнее действие после задержки.

    Args:
        context: Контекст с информацией о первоначальном обновлении

    """
    job = context.job
    if (
        job
        and hasattr(job, "context")
        and isinstance(job.context, dict)
        and "original_update" in job.context
    ):
        job.context["original_update"]
        # Здесь можно реализовать логику повторной обработки запроса
        logger.info("Повторная попытка обработки запроса после ошибки")
        # Фактическая реализация повторной обработки запроса зависит от структуры бота


async def handle_forbidden_error(
    update: Update | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает ошибки доступа (403 Forbidden).

    Args:
        update: Объект обновления
        context: Контекст бота с информацией об ошибке

    """
    error = context.error
    logger.warning("Ошибка доступа: %s", error)

    # Анализируем сообщение об ошибке для более точной диагностики
    error_message = str(error)
    user_message = "У бота нет необходимых прав для выполнения этой операции."

    if "bot was blocked by the user" in error_message:
        user_message = "Пользователь заблокировал бота. Диалог невозможен."
    elif "bot was kicked from the group" in error_message:
        user_message = "Бот был удален из группы."
    elif "not enough rights to send" in error_message:
        user_message = "У бота недостаточно прав для отправки сообщений в этот чат."

    # Отправляем сообщение пользователю, если возможно
    if update is not None and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=user_message,
            )
        except (NetworkError, TelegramError) as e:
            logger.exception(
                "Не удалось отправить сообщение об ошибке пользователю: %s",
                e,
            )


async def handle_bad_request(
    update: Update | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает ошибки некорректного запроса (400 Bad Request).

    Args:
        update: Объект обновления
        context: Контекст бота с информацией об ошибке

    """
    error = context.error
    logger.warning("Некорректный запрос: %s", error)

    # Проверяем наличие специфических ошибок
    error_message = str(error)
    user_message = "Произошла ошибка при обработке запроса."

    # Разбор типичных ошибок Bad Request и формирование понятных сообщений
    if "message is not modified" in error_message:
        # Игнорируем ошибку неизмененного сообщения
        return
    if "message to edit not found" in error_message:
        user_message = "Сообщение, которое бот пытался изменить, не найдено."
    elif "query is too old" in error_message:
        user_message = "Запрос устарел. Пожалуйста, повторите команду."
    elif "have no rights to send a message" in error_message:
        user_message = "У бота нет прав отправлять сообщения в этот чат."
    elif "can't parse entities" in error_message:
        logger.error("Ошибка форматирования сообщения: %s", error_message)
        user_message = "Произошла ошибка при форматировании сообщения."
    elif "wrong file identifier" in error_message:
        logger.error("Неверный идентификатор файла: %s", error_message)
        user_message = "Произошла ошибка при работе с файлом."

    # Отправляем сообщение пользователю, если возможно
    if update is not None and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=user_message,
            )
        except (NetworkError, TelegramError) as e:
            logger.exception(
                "Не удалось отправить сообщение об ошибке пользователю: %s",
                e,
            )


async def handle_dmarket_api_error(
    update: Update | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает ошибки при работе с DMarket API.

    Args:
        update: Объект обновления
        context: Контекст бота с информацией об ошибке

    """
    error = context.error
    dmarket_error = getattr(context, "dmarket_error", None)
    error_code = getattr(dmarket_error, "code", None)

    # Формируем сообщение для пользователя
    if error_code == 401:
        user_message = (
            "Ошибка авторизации в DMarket API. Пожалуйста, проверьте ваши API ключи."
        )
        logger.error("Ошибка авторизации DMarket API: неверные ключи")
    elif error_code == 429:
        user_message = (
            "Превышен лимит запросов к DMarket API. Пожалуйста, попробуйте позже."
        )
        logger.warning("Превышен лимит запросов к DMarket API: %s", dmarket_error)
    elif error_code in {500, 502, 503, 504}:
        user_message = (
            "Сервис DMarket временно недоступен. Пожалуйста, попробуйте позже."
        )
        logger.error("Ошибка сервера DMarket: %s", dmarket_error)
    else:
        user_message = "Произошла ошибка при взаимодействии с DMarket. Пожалуйста, попробуйте позже."
        logger.error("Ошибка DMarket API: %s, %s", error, dmarket_error)

    # Отправляем сообщение пользователю
    if update is not None and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=user_message,
                parse_mode=ParseMode.HTML,
            )
        except (NetworkError, TelegramError) as e:
            logger.exception(
                "Не удалось отправить сообщение об ошибке пользователю: %s",
                e,
            )


# Основной обработчик ошибок


async def error_handler(
    update: Update | None, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Глобальный обработчик ошибок для Telegram бота.

    Обрабатывает все типы ошибок, логирует их, отправляет сообщения
    пользователю и администраторам.

    Args:
        update: Объект обновления (может быть None)
        context: Контекст бота с информацией об ошибке

    """
    # Получаем информацию об ошибке
    error = context.error

    # Логируем трассировку ошибки
    if error:
        tb_list = traceback.format_exception(type(error), error, error.__traceback__)
        tb_string = "".join(tb_list)
    else:
        tb_string = "No traceback available"

    # Подробное логирование
    update_str = update.to_dict() if update is not None else "Нет данных update"
    logger.error("Исключение при обработке обновления %s:\n%s", update_str, tb_string)

    # Обработка различных типов ошибок
    if isinstance(error, NetworkError):
        return await handle_network_error(update, context)
    if isinstance(error, Forbidden):
        return await handle_forbidden_error(update, context)
    if isinstance(error, BadRequest):
        return await handle_bad_request(update, context)

    # Проверка на ошибки DMarket API
    if hasattr(context, "dmarket_error"):
        return await handle_dmarket_api_error(update, context)

    # Получаем информацию о пользователе и чате
    user_id = None
    chat_id = None
    username = "Неизвестно"
    message_text = "Неизвестно"

    if update is not None:
        if update.effective_user:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Неизвестно"

        if update.effective_chat:
            chat_id = update.effective_chat.id

        if update.effective_message:
            message_text = update.effective_message.text or "Неизвестно"

    # Отправляем сообщение об ошибке пользователю
    if update is not None and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=ERROR_MESSAGE_HTML,
                parse_mode=ParseMode.HTML,
            )
        except (NetworkError, TelegramError) as e:
            logger.exception(
                "Не удалось отправить сообщение об ошибке пользователю: %s",
                e,
            )

    # Отправляем уведомление администраторам
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=ERROR_MESSAGE_ADMIN_HTML.format(
                    user_id=user_id,
                    username=html.escape(str(username)),
                    chat_id=chat_id,
                    message=html.escape(str(message_text)),
                    error=html.escape(str(error)),
                    traceback=html.escape(
                        tb_string[:3000],
                    ),  # Ограничиваем длину трассировки
                ),
                parse_mode=ParseMode.HTML,
            )
        except (NetworkError, TelegramError) as e:
            logger.exception(
                "Не удалось отправить уведомление администратору %s: %s",
                admin_id,
                e,
            )
    return None


# Функция для регистрации обработчика ошибок в приложении


def setup_error_handler(
    application: Application,
    admin_ids: list[int] | None = None,
) -> None:
    """Устанавливает обработчик ошибок для приложения Telegram бота.

    Args:
        application: Экземпляр приложения Telegram бота
        admin_ids: Список ID администраторов для уведомлений об ошибках

    """
    global ADMIN_IDS

    # Инициализируем список администраторов из переменной окружения, если не задан явно
    if not admin_ids:
        admin_ids = configure_admin_ids()

    # Обновляем список администраторов
    if admin_ids:
        ADMIN_IDS = admin_ids

    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)  # type: ignore[arg-type]

    logger.info("Обработчик ошибок установлен. Администраторы: %s", ADMIN_IDS)


# Функция для обертывания обработчиков команд с отлавливанием исключений


def exception_guard(
    func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]],
) -> Callable:
    """Декоратор для защиты обработчиков команд от необработанных исключений.

    Оборачивает функцию-обработчик в try-except и логирует все исключения.

    Args:
        func: Функция-обработчик команды

    Returns:
        Обернутая функция-обработчик

    """

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        try:
            return await func(update, context)
        except (NetworkError, TelegramError, ValueError, KeyError, AttributeError) as e:
            logger.exception(
                "Необработанное исключение в обработчике %s: %s",
                func.__name__,
                e,
            )
            # Передаем ошибку глобальному обработчику
            context.error = e
            await error_handler(update, context)
            return None

    return wrapper


# Вспомогательные функции для отправки сообщений с обработкой ошибок


async def send_message_safe(
    bot: Bot,
    chat_id: int | str,
    text: str,
    **kwargs: Any,
) -> Message | None:
    """Безопасно отправляет сообщение с обработкой исключений.

    Args:
        bot: Экземпляр бота
        chat_id: ID чата для отправки
        text: Текст сообщения
        **kwargs: Дополнительные аргументы для send_message

    Returns:
        Optional[Message]: Отправленное сообщение или None в случае ошибки

    """
    try:
        return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except Forbidden:
        logger.warning("У бота нет прав отправлять сообщения в чат %s", chat_id)
    except BadRequest as e:
        logger.warning("Ошибка при отправке сообщения в чат %s: %s", chat_id, e)
    except NetworkError as e:
        logger.exception("Сетевая ошибка при отправке сообщения: %s", e)
    except TelegramError as e:
        logger.exception("Ошибка Telegram при отправке сообщения: %s", e)

    return None


# Конфигурирование администраторов из ENV переменных


def configure_admin_ids(admin_ids_str: str | None = None) -> list[int]:
    """Настраивает список ID администраторов из строки или переменной окружения.

    Args:
        admin_ids_str: Строка с ID администраторов через запятую или None

    Returns:
        list[int]: Список ID администраторов

    """
    # Используем аргумент или переменную окружения
    ids_str = admin_ids_str or os.getenv("TELEGRAM_ADMIN_IDS", "")

    # Разбираем строку в список ID
    admin_ids = []
    if ids_str:
        try:
            for id_str in ids_str.split(","):
                id_str = id_str.strip()
                if id_str:
                    admin_ids.append(int(id_str))
        except ValueError as e:
            logger.exception("Ошибка при разборе ID администраторов: %s", e)

    return admin_ids


def register_global_exception_handlers() -> None:
    """Регистрирует глобальные обработчики исключений для всего приложения.

    Используется для логирования необработанных исключений.
    """

    def exception_handler(exc_type, exc_value, exc_traceback) -> None:
        """Обработчик необработанных исключений."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical(
            "Необработанное исключение",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = exception_handler
    logger.info("Глобальные обработчики исключений зарегистрированы")
