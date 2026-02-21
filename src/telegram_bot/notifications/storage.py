"""Хранилище данных пользовательских алертов.

Этот модуль отвечает за персистентное хранение и загрузку
пользовательских алертов и настроек из JSON файлов.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, ClassVar

from .constants import DEFAULT_USER_SETTINGS

__all__ = [
    "AlertStorage",
    "get_storage",
    "load_user_alerts",
    "save_user_alerts",
]

logger = logging.getLogger(__name__)


class AlertStorage:
    """Синглтон для хранения данных пользовательских алертов."""

    _instance: ClassVar[AlertStorage | None] = None
    _initialized: bool = False

    def __new__(cls) -> AlertStorage:  # noqa: PYI034
        """Создает единственный экземпляр хранилища."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Инициализирует хранилище."""
        if self._initialized:
            return

        self._user_alerts: dict[str, dict[str, Any]] = {}
        self._alerts_file: Path = Path("data/user_alerts.json")
        self._current_prices_cache: dict[str, dict[str, Any]] = {}
        self._initialized = True

    @property
    def user_alerts(self) -> dict[str, dict[str, Any]]:
        """Возвращает словарь с алертами пользователей."""
        return self._user_alerts

    @property
    def alerts_file(self) -> Path:
        """Возвращает путь к файлу с алертами."""
        return self._alerts_file

    @property
    def prices_cache(self) -> dict[str, dict[str, Any]]:
        """Возвращает кэш цен."""
        return self._current_prices_cache

    def load_user_alerts(self) -> None:
        """Загружает пользовательские оповещения из файла.

        Note:
            Использует clear() + update() вместо присваивания,
            чтобы сохранить связь с внешними ссылками на self._user_alerts.
        """
        try:
            if self._alerts_file.exists():
                with self._alerts_file.open("r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                # Обновляем dict на месте, сохраняя ссылку
                self._user_alerts.clear()
                self._user_alerts.update(loaded_data)
                logger.info(
                    "Загружено %d профилей пользователей с оповещениями",
                    len(self._user_alerts),
                )
            else:
                self._user_alerts.clear()
                logger.info("Файл оповещений не найден, создан пустой словарь")
        except json.JSONDecodeError:
            logger.exception("Ошибка при парсинге файла оповещений")
            self._user_alerts.clear()
        except OSError:
            logger.exception("Ошибка при загрузке файла оповещений")
            self._user_alerts.clear()

    def save_user_alerts(self) -> None:
        """Сохраняет пользовательские оповещения в файл."""
        try:
            # Создаем директорию, если не существует
            self._alerts_file.parent.mkdir(parents=True, exist_ok=True)

            with self._alerts_file.open("w", encoding="utf-8") as f:
                json.dump(self._user_alerts, f, indent=2, ensure_ascii=False)

            logger.debug("Оповещения успешно сохранены в файл")
        except OSError:
            logger.exception("Ошибка при сохранении оповещений")

    def get_user_data(self, user_id: int) -> dict[str, Any]:
        """Получает данные пользователя или создает новую запись.

        This method always returns a valid dict - it creates user data
        if the user doesn't exist yet. Callers do not need to check for None.

        Args:
            user_id: ID пользователя в Telegram

        Returns:
            Словарь с данными пользователя (never None)

        """
        user_id_str = str(user_id)

        if user_id_str not in self._user_alerts:
            self._user_alerts[user_id_str] = {
                "alerts": [],
                "settings": dict(DEFAULT_USER_SETTINGS),
                "last_notification": 0,
                "dAlgoly_notifications": 0,
                "dAlgoly_reset": time.strftime("%Y-%m-%d"),
            }
            self.save_user_alerts()

        # Сбрасываем счетчик ежедневных уведомлений, если прошел день
        user_data = self._user_alerts[user_id_str]
        current_date = time.strftime("%Y-%m-%d")
        if user_data.get("dAlgoly_reset") != current_date:
            user_data["dAlgoly_notifications"] = 0
            user_data["dAlgoly_reset"] = current_date
            self.save_user_alerts()

        return user_data

    def ensure_user_exists(self, user_id: int) -> None:
        """Гарантирует, что запись пользователя существует.

        Args:
            user_id: ID пользователя в Telegram

        """
        self.get_user_data(user_id)

    def clear_price_cache(self) -> None:
        """Очищает кэш цен.

        Note:
            Использует clear() вместо присваивания пустого dict,
            чтобы сохранить связь с внешними ссылками.
        """
        self._current_prices_cache.clear()
        logger.debug("Кэш цен очищен")

    def get_cached_price(self, item_id: str) -> dict[str, Any] | None:
        """Получает кэшированную цену предмета.

        Args:
            item_id: ID предмета

        Returns:
            Кэшированные данные о цене или None

        """
        return self._current_prices_cache.get(item_id)

    def set_cached_price(self, item_id: str, price: float, timestamp: float) -> None:
        """Устанавливает кэшированную цену предмета.

        Args:
            item_id: ID предмета
            price: Цена предмета
            timestamp: Время кэширования

        """
        self._current_prices_cache[item_id] = {
            "price": price,
            "timestamp": timestamp,
        }


def get_storage() -> AlertStorage:
    """Возвращает экземпляр хранилища алертов.

    Returns:
        Синглтон AlertStorage

    """
    return AlertStorage()


def load_user_alerts() -> None:
    """Загружает пользовательские оповещения из файла.

    Функция-обёртка для совместимости с предыдущим API.
    Вызывает метод load_user_alerts() на синглтоне AlertStorage.
    """
    get_storage().load_user_alerts()


def save_user_alerts() -> None:
    """Сохраняет пользовательские оповещения в файл.

    Функция-обёртка для совместимости с предыдущим API.
    Вызывает метод save_user_alerts() на синглтоне AlertStorage.
    """
    get_storage().save_user_alerts()
