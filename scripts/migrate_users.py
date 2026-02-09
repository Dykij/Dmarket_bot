#!/usr/bin/env python3
"""Скрипт миграции данных пользователей в новую структуру профилей.

Выполняет следующие операции:
1. Ищет существующие файлы данных пользователей
2. Преобразует старый формат в новый с поддержкой профилей
3. Создает резервную копию старых данных
4. Записывает новые данные в формате JSON
"""

import argparse
import json
import os
import pathlib
import pickle
import shutil
import sys
import time
from datetime import datetime
from typing import Any


# Простое логирование для скрипта
class SimpleLogger:
    """Простой логгер для скрипта миграции."""

    def info(self, msg: str) -> None:
        """Логирует info сообщение."""
        sys.stdout.write(f"[INFO] {msg}\n")

    def warning(self, msg: str) -> None:
        """Логирует warning сообщение."""
        sys.stdout.write(f"[WARNING] {msg}\n")

    def error(self, msg: str) -> None:
        """Логирует error сообщение."""
        sys.stderr.write(f"[ERROR] {msg}\n")

    def exception(self, msg: str) -> None:
        """Логирует exception сообщение."""
        sys.stderr.write(f"[EXCEPTION] {msg}\n")

    def debug(self, msg: str) -> None:
        """Логирует debug сообщение."""
        sys.stdout.write(f"[DEBUG] {msg}\n")


logger = SimpleLogger()


def setup_args() -> argparse.Namespace:
    """Настройка аргументов командной строки.

    Returns:
        Объект с распарсенными аргументами командной строки
    """
    parser = argparse.ArgumentParser(
        description="Миграция данных пользователей в новую структуру профилей",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Путь к директории с данными пользователей",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Создать резервную копию данных перед миграцией",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительно выполнить миграцию даже при наличии конфликтов",
    )
    return parser.parse_args()


def find_user_data_files(data_dir: str) -> dict[str, str]:
    """Находит файлы с данными пользователей.

    Args:
        data_dir: Директория с данными пользователей

    Returns:
        Словарь с идентификаторами пользователей и путями к их файлам данных

    """
    user_files: dict[str, str] = {}

    # Проверяем, существует ли директория
    if not os.path.exists(data_dir):  # type: ignore[attr-defined]
        logger.warning(f"Директория '{data_dir}' не найдена")
        return user_files

    # Проверяем на наличие общего файла профилей
    profiles_path = os.path.join(data_dir, "user_profiles.json")  # type: ignore[attr-defined]
    if os.path.exists(profiles_path):  # type: ignore[attr-defined]
        logger.info(f"Найден файл профилей пользователей: {profiles_path}")
        user_files["profiles"] = profiles_path

    # Ищем отдельные файлы пользовательских данных
    for filename in os.listdir(data_dir):  # type: ignore[attr-defined]
        filepath = os.path.join(data_dir, filename)  # type: ignore[attr-defined]

        # Проверяем, что это файл (не директория)
        if not pathlib.Path(filepath).is_file():  # type: ignore[attr-defined]
            continue

        # Проверяем формат имени файла
        if filename.startswith("user_") and filename.endswith(".data"):
            user_id = filename[5:-5]  # Извлекаем ID из имени
            user_files[user_id] = filepath
            logger.info(
                f"Найден файл данных пользователя {user_id}: {filepath}",
            )
        elif filename.startswith("context_") and filename.endswith(".pickle"):
            user_id = filename[8:-7]  # Извлекаем ID из имени
            if user_id not in user_files:
                user_files[user_id] = filepath
                logger.info(
                    f"Найден файл контекста: {user_id} в {filepath}",
                )

    logger.info(
        f"Найдено {len(user_files)} файлов данных пользователей",
    )
    return user_files


