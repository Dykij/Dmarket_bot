"""Price Aggregator - Batch запросы для получения цен.

Использует эндпоинт /market-items/v1/price-aggregated для получения
минимальных цен на все предметы одним пакетом.

Преимущества:
- Один запрос для всего whitelist каждые 30 секунд
- Не тратит лимиты на тяжелый поиск с фильтрами
- Быстрое обновление рыночной базы для ML/AI

Основано на документации DMarket API.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# Commission rates by platform
COMMISSION_RATES = {
    "dmarket": 0.07,  # 7%
    "waxpeer": 0.06,  # 6%
    "steam": 0.13,  # 13%
}


class LockStatus(int, Enum):
    """Статус блокировки предмета для вывода.

    lockStatus: 0 = доступен сразу
    lockStatus: 1 = заблокирован на 7 дней (трейд-бан)
    """

    AVAILABLE = 0
    LOCKED = 1


@dataclass
class AggregatedPrice:
    """Агрегированная цена предмета."""

    item_name: str
    market_hash_name: str

    # Цены (в центах)
    min_price: int  # Минимальная цена на рынке
    max_price: int  # Максимальная цена
    avg_price: float  # Средняя цена
    median_price: float  # Медианная цена

    # Количество лотов
    listings_count: int

    # Бонусы и скидки
    has_discount: bool = False
    discount_percent: float = 0.0
    bonus_amount: int = 0  # price.bonus из API

    # Lock status
    lock_status: LockStatus = LockStatus.AVAILABLE
    lock_days_remaining: int = 0

    # Время обновления
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def min_price_usd(self) -> float:
        """Минимальная цена в USD."""
        return self.min_price / 100

    @property
    def effective_price(self) -> float:
        """Эффективная цена с учетом скидки и бонуса.

        Если предмет в холде, добавляем дисконт за ожидание.
        """
        base_price = self.min_price - self.bonus_amount

        if self.has_discount:
            base_price *= 1 - self.discount_percent / 100

        # Дисконт за lock (3-5% в зависимости от срока)
        if self.lock_status == LockStatus.LOCKED:
            lock_discount = min(0.05, 0.03 + (self.lock_days_remaining * 0.003))
            base_price *= 1 - lock_discount

        return base_price / 100  # Возвращаем в USD

    @property
    def is_good_deal(self) -> bool:
        """Проверяет, является ли предмет выгодной сделкой.

        Условия:
        1. Цена ниже средней на >5%
        2. Есть бонус от DMarket
        3. Предмет не в холде
        """
        below_avg = self.min_price < self.avg_price * 0.95
        has_bonus = self.bonus_amount > 0 or self.has_discount
        not_locked = self.lock_status == LockStatus.AVAILABLE

        return below_avg and has_bonus and not_locked


@dataclass
class PriceAggregatorConfig:
    """Конфигурация Price Aggregator."""

    # Интервал обновления (секунды)
    update_interval: int = 30

    # Максимальное количество предметов в batch-запросе
    batch_size: int = 100

    # Приоритизировать предметы без lock
    prioritize_unlocked: bool = True

    # Минимальный дисконт за lock (%)
    min_lock_discount: float = 3.0

    # Максимальный дисконт за lock (%)
    max_lock_discount: float = 5.0


class PriceAggregator:
    """Агрегатор цен для batch-запросов.

    Использует /market-items/v1/price-aggregated для эффективного
    получения цен на весь whitelist.

    Example:
        >>> aggregator = PriceAggregator(api_client)
        >>> prices = await aggregator.get_whitelist_prices(whitelist_items)
        >>> for item in prices:
        ...     if item.is_good_deal:
        ...         print(f"{item.item_name}: ${item.effective_price:.2f}")
    """

    def __init__(
        self,
        api_client: Any = None,
        config: PriceAggregatorConfig | None = None,
    ):
        """Инициализация Price Aggregator.

        Args:
            api_client: DMarket API клиент
            config: Конфигурация
        """
        self.api = api_client
        self.config = config or PriceAggregatorConfig()

        # Кэш цен
        self._price_cache: dict[str, AggregatedPrice] = {}
        self._last_update: datetime | None = None

        # Статистика
        self._requests_made = 0
        self._cache_hits = 0

        logger.info(
            "PriceAggregator initialized",
            extra={
                "update_interval": self.config.update_interval,
                "batch_size": self.config.batch_size,
            },
        )

    async def get_aggregated_prices(
        self,
        item_names: list[str],
        game: str = "csgo",
        force_refresh: bool = False,
    ) -> list[AggregatedPrice]:
        """Получить агрегированные цены для списка предметов.

        Args:
            item_names: Список названий предметов
            game: Идентификатор игры
            force_refresh: Принудительно обновить кэш

        Returns:
            Список агрегированных цен
        """
        # Проверяем нужно ли обновление
        needs_update = (
            force_refresh
            or self._last_update is None
            or (datetime.now() - self._last_update).seconds
            > self.config.update_interval
        )

        if needs_update:
            await self._fetch_prices(item_names, game)
        else:
            self._cache_hits += 1

        # Возвращаем из кэша
        result = []
        for name in item_names:
            if name in self._price_cache:
                result.append(self._price_cache[name])

        return result

    async def _fetch_prices(
        self,
        item_names: list[str],
        game: str,
    ) -> None:
        """Загрузить цены через batch-запрос.

        Использует /market-items/v1/price-aggregated endpoint.
        """
        if not self.api:
            # Mock режим для тестов
            await self._mock_fetch_prices(item_names)
            return

        try:
            # Разбиваем на batch'и
            batches = [
                item_names[i : i + self.config.batch_size]
                for i in range(0, len(item_names), self.config.batch_size)
            ]

            for batch in batches:
                # Запрос к API
                response = await self._call_price_api(batch, game)

                # Парсим ответ
                for item_data in response.get("objects", []):
                    price = self._parse_price_data(item_data)
                    self._price_cache[price.item_name] = price

                self._requests_made += 1

            self._last_update = datetime.now()

            logger.debug(
                "Prices updated",
                extra={
                    "items_count": len(item_names),
                    "batches": len(batches),
                },
            )

        except Exception as e:
            logger.exception(f"Failed to fetch aggregated prices: {e}")
            raise

    async def _call_price_api(
        self,
        item_names: list[str],
        game: str,
    ) -> dict[str, Any]:
        """Вызов API для получения цен.

        Endpoint: /price-aggregator/v1/aggregated-prices
        """
        if hasattr(self.api, "get_aggregated_prices"):
            return await self.api.get_aggregated_prices(
                titles=item_names,
                game_id=game,
            )

        # Fallback для обычного API
        params = {
            "gameId": game,
            "titles": ",".join(item_names),
            "currency": "USD",
        }

        return await self.api._request(
            method="GET",
            path="/price-aggregator/v1/aggregated-prices",
            params=params,
        )

    def _parse_price_data(self, data: dict[str, Any]) -> AggregatedPrice:
        """Парсинг данных цены из API ответа."""
        # Извлекаем бонус/скидку
        price_data = data.get("price", {})
        discount = data.get("discount", 0)
        bonus = price_data.get("bonus", 0)

        # Lock status
        lock_status = LockStatus(data.get("lockStatus", 0))
        lock_days = data.get("lockDaysRemaining", 0)

        return AggregatedPrice(
            item_name=data.get("title", ""),
            market_hash_name=data.get("extra", {}).get("nameHash", ""),
            min_price=price_data.get("min", 0),
            max_price=price_data.get("max", 0),
            avg_price=price_data.get("avg", 0),
            median_price=price_data.get("median", 0),
            listings_count=data.get("count", 0),
            has_discount=discount > 0,
            discount_percent=discount,
            bonus_amount=bonus,
            lock_status=lock_status,
            lock_days_remaining=lock_days,
            updated_at=datetime.now(),
        )

    async def _mock_fetch_prices(self, item_names: list[str]) -> None:
        """Mock загрузка для тестов."""
        import random

        for name in item_names:
            base_price = random.randint(100, 10000)  # $1-$100

            self._price_cache[name] = AggregatedPrice(
                item_name=name,
                market_hash_name=name.replace(" ", "_"),
                min_price=base_price,
                max_price=int(base_price * 1.2),
                avg_price=base_price * 1.1,
                median_price=base_price * 1.05,
                listings_count=random.randint(10, 500),
                has_discount=random.random() > 0.8,
                discount_percent=random.uniform(1, 10) if random.random() > 0.8 else 0,
                bonus_amount=random.randint(0, 50) if random.random() > 0.7 else 0,
                lock_status=(
                    LockStatus.AVAILABLE if random.random() > 0.2 else LockStatus.LOCKED
                ),
                lock_days_remaining=(
                    random.randint(1, 7) if random.random() > 0.8 else 0
                ),
            )

        self._last_update = datetime.now()

    def filter_available_items(
        self,
        prices: list[AggregatedPrice],
    ) -> list[AggregatedPrice]:
        """Фильтрует только доступные предметы (без lock).

        Args:
            prices: Список агрегированных цен

        Returns:
            Только предметы с lockStatus: 0
        """
        return [p for p in prices if p.lock_status == LockStatus.AVAILABLE]

    def filter_discounted_items(
        self,
        prices: list[AggregatedPrice],
        min_discount: float = 3.0,
    ) -> list[AggregatedPrice]:
        """Фильтрует предметы со скидкой.

        Args:
            prices: Список агрегированных цен
            min_discount: Минимальная скидка (%)

        Returns:
            Предметы со скидкой >= min_discount
        """
        return [
            p for p in prices if p.has_discount and p.discount_percent >= min_discount
        ]

    def get_good_deals(
        self,
        prices: list[AggregatedPrice],
    ) -> list[AggregatedPrice]:
        """Получить выгодные сделки.

        Критерии:
        1. Цена ниже средней
        2. Есть бонус/скидка от DMarket
        3. Доступен сразу (не в холде)
        """
        return [p for p in prices if p.is_good_deal]

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику работы."""
        return {
            "requests_made": self._requests_made,
            "cache_hits": self._cache_hits,
            "cache_size": len(self._price_cache),
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "hit_rate": self._cache_hits
            / max(1, self._requests_made + self._cache_hits),
        }
