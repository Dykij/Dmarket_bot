"""Расчеты для арбитража.

Этот модуль содержит функции для расчета комиссий, прибыли
и вспомогательные функции для анализа арбитражных возможностей.
"""

from __future__ import annotations

from .constants import (
    BASE_COMMISSION_PERCENT,
    GAME_COMMISSION_FACTORS,
    HIGH_POPULARITY_THRESHOLD,
    HIGH_RARITY_ITEMS,
    HIGH_VALUE_ITEM_TYPES,
    LOW_POPULARITY_THRESHOLD,
    LOW_RARITY_ITEMS,
    LOW_VALUE_ITEM_TYPES,
    MAX_COMMISSION_PERCENT,
    MIN_COMMISSION_PERCENT,
)


def calculate_commission(
    rarity: str,
    item_type: str,
    popularity: float,
    game: str,
) -> float:
    """Рассчитывает комиссию для предмета на основе его характеристик.

    Комиссия зависит от:
    - Редкости предмета (rare items = higher commission)
    - Типа предмета (knives/gloves = higher commission)
    - Популярности (popular = lower commission)
    - Игры (Rust = higher commission)

    Args:
        rarity: Редкость предмета (например, "covert", "classified")
        item_type: Тип предмета (например, "Knife", "Rifle")
        popularity: Популярность предмета (0.0 - 1.0)
        game: Код игры (csgo, dota2, tf2, rust)

    Returns:
        Процент комиссии (2.0 - 15.0)

    Examples:
        >>> calculate_commission("covert", "knife", 0.9, "csgo")
        8.925  # High rarity + knife type, but popular

        >>> calculate_commission("consumer", "rifle", 0.2, "rust")
        10.395  # Low rarity, but unpopular and Rust

    """
    # Базовая комиссия DMarket
    base_commission = BASE_COMMISSION_PERCENT

    # Корректировка на основе редкости
    rarity_lower = rarity.lower()
    if rarity_lower in HIGH_RARITY_ITEMS:
        rarity_factor = 1.1  # Увеличиваем комиссию для редких предметов
    elif rarity_lower in LOW_RARITY_ITEMS:
        rarity_factor = 0.9  # Уменьшаем для обычных предметов
    else:
        rarity_factor = 1.0

    # Корректировка на основе типа предмета
    item_type_lower = item_type.lower()
    if item_type_lower in HIGH_VALUE_ITEM_TYPES:
        type_factor = 1.2  # Ножи и перчатки имеют повышенную комиссию
    elif item_type_lower in LOW_VALUE_ITEM_TYPES:
        type_factor = 0.9  # Стикеры и контейнеры часто имеют меньшую комиссию
    else:
        type_factor = 1.0

    # Корректировка на основе популярности
    if popularity > HIGH_POPULARITY_THRESHOLD:
        popularity_factor = 0.85  # Популярные предметы продаются быстрее
    elif popularity < LOW_POPULARITY_THRESHOLD:
        popularity_factor = 1.15  # Непопулярные предметы могут иметь высокую комиссию
    else:
        popularity_factor = 1.0

    # Корректировка на основе игры
    game_factor = GAME_COMMISSION_FACTORS.get(game, 1.0)

    # Рассчитываем итоговую комиссию
    commission = (
        base_commission * rarity_factor * type_factor * popularity_factor * game_factor
    )

    # Ограничиваем диапазон
    return max(MIN_COMMISSION_PERCENT, min(MAX_COMMISSION_PERCENT, commission))


def calculate_profit(
    buy_price: float,
    sell_price: float,
    commission_percent: float,
) -> tuple[float, float]:
    """Рассчитывает прибыль от арбитража.

    Args:
        buy_price: Цена покупки в USD
        sell_price: Цена продажи в USD
        commission_percent: Процент комиссии

    Returns:
        Кортеж (абсолютная прибыль в USD, процент прибыли)

    Examples:
        >>> calculate_profit(10.0, 12.0, 7.0)
        (1.16, 11.6)  # $1.16 profit, 11.6% return

    """
    gross_profit = sell_price - buy_price
    commission_amount = sell_price * commission_percent / 100
    net_profit = gross_profit - commission_amount
    profit_percent = (net_profit / buy_price) * 100 if buy_price > 0 else 0.0

    return net_profit, profit_percent


