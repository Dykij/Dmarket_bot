"""
Feature flags система для управления функциональностью бота.

Позволяет включать/выключать функции без деплоя, проводить A/B тесты,
и постепенно раскатывать новые возможности.
"""

import enum
import random
from typing import Any

import structlog
import yaml
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class FeatureFlagStatus(enum.StrEnum):
    """Статус feature flag."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    CONDITIONAL = "conditional"


class Feature(enum.StrEnum):
    """Перечисление доступных feature flags."""

    # Trading features
    PORTFOLIO_MANAGEMENT = "portfolio_management"
    AUTO_SELL = "auto_sell"
    HFT_MODE = "hft_mode"
    BACKTESTING = "backtesting"

    # Arbitrage features
    CROSS_GAME_ARBITRAGE = "cross_game_arbitrage"
    INTRAMARKET_ARBITRAGE = "intramarket_arbitrage"

    # Analytics features
    MARKET_ANALYTICS = "market_analytics"
    PRICE_PREDICTION = "price_prediction"
    COMPETITION_ANALYSIS = "competition_analysis"

    # Notification features
    SMART_NOTIFICATIONS = "smart_notifications"
    DISCORD_NOTIFICATIONS = "discord_notifications"
    DAILY_REPORTS = "daily_reports"

    # Experimental features
    EXPERIMENTAL_UI = "experimental_ui"
    BETA_FEATURES = "beta_features"


class FeatureFlagsManager:
    """
    Менеджер feature flags.

    Поддерживает:
    - Глобальное включение/выключение фич
    - Процентный rollout (включать для % пользователей)
    - Whitelist/blacklist пользователей
    - A/B тестирование
    - Временные ограничения
    """

    def __init__(
        self,
        config_path: str | None = None,
        redis_client: Redis | None = None,
    ):
        """
        Инициализация менеджера.

        Args:
            config_path: Путь к YAML конфигу с флагами
            redis_client: Redis клиент для кэширования
        """
        self.redis = redis_client
        self.config_path = config_path or "config/feature_flags.yaml"

        # Загрузить конфигурацию
        self.flags = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Загрузить конфигурацию из файла."""
        try:
            with open(self.config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logger.info("feature_flags_loaded", config_path=self.config_path)
                return config.get("features", {})
        except FileNotFoundError:
            logger.warning(
                "feature_flags_config_not_found",
                path=self.config_path,
            )
            return self._get_default_config()
        except Exception:
            logger.exception("feature_flags_load_error")
            return self._get_default_config()

    def _get_default_config(self) -> dict[str, Any]:
        """Получить конфигурацию по умолчанию."""
        return {
            feature.value: {
                "enabled": True,
                "rollout_percent": 100,
                "whitelist": [],
                "blacklist": [],
            }
            for feature in Feature
        }

    async def reload_config(self) -> None:
        """Перезагрузить конфигурацию из файла."""
        self.flags = self._load_config()
        logger.info("feature_flags_reloaded")

    async def is_enabled(
        self,
        feature: Feature | str,
        user_id: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """
        Проверить включен ли feature flag.

        Args:
            feature: Feature flag для проверки
            user_id: ID пользователя
            context: Дополнительный контекст для условий

        Returns:
            True если фича включена для пользователя
        """
        feature_name = feature.value if isinstance(feature, Feature) else feature

        # Проверить кэш в Redis
        if self.redis and user_id:
            cache_key = f"feature_flag:{feature_name}:{user_id}"
            cached = await self.redis.get(cache_key)
            if cached is not None:
                return cached == b"1"

        # Получить конфигурацию фичи
        flag_config = self.flags.get(feature_name, {})

        # Проверить глобальное включение
        if (
            not flag_config.get("enabled", False)
            and (not user_id or user_id not in flag_config.get("whitelist", []))
        ) or (user_id and user_id in flag_config.get("blacklist", [])):
            result = False
        # Проверить whitelist (переопределяет выключенное состояние)
        elif user_id and flag_config.get("whitelist") and user_id in flag_config["whitelist"]:
            result = True
        # Проверить процентный rollout
        elif "rollout_percent" in flag_config:
            rollout = flag_config["rollout_percent"]
            if user_id:
                # Детерминированный rollout по user_id
                hash_val = hash(f"{feature_name}:{user_id}") % 100
                result = hash_val < rollout
            else:
                # Случайный rollout без user_id
                # Non-cryptographic use - just for feature flag distribution
                result = random.randint(0, 99) < rollout  # noqa: S311
        # Проверить условия
        elif "conditions" in flag_config and context:
            result = self._check_conditions(flag_config["conditions"], context)
        else:
            result = flag_config.get("enabled", False)

        # Кэшировать результат
        if self.redis and user_id:
            cache_key = f"feature_flag:{feature_name}:{user_id}"
            await self.redis.setex(cache_key, 300, "1" if result else "0")  # 5 мин

        return result

    def _check_conditions(
        self,
        conditions: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        """
        Проверить условия включения фичи.

        Args:
            conditions: Словарь с условиями
            context: Контекст для проверки

        Returns:
            True если все условия выполнены
        """
        for key, expected_value in conditions.items():
            if key not in context:
                return False

            actual_value = context[key]

            if isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            elif actual_value != expected_value:
                return False

        return True

    async def set_flag(
        self,
        feature: Feature | str,
        enabled: bool = True,
        rollout_percent: int | None = None,
        whitelist: list[int] | None = None,
        blacklist: list[int] | None = None,
    ) -> None:
        """
        Установить feature flag.

        Args:
            feature: Feature flag
            enabled: Включен ли глобально
            rollout_percent: Процент пользователей (0-100)
            whitelist: Список ID пользователей в whitelist
            blacklist: Список ID пользователей в blacklist
        """
        feature_name = feature.value if isinstance(feature, Feature) else feature

        if feature_name not in self.flags:
            self.flags[feature_name] = {}

        self.flags[feature_name]["enabled"] = enabled

        if rollout_percent is not None:
            self.flags[feature_name]["rollout_percent"] = max(0, min(100, rollout_percent))

        if whitelist is not None:
            self.flags[feature_name]["whitelist"] = whitelist

        if blacklist is not None:
            self.flags[feature_name]["blacklist"] = blacklist

        # Сбросить кэш в Redis
        if self.redis:
            pattern = f"feature_flag:{feature_name}:*"
            async for key in self.redis.scan_iter(match=pattern):
                await self.redis.delete(key)

        logger.info(
            "feature_flag_updated",
            feature=feature_name,
            enabled=enabled,
            rollout=rollout_percent,
        )

    async def add_to_whitelist(self, feature: Feature | str, user_id: int) -> None:
        """
        Добавить пользователя в whitelist фичи.

        Args:
            feature: Feature flag
            user_id: ID пользователя
        """
        feature_name = feature.value if isinstance(feature, Feature) else feature

        if feature_name not in self.flags:
            self.flags[feature_name] = {"enabled": False, "whitelist": []}

        if "whitelist" not in self.flags[feature_name]:
            self.flags[feature_name]["whitelist"] = []

        if user_id not in self.flags[feature_name]["whitelist"]:
            self.flags[feature_name]["whitelist"].append(user_id)

            # Обновить кэш
            if self.redis:
                cache_key = f"feature_flag:{feature_name}:{user_id}"
                await self.redis.setex(cache_key, 300, "1")

            logger.info(
                "user_added_to_whitelist",
                feature=feature_name,
                user_id=user_id,
            )

    async def remove_from_whitelist(self, feature: Feature | str, user_id: int) -> None:
        """
        Удалить пользователя из whitelist фичи.

        Args:
            feature: Feature flag
            user_id: ID пользователя
        """
        feature_name = feature.value if isinstance(feature, Feature) else feature

        if feature_name in self.flags and "whitelist" in self.flags[feature_name]:
            whitelist = self.flags[feature_name]["whitelist"]
            if user_id in whitelist:
                whitelist.remove(user_id)

                # Сбросить кэш
                if self.redis:
                    cache_key = f"feature_flag:{feature_name}:{user_id}"
                    await self.redis.delete(cache_key)

                logger.info(
                    "user_removed_from_whitelist",
                    feature=feature_name,
                    user_id=user_id,
                )

    async def get_all_flags(self) -> dict[str, Any]:
        """
        Получить все feature flags.

        Returns:
            Словарь всех флагов
        """
        return self.flags.copy()

    async def get_user_flags(self, user_id: int) -> dict[str, bool]:
        """
        Получить все активные флаги для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь {feature: enabled}
        """
        user_flags = {}

        for feature in Feature:
            enabled = await self.is_enabled(feature, user_id)
            user_flags[feature.value] = enabled

        return user_flags

    async def save_config(self) -> None:
        """Сохранить конфигурацию в файл."""
        try:
            config = {"features": self.flags}

            with open(self.config_path, "w", encoding="utf-8") as f:  # noqa: ASYNC230
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

            logger.info("feature_flags_saved", config_path=self.config_path)

        except Exception:
            logger.exception("feature_flags_save_error")


# Глобальный экземпляр (инициализируется в main)
_feature_flags: FeatureFlagsManager | None = None


def get_feature_flags() -> FeatureFlagsManager:
    """Получить глобальный экземпляр менеджера."""
    if _feature_flags is None:
        raise RuntimeError("FeatureFlagsManager not initialized")
    return _feature_flags


def init_feature_flags(
    config_path: str | None = None,
    redis_client: Redis | None = None,
) -> FeatureFlagsManager:
    """
    Инициализировать глобальный экземпляр.

    Args:
        config_path: Путь к конфигу
        redis_client: Redis клиент

    Returns:
        Инициализированный менеджер
    """
    global _feature_flags
    _feature_flags = FeatureFlagsManager(config_path, redis_client)
    return _feature_flags
