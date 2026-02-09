"""Кэширование результатов арбитража.

Этот модуль предоставляет функции для кэширования результатов
арбитражного анализа с автоматическим управлением TTL и размером.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .constants import CACHE_CLEANUP_COUNT, CACHE_TTL, MAX_CACHE_SIZE

logger = logging.getLogger(__name__)

# =============================================================================
# Глобальный кэш
# =============================================================================

_arbitrage_cache: dict[tuple[Any, ...] | str, tuple[list[dict[str, Any]], float]] = {}
"""Глобальный кэш результатов арбитража.

Формат: {cache_key: (items, timestamp)}
"""

_cache_ttl: int = CACHE_TTL
"""Время жизни кэша в секундах."""


# =============================================================================
# Функции кэширования
# =============================================================================


def get_cached_results(cache_key: str) -> list[dict[str, Any]] | None:
    """Получает кэшированные результаты по ключу.

    Args:
        cache_key: Ключ кэша (строка)

    Returns:
        Список результатов или None, если кэш пуст или устарел

    """
    global _arbitrage_cache  # noqa: PLW0602

    if cache_key not in _arbitrage_cache:
        return None

    items, timestamp = _arbitrage_cache[cache_key]

    # Проверяем актуальность кэша
    if time.time() - timestamp > _cache_ttl:
        logger.debug(f"Кэш устарел для ключа: {cache_key[:50]}...")
        return None

    logger.debug(f"Кэш найден для ключа: {cache_key[:50]}...")
    return items


def save_to_cache(cache_key: str, items: list[dict[str, Any]]) -> None:
    """Сохраняет результаты в кэш.

    Args:
        cache_key: Ключ кэша (строка)
        items: Список результатов для кэширования

    """
    global _arbitrage_cache

    # Ограничиваем размер кэша
    if len(_arbitrage_cache) > MAX_CACHE_SIZE:
        _cleanup_cache()

    _arbitrage_cache[cache_key] = (items, time.time())
    logger.debug(f"Сохранено {len(items)} элементов в кэш: {cache_key[:50]}...")


def get_arbitrage_cache(cache_key: tuple[Any, ...]) -> list[dict[str, Any]] | None:
    """Получает кэшированные результаты арбитража по tuple-ключу.

    Args:
        cache_key: Ключ кэша (кортеж)

    Returns:
        Список возможностей или None, если кэш пуст/устарел

    """
    global _arbitrage_cache  # noqa: PLW0602

    if cache_key not in _arbitrage_cache:
        return None

    items, timestamp = _arbitrage_cache[cache_key]

    # Проверяем актуальность кэша
    if time.time() - timestamp > _cache_ttl:
        return None

    return items


def save_arbitrage_cache(cache_key: tuple[Any, ...], items: list[dict[str, Any]]) -> None:
    """Сохраняет результаты арбитража в кэш.

    Args:
        cache_key: Ключ кэша (кортеж)
        items: Результаты для кэширования

    """
    global _arbitrage_cache

    # Ограничиваем размер кэша
    if len(_arbitrage_cache) > MAX_CACHE_SIZE:
        _cleanup_cache()

    _arbitrage_cache[cache_key] = (items, time.time())
    logger.debug(f"Сохранено {len(items)} возможностей в кэш с ключом {cache_key[0:2]}")


def clear_cache() -> None:
    """Очищает весь кэш арбитража."""
    global _arbitrage_cache
    _arbitrage_cache.clear()
    logger.info("Кэш арбитража очищен")


def get_cache_statistics() -> dict[str, Any]:
    """Возвращает статистику кэша.

    Returns:
        Словарь со статистикой: size, keys, oldest_timestamp, newest_timestamp

    """
    global _arbitrage_cache  # noqa: PLW0602

    if not _arbitrage_cache:
        return {
            "size": 0,
            "keys": [],
            "oldest_timestamp": None,
            "newest_timestamp": None,
        }

    timestamps = [ts for _, ts in _arbitrage_cache.values()]

    return {
        "size": len(_arbitrage_cache),
        "keys": list(_arbitrage_cache.keys()),
        "oldest_timestamp": min(timestamps) if timestamps else None,
        "newest_timestamp": max(timestamps) if timestamps else None,
    }


def set_cache_ttl(ttl_seconds: int) -> None:
    """Устанавливает время жизни кэша.

    Args:
        ttl_seconds: Время жизни в секундах

    """
    global _cache_ttl
    _cache_ttl = ttl_seconds
    logger.info(f"TTL кэша установлен: {ttl_seconds} сек.")


def _cleanup_cache() -> None:
    """Удаляет самые старые записи из кэша."""
    global _arbitrage_cache

    if len(_arbitrage_cache) <= MAX_CACHE_SIZE:
        return

    # Сортируем по времени и удаляем старые
    oldest_keys = sorted(
        _arbitrage_cache.keys(),
        key=lambda k: _arbitrage_cache[k][1],
    )[:CACHE_CLEANUP_COUNT]

    for key in oldest_keys:
        del _arbitrage_cache[key]

    logger.debug(f"Очищено {len(oldest_keys)} старых записей из кэша")


# =============================================================================
# Backward compatibility aliases
# =============================================================================

_get_cached_results = get_cached_results
"""Алиас для обратной совместимости."""

_save_to_cache = save_to_cache
"""Алиас для обратной совместимости."""

_save_arbitrage_cache = save_arbitrage_cache
"""Алиас для обратной совместимости."""


# =============================================================================
# Публичный API модуля
# =============================================================================

__all__ = [
    "_arbitrage_cache",
    "_get_cached_results",
    "_save_arbitrage_cache",
    "_save_to_cache",
    "clear_cache",
    "get_arbitrage_cache",
    "get_cache_statistics",
    "get_cached_results",
    "save_arbitrage_cache",
    "save_to_cache",
    "set_cache_ttl",
]
