"""Тесты для профессиональной конфигурации бота (BOT_ULTIMATE_V3).

Тесты покрывают:
- ProfessionalBotConfig
- SilentModeLogger
- LocalDeltaTracker
- AdaptiveRateLimiter
- AlgoProtectionSettings
- SmartScannerConfig
"""

import time
from unittest.mock import AsyncMock

import pytest

from src.dmarket.professional_bot_config import (
    AdaptiveRateLimiter,
    AlgoProtectionSettings,
    LocalDeltaTracker,
    ProfessionalBotConfig,
    SilentModeLogger,
    SmartScannerConfig,
    create_Algo_protection_settings,
    create_professional_config,
    create_smart_scanner_config,
)

# =============================================================================
# ProfessionalBotConfig Tests
# =============================================================================

class TestProfessionalBotConfig:
    """Тесты для ProfessionalBotConfig."""

    def test_default_config(self):
        """Тест значений по умолчанию."""
        config = ProfessionalBotConfig()

        assert config.min_profit_pct == 0.05
        assert config.max_item_lock_days == 0
        assert config.use_cursor_navigation is True
        assert config.silent_mode is True
        assert config.enable_adaptive_limiter is True
        assert config.enable_local_delta is True
        assert config.dry_run is True

    def test_custom_config(self):
        """Тест кастомной конфигурации."""
        config = ProfessionalBotConfig(
            min_profit_pct=0.10,
            max_item_lock_days=3,
            silent_mode=False,
        )

        assert config.min_profit_pct == 0.10
        assert config.max_item_lock_days == 3
        assert config.silent_mode is False

    def test_balance_safety_params(self):
        """Тест параметров безопасности баланса."""
        config = ProfessionalBotConfig()

        assert config.max_balance_percent_per_item == 0.25
        assert config.max_balance_in_locked_items == 0.25

    def test_rate_limit_params(self):
        """Тест параметров rate limiting."""
        config = ProfessionalBotConfig()

        assert config.base_request_delay == 0.5
        assert config.max_requests_per_minute == 60
        assert config.backoff_multiplier == 2.0
        assert config.max_backoff_seconds == 60.0


class TestCreateProfessionalConfig:
    """Тесты для create_professional_config."""

    def test_small_balance_config(self):
        """Тест конфигурации для маленького баланса."""
        config = create_professional_config(balance=30.0)

        # Консервативные настSwarmки
        assert config.min_profit_pct == 0.10  # 10%
        assert config.max_item_lock_days == 0
        assert config.max_balance_percent_per_item == 0.5

    def test_medium_balance_config(self):
        """Тест конфигурации для среднего баланса."""
        config = create_professional_config(balance=100.0)

        assert config.min_profit_pct == 0.07  # 7%
        assert config.max_item_lock_days == 0
        assert config.max_balance_percent_per_item == 0.3

    def test_large_balance_config(self):
        """Тест конфигурации для большого баланса."""
        config = create_professional_config(balance=500.0)

        assert config.min_profit_pct == 0.05  # 5%
        assert config.max_item_lock_days == 3
        assert config.max_balance_percent_per_item == 0.2

    def test_whale_balance_config(self):
        """Тест конфигурации для очень большого баланса."""
        config = create_professional_config(balance=2000.0)

        assert config.min_profit_pct == 0.03  # 3%
        assert config.max_item_lock_days == 7
        assert config.max_balance_percent_per_item == 0.1

    def test_conservative_profile(self):
        """Тест консервативного профиля риска."""
        config = create_professional_config(balance=100.0, risk_profile="conservative")

        # Более строгие настSwarmки
        assert config.max_item_lock_days == 0
        assert config.silent_mode is False

    def test_aggressive_profile(self):
        """Тест агрессивного профиля риска."""
        config = create_professional_config(balance=100.0, risk_profile="aggressive")

        # Более агрессивные настSwarmки
        assert config.max_item_lock_days > 0


# =============================================================================
# LocalDeltaTracker Tests
# =============================================================================