def calculate_net_profit(
    buy_price: float,
    sell_price: float,
    commission_percent: float = 7.0,
) -> float:
    """Рассчитывает чистую прибыль от арбитража.

    Args:
        buy_price: Цена покупки в USD
        sell_price: Цена продажи в USD
        commission_percent: Процент комиссии (по умолчанию 7%)

    Returns:
        Чистая прибыль в USD

    """
    gross_profit = sell_price - buy_price
    commission_amount = sell_price * commission_percent / 100
    return gross_profit - commission_amount


def calculate_profit_percent(
    buy_price: float,
    sell_price: float,
    commission_percent: float = 7.0,
) -> float:
    """Рассчитывает процент прибыли от арбитража.

    Args:
        buy_price: Цена покупки в USD
        sell_price: Цена продажи в USD
        commission_percent: Процент комиссии (по умолчанию 7%)

    Returns:
        Процент прибыли

    """
    if buy_price <= 0:
        return 0.0

    net_profit = calculate_net_profit(buy_price, sell_price, commission_percent)
    return (net_profit / buy_price) * 100


def get_fee_for_liquidity(liquidity_score: float) -> float:
    """Определяет комиссию на основе ликвидности предмета.

    Более ликвидные предметы имеют меньшую эффективную комиссию
    (быстрее продаются, меньше риск).

    Args:
        liquidity_score: Оценка ликвидности (0.0 - 1.0)

    Returns:
        Коэффициент комиссии (0.02 - 0.10)

    """
    from .constants import DEFAULT_FEE, HIGH_FEE, LOW_FEE

    if liquidity_score >= 0.8:
        return LOW_FEE  # Очень ликвидные - 2%
    if liquidity_score >= 0.5:
        return DEFAULT_FEE  # Средняя ликвидность - 7%
    return HIGH_FEE  # Низкая ликвидность - 10%


def cents_to_usd(cents: int) -> float:
    """Конвертирует центы в доллары.

    Args:
        cents: Сумма в центах

    Returns:
        Сумма в долларах

    Examples:
        >>> cents_to_usd(1050)
        10.5

    """
    return cents / 100


def usd_to_cents(usd: float) -> int:
    """Конвертирует доллары в центы.

    Args:
        usd: Сумма в долларах

    Returns:
        Сумма в центах

    Examples:
        >>> usd_to_cents(10.5)
        1050

    """
    return int(usd * 100)


def is_profitable_opportunity(
    buy_price: float,
    sell_price: float,
    min_profit_percent: float,
    commission_percent: float = 7.0,
) -> bool:
    """Проверяет, является ли возможность прибыльной.

    Args:
        buy_price: Цена покупки в USD
        sell_price: Цена продажи в USD
        min_profit_percent: Минимальный требуемый процент прибыли
        commission_percent: Процент комиссии

    Returns:
        True если возможность прибыльная

    """
    if buy_price <= 0 or sell_price <= buy_price:
        return False

    profit_percent = calculate_profit_percent(buy_price, sell_price, commission_percent)
    return profit_percent >= min_profit_percent


# =============================================================================
# Backward compatibility aliases
# =============================================================================

# Алиас для обратной совместимости (тесты используют _calculate_commission)
_calculate_commission = calculate_commission


# =============================================================================
# Публичный API модуля
# =============================================================================

__all__ = [
    "_calculate_commission",  # Backward compatibility alias
    "calculate_commission",
    "calculate_net_profit",
    "calculate_profit",
    "calculate_profit_percent",
    "cents_to_usd",
    "get_fee_for_liquidity",
    "is_profitable_opportunity",
    "usd_to_cents",
]
