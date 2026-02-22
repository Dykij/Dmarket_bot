"""Тесты для feature_flags.py"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.feature_flags import (
    Feature,
    FeatureFlagsManager,
    FeatureFlagStatus,
    get_feature_flags,
    init_feature_flags,
)


class TestFeatureFlagStatus:
    """Tests for FeatureFlagStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert FeatureFlagStatus.ENABLED.value == "enabled"
        assert FeatureFlagStatus.DISABLED.value == "disabled"
        assert FeatureFlagStatus.CONDITIONAL.value == "conditional"


class TestFeatureEnum:
    """Tests for Feature enum."""

    def test_trading_features(self):
        """Test trading feature values."""
        assert Feature.PORTFOLIO_MANAGEMENT.value == "portfolio_management"
        assert Feature.AUTO_SELL.value == "auto_sell"
        assert Feature.HFT_MODE.value == "hft_mode"
        assert Feature.BACKTESTING.value == "backtesting"

    def test_arbitrage_features(self):
        """Test arbitrage feature values."""
        assert Feature.CROSS_GAME_ARBITRAGE.value == "cross_game_arbitrage"
        assert Feature.INTRAMARKET_ARBITRAGE.value == "intramarket_arbitrage"

    def test_analytics_features(self):
        """Test analytics feature values."""
        assert Feature.MARKET_ANALYTICS.value == "market_analytics"
        assert Feature.PRICE_PREDICTION.value == "price_prediction"
        assert Feature.COMPETITION_ANALYSIS.value == "competition_analysis"

    def test_notification_features(self):
        """Test notification feature values."""
        assert Feature.SMART_NOTIFICATIONS.value == "smart_notifications"
        assert Feature.DISCORD_NOTIFICATIONS.value == "discord_notifications"
        assert Feature.DAlgoLY_REPORTS.value == "daily_reports"

    def test_experimental_features(self):
        """Test experimental feature values."""
        assert Feature.EXPERIMENTAL_UI.value == "experimental_ui"
        assert Feature.BETA_FEATURES.value == "beta_features"


class TestFeatureFlagsManager:
    """Тесты для FeatureFlagsManager."""

    @pytest.fixture()
    def manager(self, tmp_path):
        """Create test manager."""
        config_file = tmp_path / "test_flags.yaml"
        config_file.write_text(
            """
features:
  test_feature:
    enabled: true
    rollout_percent: 100
  rollout_feature:
    enabled: true
    rollout_percent: 50
  disabled_feature:
    enabled: false
  conditional_feature:
    enabled: true
    conditions:
      game: csgo
  whitelist_feature:
    enabled: false
    whitelist: [123, 456]
  blacklist_feature:
    enabled: true
    blacklist: [789]
"""
        )
        return FeatureFlagsManager(config_path=str(config_file))

    @pytest.mark.asyncio()
    async def test_is_enabled_global(self, manager):
        """Тест глобально включенной фичи."""
        enabled = await manager.is_enabled("test_feature")
        assert enabled is True

    @pytest.mark.asyncio()
    async def test_is_enabled_disabled(self, manager):
        """Тест выключенной фичи."""
        enabled = await manager.is_enabled("disabled_feature")
        assert enabled is False

    @pytest.mark.asyncio()
    async def test_rollout_deterministic(self, manager):
        """Тест детерминированного rollout."""
        user_id = 12345

        # Несколько вызовов должны возвращать одинаковый результат
        result1 = await manager.is_enabled("rollout_feature", user_id)
        result2 = await manager.is_enabled("rollout_feature", user_id)
        result3 = await manager.is_enabled("rollout_feature", user_id)

        assert result1 == result2 == result3

    @pytest.mark.asyncio()
    async def test_whitelist(self, manager):
        """Тест whitelist."""
        user_id = 99999

        # Сначала выключено
        enabled = await manager.is_enabled("disabled_feature", user_id)
        assert enabled is False

        # Добавить в whitelist
        await manager.add_to_whitelist("disabled_feature", user_id)

        # Теперь должно быть включено
        enabled = await manager.is_enabled("disabled_feature", user_id)
        assert enabled is True

    @pytest.mark.asyncio()
    async def test_set_flag(self, manager):
        """Тест установки флага."""
        await manager.set_flag("new_feature", enabled=True, rollout_percent=100)

        enabled = await manager.is_enabled("new_feature")
        assert enabled is True

    @pytest.mark.asyncio()
    async def test_get_user_flags(self, manager):
        """Тест получения всех флагов пользователя."""
        user_id = 12345
        flags = await manager.get_user_flags(user_id)

        assert isinstance(flags, dict)
        assert len(flags) > 0

    def test_feature_enum(self):
        """Тест Feature enum."""
        assert Feature.PORTFOLIO_MANAGEMENT.value == "portfolio_management"
        assert Feature.AUTO_SELL.value == "auto_sell"


