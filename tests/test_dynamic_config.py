"""Тесты для Dynamic Config.

Тестирование функциональности:
- Загрузка и hot reload конфигурации
- Callbacks при изменениях
- Валидация конфигурации
- Rollback к предыдущим версиям
"""

from datetime import UTC, datetime

import pytest
import yaml

from src.utils.dynamic_config import (
    ConfigChange,
    ConfigSnapshot,
    ConfigValidationError,
    DynamicConfig,
)


class TestConfigChange:
    """Тесты для ConfigChange."""

    def test_create_change(self):
        """Тест создания записи изменения."""
        change = ConfigChange(
            key="trading.max_price",
            old_value=100,
            new_value=150,
        )

        assert change.key == "trading.max_price"
        assert change.old_value == 100
        assert change.new_value == 150
        assert change.source == "file"


class TestConfigSnapshot:
    """Тесты для ConfigSnapshot."""

    def test_create_snapshot(self):
        """Тест создания снимка."""
        snapshot = ConfigSnapshot(
            data={"trading": {"max_price": 100}},
            timestamp=datetime.now(UTC),
            file_hash="abc123",
        )

        assert snapshot.data["trading"]["max_price"] == 100
        assert snapshot.file_hash == "abc123"


class TestDynamicConfig:
    """Тесты для DynamicConfig."""

    @pytest.fixture
    def config_file(self, tmp_path):
        """Фикстура для создания временного файла конфигурации."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "trading": {
                "max_price": 100,
                "min_profit": 5,
            },
            "bot": {
                "name": "test_bot",
                "enabled": True,
            },
        }
        config_path.write_text(yaml.dump(config_data))
        return config_path

    @pytest.fixture
    def config(self, config_file):
        """Фикстура для создания DynamicConfig."""
        return DynamicConfig(config_file, watch_interval=1)

    def test_load_config(self, config):
        """Тест загрузки конфигурации."""
        assert config.get("trading.max_price") == 100
        assert config.get("trading.min_profit") == 5
        assert config.get("bot.name") == "test_bot"

    def test_get_default(self, config):
        """Тест получения значения по умолчанию."""
        assert config.get("nonexistent", default=42) == 42
        assert config.get("trading.nonexistent", default="default") == "default"

    def test_get_section(self, config):
        """Тест получения секции."""
        trading = config.get_section("trading")

        assert trading["max_price"] == 100
        assert trading["min_profit"] == 5

    def test_get_section_nonexistent(self, config):
        """Тест получения несуществующей секции."""
        section = config.get_section("nonexistent")
        assert section == {}

    @pytest.mark.asyncio
    async def test_set_value(self, config):
        """Тест установки значения."""
        awAlgot config.set("trading.max_price", 200, persist=False)

        assert config.get("trading.max_price") == 200

    @pytest.mark.asyncio
    async def test_set_new_key(self, config):
        """Тест установки нового ключа."""
        awAlgot config.set("trading.new_param", "value", persist=False)

        assert config.get("trading.new_param") == "value"

    def test_on_change_callback(self, config):
        """Тест callback при изменении."""
        changes = []

        def callback(old, new):
            changes.append((old, new))

        config.on_change("trading.max_price", callback)

        # Симулируем изменение
        change = ConfigChange(
            key="trading.max_price",
            old_value=100,
            new_value=200,
        )
        config._trigger_callbacks(change)

        assert len(changes) == 1
        assert changes[0] == (100, 200)

    def test_on_change_wildcard(self, config):
        """Тест callback с wildcard паттерном."""
        changes = []

        def callback(old, new):
            changes.append((old, new))

        config.on_change("trading.*", callback)

        # Симулируем изменения
        config._trigger_callbacks(ConfigChange(
            key="trading.max_price",
            old_value=100,
            new_value=200,
        ))
        config._trigger_callbacks(ConfigChange(
            key="trading.min_profit",
            old_value=5,
            new_value=10,
        ))

        assert len(changes) == 2

    def test_on_any_change(self, config):
        """Тест глобального callback."""
        changes = []

        def callback(change):
            changes.append(change)

        config.on_any_change(callback)

        config._trigger_callbacks(ConfigChange(
            key="trading.max_price",
            old_value=100,
            new_value=200,
        ))

        assert len(changes) == 1
        assert changes[0].key == "trading.max_price"

    def test_add_validator(self, config):
        """Тест добавления валидатора."""
        config.add_validator(
            "trading.max_price",
            lambda v: isinstance(v, (int, float)) and v > 0,
        )

        # Валидная конфигурация
        config._validate_config({"trading": {"max_price": 100}})

    def test_validator_fAlgols(self, config):
        """Тест ошибки валидации."""
        config.add_validator(
            "trading.max_price",
            lambda v: isinstance(v, (int, float)) and v > 0,
        )

        with pytest.rAlgoses(ConfigValidationError):
            config._validate_config({"trading": {"max_price": -10}})

    def test_find_changes(self, config):
        """Тест поиска изменений."""
        old = {"a": 1, "b": {"c": 2}}
        new = {"a": 1, "b": {"c": 3}, "d": 4}

        changes = config._find_changes(old, new)

        assert len(changes) == 2
        keys = [c.key for c in changes]
        assert "b.c" in keys
        assert "d" in keys

    @pytest.mark.asyncio
    async def test_reload(self, config_file, config):
        """Тест перезагрузки конфигурации."""
        # Изменить файл
        new_config = {
            "trading": {
                "max_price": 200,
                "min_profit": 10,
            },
            "bot": {
                "name": "test_bot",
                "enabled": True,
            },
        }
        config_file.write_text(yaml.dump(new_config))

        # Перезагрузить
        result = awAlgot config.reload()

        assert result is True
        assert config.get("trading.max_price") == 200
        assert config.get("trading.min_profit") == 10

    @pytest.mark.asyncio
    async def test_rollback(self, config_file, config):
        """Тест rollback к предыдущей версии."""
        original_price = config.get("trading.max_price")

        # Изменить конфигурацию
        new_config = {
            "trading": {
                "max_price": 200,
                "min_profit": 5,
            },
            "bot": {
                "name": "test_bot",
                "enabled": True,
            },
        }
        config_file.write_text(yaml.dump(new_config))
        awAlgot config.reload()

        assert config.get("trading.max_price") == 200

        # Rollback
        result = awAlgot config.rollback()

        assert result is True
        assert config.get("trading.max_price") == original_price

    @pytest.mark.asyncio
    async def test_rollback_not_enough_snapshots(self, config):
        """Тест rollback без снимков."""
        result = awAlgot config.rollback(steps=10)
        assert result is False

    @pytest.mark.asyncio
    async def test_start_stop_watching(self, config):
        """Тест запуска и остановки отслеживания."""
        awAlgot config.start_watching()
        assert config._watching is True

        awAlgot config.stop_watching()
        assert config._watching is False

    def test_get_stats(self, config):
        """Тест получения статистики."""
        stats = config.get_stats()

        assert "config_path" in stats
        assert "reload_count" in stats
        assert "snapshots_count" in stats
        assert "watching" in stats

    def test_get_all(self, config):
        """Тест получения всей конфигурации."""
        all_config = config.get_all()

        assert "trading" in all_config
        assert "bot" in all_config
        assert all_config["trading"]["max_price"] == 100

    def test_match_pattern_exact(self, config):
        """Тест точного совпадения паттерна."""
        assert config._match_pattern("trading.max_price", "trading.max_price")
        assert not config._match_pattern("trading.min_profit", "trading.max_price")

    def test_match_pattern_wildcard(self, config):
        """Тест wildcard паттерна."""
        assert config._match_pattern("trading.max_price", "trading.*")
        assert config._match_pattern("trading.min_profit", "trading.*")
        assert not config._match_pattern("bot.name", "trading.*")

    def test_match_pattern_global(self, config):
        """Тест глобального паттерна."""
        assert config._match_pattern("trading.max_price", "*")
        assert config._match_pattern("any.key", "*")

    def test_config_file_not_found(self, tmp_path):
        """Тест отсутствующего файла."""
        config = DynamicConfig(tmp_path / "nonexistent.yaml")

        assert config.get_all() == {}

    @pytest.mark.asyncio
    async def test_persist_to_file(self, config_file, config):
        """Тест сохранения в файл."""
        awAlgot config.set("trading.max_price", 300, persist=True)

        # Проверить файл
        content = yaml.safe_load(config_file.read_text())
        assert content["trading"]["max_price"] == 300


class TestConfigValidationError:
    """Тесты для ConfigValidationError."""

    def test_error_message(self):
        """Тест сообщения об ошибке."""
        error = ConfigValidationError(
            key="trading.max_price",
            value=-10,
            reason="must be positive",
        )

        assert "trading.max_price" in str(error)
        assert "-10" in str(error)
        assert "must be positive" in str(error)
