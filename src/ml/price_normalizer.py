"""
Price Normalizer Module.

Нормализация цен с различных платформ (DMarket, Waxpeer, Steam) в единый формат USD.

Version: 1.0.0
Date: January 2026

Price Formats:
- DMarket: cents (1 USD = 100 cents)
- Waxpeer: mils (1 USD = 1000 mils)
- Steam: USD (прямой формат)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PriceSource(Enum):
    """Источники цен."""

    DMARKET = "dmarket"
    WAXPEER = "waxpeer"
    STEAM = "steam"


@dataclass
class NormalizedPrice:
    """Нормализованная цена с метаданными."""

    price_usd: float
    source: PriceSource
    original_value: float | int | str
    timestamp: datetime
    item_name: str | None = None
    game: str | None = None
    is_valid: bool = True
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Валидация после инициализации."""
        if self.price_usd < 0:
            self.is_valid = False
            self.error_message = "Negative price"


class PriceNormalizer:
    """
    Нормализатор цен с различных платформ.

    Конвертирует цены из разных форматов в единый USD формат.

    Attributes:
        DMARKET_DIVISOR: Делитель для конвертации DMarket (центы → USD)
        WAXPEER_DIVISOR: Делитель для конвертации Waxpeer (mils → USD)
        MIN_VALID_PRICE: Минимальная валидная цена
        MAX_VALID_PRICE: Максимальная валидная цена (защита от аномалий)

    Example:
        >>> normalizer = PriceNormalizer()
        >>> # DMarket: 1250 cents = $12.50
        >>> result = normalizer.normalize(1250, PriceSource.DMARKET)
        >>> print(result.price_usd)  # 12.50
        >>>
        >>> # Waxpeer: 12500 mils = $12.50
        >>> result = normalizer.normalize(12500, PriceSource.WAXPEER)
        >>> print(result.price_usd)  # 12.50
        >>>
        >>> # Steam: $12.50 (прямой формат)
        >>> result = normalizer.normalize(12.50, PriceSource.STEAM)
        >>> print(result.price_usd)  # 12.50
    """

    # Константы конвертации
    DMARKET_DIVISOR: int = 100  # 1 USD = 100 cents
    WAXPEER_DIVISOR: int = 1000  # 1 USD = 1000 mils

    # Лимиты валидации
    MIN_VALID_PRICE: float = 0.01  # $0.01
    MAX_VALID_PRICE: float = 1_000_000.0  # $1,000,000 (защита от аномалий)

    # Комиссии платформ
    DMARKET_COMMISSION: float = 0.07  # 7%
    WAXPEER_COMMISSION: float = 0.06  # 6%
    STEAM_COMMISSION: float = 0.15  # 15% (Valve 5% + Publisher 10%)

    def __init__(
        self,
        min_price: float | None = None,
        max_price: float | None = None,
        strict_validation: bool = True,
    ) -> None:
        """
        Инициализация нормализатора.

        Args:
            min_price: Минимальная валидная цена (опционально)
            max_price: Максимальная валидная цена (опционально)
            strict_validation: Строгая валидация цен
        """
        self.min_price = min_price or self.MIN_VALID_PRICE
        self.max_price = max_price or self.MAX_VALID_PRICE
        self.strict_validation = strict_validation
        self._conversion_count = 0
        self._error_count = 0

        logger.info(
            "price_normalizer_initialized",
            min_price=self.min_price,
            max_price=self.max_price,
            strict_validation=strict_validation,
        )

    def normalize(
        self,
        price: float | str,
        source: PriceSource | str,
        item_name: str | None = None,
        game: str | None = None,
    ) -> NormalizedPrice:
        """
        Нормализовать цену в USD.

        Args:
            price: Исходная цена в формате платформы
            source: Источник цены (DMarket, Waxpeer, Steam)
            item_name: Название предмета (опционально)
            game: Код игры (опционально)

        Returns:
            NormalizedPrice с ценой в USD

        Example:
            >>> normalizer = PriceNormalizer()
            >>> result = normalizer.normalize(1250, "dmarket", "AK-47 | Redline")
            >>> print(f"${result.price_usd:.2f}")  # $12.50
        """
        self._conversion_count += 1
        timestamp = datetime.now()

        # Нормализация источника
        if isinstance(source, str):
            try:
                source = PriceSource(source.lower())
            except ValueError:
                self._error_count += 1
                return NormalizedPrice(
                    price_usd=0.0,
                    source=PriceSource.DMARKET,  # fallback
                    original_value=price,
                    timestamp=timestamp,
                    item_name=item_name,
                    game=game,
                    is_valid=False,
                    error_message=f"Unknown source: {source}",
                )

        # Парсинг цены
        try:
            numeric_price = self._parse_price(price)
        except (ValueError, TypeError, InvalidOperation) as e:
            self._error_count += 1
            logger.warning(
                "price_parse_error",
                price=price,
                source=source.value,
                error=str(e),
            )
            return NormalizedPrice(
                price_usd=0.0,
                source=source,
                original_value=price,
                timestamp=timestamp,
                item_name=item_name,
                game=game,
                is_valid=False,
                error_message=f"Parse error: {e}",
            )

        # Конвертация в USD
        price_usd = self._convert_to_usd(numeric_price, source)

        # Валидация
        is_valid, error_msg = self._validate_price(price_usd)

        if not is_valid:
            self._error_count += 1
            logger.warning(
                "price_validation_failed",
                price_usd=price_usd,
                source=source.value,
                item_name=item_name,
                error=error_msg,
            )

        return NormalizedPrice(
            price_usd=price_usd,
            source=source,
            original_value=price,
            timestamp=timestamp,
            item_name=item_name,
            game=game,
            is_valid=is_valid,
            error_message=error_msg,
        )

    def normalize_batch(
        self,
        prices: list[dict[str, Any]],
        source: PriceSource | str,
        price_field: str = "price",
        name_field: str = "title",
    ) -> list[NormalizedPrice]:
        """
        Нормализовать список цен.

        Args:
            prices: Список словарей с ценами
            source: Источник цен
            price_field: Название поля с ценой
            name_field: Название поля с названием предмета

        Returns:
            Список NormalizedPrice

        Example:
            >>> items = [
            ...     {"title": "AK-47", "price": 1250},
            ...     {"title": "AWP", "price": 5000},
            ... ]
            >>> results = normalizer.normalize_batch(items, "dmarket")
        """
        results = []
        for item in prices:
            price = item.get(price_field)
            name = item.get(name_field)
            game = item.get("game")

            if price is not None:
                normalized = self.normalize(price, source, item_name=name, game=game)
                results.append(normalized)

        logger.info(
            "batch_normalized",
            total=len(prices),
            successful=len([r for r in results if r.is_valid]),
            source=source if isinstance(source, str) else source.value,
        )

        return results

    def _parse_price(self, price: float | str) -> float:
        """
        Парсинг цены из различных форматов.

        Args:
            price: Цена в любом поддерживаемом формате

        Returns:
            Числовое значение цены

        RAlgoses:
            ValueError: Если формат не поддерживается
        """
        if isinstance(price, int | float):
            return float(price)

        if isinstance(price, str):
            # Удаляем символы валюты и пробелы
            cleaned = price.strip().replace("$", "").replace(",", "").replace(" ", "")

            # Пробуем Decimal для точности
            return float(Decimal(cleaned))

        raise ValueError(f"Unsupported price type: {type(price)}")

    def _convert_to_usd(self, price: float, source: PriceSource) -> float:
        """
        Конвертация цены в USD.

        Args:
            price: Числовая цена в формате источника
            source: Источник цены

        Returns:
            Цена в USD
        """
        match source:
            case PriceSource.DMARKET:
                return price / self.DMARKET_DIVISOR
            case PriceSource.WAXPEER:
                return price / self.WAXPEER_DIVISOR
            case PriceSource.STEAM:
                return price  # Уже в USD
            case _:
                logger.warning("unknown_source_fallback", source=source)
                return price

    def _validate_price(self, price_usd: float) -> tuple[bool, str | None]:
        """
        Валидация цены.

        Args:
            price_usd: Цена в USD

        Returns:
            Кортеж (is_valid, error_message)
        """
        if price_usd < 0:
            return False, "Negative price"

        if self.strict_validation:
            if price_usd < self.min_price:
                return False, f"Price below minimum ({self.min_price})"

            if price_usd > self.max_price:
                return False, f"Price above maximum ({self.max_price})"

        return True, None

    def calculate_net_price(
        self,
        price_usd: float,
        source: PriceSource,
        after_commission: bool = True,
    ) -> float:
        """
        Рассчитать чистую цену с учетом комиссии.

        Args:
            price_usd: Цена в USD
            source: Платформа продажи
            after_commission: Вычесть комиссию (True) или добавить (False)

        Returns:
            Чистая цена после/до комиссии
        """
        commission_rate = {
            PriceSource.DMARKET: self.DMARKET_COMMISSION,
            PriceSource.WAXPEER: self.WAXPEER_COMMISSION,
            PriceSource.STEAM: self.STEAM_COMMISSION,
        }.get(source, 0.0)

        if after_commission:
            return price_usd * (1 - commission_rate)
        return price_usd / (1 - commission_rate)

    def calculate_arbitrage_profit(
        self,
        buy_price: float,
        buy_source: PriceSource,
        sell_price: float,
        sell_source: PriceSource,
    ) -> dict[str, float]:
        """
        Рассчитать прибыль от арбитража.

        Args:
            buy_price: Цена покупки в формате источника
            buy_source: Платформа покупки
            sell_price: Цена продажи в формате источника
            sell_source: Платформа продажи

        Returns:
            Словарь с расчетами прибыли

        Example:
            >>> profit = normalizer.calculate_arbitrage_profit(
            ...     buy_price=1000,
            ...     buy_source=PriceSource.DMARKET,
            ...     sell_price=12000,
            ...     sell_source=PriceSource.WAXPEER,
            ... )
            >>> print(f"Profit: ${profit['net_profit']:.2f}")
        """
        # Нормализация цен
        buy_usd = self.normalize(buy_price, buy_source).price_usd
        sell_usd = self.normalize(sell_price, sell_source).price_usd

        # Чистая цена после комиссии продажи
        net_sell = self.calculate_net_price(
            sell_usd, sell_source, after_commission=True
        )

        # Расчет прибыли
        gross_profit = sell_usd - buy_usd
        net_profit = net_sell - buy_usd
        profit_percent = (net_profit / buy_usd * 100) if buy_usd > 0 else 0.0

        return {
            "buy_price_usd": buy_usd,
            "sell_price_usd": sell_usd,
            "net_sell_price": net_sell,
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "profit_percent": profit_percent,
            "is_profitable": net_profit > 0,
        }

    def to_platform_price(
        self,
        price_usd: float,
        target_source: PriceSource,
    ) -> int | float:
        """
        Конвертировать USD в формат платформы.

        Args:
            price_usd: Цена в USD
            target_source: Целевая платформа

        Returns:
            Цена в формате платформы
        """
        match target_source:
            case PriceSource.DMARKET:
                return int(price_usd * self.DMARKET_DIVISOR)
            case PriceSource.WAXPEER:
                return int(price_usd * self.WAXPEER_DIVISOR)
            case PriceSource.STEAM:
                return price_usd
            case _:
                return price_usd

    def get_statistics(self) -> dict[str, Any]:
        """
        Получить статистику работы нормализатора.

        Returns:
            Словарь со статистикой
        """
        error_rate = (
            (self._error_count / self._conversion_count * 100)
            if self._conversion_count > 0
            else 0.0
        )

        return {
            "total_conversions": self._conversion_count,
            "error_count": self._error_count,
            "error_rate_percent": round(error_rate, 2),
            "min_price_limit": self.min_price,
            "max_price_limit": self.max_price,
        }

    def reset_statistics(self) -> None:
        """Сбросить статистику."""
        self._conversion_count = 0
        self._error_count = 0
        logger.info("statistics_reset")


# Глобальный экземпляр для удобства
_default_normalizer: PriceNormalizer | None = None


def get_normalizer() -> PriceNormalizer:
    """Получить глобальный экземпляр нормализатора."""
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = PriceNormalizer()
    return _default_normalizer


def normalize_price(
    price: float | str,
    source: PriceSource | str,
    item_name: str | None = None,
) -> NormalizedPrice:
    """
    Быстрая нормализация цены (использует глобальный нормализатор).

    Args:
        price: Исходная цена
        source: Источник цены
        item_name: Название предмета

    Returns:
        NormalizedPrice

    Example:
        >>> result = normalize_price(1250, "dmarket", "AK-47")
        >>> print(result.price_usd)  # 12.50
    """
    return get_normalizer().normalize(price, source, item_name)