class TestLocalDeltaTracker:
    """Тесты для LocalDeltaTracker."""

    def test_first_item_is_changed(self):
        """Первый предмет всегда считается изменённым."""
        config = ProfessionalBotConfig()
        tracker = LocalDeltaTracker(config)

        item_data = {"price": {"USD": 1000}, "lockStatus": 0}
        result = tracker.is_changed("item_1", item_data)

        assert result is True

    def test_duplicate_item_is_not_changed(self):
        """Дубликат не считается изменённым."""
        config = ProfessionalBotConfig()
        tracker = LocalDeltaTracker(config)

        item_data = {"price": {"USD": 1000}, "lockStatus": 0}

        # Первый раз
        tracker.is_changed("item_1", item_data)

        # ВтоSwarm раз с теми же данными
        result = tracker.is_changed("item_1", item_data)

        assert result is False

    def test_changed_price_is_detected(self):
        """Изменение цены детектируется."""
        config = ProfessionalBotConfig()
        tracker = LocalDeltaTracker(config)

        item_data_1 = {"price": {"USD": 1000}, "lockStatus": 0}
        item_data_2 = {"price": {"USD": 1100}, "lockStatus": 0}

        tracker.is_changed("item_1", item_data_1)
        result = tracker.is_changed("item_1", item_data_2)

        assert result is True

    def test_stats_tracking(self):
        """Тест отслеживания статистики."""
        config = ProfessionalBotConfig()
        tracker = LocalDeltaTracker(config)

        item_data = {"price": {"USD": 1000}, "lockStatus": 0}

        # 3 проверки одного и того же предмета
        tracker.is_changed("item_1", item_data)  # Новый
        tracker.is_changed("item_1", item_data)  # Дубликат
        tracker.is_changed("item_1", item_data)  # Дубликат

        stats = tracker.get_stats()

        assert stats["total_items"] == 3
        assert stats["skipped_duplicates"] == 2
        assert stats["processed_changes"] == 1

    def test_skip_rate_calculation(self):
        """Тест расчёта процента пропусков."""
        config = ProfessionalBotConfig()
        tracker = LocalDeltaTracker(config)

        item_data = {"price": {"USD": 1000}, "lockStatus": 0}

        # 1 новый + 4 дубликата = 80% skip rate
        for _ in range(5):
            tracker.is_changed("item_1", item_data)

        stats = tracker.get_stats()

        assert stats["skip_rate_percent"] == 80.0

    def test_disabled_delta_always_returns_true(self):
        """При отключенном delta всегда возвращает True."""
        config = ProfessionalBotConfig(enable_local_delta=False)
        tracker = LocalDeltaTracker(config)

        item_data = {"price": {"USD": 1000}, "lockStatus": 0}

        # Все вызовы возвращают True
        assert tracker.is_changed("item_1", item_data) is True
        assert tracker.is_changed("item_1", item_data) is True
        assert tracker.is_changed("item_1", item_data) is True

    def test_cleanup_expired(self):
        """Тест очистки устаревших записей."""
        config = ProfessionalBotConfig(delta_cache_ttl_seconds=1)
        tracker = LocalDeltaTracker(config)

        item_data = {"price": {"USD": 1000}, "lockStatus": 0}
        tracker.is_changed("item_1", item_data)

        # Ждём истечения TTL
        time.sleep(1.1)

        removed = tracker.cleanup_expired()

        assert removed == 1
        assert tracker.get_stats()["cache_size"] == 0

    def test_reset_stats(self):
        """Тест сброса статистики."""
        config = ProfessionalBotConfig()
        tracker = LocalDeltaTracker(config)

        item_data = {"price": {"USD": 1000}, "lockStatus": 0}
        tracker.is_changed("item_1", item_data)

        tracker.reset_stats()
        stats = tracker.get_stats()

        assert stats["total_items"] == 0
        assert stats["skipped_duplicates"] == 0


# =============================================================================
# AdaptiveRateLimiter Tests
# =============================================================================

