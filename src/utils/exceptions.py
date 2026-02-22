"""Централизованный модуль обработки исключений для DMarket Bot.

Содержит базовые классы исключений, специфичные исключения API,
и утилиты для обработки ошибок.
"""

import asyncio
import functools
import logging
import traceback
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar, cast, overload

# from src.utils.canonical_logging import get_logger # Removed in favor of canonical_logging

# Определение универсального типа для декораторов
F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


def get_logger(name: str) -> logging.Logger:
    """Compatibility wrapper to get logger."""
    return logging.getLogger(name)


class ErrorCode(Enum):
    """Перечисление кодов ошибок для унификации обработки."""

    UNKNOWN_ERROR = 1000
    API_ERROR = 2000
    VALIDATION_ERROR = 3000
    AUTH_ERROR = 4000
    RATE_LIMIT_ERROR = 5000
    NETWORK_ERROR = 6000
    DATABASE_ERROR = 7000
    BUSINESS_LOGIC_ERROR = 8000


class BaseAppException(Exception):
    """Базовый класс для всех исключений приложения.

    Attributes:
        code: Код ошибки из перечисления ErrorCode.
        message: Сообщение об ошибке.
        details: Дополнительные детали ошибки.
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode | int = ErrorCode.UNKNOWN_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализирует исключение.

        Args:
            message: Сообщение об ошибке.
            code: Код ошибки.
            details: Дополнительная информация об ошибке.
        """
        self.code = code if isinstance(code, int) else code.value
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Преобразует исключение в словарь для логирования или API-ответа."""
        result = {
            "code": self.code,
            "message": self.message,
        }

        if self.details:
            result["details"] = self.details

        return result

    def __str__(self) -> str:
        """Строковое представление исключения."""
        details_str = f", details: {self.details}" if self.details else ""
        return f"{self.__class__.__name__}(code={self.code}, message='{self.message}'{details_str})"


class APIError(BaseAppException):
    """Исключение, связанное с внешними API."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: ErrorCode | int = ErrorCode.API_ERROR,
        details: dict[str, Any] | None = None,
        response_body: str | None = None,
    ) -> None:
        """Инициализирует исключение API.

        Args:
            message: Сообщение об ошибке.
            status_code: HTTP статус-код ответа.
            code: Внутренний код ошибки.
            details: Дополнительная информация.
            response_body: Тело ответа от API.
        """
        details = details or {}
        details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body
        super().__init__(message, code, details)
        self.status_code = status_code

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return f"Ошибка API (код {self.status_code}): {self.message}"


class AuthenticationError(APIError):
    """Ошибка аутентификации (401)."""

    def __init__(
        self,
        message: str = "Ошибка авторизации в API",
        status_code: int = 401,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, ErrorCode.AUTH_ERROR, details)

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return f"Ошибка аутентификации: проверьте ваши API ключи или токен.\nДетали: {self.message}"


class ForbiddenError(APIError):
    """Доступ запрещен (403)."""

    def __init__(
        self,
        message: str = "Доступ запрещен",
        status_code: int = 403,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, ErrorCode.API_ERROR, details)

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return (
            f"Доступ запрещен: у вас нет прав для выполнения этого действия.\n"
            f"Детали: {self.message}"
        )


class NotFoundError(APIError):
    """Ресурс не найден (404)."""

    def __init__(
        self,
        message: str = "Запрашиваемый ресурс не найден",
        status_code: int = 404,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, ErrorCode.API_ERROR, details)

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return f"Ресурс не найден: запрашиваемые данные не существуют.\nДетали: {self.message}"


