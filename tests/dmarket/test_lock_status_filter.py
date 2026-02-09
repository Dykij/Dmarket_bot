"""Тесты для LockStatusFilter - фильтрация по статусу блокировки."""

from datetime import datetime, timedelta

import pytest

from src.dmarket.lock_status_filter import (
    ItemWithLock,
    LockFilterConfig,
    LockInfo,
    LockStatus,
    LockStatusFilter,
)


class TestLockStatus:
    """Тесты для LockStatus enum."""

    def test_available_value(self):
        """Тест значения AVAILABLE."""
        assert LockStatus.AVAILABLE == 0

    def test_locked_value(self):
        """Тест значения LOCKED."""
        assert LockStatus.LOCKED == 1


class TestLockInfo:
    """Тесты для LockInfo dataclass."""

    def test_is_available(self):
        """Тест is_available property."""
        info = LockInfo(status=LockStatus.AVAILABLE)
        assert info.is_available is True
        assert info.is_locked is False

    def test_is_locked(self):
        """Тест is_locked property."""
        info = LockInfo(status=LockStatus.LOCKED, days_remaining=5)
        assert info.is_available is False
        assert info.is_locked is True

    def test_with_unlock_date(self):
        """Тест с датой разблокировки."""
        unlock_date = datetime.now() + timedelta(days=3)
        info = LockInfo(
            status=LockStatus.LOCKED,
            days_remaining=3,
            unlock_date=unlock_date,
        )
        assert info.unlock_date is not None
        assert info.days_remaining == 3


class TestLockFilterConfig:
    """Тесты для LockFilterConfig."""

    def test_default_values(self):
        """Тест значений по умолчанию."""
        config = LockFilterConfig()

        assert config.filter_locked is True
        assert config.prioritize_unlocked is True
        assert config.min_lock_discount == 3.0
        assert config.max_lock_discount == 5.0
        assert config.discount_per_day == 0.3
        assert config.max_lock_days == 7

    def test_custom_values(self):
        """Тест пользовательских значений."""
        config = LockFilterConfig(
            filter_locked=False,
            min_lock_discount=2.0,
            max_lock_discount=10.0,
        )

        assert config.filter_locked is False
        assert config.min_lock_discount == 2.0
        assert config.max_lock_discount == 10.0


class TestItemWithLock:
    """Тесты для ItemWithLock dataclass."""

    def test_basic_item(self):
        """Тест базового предмета."""
        item = ItemWithLock(
            item_id="test_123",
            title="AK-47 | Redline",
            price=10.0,
        )

        assert item.item_id == "test_123"
        assert item.title == "AK-47 | Redline"
        assert item.price == 10.0
        assert item.lock_info.is_available is True

    def test_item_with_lock(self):
        """Тест предмета с блокировкой."""
        item = ItemWithLock(
            item_id="test_123",
            title="AWP | Asiimov",
            price=50.0,
            lock_info=LockInfo(
                status=LockStatus.LOCKED,
                days_remaining=5,
                calculated_discount=4.5,
            ),
        )

        assert item.lock_info.is_locked is True
        assert item.lock_info.days_remaining == 5


