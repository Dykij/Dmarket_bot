"""Модуль управления профилями пользователей для Telegram бота.

Этот модуль обеспечивает:
- Безопасное хранение ключей API DMarket и других учетных данных
- Управление правами доступа к различным функциям бота
- Персонализацию настроек для каждого пользователя
- Кэширование данных пользователя для снижения нагрузки на API
"""

import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

from cryptography.fernet import Fernet
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Пути к файлам данных
DATA_DIR = Path("data")
USER_PROFILES_FILE = DATA_DIR / "user_profiles.json"
ENCRYPTION_KEY_FILE = DATA_DIR / "encryption.key"

# Уровни доступа
ACCESS_LEVELS = {
    "admin": 100,  # Полный доступ ко всем функциям
    "premium": 70,  # Доступ к расширенным функциям
    "regular": 50,  # Стандартный набор функций
    "basic": 30,  # Базовый набор функций
    "restricted": 10,  # Ограниченные функции
    "blocked": 0,  # Заблокированные пользователи
}

# Минимальные уровни доступа для различных функций
FEATURE_ACCESS_LEVELS = {
    "view_balance": ACCESS_LEVELS["basic"],
    "search_items": ACCESS_LEVELS["basic"],
    "basic_arbitrage": ACCESS_LEVELS["regular"],
    "advanced_arbitrage": ACCESS_LEVELS["premium"],
    "auto_arbitrage": ACCESS_LEVELS["premium"],
    "admin_tools": ACCESS_LEVELS["admin"],
    "set_api_keys": ACCESS_LEVELS["basic"],
}