class TestFeatureFlagsManagerExtended:
    """Extended tests for FeatureFlagsManager."""

    @pytest.fixture()
    def manager(self, tmp_path):
        """Create test manager with full config."""
        config_file = tmp_path / "test_flags.yaml"
        config_file.write_text(
            """
features:
  test_feature:
    enabled: true
    rollout_percent: 100
  conditional_feature:
    enabled: true
    conditions:
      game: csgo
      min_balance: 100
  list_condition_feature:
    enabled: true
    conditions:
      game: [csgo, dota2, rust]
  whitelist_only:
    enabled: false
    whitelist: [123, 456]
  blacklist_feature:
    enabled: true
    blacklist: [789, 101112]
"""
        )
        return FeatureFlagsManager(config_path=str(config_file))

    @pytest.mark.asyncio()
    async def test_is_enabled_with_feature_enum(self, manager):
        """Test is_enabled with Feature enum."""
        # Feature enum will use default config since it's not in yaml
        result = await manager.is_enabled(Feature.PORTFOLIO_MANAGEMENT)
        assert isinstance(result, bool)

    @pytest.mark.asyncio()
    async def test_is_enabled_whitelist_overrides_disabled(self, manager):
        """Test that whitelist overrides disabled flag."""
        enabled = await manager.is_enabled("whitelist_only", user_id=123)
        assert enabled is True

    @pytest.mark.asyncio()
    async def test_is_enabled_blacklist_blocks(self, manager):
        """Test that blacklist blocks enabled flag."""
        enabled = await manager.is_enabled("blacklist_feature", user_id=789)
        assert enabled is False

    @pytest.mark.asyncio()
    async def test_is_enabled_blacklist_does_not_block_others(self, manager):
        """Test that blacklist does not block non-blacklisted users."""
        enabled = await manager.is_enabled("blacklist_feature", user_id=999)
        assert enabled is True

    @pytest.mark.asyncio()
    async def test_is_enabled_conditions_match(self, manager):
        """Test is_enabled with matching conditions."""
        enabled = await manager.is_enabled(
            "conditional_feature", context={"game": "csgo", "min_balance": 100}
        )
        assert enabled is True

    @pytest.mark.asyncio()
    async def test_is_enabled_conditions_no_match(self, manager):
        """Test is_enabled with non-matching conditions."""
        enabled = await manager.is_enabled(
            "conditional_feature", context={"game": "dota2", "min_balance": 100}
        )
        assert enabled is False

    @pytest.mark.asyncio()
    async def test_is_enabled_conditions_list_match(self, manager):
        """Test is_enabled with list conditions matching."""
        enabled = await manager.is_enabled(
            "list_condition_feature", context={"game": "dota2"}
        )
        assert enabled is True

    @pytest.mark.asyncio()
    async def test_is_enabled_conditions_list_no_match(self, manager):
        """Test is_enabled with list conditions not matching."""
        enabled = await manager.is_enabled(
            "list_condition_feature", context={"game": "tf2"}
        )
        assert enabled is False

    @pytest.mark.asyncio()
    async def test_is_enabled_conditions_missing_key(self, manager):
        """Test is_enabled with missing context key."""
        enabled = await manager.is_enabled(
            "conditional_feature", context={"other_key": "value"}
        )
        assert enabled is False

    @pytest.mark.asyncio()
    async def test_is_enabled_rollout_without_user_id(self, manager):
        """Test rollout percentage without user_id (random)."""
        # This tests the random path
        manager.flags["random_rollout"] = {"enabled": True, "rollout_percent": 50}
        # Just verify it returns a bool and doesn't crash
        result = await manager.is_enabled("random_rollout")
        assert isinstance(result, bool)

    @pytest.mark.asyncio()
    async def test_is_enabled_unknown_feature_returns_false(self, manager):
        """Test that unknown feature returns False."""
        enabled = await manager.is_enabled("unknown_feature_xyz")
        assert enabled is False

    @pytest.mark.asyncio()
    async def test_set_flag_with_all_params(self, manager):
        """Test set_flag with all parameters."""
        await manager.set_flag(
            "new_feature",
            enabled=True,
            rollout_percent=75,
            whitelist=[100, 200],
            blacklist=[300],
        )

        flag_config = manager.flags.get("new_feature")
        assert flag_config["enabled"] is True
        assert flag_config["rollout_percent"] == 75
        assert flag_config["whitelist"] == [100, 200]
        assert flag_config["blacklist"] == [300]

    @pytest.mark.asyncio()
    async def test_set_flag_clamps_rollout_percent(self, manager):
        """Test that rollout percent is clamped to 0-100."""
        await manager.set_flag("clamp_test", rollout_percent=150)
        assert manager.flags["clamp_test"]["rollout_percent"] == 100

        await manager.set_flag("clamp_test_low", rollout_percent=-10)
        assert manager.flags["clamp_test_low"]["rollout_percent"] == 0

    @pytest.mark.asyncio()
    async def test_set_flag_with_feature_enum(self, manager):
        """Test set_flag with Feature enum."""
        await manager.set_flag(Feature.AUTO_SELL, enabled=True)
        assert manager.flags["auto_sell"]["enabled"] is True

    @pytest.mark.asyncio()
    async def test_add_to_whitelist_new_feature(self, manager):
        """Test adding user to whitelist for new feature."""
        await manager.add_to_whitelist("brand_new_feature", 12345)
        assert 12345 in manager.flags["brand_new_feature"]["whitelist"]

    @pytest.mark.asyncio()
    async def test_add_to_whitelist_existing_user(self, manager):
        """Test adding user already in whitelist."""
        await manager.add_to_whitelist("whitelist_only", 123)
        # Should not add duplicate
        assert manager.flags["whitelist_only"]["whitelist"].count(123) == 1

    @pytest.mark.asyncio()
    async def test_add_to_whitelist_with_feature_enum(self, manager):
        """Test add_to_whitelist with Feature enum."""
        await manager.add_to_whitelist(Feature.BETA_FEATURES, 999)
        assert 999 in manager.flags["beta_features"]["whitelist"]

    @pytest.mark.asyncio()
    async def test_remove_from_whitelist(self, manager):
        """Test removing user from whitelist."""
        await manager.remove_from_whitelist("whitelist_only", 123)
        assert 123 not in manager.flags["whitelist_only"]["whitelist"]

    @pytest.mark.asyncio()
    async def test_remove_from_whitelist_nonexistent_user(self, manager):
        """Test removing user not in whitelist."""
        # Should not raise error
        await manager.remove_from_whitelist("whitelist_only", 99999)

    @pytest.mark.asyncio()
    async def test_remove_from_whitelist_nonexistent_feature(self, manager):
        """Test removing user from nonexistent feature whitelist."""
        # Should not raise error
        await manager.remove_from_whitelist("nonexistent_feature", 123)

    @pytest.mark.asyncio()
    async def test_get_all_flags(self, manager):
        """Test get_all_flags returns copy of flags."""
        flags = await manager.get_all_flags()
        assert isinstance(flags, dict)
        # Should be a copy, not original
        flags["modified"] = True
        assert "modified" not in manager.flags

    @pytest.mark.asyncio()
    async def test_reload_config(self, manager, tmp_path):
        """Test reload_config reloads from file."""
        # Modify the original config file
        config_file = tmp_path / "test_flags.yaml"
        config_file.write_text(
            """
features:
  reloaded_feature:
    enabled: true
"""
        )
        manager.config_path = str(config_file)
        await manager.reload_config()
        assert "reloaded_feature" in manager.flags

    @pytest.mark.asyncio()
    async def test_save_config(self, manager, tmp_path):
        """Test save_config saves to file."""
        save_path = tmp_path / "saved_flags.yaml"
        manager.config_path = str(save_path)
        await manager.save_config()
        assert save_path.exists()


