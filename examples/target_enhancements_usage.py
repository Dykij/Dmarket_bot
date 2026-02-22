"""Пример использования расширенной системы таргетов.

Демонстрирует все новые возможности:
- Создание таргетов с фильтрами
- Автоматическое перебитие
- Контроль перевыставлений
- Мониторинг диапазона цен
- Пакетные операции

Этот файл служит документацией и примером для пользователей.
"""

import asyncio

from src.dmarket.dmarket_api import DMarketAPI
from src.dmarket.models.target_enhancements import (
    PriceRangeAction,
    PriceRangeConfig,
    RelistAction,
    RelistLimitConfig,
    TargetDefaults,
    TargetOverbidConfig,
)
from src.dmarket.targets import TargetManager


async def example_full_integration():
    """Пример: Полная интеграция всех функций."""
    print("\n=== Полная интеграция всех функций ===")

    api = DMarketAPI(public_key="your_key", secret_key="your_secret")

    # Настроить все дефолты
    defaults = TargetDefaults(
        default_amount=1,
        default_overbid_config=TargetOverbidConfig(enabled=True, max_overbid_percent=2.0),
        default_relist_config=RelistLimitConfig(max_relists=5, action_on_limit=RelistAction.PAUSE),
        default_price_range_config=PriceRangeConfig(
            min_price=8.0, max_price=15.0, action_on_breach=PriceRangeAction.NOTIFY
        ),
    )

    # Создать менеджер со всеми возможностями
    manager = TargetManager(
        api_client=api,
        defaults=defaults,
        enable_overbid=True,
        enable_relist_control=True,
        enable_price_monitoring=True,
    )

    print("✅ TargetManager создан со всеми функциями")


async def main():
    """Запустить примеры."""
    print("🚀 Пример расширенной системы таргетов")
    print("=" * 60)
    print("\n⚠️ Для реального использования замените API ключи\n")

    # await example_full_integration()


if __name__ == "__main__":
    asyncio.run(main())
