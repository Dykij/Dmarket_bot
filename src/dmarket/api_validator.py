"""
Утилиты для валидации ответов DMarket API с помощью Pydantic схем.

Этот модуль предоставляет декораторы и функции для автоматической валидации
ответов API и отправки уведомлений при изменении формата API.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from src.telegram_bot.notifier import Notifier

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def send_api_change_notification(
    endpoint: str,
    validation_error: ValidationError,
    response_data: dict[str, Any],
    notifier: "Notifier | None" = None,
) -> None:
    """
    Отправить критическое уведомление об изменении формата DMarket API.

    Args:
        endpoint: Эндпоинт API, который вернул невалидный ответ
        validation_error: Ошибка валидации Pydantic
        response_data: Данные ответа от API
        notifier: Инстанс Notifier для отправки уведомлений
    """
    error_count = len(validation_error.errors())
    first_errors = validation_error.errors()[:3]  # Первые 3 ошибки

    error_details = "\n".join([f"- {err['loc']}: {err['msg']}" for err in first_errors])

    message = f"""
🚨 КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ DMarket API

📍 Эндпоинт: {endpoint}
❌ Ошибок валидации: {error_count}

Первые ошибки:
{error_details}

⚠️ API DMarket изменился! Требуется обновление схем валидации.
"""

    logger.critical(
        "API_SCHEMA_CHANGE_DETECTED",
        extra={
            "endpoint": endpoint,
            "validation_errors": error_count,
            "first_errors": first_errors,
            "response_sample": str(response_data)[:500],
        },
    )

    # Отправляем уведомление, если доступен notifier
    if notifier:
        try:
            await notifier.send_message(
                message=message,
                priority="critical",
                category="system",
            )
        except Exception as e:
            logger.exception(f"Failed to send API change notification: {e}")


def validate_response(  # noqa: UP047
    schema: type[T],
    endpoint: str = "unknown",
) -> Callable:
    """
    Декоратор для автоматической валидации ответов API через Pydantic схемы.

    При ValidationError:
    - Логирует критическую ошибку
    - Отправляет уведомление администраторам (если у instance есть notifier)
    - Возвращает исходные данные без валидации

    Args:
        schema: Pydantic модель для валидации
        endpoint: Название эндпоинта (для логирования)

    Returns:
        Декоратор функции

    Example:
        @validate_response(BalanceResponse, endpoint="/account/v1/balance")
        async def get_balance(self) -> dict[str, Any]:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any] | T:
            # Вызываем оригинальную функцию
            response_data = await func(*args, **kwargs)

            # Если ответ содержит ошибку, не валидируем
            if isinstance(response_data, dict) and response_data.get("error"):
                return response_data

            # Пытаемся валидировать через схему
            try:
                schema.model_validate(response_data)
                logger.debug(f"API response validated successfully for {endpoint}")
                # Возвращаем исходные данные (dict) для backward compatibility
                return response_data
            except ValidationError as e:
                # Критическая ошибка - формат API изменился!
                logger.critical(
                    f"VALIDATION_FAlgoLED for {endpoint}: {e}",
                    extra={
                        "endpoint": endpoint,
                        "validation_error": str(e),
                        "response": response_data,
                    },
                )

                # Получаем notifier из instance если доступен
                notifier = None
                if args and hasattr(args[0], "notifier"):
                    notifier = args[0].notifier

                # Отправляем уведомление асинхронно
                try:
                    await send_api_change_notification(
                        endpoint=endpoint,
                        validation_error=e,
                        response_data=response_data,
                        notifier=notifier,
                    )
                except Exception as notify_error:
                    logger.exception(f"Failed to send notification: {notify_error}")

                # Возвращаем невалидированные данные для backward compatibility
                logger.warning(
                    f"Returning unvalidated data for {endpoint} due to validation failure"
                )
                return response_data

        return wrapper

    return decorator


def validate_and_log(  # noqa: UP047
    data: dict[str, Any],
    schema: type[T],
    endpoint: str = "unknown",
) -> T | dict[str, Any]:
    """
    Синхронная функция для валидации данных с логированием.

    Используется когда декоратор не подходит (например, внутри метода).

    Args:
        data: Данные для валидации
        schema: Pydantic модель
        endpoint: Название эндпоинта (для логирования)

    Returns:
        Валидированная модель или исходные данные при ошибке
    """
    try:
        validated = schema.model_validate(data)
        logger.debug(f"Data validated successfully for {endpoint}")
        return validated
    except ValidationError as e:
        logger.warning(
            f"Validation failed for {endpoint}: {e}",
            extra={
                "endpoint": endpoint,
                "validation_error": str(e),
                "data_sample": str(data)[:200],
            },
        )
        return data