class TestAdaptiveRateLimiter:
    """Тесты для AdaptiveRateLimiter."""

    def test_initial_delay(self):
        """Тест начальной задержки."""
        config = ProfessionalBotConfig()
        limiter = AdaptiveRateLimiter(config)

        stats = limiter.get_stats()

        assert stats["current_delay"] == config.base_request_delay

    def test_record_success_decreases_delay(self):
        """Успешные запросы уменьшают задержку."""
        config = ProfessionalBotConfig()
        limiter = AdaptiveRateLimiter(config)

        # Сначала увеличиваем задержку
        limiter.record_429_error()
        initial_delay = limiter.get_stats()["current_delay"]

        # 10 успешных запросов должны уменьшить задержку
        for _ in range(10):
            limiter.record_success()

        final_delay = limiter.get_stats()["current_delay"]

        assert final_delay < initial_delay

    def test_record_429_increases_delay(self):
        """Ошибка 429 увеличивает задержку."""
        config = ProfessionalBotConfig()
        limiter = AdaptiveRateLimiter(config)

        initial_delay = limiter.get_stats()["current_delay"]

        limiter.record_429_error()

        new_delay = limiter.get_stats()["current_delay"]

        assert new_delay == initial_delay * config.backoff_multiplier

    def test_max_backoff_limit(self):
        """Задержка не превышает максимум."""
        config = ProfessionalBotConfig(max_backoff_seconds=10.0)
        limiter = AdaptiveRateLimiter(config)

        # Много ошибок 429
        for _ in range(20):
            limiter.record_429_error()

        delay = limiter.get_stats()["current_delay"]

        assert delay <= config.max_backoff_seconds

    def test_retry_after_header_used(self):
        """Используется значение Retry-After."""
        config = ProfessionalBotConfig()
        limiter = AdaptiveRateLimiter(config)

        wait_time = limiter.record_429_error(retry_after=30)

        assert wait_time == 30.0

    def test_stats_tracking(self):
        """Тест отслеживания статистики."""
        config = ProfessionalBotConfig()
        limiter = AdaptiveRateLimiter(config)

        limiter.record_success()
        limiter.record_success()
        limiter.record_429_error()

        stats = limiter.get_stats()

        assert stats["consecutive_successes"] == 0  # Сброшены после 429
        assert stats["consecutive_429s"] == 1
        assert stats["total_429_errors"] == 1

    @pytest.mark.asyncio()
    async def test_disabled_limiter(self):
        """При отключенном limiter wait не вызывается."""
        config = ProfessionalBotConfig(enable_adaptive_limiter=False)
        limiter = AdaptiveRateLimiter(config)

        # wait_before_request должен просто вернуться без блокировки
        await limiter.wait_before_request()


# =============================================================================
# AlgoProtectionSettings Tests
# =============================================================================

class TestAlgoProtectionSettings:
    """Тесты для AlgoProtectionSettings."""

    def test_default_settings(self):
        """Тест значений по умолчанию."""
        settings = AlgoProtectionSettings()

        assert settings.min_samples_leaf == 5
        assert settings.min_samples_split == 10
        assert settings.max_depth == 10
        assert settings.max_prediction_confidence == 0.95

    def test_get_random_forest_params(self):
        """Тест параметров RandomForest."""
        settings = AlgoProtectionSettings()
        params = settings.get_random_forest_params()

        assert params["min_samples_leaf"] == 5
        assert params["min_samples_split"] == 10
        assert params["max_depth"] == 10
        assert params["n_estimators"] == 100
        assert params["random_state"] == 42

    def test_get_gradient_boosting_params(self):
        """Тест параметров GradientBoosting."""
        settings = AlgoProtectionSettings()
        params = settings.get_gradient_boosting_params()

        assert params["min_samples_leaf"] == 5
        assert params["max_depth"] <= 5  # GB требует меньшую глубину
        assert params["learning_rate"] == 0.1

    def test_validate_prediction_low_confidence(self):
        """Тест валидации при низкой уверенности."""
        settings = AlgoProtectionSettings(min_prediction_confidence=0.5)

        is_valid, reason = settings.validate_prediction(
            predicted_price=100.0,
            current_price=100.0,
            confidence=0.3,
        )

        assert is_valid is False
        assert "too low" in reason.lower()

    def test_validate_prediction_large_change(self):
        """Тест валидации при большом изменении цены."""
        settings = AlgoProtectionSettings(max_price_change_percent=20.0)

        is_valid, reason = settings.validate_prediction(
            predicted_price=200.0,  # 100% изменение
            current_price=100.0,
            confidence=0.7,
        )

        assert is_valid is False
        assert "too large" in reason.lower()

    def test_validate_prediction_success(self):
        """Тест успешной валидации."""
        settings = AlgoProtectionSettings()

        is_valid, reason = settings.validate_prediction(
            predicted_price=110.0,  # 10% изменение
            current_price=100.0,
            confidence=0.7,
        )

        assert is_valid is True
        assert reason == "OK"


class TestCreateAlgoProtectionSettings:
    """Тесты для create_Algo_protection_settings."""

    def test_strict_settings(self):
        """Тест строгих настроек."""
        settings = create_Algo_protection_settings(strict=True)

        assert settings.min_samples_leaf == 5
        assert settings.max_depth == 8
        assert settings.max_prediction_confidence == 0.9

    def test_lenient_settings(self):
        """Тест менее строгих настроек."""
        settings = create_Algo_protection_settings(strict=False)

        assert settings.min_samples_leaf == 3
        assert settings.max_depth == 12
        assert settings.max_prediction_confidence == 0.98


# =============================================================================
# SmartScannerConfig Tests
# =============================================================================