class RateLimitExceeded(APIError):
    """Превышен лимит запросов (429)."""

    def __init__(
        self,
        message: str = "Превышен лимит запросов",
        status_code: int = 429,
        response_data: dict[str, Any] | None = None,
        retry_after: int = 60,
    ) -> None:
        """Инициализирует исключение о превышении лимита запросов.

        Args:
            message: Сообщение об ошибке
            status_code: HTTP статус-код ответа
            response_data: Данные ответа API
            retry_after: Рекомендуемое время ожидания в секундах
        """
        super().__init__(
            message, status_code, ErrorCode.RATE_LIMIT_ERROR, response_data
        )
        self.retry_after = retry_after

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return (
            f"Превышен лимит запросов: пожалуйста, подождите "
            f"{self.retry_after} секунд.\n"
            f"Детали: {self.message}"
        )


class NetworkError(BaseAppException):
    """Исключение, связанное с сетевыми ошибками."""

    def __init__(
        self,
        message: str = "Ошибка сети",
        code: ErrorCode | int = ErrorCode.NETWORK_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализирует исключение сетевой ошибки.

        Args:
            message: Сообщение об ошибке
            code: Внутренний код ошибки
            details: Дополнительная информация
        """
        super().__init__(message, code, details)


class ServerError(APIError):
    """Серверная ошибка (5xx)."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, ErrorCode.API_ERROR, details)

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return (
            f"Ошибка сервера: произошла внутренняя ошибка на сервере.\n"
            f"Код: {self.status_code}\n"
            f"Детали: {self.message}"
        )


class BadRequestError(APIError):
    """Ошибка в запросе клиента (400)."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, ErrorCode.API_ERROR, details)

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return f"Неверный запрос: проверьте параметры вашего запроса.\nДетали: {self.message}"


class DMarketSpecificError(APIError):
    """Ошибки, специфичные для DMarket API."""

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response_data: dict[str, Any] | None = None,
        error_code: str = "",
    ) -> None:
        """Инициализирует исключение для ошибок, специфичных для DMarket API.

        Args:
            message: Сообщение об ошибке
            status_code: HTTP статус-код ответа
            response_data: Данные ответа API
            error_code: Код ошибки DMarket API
        """
        super().__init__(message, status_code, ErrorCode.API_ERROR, response_data)
        self._error_code = error_code

    @property
    def error_code(self) -> str:
        """Код ошибки из ответа API."""
        if self._error_code:
            return self._error_code
        if isinstance(self.details, dict):
            return str(
                self.details.get(
                    "code",
                    self.details.get(
                        "error_code",
                        self.details.get("error", ""),
                    ),
                ),
            )
        return ""

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        code_msg = f" (код {self.error_code})" if self.error_code else ""
        return f"Ошибка DMarket API{code_msg}: {self.message}"


class InsufficientFundsError(DMarketSpecificError):
    """Недостаточно средств для выполнения операции."""

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return "Недостаточно средств на балансе для выполнения операции."


class ItemNotAvAlgolableError(DMarketSpecificError):
    """Предмет недоступен для покупки/продажи."""

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return "Предмет более недоступен для покупки или продажи."


class TemporaryUnavAlgolableError(DMarketSpecificError):
    """API временно недоступно."""

    @property
    def human_readable(self) -> str:
        """Человекочитаемое сообщение об ошибке."""
        return "API DMarket временно недоступно. Пожалуйста, попробуйте позже."


class ValidationError(BaseAppException):
    """Исключение при ошибках валидации данных."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        code: ErrorCode | int = ErrorCode.VALIDATION_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализирует исключение валидации.

        Args:
            message: Сообщение об ошибке.
            field: Поле, вызвавшее ошибку валидации.
            code: Код ошибки.
            details: Дополнительная информация.
        """
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, code, details)


class BusinessLogicError(BaseAppException):
    """Исключение при ошибках бизнес-логики."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        code: ErrorCode | int = ErrorCode.BUSINESS_LOGIC_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализирует исключение бизнес-логики.

        Args:
            message: Сообщение об ошибке.
            operation: Операция, вызвавшая ошибку.
            code: Код ошибки.
            details: Дополнительная информация.
        """
        details = details or {}
        if operation:
            details["operation"] = operation
        super().__init__(message, code, details)


# Словарь для маппинга кодов ошибок DMarket на классы исключений
DMARKET_ERROR_MAPPING = {
    "InsuficientAmount": InsufficientFundsError,
    "NotEnoughMoney": InsufficientFundsError,
    "ItemNotFound": ItemNotAvAlgolableError,
    "WalletNotFound": DMarketSpecificError,
    "OfferNotFound": ItemNotAvAlgolableError,
    "TemporaryUnavAlgolable": TemporaryUnavAlgolableError,
    "ServiceUnavAlgolable": TemporaryUnavAlgolableError,
}


def categorize_error(error: Exception) -> str:
    """Определяет категорию ошибки на основе типа исключения и сообщения.

    Args:
        error: Исключение для категоризации

    Returns:
        Строка с категорией ошибки
    """
    if isinstance(error, RateLimitExceeded):
        return "RATE_LIMIT_ERROR"
    if isinstance(error, AuthenticationError):
        return "AUTH_ERROR"
    if isinstance(error, InsufficientFundsError):
        return "BALANCE_ERROR"
    if isinstance(error, APIError):
        return "API_ERROR"
    if isinstance(error, ValidationError):
        return "VALIDATION_ERROR"

    error_msg = str(error).lower()

    # Определяем категорию по типу и содержимому ошибки
    if "connection" in error_msg or "timeout" in error_msg or "socket" in error_msg:
        return "NETWORK_ERROR"

    if "api" in error_msg or "request" in error_msg or "response" in error_msg:
        return "API_ERROR"

    if (
        "auth" in error_msg
        or "token" in error_msg
        or "key" in error_msg
        or "unauthorized" in error_msg
    ):
        return "AUTH_ERROR"

    if "balance" in error_msg or "insufficient" in error_msg or "funds" in error_msg:
        return "BALANCE_ERROR"

    if "json" in error_msg or "parse" in error_msg or "data" in error_msg:
        return "DATA_ERROR"

    # По умолчанию считаем ошибку внутренней
    return "INTERNAL_ERROR"


def format_error_for_user(
    error: Exception | str,
    with_details: bool = False,
    lang: str = "ru",
) -> str:
    """Форматирует сообщение об ошибке для пользователя.

    Args:
        error: Исключение или строка с сообщением об ошибке
        with_details: Включать ли детали ошибки
        lang: Язык сообщения

    Returns:
        Отформатированное сообщение об ошибке
    """
    # Если это исключение с human_readable, используем его
    if hasattr(error, "human_readable"):
        return f"❌ {error.human_readable}"

    # Определяем базовый текст ошибки
    if isinstance(error, Exception):
        error_message = str(error)
        error_type = type(error).__name__
        category = categorize_error(error)
    else:
        error_message = str(error)
        error_type = "Error"
        category = "INTERNAL_ERROR"

    # Формируем базовое сообщение в зависимости от языка и категории
    if lang == "ru":
        base_messages = {
            "API_ERROR": "Ошибка API DMarket",
            "NETWORK_ERROR": "Ошибка сети",
            "AUTH_ERROR": "Ошибка авторизации",
            "BALANCE_ERROR": "Недостаточно средств",
            "DATA_ERROR": "Ошибка данных",
            "VALIDATION_ERROR": "Ошибка валидации",
            "RATE_LIMIT_ERROR": "Превышен лимит запросов",
            "INTERNAL_ERROR": "Внутренняя ошибка бота",
        }
    else:  # По умолчанию используем английский
        base_messages = {
            "API_ERROR": "DMarket API error",
            "NETWORK_ERROR": "Network error",
            "AUTH_ERROR": "Authorization error",
            "BALANCE_ERROR": "Insufficient funds",
            "DATA_ERROR": "Data error",
            "VALIDATION_ERROR": "Validation error",
            "RATE_LIMIT_ERROR": "Rate limit exceeded",
            "INTERNAL_ERROR": "Internal bot error",
        }

    # Получаем базовое сообщение для категории или используем общее
    base_message = base_messages.get(category, "Error")

    # Если нужно показать детали, добавляем их
    if with_details:
        if lang == "ru":
            return f"❌ {base_message}: {error_message}\n\nТип: {error_type}"
        return f"❌ {base_message}: {error_message}\n\nType: {error_type}"
    if lang == "ru":
        return f"❌ {base_message}. Пожалуйста, попробуйте позже или обратитесь к администратору."
    return f"❌ {base_message}. Please try agAlgon later or contact the administrator."


@overload
def handle_exceptions(  # noqa: UP047
    func_or_logger: F,
    default_error_message: str = ...,
    reraise: bool = ...,
    *,
    logger_instance: logging.Logger | None = ...,
) -> F: ...


@overload
def handle_exceptions(  # noqa: UP047
    func_or_logger: logging.Logger | None = ...,
    default_error_message: str = ...,
    reraise: bool = ...,
    *,
    logger_instance: logging.Logger | None = ...,
) -> Callable[[F], F]: ...


def handle_exceptions(  # noqa: UP047
    func_or_logger: Callable[..., Any] | logging.Logger | None = None,
    default_error_message: str = "Произошла ошибка",
    reraise: bool = True,
    *,
    logger_instance: logging.Logger | None = None,
) -> Callable[[F], F] | F:
    """Декоратор для обработки исключений с логированием.

    Поддерживает как синхронные, так и асинхронные функции.
    Может быть использован со скобками @handle_exceptions() или без @handle_exceptions.

    Args:
        func_or_logger: Функция (если без скобок) или логгер (если со скобками).
        default_error_message: Сообщение по умолчанию при ошибке.
        reraise: Если True, исключение будет выброшено повторно.

    Returns:
        Декорированная функция.

    Examples:
        # Использование без скобок
        @handle_exceptions
        async def my_handler(update, context):
            pass

        # Использование со скобками
        @handle_exceptions(default_error_message="Ошибка обработки")
        async def my_handler(update, context):
            pass
    """
    # Определяем, был ли декоратор вызван без скобок (func передан напрямую)
    is_called_without_parens = callable(func_or_logger) and not isinstance(
        func_or_logger, logging.Logger
    )

    # Получаем логгер: сначала из logger_instance, потом из func_or_logger
    effective_logger: logging.Logger | None = (
        logger_instance  # Явно переданный через logger_instance=
        if logger_instance is not None
        else (
            None
            if is_called_without_parens
            else func_or_logger if isinstance(func_or_logger, logging.Logger) else None
        )
    )

    def decorator(func: F) -> F:
        # Создаем логгер на основе имени функции, если не передан
        nonlocal effective_logger
        if effective_logger is None:
            effective_logger = get_logger(f"{func.__module__}.{func.__qualname__}")

        async def _send_error_to_user(
            args: tuple[Any, ...], error_message: str
        ) -> None:
            """Отправить сообщение об ошибке пользователю."""
            # Проверяем как args[0] (для функций), так и args[1] (для методов класса)
            update = None
            if args:
                # Для методов класса Update может быть во втором аргументе
                if len(args) > 1 and hasattr(args[1], "message"):
                    update = args[1]
                # Для обычных функций Update в первом аргументе
                elif hasattr(args[0], "message"):
                    update = args[0]

            if update:
                # Проверка на callback query (должен быть не None)
                if (
                    hasattr(update, "callback_query")
                    and update.callback_query is not None
                ):
                    try:
                        if hasattr(update.callback_query, "answer"):
                            await update.callback_query.answer(
                                text=f"❌ {error_message}",
                                show_alert=True,
                            )
                    except Exception as answer_error:
                        effective_logger.exception(
                            f"Не удалось отправить answer: {answer_error!s}"
                        )
                elif update.message and hasattr(update.message, "reply_text"):
                    try:
                        await update.message.reply_text(
                            f"❌ {error_message}",
                        )
                    except Exception as reply_error:
                        effective_logger.exception(
                            f"Не удалось отправить сообщение: {reply_error!s}"
                        )

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except BaseAppException as e:
                # Логируем исключение приложения
                effective_logger.exception(
                    f"{default_error_message}: {e!s}",
                    extra={"context": e.to_dict()},
                )

                # Отправляем сообщение об ошибке пользователю
                if not reraise:
                    await _send_error_to_user(args, default_error_message)

                if reraise:
                    raise
            except Exception as e:
                # Логируем неожиданное исключение
                error_details = {
                    "exception_type": e.__class__.__name__,
                    "traceback": traceback.format_exc().split("\n"),
                }
                effective_logger.exception(
                    f"Необработанное исключение в {func.__qualname__}: {e!s}",
                    extra={"context": error_details},
                )

                # Отправляем сообщение об ошибке пользователю
                if not reraise:
                    await _send_error_to_user(args, default_error_message)

                if reraise:
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except BaseAppException as e:
                # Логируем исключение приложения
                effective_logger.exception(
                    f"{default_error_message}: {e!s}",
                    extra={"context": e.to_dict()},
                )
                if reraise:
                    raise
            except Exception as e:
                # Логируем неожиданное исключение
                error_details = {
                    "exception_type": e.__class__.__name__,
                    "traceback": traceback.format_exc().split("\n"),
                }
                effective_logger.exception(
                    f"Необработанное исключение в {func.__qualname__}: {e!s}",
                    extra={"context": error_details},
                )
                if reraise:
                    raise

        if asyncio.iscoroutinefunction(func):
            return cast("F", async_wrapper)
        return cast("F", sync_wrapper)

    # Если вызван без скобок - применяем decorator к функции напрямую
    if is_called_without_parens:
        return decorator(cast("F", func_or_logger))
    return decorator


# Retry strategy enumeration
class RetryStrategy(Enum):
    """Стратегия повторных попыток при ошибках."""

    EXPONENTIAL_BACKOFF = "exponential"
    LINEAR_BACKOFF = "linear"
    FIXED_DELAY = "fixed"
    NO_RETRY = "none"


# API error handler function
def handle_api_error(
    error: Exception,
    context: dict[str, Any] | None = None,
    logger_instance: logging.Logger | None = None,
) -> None:
    """Handle API errors with logging.

    Args:
        error: Exception to handle
        context: Additional context information
        logger_instance: Logger instance to use

    """
    log = logger_instance or logger
    error_context = context or {}

    if isinstance(error, APIError):
        log.error(
            f"API Error: {error.message}",
            extra={"status_code": error.status_code, **error_context},
        )
    else:
        log.error(f"Unexpected error: {error}", extra=error_context)


# Async retry decorator
def retry_async(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    exceptions: tuple[type[Exception], ...] = (APIError, NetworkError),
) -> Callable[[F], F]:
    """Decorator for retrying async functions with backoff strategy.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        retry_strategy: Strategy for calculating retry delays
        exceptions: Tuple of exception types to retry on

    Returns:
        Decorated function with retry logic

    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        # Calculate delay based on strategy
                        if retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                            delay = retry_delay * (2**attempt)
                        elif retry_strategy == RetryStrategy.LINEAR_BACKOFF:
                            delay = retry_delay * (attempt + 1)
                        else:  # FIXED_DELAY
                            delay = retry_delay

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed, "
                            f"retrying in {delay}s: {e}",
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.exception(f"All {max_retries} attempts failed: {e}")
                        raise

            if last_error:
                raise last_error
            return None

        return cast("F", wrapper)

    return decorator


# Aliases for backward compatibility
RateLimitError = RateLimitExceeded