# Синглтон для хранения профилей пользователей в памяти
class UserProfileManager:
    """Менеджер профилей пользователей.

    Этот класс обеспечивает интерфейс для работы с профилями пользователей,
    включая загрузку, сохранение и шифрование конфиденциальных данных.
    """

    _instance: "UserProfileManager | None" = None

    def __new__(cls) -> "UserProfileManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._profiles: dict[int, dict[str, Any]] = {}
        self._encryption_key: bytes | None = None
        self._fernet: Fernet | None = None
        self._admin_ids: set[int] = set()
        self._last_save_time: float = 0
        self._initialized: bool = True

        # Создаем каталог данных, если он не существует
        DATA_DIR.mkdir(exist_ok=True)

        # Инициализируем шифрование
        self._init_encryption()

        # Загружаем профили
        self.load_profiles()

    def _init_encryption(self) -> None:
        """Инициализирует систему шифрования.

        Загружает или создает ключ шифрования для защиты конфиденциальных данных.
        """
        if ENCRYPTION_KEY_FILE.exists():
            # Загружаем существующий ключ
            self._encryption_key = Path(ENCRYPTION_KEY_FILE).read_bytes()
        else:
            # Создаем новый ключ
            self._encryption_key = Fernet.generate_key()
            Path(ENCRYPTION_KEY_FILE).write_bytes(self._encryption_key)

            # Устанавливаем ограничения доступа к файлу ключа
            try:
                os.chmod(
                    ENCRYPTION_KEY_FILE,
                    0o600,
                )  # Только чтение и запись для владельца
            except Exception as e:
                logger.warning(f"Не удалось установить разрешения для файла ключа: {e}")

        # Создаем объект для шифрования/дешифрования
        if self._encryption_key is not None:
            self._fernet = Fernet(self._encryption_key)

    def _encrypt(self, data: str) -> str:
        """Шифрует строку данных.

        Args:
            data: Строка для шифрования

        Returns:
            Зашифрованная строка в base64

        """
        if not data:
            return ""

        if self._fernet is None:
            self._init_encryption()

        if self._fernet is None:
            return ""

        return self._fernet.encrypt(data.encode()).decode()

    def _decrypt(self, encrypted_data: str) -> str:
        """Дешифрует строку данных.

        Args:
            encrypted_data: Зашифрованная строка в base64

        Returns:
            Расшифрованная строка

        """
        if not encrypted_data:
            return ""

        if self._fernet is None:
            self._init_encryption()

        if self._fernet is None:
            return ""

        try:
            return self._fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.exception(f"Ошибка при дешифровании данных: {e}")
            return ""

    def load_profiles(self) -> None:
        """Загружает профили пользователей из файла."""
        if not USER_PROFILES_FILE.exists():
            logger.info("Файл профилей пользователей не найден. Создаем новый.")
            self._profiles = {}
            return

        try:
            with open(USER_PROFILES_FILE, encoding="utf-8") as f:
                profiles_data = json.load(f)

            # Преобразуем ключи из строк в целые числа
            self._profiles = {}
            for user_id_str, profile in profiles_data.items():
                user_id = int(user_id_str)

                # Дешифруем конфиденциальные данные
                if "api_keys" in profile and isinstance(profile["api_keys"], dict):
                    for key_name, encrypted_value in profile["api_keys"].items():
                        profile["api_keys"][key_name] = self._decrypt(encrypted_value)

                self._profiles[user_id] = profile

                # Добавляем админов в список
                if profile.get("access_level") == "admin":
                    self._admin_ids.add(user_id)

            logger.info(f"Загружено {len(self._profiles)} профилей пользователей")

        except Exception as e:
            logger.exception(f"Ошибка при загрузке профилей пользователей: {e}")
            self._profiles = {}

    def save_profiles(self, force: bool = False) -> None:
        """Сохраняет профили пользователей в файл.

        Args:
            force: Принудительное сохранение, игнорируя время с последнего сохранения

        """
        # Ограничиваем частоту сохранений (не чаще 1 раза в 5 секунд)
        current_time = time.time()
        if not force and current_time - self._last_save_time < 5:
            return

        try:
            # Создаем копию профилей для сохранения
            profiles_to_save = {}

            for user_id, profile in self._profiles.items():
                # Создаем копию профиля
                profile_copy = profile.copy()

                # Шифруем конфиденциальные данные
                if "api_keys" in profile_copy and isinstance(
                    profile_copy["api_keys"],
                    dict,
                ):
                    encrypted_keys = {}
                    for key_name, value in profile_copy["api_keys"].items():
                        encrypted_keys[key_name] = self._encrypt(value)
                    profile_copy["api_keys"] = encrypted_keys

                profiles_to_save[str(user_id)] = profile_copy

            # Записываем в файл
            with open(USER_PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(profiles_to_save, f, indent=2)

            self._last_save_time = current_time
            logger.info(f"Сохранено {len(self._profiles)} профилей пользователей")

        except Exception as e:
            logger.exception(f"Ошибка при сохранении профилей пользователей: {e}")

    def get_profile(self, user_id: int) -> dict[str, Any]:
        """Получает профиль пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Профиль пользователя (словарь с данными)

        """
        if user_id not in self._profiles:
            self._profiles[user_id] = self._create_default_profile()
            self.save_profiles()

        return self._profiles[user_id]

    def _create_default_profile(self) -> dict[str, Any]:
        """Создает профиль пользователя по умолчанию.

        Returns:
            Новый профиль с настройками по умолчанию

        """
        return {
            "created_at": int(time.time()),
            "last_activity": int(time.time()),
            "access_level": "basic",
            "settings": {
                "language": "ru",
                "items_per_page": 5,
                "notification_enabled": True,
            },
            "api_keys": {},
            "stats": {
                "commands_used": 0,
                "searches_performed": 0,
                "arbitrage_found": 0,
            },
        }

    def update_profile(self, user_id: int, data: dict[str, Any]) -> None:
        """Обновляет данные в профиле пользователя.

        Args:
            user_id: ID пользователя
            data: Данные для обновления (ключи и значения)

        """
        if user_id not in self._profiles:
            self._profiles[user_id] = self._create_default_profile()

        # Обновляем данные верхнего уровня
        for key, value in data.items():
            if key != "api_keys":  # API ключи обрабатываются отдельно
                self._profiles[user_id][key] = value

        # Обновляем время последней активности
        self._profiles[user_id]["last_activity"] = int(time.time())

        # Проверяем, является ли пользователь админом
        if self._profiles[user_id].get("access_level") == "admin":
            self._admin_ids.add(user_id)
        elif user_id in self._admin_ids:
            self._admin_ids.remove(user_id)

        self.save_profiles()

    def set_api_key(self, user_id: int, key_name: str, key_value: str) -> None:
        """Безопасно сохраняет ключ API в профиле пользователя.

        Args:
            user_id: ID пользователя
            key_name: Имя ключа (например, "dmarket_public_key")
            key_value: Значение ключа

        """
        profile = self.get_profile(user_id)

        # Инициализируем секцию для API ключей, если её нет
        if "api_keys" not in profile:
            profile["api_keys"] = {}

        # Сохраняем ключ
        profile["api_keys"][key_name] = key_value

        # Сохраняем профиль
        self.save_profiles(force=True)

    def get_api_key(self, user_id: int, key_name: str) -> str:
        """Получает API ключ из профиля пользователя.

        Args:
            user_id: ID пользователя
            key_name: Имя ключа (например, "dmarket_public_key")

        Returns:
            Значение ключа или пустую строку, если ключ не найден

        """
        profile = self.get_profile(user_id)

        if "api_keys" not in profile:
            return ""

        return profile["api_keys"].get(key_name, "")

    def has_access(self, user_id: int, feature: str) -> bool:
        """Проверяет, имеет ли пользователь доступ к функции.

        Args:
            user_id: ID пользователя
            feature: Имя функции (из FEATURE_ACCESS_LEVELS)

        Returns:
            True, если у пользователя есть доступ, иначе False

        """
        profile = self.get_profile(user_id)
        user_level_name = profile.get("access_level", "basic")
        user_level = ACCESS_LEVELS.get(user_level_name, ACCESS_LEVELS["basic"])

        required_level = FEATURE_ACCESS_LEVELS.get(feature, ACCESS_LEVELS["admin"])

        return user_level >= required_level

    def set_access_level(self, user_id: int, level: str) -> bool:
        """Устанавливает уровень доступа для пользователя.

        Args:
            user_id: ID пользователя
            level: Уровень доступа (из ACCESS_LEVELS)

        Returns:
            True, если уровень был установлен, иначе False

        """
        if level not in ACCESS_LEVELS:
            return False

        profile = self.get_profile(user_id)
        profile["access_level"] = level

        # Обновляем список админов, если нужно
        if level == "admin":
            self._admin_ids.add(user_id)
        elif user_id in self._admin_ids:
            self._admin_ids.remove(user_id)

        self.save_profiles()
        return True

    def get_admin_ids(self) -> set[int]:
        """Возвращает набор ID пользователей с правами администратора.

        Returns:
            Множество ID администраторов

        """
        return self._admin_ids.copy()

    def track_stat(self, user_id: int, stat_name: str, increment: int = 1) -> None:
        """Обновляет статистику пользователя.

        Args:
            user_id: ID пользователя
            stat_name: Имя счетчика статистики
            increment: Значение для инкремента (по умолчанию 1)

        """
        profile = self.get_profile(user_id)

        if "stats" not in profile:
            profile["stats"] = {}

        if stat_name not in profile["stats"]:
            profile["stats"][stat_name] = 0

        profile["stats"][stat_name] += increment

        # Не сохраняем после каждого обновления статистики, чтобы избежать частых записей
        # Сохранение произойдет при следующем вызове update_profile или set_api_key


# Создаем глобальный экземпляр менеджера профилей
profile_manager = UserProfileManager()


# Вспомогательные функции для работы с профилями в контексте Telegram бота


async def check_user_access(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    feature: str,
) -> bool:
    """Проверяет доступ пользователя к функции бота.

    Args:
        update: Объект Update от Telegram
        context: Контекст обработчика
        feature: Имя функции (из FEATURE_ACCESS_LEVELS)

    Returns:
        True, если у пользователя есть доступ, иначе False

    """
    if not update.effective_user:
        return False

    user_id = update.effective_user.id

    # Проверяем доступ через менеджер профилей
    return profile_manager.has_access(user_id, feature)


async def get_api_keys(user_id: int) -> tuple[str | None, str | None]:
    """Получает API ключи DMarket для пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        Кортеж (public_key, secret_key) или (None, None), если ключи не найдены

    """
    public_key = profile_manager.get_api_key(user_id, "dmarket_public_key")
    secret_key = profile_manager.get_api_key(user_id, "dmarket_secret_key")

    if not public_key or not secret_key:
        return None, None

    return public_key, secret_key


async def set_api_keys(user_id: int, public_key: str, secret_key: str) -> bool:
    """Сохраняет API ключи DMarket для пользователя.

    Args:
        user_id: ID пользователя
        public_key: Публичный ключ API DMarket
        secret_key: Секретный ключ API DMarket

    Returns:
        True в случае успеха, иначе False

    """
    try:
        # Проверяем, что ключи не пустые
        if not public_key or not secret_key:
            return False

        # Сохраняем ключи
        profile_manager.set_api_key(user_id, "dmarket_public_key", public_key)
        profile_manager.set_api_key(user_id, "dmarket_secret_key", secret_key)

        # Обновляем дату установки ключей
        profile = profile_manager.get_profile(user_id)
        if "api_keys_info" not in profile:
            profile["api_keys_info"] = {}

        profile["api_keys_info"]["setup_time"] = int(time.time())
        profile_manager.update_profile(
            user_id,
            {"api_keys_info": profile["api_keys_info"]},
        )

        return True

    except Exception as e:
        logger.exception(f"Ошибка при установке API ключей для пользователя {user_id}: {e}")
        return False


async def get_user_settings(user_id: int) -> dict[str, Any]:
    """Получает настройки пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        Словарь с настройками пользователя

    """
    profile = profile_manager.get_profile(user_id)
    return profile.get("settings", {})


async def update_user_settings(user_id: int, settings: dict[str, Any]) -> None:
    """Обновляет настройки пользователя.

    Args:
        user_id: ID пользователя
        settings: Словарь с настройками для обновления

    """
    profile = profile_manager.get_profile(user_id)

    if "settings" not in profile:
        profile["settings"] = {}

    # Обновляем настройки
    for key, value in settings.items():
        profile["settings"][key] = value

    profile_manager.update_profile(user_id, {"settings": profile["settings"]})


# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Awaitable[None]])


# Декоратор для проверки прав доступа
def require_access_level(feature: str) -> Callable[[F], F]:
    """Декоратор для проверки прав доступа к функции бота.

    Args:
        feature: Имя функции (из FEATURE_ACCESS_LEVELS)

    Returns:
        Декоратор, который проверяет доступ к функции

    """

    def decorator(func: F) -> F:
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args: Any,
            **kwargs: Any,
        ) -> None:
            if not update.effective_user:
                if update.message:
                    await update.message.reply_text(
                        "⚠️ Ошибка: Не удалось определить пользователя.",
                    )
                return

            user_id = update.effective_user.id

            if not profile_manager.has_access(user_id, feature):
                if update.message:
                    await update.message.reply_text(
                        f"⛔ У вас нет доступа к этой функции ({feature}).\n"
                        "Для получения доступа обратитесь к администратору.",
                    )
                return

            # Если доступ есть, выполняем исходную функцию
            await func(update, context, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
