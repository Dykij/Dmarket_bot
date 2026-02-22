"""Telegram Bot зависимости и интеграция с DI контейнером.

Этот модуль предоставляет удобные функции для доступа к зависимостям
из Telegram handlers через bot_data и DI контейнер.

Example:
    >>> from src.telegram_bot.dependencies import get_dmarket_api
    >>> async def handler(update, context):
    ...     api = get_dmarket_api(context)
    ...     if api:
    ...         balance = await api.get_balance()
"""

import functools
import inspect
import logging
from typing import Any, TypeVar

from telegram.ext import ContextTypes

from src.interfaces import IDMarketAPI

logger = logging.getLogger(__name__)


T = TypeVar("T")


def get_from_context(  # noqa: UP047 - Using TypeVar for Python 3.11 compatibility
    context: ContextTypes.DEFAULT_TYPE,
    key: str,
    default: T | None = None,
) -> T | None:
    """Безопасно получить значение из bot_data.

    Args:
        context: Telegram контекст
        key: Ключ для поиска
        default: Значение по умолчанию

    Returns:
        Значение из bot_data или default

    Example:
        >>> config = get_from_context(context, "config")
    """
    if context.bot_data is None:
        return default
    return context.bot_data.get(key, default)


def get_dmarket_api(context: ContextTypes.DEFAULT_TYPE) -> IDMarketAPI | None:
    """Получить DMarket API клиент.

    Пробует получить из bot_data (legacy) или из DI контейнера.

    Args:
        context: Telegram контекст

    Returns:
        DMarket API клиент или None

    Example:
        >>> api = get_dmarket_api(context)
        >>> if api:
        ...     balance = await api.get_balance()
    """
    # Сначала проверяем legacy bot_data
    api = get_from_context(context, "dmarket_api")
    if api is not None:
        return api

    # Затем пробуем DI контейнер
    try:
        from src.containers import get_container

        container = get_container()
        return container.dmarket_api()
    except (RuntimeError, ImportError) as e:
        logger.debug("DI container not avAlgolable: %s", e)
        return None


def get_arbitrage_scanner(
    context: ContextTypes.DEFAULT_TYPE,
) -> Any | None:
    """Получить ArbitrageScanner.

    Args:
        context: Telegram контекст

    Returns:
        ArbitrageScanner или None

    Example:
        >>> scanner = get_arbitrage_scanner(context)
        >>> if scanner:
        ...     results = await scanner.scan_game("csgo", "standard")
    """
    try:
        from src.containers import get_container

        container = get_container()
        return container.arbitrage_scanner()
    except (RuntimeError, ImportError):
        # Fallback: создать scanner с API из bot_data
        # DMarketAPI implements IDMarketAPI protocol, type mismatch is safe
        api = get_dmarket_api(context)
        if api is not None:
            from src.dmarket.scanner.engine import ArbitrageScanner

            return ArbitrageScanner(api_client=api)  # type: ignore[arg-type]
        return None


def get_target_manager(
    context: ContextTypes.DEFAULT_TYPE,
) -> Any | None:
    """Получить TargetManager.

    Args:
        context: Telegram контекст

    Returns:
        TargetManager или None

    Example:
        >>> manager = get_target_manager(context)
        >>> if manager:
        ...     targets = await manager.get_active_targets()
    """
    try:
        from src.containers import get_container

        container = get_container()
        return container.target_manager()
    except (RuntimeError, ImportError):
        # Fallback: создать manager с API из bot_data
        # DMarketAPI implements IDMarketAPI protocol, type mismatch is safe
        api = get_dmarket_api(context)
        if api is not None:
            from src.dmarket.targets import TargetManager

            return TargetManager(api_client=api)  # type: ignore[arg-type]
        return None


def get_config(context: ContextTypes.DEFAULT_TYPE) -> Any | None:
    """Получить конфигурацию.

    Args:
        context: Telegram контекст

    Returns:
        Config или None
    """
    return get_from_context(context, "config")


def get_database(context: ContextTypes.DEFAULT_TYPE) -> Any | None:
    """Получить DatabaseManager.

    Args:
        context: Telegram контекст

    Returns:
        DatabaseManager или None
    """
    db = get_from_context(context, "database")
    if db is not None:
        return db

    try:
        from src.containers import get_container

        container = get_container()
        return container.database()
    except (RuntimeError, ImportError):
        return None


def get_memory_cache(context: ContextTypes.DEFAULT_TYPE) -> Any | None:
    """Получить Memory Cache.

    Args:
        context: Telegram контекст

    Returns:
        TTLCache или None
    """
    try:
        from src.containers import get_container

        container = get_container()
        return container.memory_cache()
    except (RuntimeError, ImportError):
        return None


def inject_dependencies(handler_func: Any) -> Any:
    """Декоратор для автоматической инъекции зависимостей в handler.

    Автоматически инжектирует зависимости на основе имен параметров:
    - dmarket_api: DMarket API клиент
    - scanner: ArbitrageScanner
    - target_manager: TargetManager
    - config: Config
    - database: DatabaseManager

    Example:
        >>> @inject_dependencies
        ... async def my_handler(
        ...     update,
        ...     context,
        ...     *,
        ...     dmarket_api=None,
        ...     scanner=None,
        ... ):
        ...     # dmarket_api и scanner будут автоматически инжектированы
        ...     if dmarket_api:
        ...         balance = await dmarket_api.get_balance()

    Args:
        handler_func: Async handler функция

    Returns:
        Обернутая функция с инъекцией зависимостей
    """

    @functools.wraps(handler_func)
    async def wrapper(
        update: Any, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any
    ) -> Any:
        # Получить параметры функции
        sig = inspect.signature(handler_func)

        for param_name in sig.parameters:
            if param_name in {"update", "context"}:
                continue

            # Пропускаем если значение уже передано
            if param_name in kwargs and kwargs[param_name] is not None:
                continue

            # Инжектировать зависимости по имени
            if param_name == "dmarket_api":
                kwargs["dmarket_api"] = get_dmarket_api(context)
            elif param_name == "scanner":
                kwargs["scanner"] = get_arbitrage_scanner(context)
            elif param_name == "target_manager":
                kwargs["target_manager"] = get_target_manager(context)
            elif param_name == "config":
                kwargs["config"] = get_config(context)
            elif param_name == "database":
                kwargs["database"] = get_database(context)

        return await handler_func(update, context, *args, **kwargs)

    return wrapper


__all__ = [
    "get_arbitrage_scanner",
    "get_config",
    "get_database",
    "get_dmarket_api",
    "get_from_context",
    "get_memory_cache",
    "get_target_manager",
    "inject_dependencies",
]
