"""
Тесты для user_rate_limiter.py
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.user_rate_limiter import RateLimitConfig, UserRateLimiter


class TestUserRateLimiter:
    """Тесты для UserRateLimiter."""

    @pytest.fixture()
    def limiter(self):
        """Create test limiter without Redis."""
        return UserRateLimiter(redis_client=None)

    @pytest.mark.asyncio()
    async def test_check_limit_first_request(self, limiter):
        """Тест первого запроса - должен быть разрешен."""
        user_id = 12345
        allowed, info = await limiter.check_limit(user_id, "default")

        assert allowed is True
        assert info["remaining"] < info["limit"]
        assert info["action"] == "default"

    @pytest.mark.asyncio()
    async def test_check_limit_within_limits(self, limiter):
        """Тест запросов в пределах лимита."""
        user_id = 12345

        # Отправить несколько запросов
        for _ in range(5):
            allowed, _info = await limiter.check_limit(user_id, "scan")
            assert allowed is True

    @pytest.mark.asyncio()
    async def test_check_limit_exceeded(self, limiter):
        """Тест превышения лимита."""
        user_id = 12345

        # Установить низкий лимит
        limiter.update_limit("test", RateLimitConfig(requests=3, window=60))

        # Отправить запросы до превышения
        for _ in range(3):
            allowed, _ = await limiter.check_limit(user_id, "test")
            assert allowed is True

        # Следующий запрос должен быть отклонен
        allowed, info = await limiter.check_limit(user_id, "test")
        assert allowed is False
        assert info["remaining"] == 0
        # retry_after может быть 0 если окно еще не истекло, но это нормально

    @pytest.mark.asyncio()
    async def test_sliding_window(self, limiter):
        """Тест sliding window algorithm."""
        user_id = 12345

        # Установить короткое окно
        limiter.update_limit("test", RateLimitConfig(requests=2, window=1))

        # Первые 2 запроса разрешены
        await limiter.check_limit(user_id, "test")
        await limiter.check_limit(user_id, "test")

        # Третий отклонен
        allowed, _ = await limiter.check_limit(user_id, "test")
        assert allowed is False

        # Ждем истечения окна
        await asyncio.sleep(1.1)

        # Теперь должно быть разрешено
        allowed, _ = await limiter.check_limit(user_id, "test")
        assert allowed is True

    @pytest.mark.asyncio()
    async def test_burst_mode(self, limiter):
        """Тест burst режима."""
        user_id = 12345

        limiter.update_limit(
            "test",
            RateLimitConfig(requests=5, window=60, burst=10),
        )

        # Burst позволяет до 10 запросов
        for _ in range(10):
            allowed, _ = await limiter.check_limit(user_id, "test")
            assert allowed is True

        # 11-й должен быть отклонен
        allowed, _ = await limiter.check_limit(user_id, "test")
        assert allowed is False

    @pytest.mark.asyncio()
    async def test_weighted_rate_limiting(self, limiter):
        """Тест взвешенного rate limiting."""
        user_id = 12345

        limiter.update_limit("test", RateLimitConfig(requests=10, window=60))

        # Запрос с cost=5 занимает 5 слотов
        allowed, info = await limiter.check_limit(user_id, "test", cost=5)
        assert allowed is True
        assert info["remaining"] == 5

        # Еще один с cost=5
        allowed, info = await limiter.check_limit(user_id, "test", cost=5)
        assert allowed is True
        assert info["remaining"] == 0

        # Следующий должен быть отклонен
        allowed, _ = await limiter.check_limit(user_id, "test", cost=1)
        assert allowed is False

    @pytest.mark.asyncio()
    async def test_different_actions_independent(self, limiter):
        """Тест независимости лимитов для разных действий."""
        user_id = 12345

        limiter.update_limit("action1", RateLimitConfig(requests=2, window=60))
        limiter.update_limit("action2", RateLimitConfig(requests=2, window=60))

        # Заполнить лимит action1
        await limiter.check_limit(user_id, "action1")
        await limiter.check_limit(user_id, "action1")
        allowed, _ = await limiter.check_limit(user_id, "action1")
        assert allowed is False

        # action2 должен работать независимо
        allowed, _ = await limiter.check_limit(user_id, "action2")
        assert allowed is True

    @pytest.mark.asyncio()
    async def test_different_users_independent(self, limiter):
        """Тест независимости лимитов для разных пользователей."""
        user1 = 12345
        user2 = 67890

        limiter.update_limit("test", RateLimitConfig(requests=2, window=60))

        # Заполнить лимит user1
        await limiter.check_limit(user1, "test")
        await limiter.check_limit(user1, "test")
        allowed, _ = await limiter.check_limit(user1, "test")
        assert allowed is False

        # user2 должен работать независимо
        allowed, _ = await limiter.check_limit(user2, "test")
        assert allowed is True

    @pytest.mark.asyncio()
    async def test_get_user_stats(self, limiter):
        """Тест получения статистики пользователя."""
        user_id = 12345

        # Сделать несколько запросов
        await limiter.check_limit(user_id, "scan")
        await limiter.check_limit(user_id, "target_create")

        stats = await limiter.get_user_stats(user_id)

        assert "scan" in stats
        assert "target_create" in stats
        assert "default" in stats

        # Проверить структуру stat
        assert "limit" in stats["scan"]
        assert "remaining" in stats["scan"]
        assert "reset" in stats["scan"]

    @pytest.mark.asyncio()
    async def test_reset_user_limits_specific_action(self, limiter):
        """Тест сброса лимита для конкретного действия."""
        user_id = 12345

        limiter.update_limit("test", RateLimitConfig(requests=2, window=60))

        # Заполнить лимит
        await limiter.check_limit(user_id, "test")
        await limiter.check_limit(user_id, "test")
        allowed, _ = await limiter.check_limit(user_id, "test")
        assert allowed is False

        # Сбросить лимит
        await limiter.reset_user_limits(user_id, "test")

        # Теперь должно работать
        allowed, _ = await limiter.check_limit(user_id, "test")
        assert allowed is True

    @pytest.mark.asyncio()
    async def test_reset_user_limits_all_actions(self, limiter):
        """Тест сброса всех лимитов пользователя."""
        user_id = 12345

        limiter.update_limit("action1", RateLimitConfig(requests=1, window=60))
        limiter.update_limit("action2", RateLimitConfig(requests=1, window=60))

        # Заполнить лимиты
        await limiter.check_limit(user_id, "action1")
        await limiter.check_limit(user_id, "action2")

        # Сбросить все
        await limiter.reset_user_limits(user_id)

        # Оба должны работать
        allowed, _ = await limiter.check_limit(user_id, "action1")
        assert allowed is True
        allowed, _ = await limiter.check_limit(user_id, "action2")
        assert allowed is True

    @pytest.mark.asyncio()
    async def test_whitelist(self, limiter):
        """Тест whitelist функциональности (без Redis)."""
        user_id = 12345

        # Без Redis whitelist не работает (возвращает False)
        is_whitelisted = await limiter.is_whitelisted(user_id)
        assert is_whitelisted is False

        # Добавить в whitelist (без Redis это no-op)
        await limiter.add_whitelist(user_id)

        # Без Redis всегда False
        is_whitelisted = await limiter.is_whitelisted(user_id)
        assert is_whitelisted is False

    @pytest.mark.asyncio()
    async def test_update_limit(self, limiter):
        """Тест обновления лимита."""
        new_config = RateLimitConfig(requests=100, window=120, burst=150)

        limiter.update_limit("custom", new_config)

        assert "custom" in limiter.limits
        assert limiter.limits["custom"].requests == 100
        assert limiter.limits["custom"].window == 120
        assert limiter.limits["custom"].burst == 150

    @pytest.mark.asyncio()
    async def test_concurrent_requests(self, limiter):
        """Тест конкурентных запросов."""
        user_id = 12345

        limiter.update_limit("test", RateLimitConfig(requests=10, window=60))

        # Отправить 10 конкурентных запросов
        tasks = [limiter.check_limit(user_id, "test") for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # Все должны быть разрешены
        assert all(result[0] for result in results)

        # 11-й должен быть отклонен
        allowed, _ = await limiter.check_limit(user_id, "test")
        assert allowed is False

    @pytest.mark.parametrize(
        ("action", "expected_limit"),
        (
            ("scan", 10),
            ("target_create", 5),
            ("balance", 20),
            ("default", 30),
        ),
    )
    def test_default_limits(self, limiter, action, expected_limit):
        """Тест лимитов по умолчанию."""
        config = limiter._get_limit(action)
        assert config.requests == expected_limit

    @pytest.mark.asyncio()
    async def test_redis_mode(self):
        """Тест с Redis (мок)."""
        mock_redis = MagicMock()

        # Создать правильный mock pipeline который возвращает себя
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore.return_value = mock_pipeline
        mock_pipeline.zcard.return_value = mock_pipeline
        mock_pipeline.zadd.return_value = mock_pipeline
        mock_pipeline.expire.return_value = mock_pipeline
        mock_pipeline.execute = AsyncMock(return_value=[None, 0, None, None])

        # pipeline() должен возвращать mock_pipeline (не coroutine)
        mock_redis.pipeline.return_value = mock_pipeline

        limiter = UserRateLimiter(redis_client=mock_redis)

        user_id = 12345
        allowed, info = await limiter.check_limit(user_id, "default")

        # Проверить что использовался Redis
        mock_redis.pipeline.assert_called()
        assert allowed is True
        assert info["action"] == "default"
