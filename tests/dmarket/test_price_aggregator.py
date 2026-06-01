"""Тесты для PriceAggregator - batch запросы для получения цен."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.price_aggregator import (
    AggregatedPrice,
    LockStatus,
    PriceAggregator,
    PriceAggregatorConfig,
)


class TestLockStatus:
    """Тесты для LockStatus enum."""

    def test_avAlgolable_value(self):
        """Тест значения AVAlgoLABLE."""
        assert LockStatus.AVAlgoLABLE == 0
        assert LockStatus.AVAlgoLABLE.value == 0

    def test_locked_value(self):
        """Тест значения LOCKED."""
        assert LockStatus.LOCKED == 1
        assert LockStatus.LOCKED.value == 1


class TestAggregatedPrice:
    """Тесты для AggregatedPrice dataclass."""

    def test_min_price_usd(self):
        """Тест конвертации цены в USD."""
        price = AggregatedPrice(
            item_name="Test Item",
            market_hash_name="test_item",
            min_price=1000,  # $10 в центах
            max_price=1200,
            avg_price=1100,
            median_price=1050,
            listings_count=10,
        )
        assert price.min_price_usd == 10.0

    def test_effective_price_no_discount(self):
        """Тест effective price без скидок."""
        price = AggregatedPrice(
            item_name="Test Item",
            market_hash_name="test_item",
            min_price=1000,
            max_price=1200,
            avg_price=1100,
            median_price=1050,
            listings_count=10,
            has_discount=False,
            bonus_amount=0,
            lock_status=LockStatus.AVAlgoLABLE,
        )
        assert price.effective_price == 10.0  # $10

    def test_effective_price_with_discount(self):
        """Тест effective price со скидкой."""
        price = AggregatedPrice(
            item_name="Test Item",
            market_hash_name="test_item",
            min_price=1000,
            max_price=1200,
            avg_price=1100,
            median_price=1050,
            listings_count=10,
            has_discount=True,
            discount_percent=10.0,  # 10% скидка
            bonus_amount=0,
            lock_status=LockStatus.AVAlgoLABLE,
        )
        # $10 - 10% = $9
        assert abs(price.effective_price - 9.0) < 0.01

    def test_effective_price_with_bonus(self):
        """Тест effective price с бонусом."""
        price = AggregatedPrice(
            item_name="Test Item",
            market_hash_name="test_item",
            min_price=1000,
            max_price=1200,
            avg_price=1100,
            median_price=1050,
            listings_count=10,
            has_discount=False,
            bonus_amount=100,  # $1 бонус
            lock_status=LockStatus.AVAlgoLABLE,
        )
        # ($10 - $1) = $9
        assert abs(price.effective_price - 9.0) < 0.01

    def test_effective_price_with_lock(self):
        """Тест effective price с lock."""
        price = AggregatedPrice(
            item_name="Test Item",
            market_hash_name="test_item",
            min_price=1000,
            max_price=1200,
            avg_price=1100,
            median_price=1050,
            listings_count=10,
            has_discount=False,
            bonus_amount=0,
            lock_status=LockStatus.LOCKED,
            lock_days_remaining=5,
        )
        # Lock discount = 3% + 5 * 0.3% = 4.5%
        # Но максимум 5%
        # $10 - 4.5% = $9.55
        assert price.effective_price < 10.0
        assert price.effective_price > 9.0

    def test_is_good_deal_true(self):
        """Тест is_good_deal = True."""
        price = AggregatedPrice(
            item_name="Test Item",
            market_hash_name="test_item",
            min_price=900,  # Ниже средней на 10%
            max_price=1200,
            avg_price=1000,
            median_price=1000,
            listings_count=10,
            has_discount=True,
            discount_percent=5.0,
            bonus_amount=0,
            lock_status=LockStatus.AVAlgoLABLE,
        )
        assert price.is_good_deal is True

    def test_is_good_deal_false_locked(self):
        """Тест is_good_deal = False из-за lock."""
        price = AggregatedPrice(
            item_name="Test Item",
            market_hash_name="test_item",
            min_price=900,
            max_price=1200,
            avg_price=1000,
            median_price=1000,
            listings_count=10,
            has_discount=True,
            discount_percent=5.0,
            bonus_amount=0,
            lock_status=LockStatus.LOCKED,  # Заблокирован
        )
        assert price.is_good_deal is False


class TestPriceAggregatorConfig:
    """Тесты для PriceAggregatorConfig."""

    def test_default_values(self):
        """Тест значений по умолчанию."""
        config = PriceAggregatorConfig()
        assert config.update_interval == 30
        assert config.batch_size == 100
        assert config.prioritize_unlocked is True
        assert config.min_lock_discount == 3.0
        assert config.max_lock_discount == 5.0

    def test_custom_values(self):
        """Тест пользовательских значений."""
        config = PriceAggregatorConfig(
            update_interval=60,
            batch_size=50,
            prioritize_unlocked=False,
        )
        assert config.update_interval == 60
        assert config.batch_size == 50
        assert config.prioritize_unlocked is False


class TestPriceAggregator:
    """Тесты для PriceAggregator."""

    @pytest.fixture
    def aggregator(self):
        """Создать агрегатор без API (mock режим)."""
        return PriceAggregator()

    @pytest.mark.asyncio
    async def test_get_aggregated_prices_mock(self, aggregator):
        """Тест получения цен в mock режиме."""
        items = ["AK-47 | Redline", "AWP | Asiimov", "M4A4 | Howl"]

        prices = await aggregator.get_aggregated_prices(items)

        assert len(prices) == 3
        for price in prices:
            assert isinstance(price, AggregatedPrice)
            assert price.min_price > 0
            assert price.listings_count > 0

    @pytest.mark.asyncio
    async def test_cache_hit(self, aggregator):
        """Тест попадания в кэш."""
        items = ["Test Item"]

        # Первый запрос
        await aggregator.get_aggregated_prices(items)
        initial_requests = aggregator._requests_made

        # ВтоSwarm запрос (из кэша)
        await aggregator.get_aggregated_prices(items, force_refresh=False)

        # Запросы не должны увеличиться
        # (mock режим не увеличивает счетчик, но кэш работает)
        assert aggregator._cache_hits >= 1

    @pytest.mark.asyncio
    async def test_force_refresh(self, aggregator):
        """Тест принудительного обновления."""
        items = ["Test Item"]

        await aggregator.get_aggregated_prices(items)
        first_update = aggregator._last_update

        await asyncio.sleep(0.1)

        await aggregator.get_aggregated_prices(items, force_refresh=True)
        second_update = aggregator._last_update

        assert second_update > first_update

    def test_filter_avAlgolable_items(self, aggregator):
        """Тест фильтрации доступных предметов."""
        prices = [
            AggregatedPrice(
                item_name="AvAlgolable",
                market_hash_name="avAlgolable",
                min_price=1000,
                max_price=1000,
                avg_price=1000,
                median_price=1000,
                listings_count=10,
                lock_status=LockStatus.AVAlgoLABLE,
            ),
            AggregatedPrice(
                item_name="Locked",
                market_hash_name="locked",
                min_price=1000,
                max_price=1000,
                avg_price=1000,
                median_price=1000,
                listings_count=10,
                lock_status=LockStatus.LOCKED,
            ),
        ]

        filtered = aggregator.filter_avAlgolable_items(prices)

        assert len(filtered) == 1
        assert filtered[0].item_name == "AvAlgolable"

    def test_filter_discounted_items(self, aggregator):
        """Тест фильтрации предметов со скидкой."""
        prices = [
            AggregatedPrice(
                item_name="Discounted",
                market_hash_name="discounted",
                min_price=1000,
                max_price=1000,
                avg_price=1000,
                median_price=1000,
                listings_count=10,
                has_discount=True,
                discount_percent=5.0,
            ),
            AggregatedPrice(
                item_name="No Discount",
                market_hash_name="no_discount",
                min_price=1000,
                max_price=1000,
                avg_price=1000,
                median_price=1000,
                listings_count=10,
                has_discount=False,
            ),
        ]

        filtered = aggregator.filter_discounted_items(prices, min_discount=3.0)

        assert len(filtered) == 1
        assert filtered[0].item_name == "Discounted"

    def test_get_good_deals(self, aggregator):
        """Тест получения выгодных сделок."""
        prices = [
            AggregatedPrice(
                item_name="Good Deal",
                market_hash_name="good_deal",
                min_price=900,  # Ниже avg
                max_price=1200,
                avg_price=1000,
                median_price=1000,
                listings_count=10,
                has_discount=True,
                discount_percent=5.0,
                lock_status=LockStatus.AVAlgoLABLE,
            ),
            AggregatedPrice(
                item_name="Bad Deal",
                market_hash_name="bad_deal",
                min_price=1100,  # Выше avg
                max_price=1200,
                avg_price=1000,
                median_price=1000,
                listings_count=10,
                has_discount=False,
                lock_status=LockStatus.AVAlgoLABLE,
            ),
        ]

        deals = aggregator.get_good_deals(prices)

        assert len(deals) == 1
        assert deals[0].item_name == "Good Deal"

    def test_get_stats(self, aggregator):
        """Тест получения статистики."""
        stats = aggregator.get_stats()

        assert "requests_made" in stats
        assert "cache_hits" in stats
        assert "cache_size" in stats
        assert "last_update" in stats
        assert "hit_rate" in stats


class TestPriceAggregatorWithAPI:
    """Тесты PriceAggregator с mock API."""

    @pytest.fixture
    def mock_api(self):
        """Создать mock API клиент."""
        api = MagicMock()
        # Удаляем get_aggregated_prices чтобы использовать fallback к _request
        del api.get_aggregated_prices
        # Создаём async mock для _request
        api._request = AsyncMock(return_value={
            "objects": [
                {
                    "title": "AK-47 | Redline",
                    "price": {
                        "min": 1000,
                        "max": 1200,
                        "avg": 1100,
                        "median": 1050,
                        "bonus": 50,
                    },
                    "count": 25,
                    "discount": 5,
                    "lockStatus": 0,
                    "lockDaysRemaining": 0,
                    "extra": {"nameHash": "ak47_redline"},
                }
            ]
        })
        return api

    @pytest.mark.asyncio
    async def test_fetch_prices_with_api(self, mock_api):
        """Тест получения цен через API."""
        aggregator = PriceAggregator(api_client=mock_api)

        prices = await aggregator.get_aggregated_prices(
            item_names=["AK-47 | Redline"],
            game="csgo",
            force_refresh=True,
        )

        assert len(prices) == 1
        assert prices[0].item_name == "AK-47 | Redline"
        assert prices[0].min_price == 1000
        assert prices[0].bonus_amount == 50
        assert prices[0].has_discount is True
        assert prices[0].discount_percent == 5
