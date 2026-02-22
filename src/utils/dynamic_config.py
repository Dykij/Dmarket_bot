"""Dynamic Configuration - горячая перезагрузка конфигурации без перезапуска.

Этот модуль обеспечивает:
1. Hot reload конфигурации при изменении файлов
2. Подписка на изменения конфигурации (callbacks)
3. Валидация изменений перед применением
4. Rollback при ошибках
5. Метрики для мониторинга

Использование:
    >>> config = DynamicConfig("config/app.yaml")
    >>> config.on_change("trading.max_price", lambda old, new: print(f"{old} -> {new}"))
    >>> await config.start_watching()

Created: January 2026
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


@dataclass
class ConfigChange:
    """Запись об изменении конфигурации.

    Attributes:
        key: Путь к изменённому параметру (e.g., "trading.max_price")
        old_value: Старое значение
        new_value: Новое значение
        timestamp: Время изменения
        source: Источник изменения (file, api, env)
    """

    key: str
    old_value: Any
    new_value: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = "file"


@dataclass
class ConfigSnapshot:
    """Снимок конфигурации для rollback.

    Attributes:
        data: Данные конфигурации
        timestamp: Время создания снимка
        file_hash: Hash файла конфигурации
    """

    data: dict[str, Any]
    timestamp: datetime
    file_hash: str


class ConfigValidationError(Exception):
    """Ошибка валидации конфигурации."""

    def __init__(self, key: str, value: Any, reason: str) -> None:
        """Инициализация ошибки.

        Args:
            key: Ключ конфигурации
            value: Невалидное значение
            reason: Причина ошибки
        """
        self.key = key
        self.value = value
        self.reason = reason
        super().__init__(f"Invalid config '{key}': {reason} (value: {value})")


class DynamicConfig:
    """Динамическая конфигурация с hot reload.

    Особенности:
    - Автоматическое отслеживание изменений файла
    - Callbacks при изменении значений
    - Валидация перед применением
    - Rollback при ошибках
    - Prometheus метрики

    Пример:
        config = DynamicConfig("config/app.yaml")

        # Подписка на изменения
        config.on_change("trading.max_price", handler)

        # Запуск отслеживания
        await config.start_watching()

        # Получение значений
        max_price = config.get("trading.max_price", default=100)
    """

    def __init__(
        self,
        config_path: str | Path,
        watch_interval: int = 5,
        max_snapshots: int = 10,
    ) -> None:
        """Инициализация динамической конфигурации.

        Args:
            config_path: Путь к файлу конфигурации
            watch_interval: Интервал проверки изменений (секунды)
            max_snapshots: Максимальное количество снимков для rollback
        """
        self._config_path = Path(config_path)
        self._watch_interval = watch_interval
        self._max_snapshots = max_snapshots

        self._config: dict[str, Any] = {}
        self._snapshots: list[ConfigSnapshot] = []
        self._last_hash: str = ""

        # Callbacks: {key_pattern: [callback, ...]}
        self._callbacks: dict[str, list[Callable[[Any, Any], None]]] = {}
        self._global_callbacks: list[Callable[[ConfigChange], None]] = []

        # Validators: {key_pattern: validator_func}
        self._validators: dict[str, Callable[[Any], bool]] = {}

        # Состояние
        self._watching = False
        self._watch_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

        # Статистика
        self._reload_count = 0
        self._last_reload: datetime | None = None
        self._validation_errors = 0

        # Загрузить начальную конфигурацию
        self._load_config()

        logger.info(
            "dynamic_config_initialized",
            path=str(self._config_path),
            watch_interval=watch_interval,
        )

    def _load_config(self) -> bool:
        """Загрузить конфигурацию из файла.

        Returns:
            True если конфигурация была изменена
        """
        if not self._config_path.exists():
            logger.warning(
                "config_file_not_found",
                path=str(self._config_path),
            )
            return False

        try:
            content = self._config_path.read_text(encoding="utf-8")
            new_hash = hashlib.sha256(content.encode()).hexdigest()

            if new_hash == self._last_hash:
                return False  # Нет изменений

            new_config = yaml.safe_load(content) or {}

            # Валидировать новую конфигурацию
            self._validate_config(new_config)

            # Сохранить снимок стаSwarm конфигурации
            if self._config:
                self._save_snapshot()

            # Найти изменения
            changes = self._find_changes(self._config, new_config)

            # Применить новую конфигурацию
            self._config = new_config
            self._last_hash = new_hash
            self._reload_count += 1
            self._last_reload = datetime.now(UTC)

            # Вызвать callbacks
            for change in changes:
                self._trigger_callbacks(change)

            logger.info(
                "config_reloaded",
                path=str(self._config_path),
                changes_count=len(changes),
            )

            return True

        except yaml.YAMLError as e:
            logger.exception("config_parse_error", error=str(e))
            self._validation_errors += 1
            return False
        except ConfigValidationError as e:
            logger.exception(
                "config_validation_error",
                key=e.key,
                value=e.value,
                reason=e.reason,
            )
            self._validation_errors += 1
            return False

    def _validate_config(self, config: dict[str, Any]) -> None:
        """Валидировать конфигурацию.

        Args:
            config: Новая конфигурация для валидации

        RAlgoses:
            ConfigValidationError: Если валидация не прошла
        """
        for pattern, validator in self._validators.items():
            value = self._get_nested(config, pattern)
            if value is not None and not validator(value):
                raise ConfigValidationError(
                    pattern,
                    value,
                    "validation failed",
                )

    def _find_changes(
        self,
        old_config: dict[str, Any],
        new_config: dict[str, Any],
        prefix: str = "",
    ) -> list[ConfigChange]:
        """Найти изменения между конфигурациями.

        Args:
            old_config: Старая конфигурация
            new_config: Новая конфигурация
            prefix: Префикс пути для вложенных ключей

        Returns:
            Список изменений
        """
        changes = []

        all_keys = set(old_config.keys()) | set(new_config.keys())

        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_value = old_config.get(key)
            new_value = new_config.get(key)

            if isinstance(old_value, dict) and isinstance(new_value, dict):
                # Рекурсивно обработать вложенные словари
                changes.extend(self._find_changes(old_value, new_value, full_key))
            elif old_value != new_value:
                changes.append(
                    ConfigChange(
                        key=full_key,
                        old_value=old_value,
                        new_value=new_value,
                    )
                )

        return changes

    def _save_snapshot(self) -> None:
        """Сохранить снимок текущей конфигурации."""
        snapshot = ConfigSnapshot(
            data=self._config.copy(),
            timestamp=datetime.now(UTC),
            file_hash=self._last_hash,
        )

        self._snapshots.append(snapshot)

        # Ограничить количество снимков
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots :]

        logger.debug(
            "config_snapshot_saved",
            total_snapshots=len(self._snapshots),
        )

    def _trigger_callbacks(self, change: ConfigChange) -> None:
        """Вызвать callbacks для изменения.

        Args:
            change: Изменение конфигурации
        """
        # Глобальные callbacks
        for callback in self._global_callbacks:
            try:
                callback(change)
            except Exception as e:
                logger.exception(
                    "config_callback_error",
                    key=change.key,
                    error=str(e),
                )

        # Специфичные callbacks
        for pattern, callbacks in self._callbacks.items():
            if self._match_pattern(change.key, pattern):
                for callback in callbacks:
                    try:
                        callback(change.old_value, change.new_value)
                    except Exception as e:
                        logger.exception(
                            "config_callback_error",
                            key=change.key,
                            pattern=pattern,
                            error=str(e),
                        )

    @staticmethod
    def _match_pattern(key: str, pattern: str) -> bool:
        """Проверить соответствие ключа паттерну.

        Args:
            key: Ключ конфигурации
            pattern: Паттерн (поддерживает * для wildcard)

        Returns:
            True если соответствует
        """
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return key.startswith(pattern[:-1])
        return key == pattern

    @staticmethod
    def _get_nested(
        config: dict[str, Any],
        key: str,
        default: Any = None,
    ) -> Any:
        """Получить вложенное значение по ключу.

        Args:
            config: Словарь конфигурации
            key: Ключ в формате "section.subsection.key"
            default: Значение по умолчанию

        Returns:
            Значение или default
        """
        parts = key.split(".")
        value = config

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение конфигурации.

        Args:
            key: Ключ в формате "section.subsection.key"
            default: Значение по умолчанию

        Returns:
            Значение конфигурации

        Example:
            >>> config.get("trading.max_price", default=100)
            150.0
        """
        return self._get_nested(self._config, key, default)

    def get_section(self, section: str) -> dict[str, Any]:
        """Получить секцию конфигурации.

        Args:
            section: Название секции

        Returns:
            Словарь секции или пустой словарь
        """
        value = self.get(section, {})
        return value if isinstance(value, dict) else {}

    async def set(
        self,
        key: str,
        value: Any,
        persist: bool = True,
    ) -> None:
        """Установить значение конфигурации.

        Args:
            key: Ключ конфигурации
            value: Новое значение
            persist: Сохранить в файл

        Example:
            >>> await config.set("trading.max_price", 200)
        """
        async with self._lock:
            old_value = self.get(key)

            # Установить значение
            parts = key.split(".")
            current = self._config

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            current[parts[-1]] = value

            # Вызвать callbacks
            if old_value != value:
                change = ConfigChange(
                    key=key,
                    old_value=old_value,
                    new_value=value,
                    source="api",
                )
                self._trigger_callbacks(change)

            # Сохранить в файл
            if persist:
                await self._save_to_file()

            logger.info(
                "config_value_set",
                key=key,
                old_value=old_value,
                new_value=value,
            )

    async def _save_to_file(self) -> None:
        """Сохранить конфигурацию в файл."""
        try:
            content = yaml.dump(
                self._config,
                default_flow_style=False,
                allow_unicode=True,
            )

            # Обновить hash перед записью
            self._last_hash = hashlib.sha256(content.encode()).hexdigest()

            self._config_path.write_text(content, encoding="utf-8")

            logger.debug("config_saved_to_file", path=str(self._config_path))

        except Exception as e:
            logger.exception("config_save_error", error=str(e))

    def on_change(
        self,
        key_pattern: str,
        callback: Callable[[Any, Any], None],
    ) -> None:
        """Подписаться на изменения конфигурации.

        Args:
            key_pattern: Паттерн ключа (поддерживает * для wildcard)
            callback: Функция callback(old_value, new_value)

        Example:
            >>> config.on_change("trading.*", lambda old, new: print(f"Changed: {old} -> {new}"))
        """
        if key_pattern not in self._callbacks:
            self._callbacks[key_pattern] = []

        self._callbacks[key_pattern].append(callback)

        logger.debug(
            "config_callback_registered",
            pattern=key_pattern,
        )

    def on_any_change(self, callback: Callable[[ConfigChange], None]) -> None:
        """Подписаться на любые изменения конфигурации.

        Args:
            callback: Функция callback(ConfigChange)
        """
        self._global_callbacks.append(callback)

    def add_validator(
        self,
        key_pattern: str,
        validator: Callable[[Any], bool],
    ) -> None:
        """Добавить валидатор для ключа.

        Args:
            key_pattern: Паттерн ключа
            validator: Функция валидации (возвращает True если валидно)

        Example:
            >>> config.add_validator(
            ...     "trading.max_price",
            ...     lambda v: isinstance(v, (int, float)) and v > 0
            ... )
        """
        self._validators[key_pattern] = validator

        logger.debug(
            "config_validator_registered",
            pattern=key_pattern,
        )

    async def rollback(self, steps: int = 1) -> bool:
        """Откатить конфигурацию к предыдущему снимку.

        Args:
            steps: Количество шагов назад

        Returns:
            True если rollback успешен
        """
        async with self._lock:
            if len(self._snapshots) < steps:
                logger.warning(
                    "rollback_failed_not_enough_snapshots",
                    requested=steps,
                    avAlgolable=len(self._snapshots),
                )
                return False

            # Получить нужный снимок
            snapshot_index = -steps
            snapshot = self._snapshots[snapshot_index]

            # Найти изменения для callbacks
            changes = self._find_changes(self._config, snapshot.data)

            # Применить снимок
            self._config = snapshot.data.copy()
            self._last_hash = snapshot.file_hash

            # Удалить использованные снимки
            self._snapshots = self._snapshots[:snapshot_index]

            # Вызвать callbacks
            for change in changes:
                self._trigger_callbacks(change)

            # Сохранить в файл
            await self._save_to_file()

            logger.info(
                "config_rollback_complete",
                steps=steps,
                timestamp=snapshot.timestamp.isoformat(),
            )

            return True

    async def start_watching(self) -> None:
        """Запустить отслеживание изменений файла."""
        if self._watching:
            return

        self._watching = True
        self._watch_task = asyncio.create_task(self._watch_loop())

        logger.info(
            "config_watching_started",
            interval=self._watch_interval,
        )

    async def stop_watching(self) -> None:
        """Остановить отслеживание изменений."""
        self._watching = False

        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass

        logger.info("config_watching_stopped")

    async def _watch_loop(self) -> None:
        """Цикл отслеживания изменений."""
        while self._watching:
            try:
                self._load_config()
                await asyncio.sleep(self._watch_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("config_watch_error", error=str(e))
                await asyncio.sleep(self._watch_interval)

    async def reload(self) -> bool:
        """Принудительно перезагрузить конфигурацию.

        Returns:
            True если конфигурация была изменена
        """
        async with self._lock:
            # Сбросить hash для принудительной перезагрузки
            self._last_hash = ""
            return self._load_config()

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику.

        Returns:
            Словарь со статистикой
        """
        return {
            "config_path": str(self._config_path),
            "reload_count": self._reload_count,
            "last_reload": (
                self._last_reload.isoformat() if self._last_reload else None
            ),
            "validation_errors": self._validation_errors,
            "snapshots_count": len(self._snapshots),
            "callbacks_count": sum(len(cbs) for cbs in self._callbacks.values()),
            "validators_count": len(self._validators),
            "watching": self._watching,
        }

    def get_all(self) -> dict[str, Any]:
        """Получить всю конфигурацию.

        Returns:
            Копия всей конфигурации
        """
        return self._config.copy()


# Глобальный экземпляр
_dynamic_config: DynamicConfig | None = None


def get_dynamic_config() -> DynamicConfig:
    """Получить глобальный экземпляр DynamicConfig.

    Returns:
        DynamicConfig

    RAlgoses:
        RuntimeError: Если конфигурация не инициализирована
    """
    if _dynamic_config is None:
        raise RuntimeError("DynamicConfig not initialized")
    return _dynamic_config


def init_dynamic_config(
    config_path: str | Path,
    watch_interval: int = 5,
) -> DynamicConfig:
    """Инициализировать глобальный экземпляр DynamicConfig.

    Args:
        config_path: Путь к файлу конфигурации
        watch_interval: Интервал проверки изменений

    Returns:
        DynamicConfig
    """
    global _dynamic_config
    _dynamic_config = DynamicConfig(config_path, watch_interval)
    return _dynamic_config


__all__ = [
    "ConfigChange",
    "ConfigSnapshot",
    "ConfigValidationError",
    "DynamicConfig",
    "get_dynamic_config",
    "init_dynamic_config",
]