def load_user_data(filepath: str) -> dict[str, Any] | None:
    """Загружает данные пользователя из файла.

    Args:
        filepath: Путь к файлу данных

    Returns:
        Данные пользователя или None в случае ошибки

    """
    try:
        # Определяем формат файла по расширению
        if filepath.endswith(".data"):
            # Старый формат - простой текстовый файл
            with open(filepath, encoding="utf-8") as f:
                data = {}
                for line in f:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        data[key] = value
                return data
        elif filepath.endswith(".json"):
            # JSON формат
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        elif filepath.endswith(".pickle"):
            # Pickle формат (для контекста)
            with open(filepath, "rb") as f:
                data: dict[str, Any] = pickle.load(f)  # noqa: S301
                return data
        else:
            logger.warning(f"Неизвестный формат файла: {filepath}")
            return None
    except (OSError, json.JSONDecodeError, pickle.PickleError):
        logger.exception(f"Ошибка при загрузке данных из {filepath}")
        return None


def create_backup(user_files: dict[str, str], backup_dir: str) -> bool:
    """Создает резервную копию файлов данных пользователей.

    Args:
        user_files: Словарь с путями к файлам данных пользователей
        backup_dir: Директория для резервных копий

    Returns:
        True, если резервная копия создана успешно, иначе False

    """

    timestamp = datetime.now(tz=datetime.now().astimezone().tzinfo).strftime(
        "%Y%m%d_%H%M%S",
    )
    backup_path = os.path.join(  # type: ignore[attr-defined]
        backup_dir,
        f"user_data_backup_{timestamp}",
    )

    try:
        os.makedirs(backup_path, exist_ok=True)  # type: ignore[attr-defined]
        logger.info(f"Создана директория для резервных копий: {backup_path}")

        # Копируем каждый файл
        for filepath in user_files.values():
            if not os.path.exists(filepath):  # type: ignore[attr-defined]
                continue

            filename = os.path.basename(filepath)  # type: ignore[attr-defined]
            dest_path = os.path.join(  # type: ignore[attr-defined]
                backup_path,
                filename,
            )
            shutil.copy2(filepath, dest_path)
            logger.debug(f"Создана резервная копия {filepath} -> {dest_path}")

        logger.info(
            f"Резервное копирование завершено: {len(user_files)} файлов",
        )
    except OSError:
        logger.exception("Ошибка при создании резервных копий")
        return False
    else:
        return True


def migrate_user_data(
    user_files: dict[str, str],
    output_path: str,
) -> dict[str, Any]:
    """Преобразует старый формат данных пользователей в новый.

    Args:
        user_files: Словарь с путями к файлам данных пользователей
        output_path: Путь для сохранения нового файла профилей

    Returns:
        Словарь с мигрированными профилями пользователей

    """
    profiles = {}

    # Проверка на наличие существующего файла профилей
    if "profiles" in user_files:
        try:
            existing_profiles = load_user_data(user_files["profiles"])
            if existing_profiles:
                profiles = existing_profiles
                logger.info(f"Загружено {len(profiles)} существующих профилей")
        except (OSError, json.JSONDecodeError):
            logger.exception("Ошибка при загрузке существующих профилей")

    # Обрабатываем каждый файл пользователя
    migrated_count = 0
    for user_id, filepath in user_files.items():
        if user_id == "profiles":
            continue

        user_data = load_user_data(filepath)
        if not user_data:
            continue

        # Если пользователь уже существует в профилях, объединяем данные
        if user_id in profiles:
            logger.info(f"Объединение данных для пользователя {user_id}")
            migrate_single_user(user_id, user_data, profiles)
        else:
            # Создаем новый профиль
            profiles[user_id] = create_user_profile(user_id, user_data)
            migrated_count += 1

    logger.info(
        f"Создано {migrated_count} новых, всего: {len(profiles)}",
    )

    # Сохраняем результат в новый файл
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
        logger.info(f"Профили пользователей сохранены в {output_path}")
    except OSError:
        logger.exception("Ошибка при сохранении профилей")

    return profiles