class TestLockStatusFilter:
    """Тесты для LockStatusFilter."""

    @pytest.fixture
    def filter(self):
        """Создать фильтр."""
        return LockStatusFilter()

    def test_calculate_lock_discount_zero_days(self, filter):
        """Тест дисконта для 0 дней."""
        discount = filter.calculate_lock_discount(0)
        assert discount == 0.0

    def test_calculate_lock_discount_one_day(self, filter):
        """Тест дисконта для 1 дня."""
        discount = filter.calculate_lock_discount(1)
        # 3% + 1 * 0.3% = 3.3%
        assert abs(discount - 3.3) < 0.01

    def test_calculate_lock_discount_five_days(self, filter):
        """Тест дисконта для 5 дней."""
        discount = filter.calculate_lock_discount(5)
        # 3% + 5 * 0.3% = 4.5%
        assert abs(discount - 4.5) < 0.01

    def test_calculate_lock_discount_max(self, filter):
        """Тест максимального дисконта."""
        discount = filter.calculate_lock_discount(10)
        # 3% + 10 * 0.3% = 6%, но max = 5%
        assert discount == 5.0

    def test_apply_lock_discount_available(self, filter):
        """Тест применения дисконта к доступному предмету."""
        lock_info = LockInfo(status=LockStatus.AVAILABLE)

        discounted = filter.apply_lock_discount(100.0, lock_info)

        assert discounted == 100.0

    def test_apply_lock_discount_locked(self, filter):
        """Тест применения дисконта к заблокированному предмету."""
        lock_info = LockInfo(
            status=LockStatus.LOCKED,
            days_remaining=5,
            calculated_discount=4.5,
        )

        discounted = filter.apply_lock_discount(100.0, lock_info)

        # $100 * (1 - 4.5%) = $95.50
        assert abs(discounted - 95.5) < 0.01

    def test_adjust_profit_for_lock(self, filter):
        """Тест корректировки профита с учетом lock."""
        lock_info = LockInfo(
            status=LockStatus.LOCKED,
            calculated_discount=4.5,
        )

        adjusted = filter.adjust_profit_for_lock(10.0, lock_info)

        # 10% - 4.5% = 5.5%
        assert abs(adjusted - 5.5) < 0.01

    def test_adjust_profit_available(self, filter):
        """Тест корректировки профита для доступного предмета."""
        lock_info = LockInfo(status=LockStatus.AVAILABLE)

        adjusted = filter.adjust_profit_for_lock(10.0, lock_info)

        assert adjusted == 10.0

    def test_parse_lock_info_available(self, filter):
        """Тест парсинга доступного предмета."""
        item_data = {
            "lockStatus": 0,
            "lockDaysRemaining": 0,
        }

        lock_info = filter.parse_lock_info(item_data)

        assert lock_info.status == LockStatus.AVAILABLE
        assert lock_info.is_available is True

    def test_parse_lock_info_locked(self, filter):
        """Тест парсинга заблокированного предмета."""
        item_data = {
            "lockStatus": 1,
            "lockDaysRemaining": 5,
        }

        lock_info = filter.parse_lock_info(item_data)

        assert lock_info.status == LockStatus.LOCKED
        assert lock_info.days_remaining == 5
        assert lock_info.calculated_discount > 0

    def test_filter_items(self, filter):
        """Тест фильтрации предметов."""
        items = [
            {
                "itemId": "item_1",
                "title": "Available Item",
                "price": {"USD": 1000},
                "lockStatus": 0,
            },
            {
                "itemId": "item_2",
                "title": "Locked Item",
                "price": {"USD": 2000},
                "lockStatus": 1,
                "lockDaysRemaining": 5,
            },
        ]

        filtered = filter.filter_items(items, allow_locked=False)

        assert len(filtered) == 1
        assert filtered[0].title == "Available Item"

    def test_filter_items_allow_locked(self, filter):
        """Тест фильтрации с разрешением locked."""
        items = [
            {
                "itemId": "item_1",
                "title": "Available Item",
                "price": {"USD": 1000},
                "lockStatus": 0,
            },
            {
                "itemId": "item_2",
                "title": "Locked Item",
                "price": {"USD": 2000},
                "lockStatus": 1,
                "lockDaysRemaining": 5,
            },
        ]

        filtered = filter.filter_items(items, allow_locked=True)

        assert len(filtered) == 2

    def test_filter_items_max_lock_days(self):
        """Тест фильтрации по max_lock_days."""
        config = LockFilterConfig(max_lock_days=3)
        filter = LockStatusFilter(config=config)

        items = [
            {
                "itemId": "item_1",
                "title": "Short Lock",
                "price": {"USD": 1000},
                "lockStatus": 1,
                "lockDaysRemaining": 2,
            },
            {
                "itemId": "item_2",
                "title": "Long Lock",
                "price": {"USD": 2000},
                "lockStatus": 1,
                "lockDaysRemaining": 5,  # > max_lock_days
            },
        ]

        filtered = filter.filter_items(items, allow_locked=True)

        assert len(filtered) == 1
        assert filtered[0].title == "Short Lock"

    def test_filter_items_with_discount(self, filter):
        """Тест фильтрации предметов со скидкой."""
        items = [
            {
                "itemId": "item_1",
                "title": "Discounted Item",
                "price": {"USD": 1000, "bonus": 50},
                "discount": 5,
                "lockStatus": 0,
            },
        ]

        filtered = filter.filter_items(items)

        assert len(filtered) == 1
        assert filtered[0].discount_percent == 5
        assert filtered[0].bonus_amount == 0.5  # $0.50

    def test_priority_score_unlocked_higher(self, filter):
        """Тест что unlocked имеет выше приоритет."""
        items = [
            {
                "itemId": "item_1",
                "title": "Locked",
                "price": {"USD": 1000},
                "lockStatus": 1,
                "lockDaysRemaining": 5,
            },
            {
                "itemId": "item_2",
                "title": "Unlocked",
                "price": {"USD": 1000},
                "lockStatus": 0,
            },
        ]

        filtered = filter.filter_items(items, allow_locked=True)

        # Unlocked должен быть первым
        assert filtered[0].title == "Unlocked"
        assert filtered[0].priority_score > filtered[1].priority_score

    def test_should_buy_unlocked(self, filter):
        """Тест should_buy для доступного предмета."""
        item = ItemWithLock(
            item_id="test",
            title="Test",
            price=10.0,
            lock_info=LockInfo(status=LockStatus.AVAILABLE),
        )

        should_buy, reason = filter.should_buy(item, target_profit=10.0, current_balance=100.0)

        assert should_buy is True

    def test_should_buy_locked_low_profit(self, filter):
        """Тест should_buy для locked с низким профитом."""
        item = ItemWithLock(
            item_id="test",
            title="Test",
            price=10.0,
            lock_info=LockInfo(
                status=LockStatus.LOCKED,
                days_remaining=5,
                calculated_discount=4.5,
            ),
        )

        # Профит 3% - после lock adjustment = -1.5%
        should_buy, reason = filter.should_buy(item, target_profit=3.0, current_balance=100.0)

        assert should_buy is False
        assert "profit too low" in reason.lower()

    def test_should_buy_freeze_capital(self, filter):
        """Тест should_buy с заморозкой большой части баланса."""
        item = ItemWithLock(
            item_id="test",
            title="Test",
            price=30.0,  # 30% баланса
            lock_info=LockInfo(
                status=LockStatus.LOCKED,
                days_remaining=5,  # > 3 days
                calculated_discount=4.5,
            ),
        )

        should_buy, reason = filter.should_buy(item, target_profit=15.0, current_balance=100.0)

        assert should_buy is False
        assert "freeze" in reason.lower()

    def test_should_buy_double_confirmation(self, filter):
        """Тест should_buy с двойным подтверждением."""
        item = ItemWithLock(
            item_id="test",
            title="Test",
            price=10.0,
            lock_info=LockInfo(status=LockStatus.AVAILABLE),
            discount_percent=5.0,  # DMarket discount
        )

        should_buy, reason = filter.should_buy(item, target_profit=10.0, current_balance=100.0)

        assert should_buy is True
        assert "double confirmation" in reason.lower()

    def test_get_stats(self, filter):
        """Тест получения статистики."""
        items = [
            ItemWithLock(
                item_id="1",
                title="Available",
                price=10.0,
                lock_info=LockInfo(status=LockStatus.AVAILABLE),
            ),
            ItemWithLock(
                item_id="2",
                title="Locked",
                price=20.0,
                lock_info=LockInfo(
                    status=LockStatus.LOCKED,
                    days_remaining=5,
                ),
                discount_percent=5.0,
            ),
        ]

        stats = filter.get_stats(items)

        assert stats["total_items"] == 2
        assert stats["available_now"] == 1
        assert stats["locked"] == 1
        assert stats["locked_percent"] == 50.0
        assert stats["avg_lock_days"] == 5.0
        assert stats["with_discount"] == 1
