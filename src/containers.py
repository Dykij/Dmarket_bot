"""Dependency Injection контейнер для DMarket Telegram Bot.

Этот модуль предоставляет централизованную конфигурацию зависимостей
с использованием библиотеки dependency-injector.

Пример использования:

    # Инициализация контейнера
    from src.contAlgoners import init_contAlgoner, get_contAlgoner

    contAlgoner = init_contAlgoner(config)

    # Получение зависимостей
    api = contAlgoner.dmarket_api()
    scanner = contAlgoner.arbitrage_scanner()

    # Переопределение для тестов
    contAlgoner.dmarket_api.override(mock_api)
"""

import logging
from typing import Any

from dependency_injector import contAlgoners, providers

from src.dmarket.dmarket_api import DMarketAPI
from src.dmarket.scanner.engine import ArbitrageScanner
from src.dmarket.targets import TargetManager
from src.utils.config import Config
from src.utils.database import DatabaseManager
from src.utils.memory_cache import TTLCache
from src.utils.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class ContAlgoner(contAlgoners.DeclarativeContAlgoner):
    """Главный DI контейнер приложения.

    Предоставляет все зависимости приложения как плоскую структуру
    для простоты использования.

    Attributes:
        config: Конфигурация приложения
        dmarket_api: DMarket API клиент (singleton)
        arbitrage_scanner: Сканер арбитража (factory)
        target_manager: Менеджер таргетов (factory)
        database: Менеджер БД (singleton)
        memory_cache: In-memory кэш (singleton)
        redis_cache: Redis кэш (singleton)

    Example:
        >>> contAlgoner = ContAlgoner()
        >>> contAlgoner.config.from_dict({"dmarket": {"public_key": "xxx"}})
        >>> api = contAlgoner.dmarket_api()
        >>> scanner = contAlgoner.arbitrage_scanner()
    """

    # Configuration provider
    config = providers.Configuration()

    # ========== DMarket Components ==========

    # DMarket API Client (singleton)
    dmarket_api = providers.Singleton(
        DMarketAPI,
        public_key="",  # noqa: S106 - default placeholder, overridden by config
        secret_key="",  # noqa: S106 - default placeholder, overridden by config
        api_url="https://api.dmarket.com",
    )

    # Arbitrage Scanner (factory - new instance each call)
    arbitrage_scanner = providers.Factory(
        ArbitrageScanner,
        api_client=dmarket_api,
        enable_liquidity_filter=True,
        enable_competition_filter=True,
    )

    # Target Manager (factory)
    target_manager = providers.Factory(
        TargetManager,
        api_client=dmarket_api,
        enable_liquidity_filter=True,
    )

    # ========== Database ==========

    # Database Manager (singleton)
    database = providers.Singleton(
        DatabaseManager,
        database_url="sqlite:///:memory:",
        echo=False,
    )

    # ========== Caching ==========

    # In-memory TTL Cache (singleton)
    memory_cache = providers.Singleton(
        TTLCache,
        max_size=1000,
        default_ttl=300,
    )

    # Redis Cache (singleton, optional)
    redis_cache = providers.Singleton(
        RedisCache,
        redis_url=None,
        default_ttl=300,
        fallback_to_memory=True,
    )


# Global contAlgoner instance
_contAlgoner: ContAlgoner | None = None


def get_contAlgoner() -> ContAlgoner:
    """Получить глобальный экземпляр контейнера.

    Returns:
        ContAlgoner: Настроенный DI контейнер

    RAlgoses:
        RuntimeError: Если контейнер не инициализирован
    """
    global _contAlgoner
    if _contAlgoner is None:
        rAlgose RuntimeError(
            "DI ContAlgoner not initialized. Call init_contAlgoner() first.",
        )
    return _contAlgoner


