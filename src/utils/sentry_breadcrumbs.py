"""Утилиты для добавления breadcrumbs в Sentry.

Этот модуль предоставляет удобные функции для добавления контекстной информации
в Sentry breadcrumbs, что помогает при отладке ошибок в production.

Breadcrumbs автоматически захватываются Sentry и предоставляют полный контекст
действий пользователя перед возникновением ошибки.
"""

import logging
from typing import Any

import sentry_sdk

logger = logging.getLogger(__name__)


def add_trading_breadcrumb(
    action: str,
    game: str | None = None,
    level: str | None = None,
    user_id: int | None = None,
    balance: float | None = None,
    **extra_data: Any,
) -> None:
    """Добавить breadcrumb для торговых операций.

    Args:
        action: Действие (scanning, buying, selling, etc.)
        game: Название игры (csgo, dota2, tf2, rust)
        level: Уровень арбитража (boost, standard, medium, advanced, pro)
        user_id: ID пользователя Telegram
        balance: Текущий баланс
        **extra_data: Дополнительные данные для контекста

    Example:
        add_trading_breadcrumb(
            action='scanning_market',
            game='csgo',
            level='standard',
            user_id=123456789,
            balance=100.50,
            item_count=50
        )
    """
    if not sentry_sdk.is_initialized():
        return

    data: dict[str, Any] = {}

    if game:
        data["game"] = game
    if level:
        data["level"] = level
    if user_id:
        data["user_id"] = user_id
    if balance is not None:
        data["balance"] = f"${balance:.2f}"

    # Добавляем дополнительные данные
    data.update(extra_data)

    sentry_sdk.add_breadcrumb(
        category="trading",
        message=f"Trading action: {action}",
        level="info",
        data=data,
    )

    logger.debug("Sentry breadcrumb added: trading/%s", action, extra={"data": data})


def add_api_breadcrumb(
    endpoint: str,
    method: str = "GET",
    status_code: int | None = None,
    response_time_ms: float | None = None,
    **extra_data: Any,
) -> None:
    """Добавить breadcrumb для API запросов.

    Args:
        endpoint: API эндпоинт (например, /marketplace-api/v1/items)
        method: HTTP метод (GET, POST, PATCH, DELETE)
        status_code: HTTP статус код ответа
        response_time_ms: Время ответа в миллисекундах
        **extra_data: Дополнительные данные

    Example:
        add_api_breadcrumb(
            endpoint='/marketplace-api/v1/items',
            method='GET',
            status_code=200,
            response_time_ms=250.5,
            game='csgo'
        )
    """
    if not sentry_sdk.is_initialized():
        return

    data: dict[str, Any] = {
        "endpoint": endpoint,
        "method": method,
    }

    if status_code is not None:
        data["status_code"] = status_code
    if response_time_ms is not None:
        data["response_time_ms"] = f"{response_time_ms:.2f}"

    data.update(extra_data)

    sentry_sdk.add_breadcrumb(
        category="http",
        message=f"API request: {method} {endpoint}",
        level="info",
        data=data,
    )

    logger.debug(
        "Sentry breadcrumb added: http/%s %s",
        method,
        endpoint,
        extra={"data": data},
    )


def add_command_breadcrumb(
    command: str,
    user_id: int,
    username: str | None = None,
    chat_id: int | None = None,
    **extra_data: Any,
) -> None:
    """Добавить breadcrumb для команд Telegram бота.

    Args:
        command: Название команды (start, balance, scan, etc.)
        user_id: ID пользователя Telegram
        username: Username пользователя
        chat_id: ID чата
        **extra_data: Дополнительные данные

    Example:
        add_command_breadcrumb(
            command='scan',
            user_id=123456789,
            username='john_doe',
            chat_id=-1001234567890,
            game='csgo',
            level='standard'
        )
    """
    if not sentry_sdk.is_initialized():
        return

    data: dict[str, Any] = {
        "command": command,
        "user_id": user_id,
    }

    if username:
        data["username"] = username
    if chat_id:
        data["chat_id"] = chat_id

    data.update(extra_data)

    sentry_sdk.add_breadcrumb(
        category="telegram",
        message=f"Bot command: /{command}",
        level="info",
        data=data,
    )

    logger.debug(
        "Sentry breadcrumb added: telegram/%s",
        command,
        extra={"data": data},
    )