def create_user_profile(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Создает профиль пользователя из старых данных.

    Args:
        user_id: ID пользователя
        data: Старые данные пользователя

    Returns:
        Новый профиль пользователя
    """
    # Создаем базовый профиль
    profile = {
        "language": "ru",
        "api_key": "",
        "api_secret": "",
        "auto_trading_enabled": False,
        "trade_settings": {
            "min_profit": 2.0,
            "max_price": 50.0,
            "max_trades": 3,
            "risk_level": "medium",
        },
        "last_activity": time.time(),
    }

    # Переносим существующие API ключи
    if "api_key" in data:
        profile["api_key"] = str(data["api_key"])
    if "api_secret" in data:
        profile["api_secret"] = str(data["api_secret"])

    # Если в данных есть настройки торговли, переносим их
    if "trade_settings" in data and isinstance(data["trade_settings"], dict):
        for key, value in data["trade_settings"].items():
            if key in profile["trade_settings"]:
                profile["trade_settings"][key] = value

    # Извлекаем настройки авто-торговли
    if "auto_trading_enabled" in data:
        if isinstance(data["auto_trading_enabled"], bool):
            profile["auto_trading_enabled"] = data["auto_trading_enabled"]
        elif isinstance(data["auto_trading_enabled"], str):
            profile["auto_trading_enabled"] = data["auto_trading_enabled"].lower() == "true"

    # Извлекаем язык
    if "language" in data:
        profile["language"] = str(data["language"])

    logger.debug(f"Создан профиль для пользователя {user_id}")
    return profile


def migrate_single_user(
    user_id: str,
    data: dict[str, Any],
    profiles: dict[str, Any],
) -> None:
    """Объединяет данные пользователя с существующим профилем.

    Args:
        user_id: ID пользователя
        data: Данные пользователя
        profiles: Словарь с профилями пользователей

    """
    # Если пользователя нет в профилях, создаем новый
    if user_id not in profiles:
        profiles[user_id] = create_user_profile(user_id, data)
        return

    # Обновляем только те поля, которые отсутствуют или пусты в профиле
    if "api_key" in data and not profiles[user_id]["api_key"]:
        profiles[user_id]["api_key"] = str(data["api_key"])

    if "api_secret" in data and not profiles[user_id]["api_secret"]:
        profiles[user_id]["api_secret"] = str(data["api_secret"])

    # Обновляем настройки торговли
    if "trade_settings" in data and isinstance(data["trade_settings"], dict):
        trade_settings = data["trade_settings"]
        for key, value in trade_settings.items():
            if "trade_settings" in profiles[user_id] and key in profiles[user_id]["trade_settings"]:
                profiles[user_id]["trade_settings"][key] = value

    logger.debug(f"Обновлен существующий профиль пользователя {user_id}")


def main() -> int:
    """Основная функция миграции.

    Returns:
        Код возврата: 0 при успехе, 1 при ошибке
    """
    args = setup_args()

    # Создаем директорию данных, если она не существует
    if not os.path.exists(args.data_dir):  # type: ignore[attr-defined]
        try:
            os.makedirs(args.data_dir)  # type: ignore[attr-defined]
            logger.info(f"Создана директория данных: {args.data_dir}")
        except OSError:
            logger.exception("Ошибка при создании директории данных")
            return 1

    # Находим файлы пользователей
    user_files = find_user_data_files(args.data_dir)
    if not user_files:
        logger.warning("Файлы данных пользователей не найдены")
        return 0

    # Создаем резервную копию, если запрошено
    if args.backup:
        backup_dir = os.path.join(  # type: ignore[attr-defined]
            args.data_dir,
            "backups",
        )
        os.makedirs(backup_dir, exist_ok=True)  # type: ignore[attr-defined]
        if not create_backup(user_files, backup_dir):
            if not args.force:
                logger.error(
                    "Миграция отменена из-за ошибки резервного копирования",
                )
                return 1
            logger.warning(
                "Продолжение миграции без резервной копии (--force)",
            )

    # Путь для нового файла профилей
    output_path = os.path.join(  # type: ignore[attr-defined]
        args.data_dir,
        "user_profiles.json",
    )

    # Выполняем миграцию
    profiles = migrate_user_data(user_files, output_path)

    # Выводим статистику
    logger.info(
        f"Миграция завершена. Создано/обновлено {len(profiles)} профилей.",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
