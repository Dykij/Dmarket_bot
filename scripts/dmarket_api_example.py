#!/usr/bin/env python3
"""Примеры использования DMarket API v1.1.0.

Этот скрипт демонстрирует основные возможности работы с DMarket API:
- Получение баланса пользователя
- Получение списка предметов на рынке
- Использование новых эндпоинтов v1.1.0
- Работа с таргетами (Buy Orders)
- Конвертация цен (USD ↔ центы)

Документация:
- Swagger: https://docs.dmarket.com/v1/swagger.html
- Help Center: https://help.dmarket.com/

Обновлено: 28 декабря 2025
Версия: 1.0.0
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# Add the project root to the path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.dmarket.api.endpoints import (  # noqa: E402
    GAME_CSGO,
    GAME_DOTA2,
    GAME_RUST,
    GAME_TF2,
    cents_to_price,
    get_game_id,
    get_game_name,
    price_to_cents,
)
from src.dmarket.dmarket_api import DMarketAPI  # noqa: E402

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed")


def get_api_keys() -> tuple[str, str]:
    """Получить API ключи из переменных окружения.

    Returns:
        Кортеж (public_key, secret_key)

    Raises:
        SystemExit: Если ключи не настроены
    """
    public_key = os.environ.get("DMARKET_PUBLIC_KEY", "")
    secret_key = os.environ.get("DMARKET_SECRET_KEY", "")

    if not public_key or not secret_key:
        print("❌ Error: DMARKET_PUBLIC_KEY and DMARKET_SECRET_KEY must be set")
        print("\n📝 Инструкция:")
        print("   1. Создайте файл .env в корневой директории")
        print("   2. Добавьте:")
        print("      DMARKET_PUBLIC_KEY=ваш_публичный_ключ")
        print("      DMARKET_SECRET_KEY=ваш_секретный_ключ")
        print("\n🔗 Получить ключи: https://dmarket.com/account/api-keys")
        sys.exit(1)

    return public_key, secret_key


async def demo_balance(api: DMarketAPI) -> None:
    """Демонстрация получения баланса.

    Args:
        api: Экземпляр DMarket API клиента
    """
    print("\n" + "=" * 60)
    print("💰 ПОЛУЧЕНИЕ БАЛАНСА")
    print("=" * 60)

    try:
        balance = await api.get_balance()

        if balance.get("error"):
            print(f"❌ Ошибка: {balance.get('error_message', 'Unknown')}")
            return

        available = balance.get("available_balance", 0.0)
        total = balance.get("total_balance", 0.0)
        locked = balance.get("locked_balance", 0.0)

        print(f"💰 Всего: ${total:.2f} USD ({price_to_cents(total)} центов)")
        print(f"✅ Доступно: ${available:.2f} USD")
        print(f"🔒 Заблокировано: ${locked:.2f} USD")

    except Exception as e:
        print(f"❌ Ошибка при получении баланса: {e}")


async def demo_market_items(api: DMarketAPI, game: str = "csgo", limit: int = 5) -> None:
    """Демонстрация получения предметов с маркета.

    Args:
        api: Экземпляр DMarket API клиента
        game: Название игры (csgo, dota2, tf2, rust)
        limit: Количество предметов
    """
    print("\n" + "=" * 60)
    print(f"🎮 ПРЕДМЕТЫ НА МАРКЕТЕ ({get_game_name(get_game_id(game))})")
    print("=" * 60)

    try:
        game_id = get_game_id(game)
        items: dict[str, Any] = await api.get_market_items(game=game_id, limit=limit)
        items_list = items.get("objects", [])

        print(f"📦 Найдено предметов: {len(items_list)}")

        for i, item in enumerate(items_list[:5], 1):
            title = item.get("title", "Unknown")
            price_data = item.get("price", {})

            # Цена в центах
            price_cents = int(price_data.get("USD", 0))
            price_usd = cents_to_price(price_cents)

            print(f"\n  {i}. {title}")
            print(f"     💵 Цена: ${price_usd:.2f} ({price_cents} центов)")

    except ValueError as e:
        print(f"❌ Ошибка: {e}")
    except Exception as e:
        print(f"❌ Ошибка при получении предметов: {e}")


async def demo_supported_games() -> None:
    """Демонстрация поддерживаемых игр."""
    print("\n" + "=" * 60)
    print("🎮 ПОДДЕРЖИВАЕМЫЕ ИГРЫ")
    print("=" * 60)

    games = [
        ("csgo", GAME_CSGO),
        ("dota2", GAME_DOTA2),
        ("tf2", GAME_TF2),
        ("rust", GAME_RUST),
    ]

    for name, game_id in games:
        display_name = get_game_name(game_id)
        print(f"  • {name} → {game_id} ({display_name})")


async def demo_price_conversion() -> None:
    """Демонстрация конвертации цен."""
    print("\n" + "=" * 60)
    print("💱 КОНВЕРТАЦИЯ ЦЕН")
    print("=" * 60)

    test_prices = [1.50, 10.00, 99.99, 1000.00]

    print("\nUSD → Центы:")
    for price in test_prices:
        cents = price_to_cents(price)
        print(f"  ${price:.2f} = {cents} центов")

    print("\nЦенты → USD:")
    test_cents = [150, 1000, 9999, 100000]
    for cents in test_cents:
        usd = cents_to_price(cents)
        print(f"  {cents} центов = ${usd:.2f}")


async def main(args: argparse.Namespace) -> int:
    """Главная функция демонстрации DMarket API.

    Args:
        args: Аргументы командной строки

    Returns:
        Код завершения (0 - успех, 1 - ошибка)
    """
    print("\n" + "=" * 60)
    print("🚀 DMarket API v1.1.0 - Примеры использования")
    print("=" * 60)
    print("📅 Версия: 1.0.0 | Дата: 28 декабря 2025")

    # Демонстрация без API ключей
    if args.demo_only:
        await demo_supported_games()
        await demo_price_conversion()
        return 0

    # Получаем API ключи
    public_key, secret_key = get_api_keys()

    # Создаем API клиент
    api = DMarketAPI(public_key, secret_key)

    try:
        # Демонстрация различных функций
        await demo_balance(api)
        await demo_market_items(api, game=args.game, limit=args.limit)
        await demo_supported_games()
        await demo_price_conversion()

        print("\n" + "=" * 60)
        print("✅ Демонстрация завершена успешно!")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        return 1

    finally:
        # Закрываем клиент
        await api._close_client()


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов командной строки.

    Returns:
        Распарсенные аргументы
    """
    parser = argparse.ArgumentParser(
        description="DMarket API v1.1.0 - Примеры использования",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s                    # Полная демонстрация с API ключами
  %(prog)s --demo-only        # Только демо без API ключей
  %(prog)s --game dota2       # Показать предметы Dota 2
  %(prog)s --limit 10         # Показать 10 предметов
        """,
    )
    parser.add_argument(
        "--game",
        choices=["csgo", "dota2", "tf2", "rust"],
        default="csgo",
        help="Игра для демонстрации (default: csgo)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Количество предметов для отображения (default: 5)",
    )
    parser.add_argument(
        "--demo-only",
        action="store_true",
        help="Только демо без API ключей",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(main(args)))