class TestFeatureFlagsManagerWithRedis:
    """Tests for FeatureFlagsManager with Redis."""

    @pytest.fixture()
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        redis.scan_iter = MagicMock(return_value=iter([]))
        return redis

    @pytest.fixture()
    def manager_with_redis(self, tmp_path, mock_redis):
        """Create manager with mocked Redis."""
        config_file = tmp_path / "test_flags.yaml"
        config_file.write_text(
            """
features:
  cached_feature:
    enabled: true
"""
        )
        return FeatureFlagsManager(
            config_path=str(config_file),
            redis_client=mock_redis,
        )

    @pytest.mark.asyncio()
    async def test_is_enabled_uses_redis_cache(self, manager_with_redis, mock_redis):
        """Test that is_enabled checks Redis cache."""
        mock_redis.get.return_value = b"1"  # Cached as enabled

        enabled = await manager_with_redis.is_enabled("cached_feature", user_id=123)

        assert enabled is True
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio()
    async def test_is_enabled_caches_result(self, manager_with_redis, mock_redis):
        """Test that is_enabled caches result in Redis."""
        mock_redis.get.return_value = None  # No cache

        await manager_with_redis.is_enabled("cached_feature", user_id=123)

        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio()
    async def test_is_enabled_cache_disabled(self, manager_with_redis, mock_redis):
        """Test cache returns disabled."""
        mock_redis.get.return_value = b"0"  # Cached as disabled

        enabled = await manager_with_redis.is_enabled("cached_feature", user_id=123)

        assert enabled is False

    @pytest.mark.asyncio()
    async def test_add_to_whitelist_updates_redis(self, manager_with_redis, mock_redis):
        """Test add_to_whitelist updates Redis cache."""
        await manager_with_redis.add_to_whitelist("cached_feature", 999)
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio()
    async def test_remove_from_whitelist_clears_redis(
        self, manager_with_redis, mock_redis
    ):
        """Test remove_from_whitelist clears Redis cache."""
        # First add to whitelist
        await manager_with_redis.add_to_whitelist("cached_feature", 888)
        await manager_with_redis.remove_from_whitelist("cached_feature", 888)
        mock_redis.delete.assert_called()