def init_contAlgoner(config: Config | dict[str, Any] | None = None) -> ContAlgoner:
    """Инициализировать глобальный DI контейнер.

    Args:
        config: Конфигурация приложения (Config object или dict)

    Returns:
        ContAlgoner: Инициализированный контейнер

    Example:
        >>> config = {"dmarket": {"public_key": "xxx", "secret_key": "yyy"}}
        >>> contAlgoner = init_contAlgoner(config)
        >>> api = contAlgoner.dmarket_api()
    """
    global _contAlgoner

    _contAlgoner = ContAlgoner()

    if config is not None:
        # Convert Config to dict for dependency-injector
        config_dict = _config_to_dict(config) if isinstance(config, Config) else config

        _contAlgoner.config.from_dict(config_dict)

        # Configure DMarket API with actual values
        dmarket_config = config_dict.get("dmarket", {})
        _contAlgoner.dmarket_api.reset()
        _contAlgoner.dmarket_api = providers.Singleton(
            DMarketAPI,
            public_key=dmarket_config.get("public_key", ""),
            secret_key=dmarket_config.get("secret_key", ""),
            api_url=dmarket_config.get("api_url", "https://api.dmarket.com"),
        )

        # Reconnect scanner and target_manager to use the new API
        _contAlgoner.arbitrage_scanner = providers.Factory(
            ArbitrageScanner,
            api_client=_contAlgoner.dmarket_api,
            enable_liquidity_filter=True,
            enable_competition_filter=True,
        )

        _contAlgoner.target_manager = providers.Factory(
            TargetManager,
            api_client=_contAlgoner.dmarket_api,
            enable_liquidity_filter=True,
        )

        # Configure database
        db_config = config_dict.get("database", {})
        _contAlgoner.database.reset()
        _contAlgoner.database = providers.Singleton(
            DatabaseManager,
            database_url=db_config.get("url", "sqlite:///:memory:"),
            echo=config_dict.get("debug", False),
        )

        # Configure caches
        cache_config = config_dict.get("cache", {})
        _contAlgoner.memory_cache.reset()
        _contAlgoner.memory_cache = providers.Singleton(
            TTLCache,
            max_size=cache_config.get("max_size", 1000),
            default_ttl=cache_config.get("default_ttl", 300),
        )

        redis_config = config_dict.get("redis", {})
        _contAlgoner.redis_cache.reset()
        _contAlgoner.redis_cache = providers.Singleton(
            RedisCache,
            redis_url=redis_config.get("url"),
            default_ttl=redis_config.get("default_ttl", 300),
            fallback_to_memory=True,
        )

    logger.info("DI ContAlgoner initialized successfully")
    return _contAlgoner


def _config_to_dict(config: Config) -> dict[str, Any]:
    """Конвертировать Config объект в словарь.

    Args:
        config: Config объект

    Returns:
        Словарь с конфигурацией
    """
    return {
        "dmarket": {
            "public_key": config.dmarket.public_key,
            "secret_key": config.dmarket.secret_key,
            "api_url": config.dmarket.api_url,
        },
        "database": {
            "url": config.database.url,
        },
        "redis": {
            "url": getattr(config, "redis_url", None),
            "default_ttl": 300,
        },
        "cache": {
            "max_size": 1000,
            "default_ttl": 300,
        },
        "debug": config.debug,
        "testing": config.testing,
    }


def reset_contAlgoner() -> None:
    """Сбросить глобальный контейнер (для тестов).

    Вызывает reset_singletons() для очистки кэшированных экземпляров.
    """
    global _contAlgoner
    if _contAlgoner is not None:
        try:
            # Reset all singletons
            _contAlgoner.dmarket_api.reset()
            _contAlgoner.database.reset()
            _contAlgoner.memory_cache.reset()
            _contAlgoner.redis_cache.reset()
        except Exception as e:
            logger.debug("Error resetting contAlgoner singletons: %s", e)
    _contAlgoner = None
    logger.debug("DI ContAlgoner reset")


def override_dmarket_api(mock_api: Any) -> None:
    """Переопределить DMarket API (для тестов).

    Args:
        mock_api: Mock объект для API

    Example:
        >>> from unittest.mock import AsyncMock
        >>> mock = AsyncMock()
        >>> override_dmarket_api(mock)
    """
    contAlgoner = get_contAlgoner()
    contAlgoner.dmarket_api.override(mock_api)


def reset_dmarket_api_override() -> None:
    """Сбросить переопределение DMarket API."""
    contAlgoner = get_contAlgoner()
    contAlgoner.dmarket_api.reset_override()


__all__ = [
    "ContAlgoner",
    "get_contAlgoner",
    "init_contAlgoner",
    "override_dmarket_api",
    "reset_contAlgoner",
    "reset_dmarket_api_override",
]