class TestSmartScannerConfig:
    """Тесты для SmartScannerConfig."""

    def test_default_config(self):
        """Тест значений по умолчанию."""
        config = SmartScannerConfig()

        assert config.use_cursor is True
        assert config.items_per_request == 100
        assert config.enable_delta is True

    def test_to_dict(self):
        """Тест конвертации в словарь."""
        config = SmartScannerConfig()
        result = config.to_dict()

        assert "navigation" in result
        assert "lock_filter" in result
        assert "delta" in result
        assert "parallel" in result
        assert "filters" in result

        assert result["navigation"]["use_cursor"] is True
        assert result["lock_filter"]["max_lock_days"] == 0


class TestCreateSmartScannerConfig:
    """Тесты для create_smart_scanner_config."""

    def test_small_balance_config(self):
        """Тест конфигурации для маленького баланса."""
        config = create_smart_scanner_config(for_small_balance=True)

        assert config.max_lock_days == 0
        assert config.min_profit_percent == 7.0
        assert config.min_liquidity_score == 70
        assert config.max_concurrent_requests == 2

    def test_large_balance_config(self):
        """Тест конфигурации для большого баланса."""
        config = create_smart_scanner_config(for_small_balance=False)

        assert config.max_lock_days == 3
        assert config.min_profit_percent == 4.0
        assert config.min_liquidity_score == 40
        assert config.max_concurrent_requests == 5


# =============================================================================
# SilentModeLogger Tests
# =============================================================================

class TestSilentModeLogger:
    """Тесты для SilentModeLogger."""

    def test_log_scan_result_silent_mode(self):
        """В silent mode результаты скана не идут в TG."""
        config = ProfessionalBotConfig(silent_mode=True, log_to_file=False)
        logger_instance = SilentModeLogger(config, notifier=None)

        # Не должно вызывать исключений
        logger_instance.log_scan_result(
            items_scanned=100,
            opportunities_found=5,
            scan_time_ms=500,
        )

    @pytest.mark.asyncio
    async def test_log_purchase_sends_to_telegram(self):
        """Покупки всегда отправляются в TG."""
        config = ProfessionalBotConfig(silent_mode=True, log_to_file=False)
        notifier = AsyncMock()
        logger_instance = SilentModeLogger(config, notifier=notifier)

        await logger_instance.log_purchase(
            item_name="Test Item",
            buy_price=10.0,
            expected_profit=1.0,
            profit_percent=10.0,
        )

        notifier.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_critical_error_sends_to_telegram(self):
        """Критические ошибки отправляются в TG."""
        config = ProfessionalBotConfig(silent_mode=True, log_to_file=False)
        notifier = AsyncMock()
        logger_instance = SilentModeLogger(config, notifier=notifier)

        await logger_instance.log_error(
            error_type="API_ERROR",
            error_message="Connection failed",
            critical=True,
        )

        notifier.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_non_critical_error_not_sent(self):
        """Некритические ошибки не отправляются в TG."""
        config = ProfessionalBotConfig(silent_mode=True, log_to_file=False)
        notifier = AsyncMock()
        logger_instance = SilentModeLogger(config, notifier=notifier)

        await logger_instance.log_error(
            error_type="WARNING",
            error_message="Minor issue",
            critical=False,
        )

        notifier.send_message.assert_not_called()


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Интеграционные тесты."""

    def test_full_workflow_small_balance(self):
        """Полный workflow для маленького баланса."""
        # 1. Создаём конфигурацию
        config = create_professional_config(balance=45.50)

        # 2. Проверяем настSwarmки
        assert config.min_profit_pct == 0.10  # 10% для маленького баланса
        assert config.max_item_lock_days == 0
        assert config.silent_mode is True

        # 3. Создаём Algo protection
        Algo_settings = create_Algo_protection_settings(strict=True)
        assert Algo_settings.min_samples_leaf == 5

        # 4. Создаём scanner config
        scanner_config = create_smart_scanner_config(for_small_balance=True)
        assert scanner_config.max_lock_days == 0

        # 5. Создаём delta tracker
        delta = LocalDeltaTracker(config)

        # 6. Создаём rate limiter
        limiter = AdaptiveRateLimiter(config)

        # Всё должно работать вместе
        assert delta.get_stats()["total_items"] == 0
        assert limiter.get_stats()["total_requests"] == 0

    def test_config_consistency(self):
        """Тест консистентности настроек."""
        for balance in [10, 50, 100, 500, 2000]:
            config = create_professional_config(balance=float(balance))

            # Profit всегда положительный
            assert config.min_profit_pct > 0

            # Max item price не превышает баланс
            assert config.max_item_price <= balance * config.max_balance_percent_per_item * 2

            # Safety settings всегда включены
            assert config.dry_run is True