class TestFeatureFlagsManagerConfigLoading:
    """Tests for config loading edge cases."""

    def test_load_config_file_not_found(self, tmp_path):
        """Test handling of missing config file."""
        manager = FeatureFlagsManager(config_path=str(tmp_path / "nonexistent.yaml"))
        # Should use default config
        assert len(manager.flags) > 0

    def test_load_config_invalid_yaml(self, tmp_path):
        """Test handling of invalid YAML."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [[")

        manager = FeatureFlagsManager(config_path=str(config_file))
        # Should use default config
        assert len(manager.flags) > 0

    def test_default_config_has_all_features(self, tmp_path):
        """Test that default config includes all Feature enum values."""
        manager = FeatureFlagsManager(config_path=str(tmp_path / "nonexistent.yaml"))
        for feature in Feature:
            assert feature.value in manager.flags


class TestGlobalFeatureFlags:
    """Tests for global feature flags functions."""

    def test_get_feature_flags_not_initialized(self):
        """Test get_feature_flags raises error when not initialized."""
        import src.utils.feature_flags as ff

        ff._feature_flags = None

        with pytest.raises(RuntimeError, match="not initialized"):
            get_feature_flags()

    def test_init_feature_flags(self, tmp_path):
        """Test init_feature_flags creates global instance."""
        import src.utils.feature_flags as ff

        config_file = tmp_path / "global_flags.yaml"
        config_file.write_text("features: {}")

        manager = init_feature_flags(config_path=str(config_file))

        assert manager is not None
        assert ff._feature_flags is manager

    def test_get_feature_flags_after_init(self, tmp_path):
        """Test get_feature_flags after initialization."""

        config_file = tmp_path / "global_flags2.yaml"
        config_file.write_text("features: {}")

        init_feature_flags(config_path=str(config_file))
        manager = get_feature_flags()

        assert manager is not None
