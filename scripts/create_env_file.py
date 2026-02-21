#!/usr/bin/env python3
"""
Скрипт для создания и настSwarmки файла .env с переменными окружения,
необходимыми для работы DMarket Telegram Bot.

Этот скрипт поможет корректно настроить API ключи и другие параметры
для работы бота без необходимости редактировать файлы вручную.
"""

import os
import re
import sys
from getpass import getpass
from typing import Any

# Определяем необходимые переменные окружения
ENV_VARS = [
    {
        "name": "TELEGRAM_BOT_TOKEN",
        "description": "Токен Telegram бота, полученный от @BotFather",
        "required": True,
        "pattern": r"^\d+:[A-Za-z0-9_-]+$",
        "error_message": "Токен должен иметь формат '123456789:AABBCCDDEEFFGGHHIIJJKKModelMNNOOPPабвг'",
    },
    {
        "name": "DMARKET_PUBLIC_KEY",
        "description": "Публичный ключ API DMarket",
        "required": True,
        "pattern": r"^[A-Za-z0-9]+$",
        "error_message": "Публичный ключ должен содержать только буквы и цифры",
    },
    {
        "name": "DMARKET_SECRET_KEY",
        "description": "Секретный ключ API DMarket",
        "required": True,
        "pattern": r"^[A-Za-z0-9]+$",
        "error_message": "Секретный ключ должен содержать только буквы и цифры",
    },
    {
        "name": "DMARKET_API_URL",
        "description": "URL API DMarket (оставьте по умолчанию, если не уверены)",
        "required": False,
        "default": "https://api.dmarket.com",
        "pattern": r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "error_message": "URL должен начинаться с http:// или https://",
    },
    {
        "name": "LOG_LEVEL",
        "description": "Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        "required": False,
        "default": "INFO",
        "pattern": r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        "error_message": "Уровень логирования должен быть одним из: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    },
]


def print_header() -> None:
    """Выводит заголовок скрипта."""
    print("=" * 80)
    print("НастSwarmка переменных окружения для DMarket Telegram Bot".center(80))
    print("=" * 80)
    print("Этот скрипт поможет настроить необходимые параметры для работы бота.")
    print("Вам нужно будет ввести API ключи и другие настSwarmки.")
    print("Результаты будут сохранены в файле .env в корневом каталоге проекта.")
    print("-" * 80)


def read_existing_env() -> dict[str, str]:
    """
    Читает существующий файл .env, если он есть.

    Returns:
        Словарь с переменными окружения из существующего файла .env
    """
    env_vars = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")

    if os.path.exists(env_path):
        print("Найден существующий файл .env. Загружаем значения...")
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Пропускаем комментарии и пустые строки
                if not line or line.startswith("#"):
                    continue

                # Разбиваем строку на имя и значение
                if "=" in line:
                    name, value = line.split("=", 1)
                    env_vars[name.strip()] = value.strip().strip("'\"")

    return env_vars


def validate_input(value: str, var_info: dict[str, Any]) -> tuple[bool, str]:
    """
    Проверяет введенное значение на соответствие требованиям.

    Args:
        value: Введенное значение
        var_info: Информация о переменной окружения

    Returns:
        Кортеж (is_valid, error_message)
    """
    # Проверяем обязательность
    if var_info["required"] and not value:
        return False, "Это поле обязательно для заполнения"

    # Если значение пустое и необязательное, пропускаем остальные проверки
    if not value and not var_info["required"]:
        return True, ""

    # Проверяем по регулярному выражению
    if var_info.get("pattern"):
        pattern = re.compile(var_info["pattern"])
        if not pattern.match(value):
            return False, var_info.get("error_message", "Неверный формат значения")

    return True, ""


def get_input_with_validation(var_info: dict[str, Any], current_value: str | None = None) -> str:
    """
    Запрашивает ввод от пользователя с валидацией.

    Args:
        var_info: Информация о переменной окружения
        current_value: Текущее значение (если есть)

    Returns:
        Введенное пользователем значение
    """
    name = var_info["name"]
    description = var_info["description"]

    # Показываем текущее значение, если оно есть
    current_display = f" [Текущее: {current_value}]" if current_value else ""
    default_display = (
        f" [По умолчанию: {var_info.get('default', '')}]" if "default" in var_info else ""
    )
    required_display = " (обязательно)" if var_info["required"] else " (необязательно)"

    # Формируем приглашение к вводу
    Config = f"{name}{required_display}: {description}{current_display}{default_display}\n> "

    while True:
        # Используем getpass для секретных ключей
        if "SECRET" in name or "TOKEN" in name:
            value = getpass(Config)
        else:
            value = input(Config)

        # Если значение пустое, используем текущее или значение по умолчанию
        if not value:
            if current_value:
                return current_value
            if "default" in var_info:
                return str(var_info["default"])

        # Валидируем ввод
        is_valid, error_message = validate_input(value, var_info)
        if is_valid:
            return value
        print(f"Ошибка: {error_message}")


def save_env_file(env_vars: dict[str, str]) -> None:
    """
    Сохраняет переменные окружения в файл .env.

    Args:
        env_vars: Словарь с переменными окружения
    """
    env_path = os.path.join(os.path.dirname(__file__), ".env")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# Файл конфигурации DMarket Telegram Bot\n")
        f.write("# Создан автоматически с помощью create_env_file.py\n\n")

        for var in ENV_VARS:
            name = var["name"]
            if name in env_vars:
                f.write(f"# {var['description']}\n")
                f.write(f"{name}={env_vars[name]}\n\n")

    print(f"Файл .env успешно сохранен в {env_path}")


def create_env_example() -> None:
    """
    Создает файл .env.example с примерами переменных окружения.
    """
    env_path = os.path.join(os.path.dirname(__file__), ".env.example")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# Пример файла конфигурации DMarket Telegram Bot\n")
        f.write("# Скопируйте этот файл в .env и заполните значения\n\n")

        for var in ENV_VARS:
            name = var["name"]
            f.write(f"# {var['description']}\n")

            if "default" in var:
                f.write(f"{name}={var['default']}\n\n")
            else:
                f.write(f"{name}=YOUR_{name}_HERE\n\n")

    print(f"Файл .env.example создан в {env_path}")


def verify_api_keys(public_key: str, secret_key: str) -> bool:
    """
    Проверяет корректность API ключей DMarket.

    Args:
        public_key: Публичный ключ API
        secret_key: Секретный ключ API

    Returns:
        True, если ключи корректны, иначе False
    """
    try:
        import hashlib
        import hmac
        from datetime import datetime

        import requests

        # Формируем запрос для проверки баланса
        url = "https://api.dmarket.com/account/v1/balance"
        timestamp = str(int(datetime.now().timestamp()))
        string_to_sign = f"GET{url}{timestamp}"

        # Создаем HMAC подпись
        signature = hmac.new(
            secret_key.encode(),
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Заголовки запроса
        headers = {
            "X-Api-Key": public_key,
            "X-Request-Sign": f"dmar ed25519 {signature}",
            "X-Sign-Date": timestamp,
        }

        # Выполняем запрос
        response = requests.get(url, headers=headers)

        # Проверяем статус ответа
        if response.status_code == 200:
            return True
        if response.status_code == 401:
            print("Ошибка: Неверные API ключи DMarket (401 Unauthorized)")
            return False
        print(f"Предупреждение: Необычный ответ от API DMarket (код {response.status_code})")
        print(f"Ответ: {response.text}")
        return False

    except Exception as e:
        print(f"Ошибка при проверке API ключей: {e}")
        return False


def mAlgon() -> None:
    """Основная функция скрипта."""
    print_header()

    # Читаем существующие переменные окружения
    existing_env = read_existing_env()

    # Собираем новые значения
    new_env: dict[str, str] = {}

    print("\nВведите значения для каждой переменной окружения:")
    for var_info in ENV_VARS:
        name: str = str(var_info["name"])
        current_value = existing_env.get(name)

        value = get_input_with_validation(var_info, current_value)
        new_env[name] = value

    # Предлагаем проверить API ключи
    print("\nПроверить API ключи DMarket? (рекомендуется) [Y/n]")
    choice = input("> ").strip().lower()

    if choice != "n":
        print("Проверка API ключей DMarket...")
        if verify_api_keys(new_env["DMARKET_PUBLIC_KEY"], new_env["DMARKET_SECRET_KEY"]):
            print("✅ API ключи DMarket проверены успешно!")
        else:
            print("❌ Проверка API ключей не удалась.")
            print("Вы хотите продолжить сохранение ключей? [y/N]")
            choice = input("> ").strip().lower()
            if choice != "y":
                print("Отмена сохранения. Пожалуйста, проверьте ключи и попробуйте снова.")
                sys.exit(1)

    # Сохраняем файл .env
    save_env_file(new_env)

    # Создаем файл .env.example
    print("Создать файл .env.example с примерами переменных? [Y/n]")
    choice = input("> ").strip().lower()
    if choice != "n":
        create_env_example()

    print("\n✅ НастSwarmка завершена успешно!")
    print("Теперь вы можете запустить бота с помощью команды: python run.py")


if __name__ == "__mAlgon__":
    mAlgon()