def add_database_breadcrumb(
    operation: str,
    table: str | None = None,
    record_id: int | None = None,
    affected_rows: int | None = None,
    **extra_data: Any,
) -> None:
    """Добавить breadcrumb для операций с БД.

    Args:
        operation: Тип операции (select, insert, update, delete)
        table: Название таблицы
        record_id: ID записи
        affected_rows: Количество затронутых записей
        **extra_data: Дополнительные данные

    Example:
        add_database_breadcrumb(
            operation='insert',
            table='market_data',
            affected_rows=100,
            batch_size=100
        )
    """
    if not sentry_sdk.is_initialized():
        return

    data: dict[str, Any] = {
        "operation": operation,
    }

    if table:
        data["table"] = table
    if record_id is not None:
        data["record_id"] = record_id
    if affected_rows is not None:
        data["affected_rows"] = affected_rows

    data.update(extra_data)

    sentry_sdk.add_breadcrumb(
        category="database",
        message=f"DB operation: {operation}",
        level="info",
        data=data,
    )

    logger.debug(
        "Sentry breadcrumb added: database/%s",
        operation,
        extra={"data": data},
    )


def add_error_breadcrumb(
    error_type: str,
    error_message: str,
    severity: str = "error",
    **extra_data: Any,
) -> None:
    """Добавить breadcrumb для ошибок.

    Args:
        error_type: Тип ошибки (ValueError, APIError, etc.)
        error_message: Сообщение об ошибке
        severity: Серьезность (info, warning, error, fatal)
        **extra_data: Дополнительные данные

    Example:
        add_error_breadcrumb(
            error_type='RateLimitError',
            error_message='Too many requests',
            severity='warning',
            retry_after=60
        )
    """
    if not sentry_sdk.is_initialized():
        return

    data: dict[str, Any] = {
        "error_type": error_type,
        "error_message": error_message,
    }

    data.update(extra_data)

    sentry_sdk.add_breadcrumb(
        category="error",
        message=f"Error: {error_type}",
        level=severity,
        data=data,
    )

    logger.debug(
        "Sentry breadcrumb added: error/%s",
        error_type,
        extra={"data": data},
    )


def add_custom_breadcrumb(category: str, message: str, level: str = "info", **data: Any) -> None:
    """Добавить кастомный breadcrumb.

    Args:
        category: Категория breadcrumb
        message: Сообщение
        level: Уровень (debug, info, warning, error, fatal)
        **data: Данные breadcrumb

    Example:
        add_custom_breadcrumb(
            category='cache',
            message='Cache hit',
            level='debug',
            cache_key='market_items_csgo',
            ttl=300
        )
    """
    if not sentry_sdk.is_initialized():
        return

    sentry_sdk.add_breadcrumb(category=category, message=message, level=level, data=data)

    logger.debug(
        "Sentry breadcrumb added: %s/%s",
        category,
        message,
        extra={"data": data},
    )


def set_user_context(user_id: int, username: str | None = None, **extra: Any) -> None:
    """Установить контекст пользователя для Sentry.

    Args:
        user_id: ID пользователя Telegram
        username: Username пользователя
        **extra: Дополнительные данные пользователя

    Example:
        set_user_context(
            user_id=123456789,
            username='john_doe',
            subscription='premium',
            balance=100.50
        )
    """
    if not sentry_sdk.is_initialized():
        return

    user_data: dict[str, Any] = {
        "id": str(user_id),
    }

    if username:
        user_data["username"] = username

    user_data.update(extra)

    sentry_sdk.set_user(user_data)

    logger.debug(
        "Sentry user context set: user_id=%s",
        user_id,
        extra={"data": user_data},
    )


def set_context_tag(key: str, value: str | float | bool) -> None:
    """Установить тег контекста для Sentry.

    Args:
        key: Название тега
        value: Значение тега

    Example:
        set_context_tag('game', 'csgo')
        set_context_tag('trading_level', 'standard')
    """
    if not sentry_sdk.is_initialized():
        return

    sentry_sdk.set_tag(key, value)

    logger.debug(f"Sentry tag set: {key}={value}")


def clear_breadcrumbs() -> None:
    """Очистить все breadcrumbs в текущем scope."""
    if not sentry_sdk.is_initialized():
        return

    # Создать новый scope для очистки breadcrumbs
    with sentry_sdk.push_scope():
        pass

    logger.debug("Sentry breadcrumbs cleared")
