"""
Пример использования Steam Integration в ArbitrageScanner.

Демонстрирует:
- Создание сканера с включенной Steam проверкой
- Сканирование с обогащением Steam данными
- Обработку результатов с Steam ценами
"""

import asyncio
import logging

from src.dmarket.arbitrage_scanner import ArbitrageScanner

from src.dmarket.dmarket_api import DMarketAPI

# НастSwarmка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def example_steam_arbitrage():
    """Пример поиска арбитража с Steam проверкой."""

    # 1. Создаем API клиент
    api_client = DMarketAPI()

    # 2. Создаем сканер с включенной Steam проверкой
    scanner = ArbitrageScanner(
        api_client=api_client,
        enable_liquidity_filter=True,
        enable_steam_check=True,  # 🔥 Включаем Steam интеграцию
    )

    logger.info("Scanner created with Steam integration enabled")

    # 3. Сканируем CS:GO рынок
    logger.info("Scanning CS:GO market for arbitrage opportunities...")

    results = await scanner.scan_game(
        game="csgo",
        mode="medium",
        max_items=10,
        price_from=5.0,  # От $5
        price_to=50.0,  # До $50
    )

    # 4. Обрабатываем результаты
    if not results:
        logger.warning("No arbitrage opportunities found")
        return

    logger.info(f"Found {len(results)} arbitrage opportunities!")
    print("\n" + "=" * 80)
    print("🎯 ARBITRAGE OPPORTUNITIES WITH STEAM PRICES")
    print("=" * 80 + "\n")

    for i, item in enumerate(results, 1):
        title = item.get("title", "Unknown")
        dmarket_price = item.get("price", {}).get("USD", 0) / 100

        print(f"{i}. {title}")
        print(f"   💰 DMarket Price: ${dmarket_price:.2f}")

        # Проверяем наличие Steam данных
        if "steam_price" in item:
            steam_price = item["steam_price"]
            steam_profit = item.get("steam_profit_pct", 0)
            steam_volume = item.get("steam_volume", 0)
            liquidity = item.get("liquidity_status", "Unknown")

            print(f"   🎮 Steam Price: ${steam_price:.2f}")
            print(f"   📈 Net Profit: {steam_profit:.1f}% (after 13.04% Steam commission)")
            print(f"   📊 Volume: {steam_volume} sales/day")
            print(f"   💧 Liquidity: {liquidity}")

            # Рекомендация
            if steam_profit > 20:
                print("   ✅ EXCELLENT OPPORTUNITY! High profit margin")
            elif steam_profit > 10:
                print("   ✅ Good opportunity")
            else:
                print("   ⚠️  Low margin - consider carefully")
        else:
            # Без Steam данных
            profit = item.get("profit", 0)
            print(f"   📈 Estimated Profit: {profit:.1f}%")
            print("   ⚠️  Steam data not avAlgolable")

        print()

    print("=" * 80)
    print(f"Total opportunities: {len(results)}")
    print("=" * 80)


async def example_compare_with_without_steam():
    """Сравнение результатов со Steam и без Steam."""

    api_client = DMarketAPI()

    # Сканирование БЕЗ Steam
    print("\n" + "=" * 80)
    print("🔍 SCANNING WITHOUT STEAM (Traditional mode)")
    print("=" * 80 + "\n")

    scanner_without_steam = ArbitrageScanner(api_client=api_client, enable_steam_check=False)

    results_without = await scanner_without_steam.scan_game("csgo", "medium", 10)
    print(f"Found {len(results_without)} items without Steam check")

    # Сканирование С Steam
    print("\n" + "=" * 80)
    print("🔥 SCANNING WITH STEAM (Enhanced mode)")
    print("=" * 80 + "\n")

    scanner_with_steam = ArbitrageScanner(api_client=api_client, enable_steam_check=True)

    results_with = await scanner_with_steam.scan_game("csgo", "medium", 10)
    print(f"Found {len(results_with)} items with Steam check")

    # Сравнение
    print("\n" + "=" * 80)
    print("📊 COMPARISON")
    print("=" * 80)
    print(f"Without Steam: {len(results_without)} opportunities")
    print(f"With Steam: {len(results_with)} opportunities")

    filtered = len(results_without) - len(results_with)
    if filtered > 0:
        print(
            f"Filtered out: {filtered} low-quality items ({filtered * 100 // len(results_without)}%)"
        )
    print("\n✅ Steam filter helps reduce false positives!")
    print("=" * 80)


async def example_settings_control():
    """Пример управления настSwarmками Steam."""

    from src.utils.steam_db_handler import get_steam_db

    db = get_steam_db()

    print("\n" + "=" * 80)
    print("⚙️ STEAM SETTINGS CONTROL")
    print("=" * 80 + "\n")

    # Получаем текущие настSwarmки
    settings = db.get_settings()
    print("Current settings:")
    print(f"  • Min Profit: {settings['min_profit']:.1f}%")
    print(f"  • Min Volume: {settings['min_volume']} sales/day")
    print(f"  • Status: {'⏸️ Paused' if settings['is_paused'] else '▶️ Active'}")

    # Обновляем настSwarmки
    print("\nUpdating settings...")
    db.update_settings(
        min_profit=15.0,  # Требуем минимум 15% профита
        min_volume=100,  # Требуем минимум 100 продаж/день
    )

    # Проверяем обновленные настSwarmки
    updated = db.get_settings()
    print("\nUpdated settings:")
    print(f"  • Min Profit: {updated['min_profit']:.1f}%")
    print(f"  • Min Volume: {updated['min_volume']} sales/day")
    print("\n✅ Settings updated successfully!")
    print("=" * 80)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║       🔥 Steam API Integration Example 🔥                   ║
║                                                              ║
║  Demonstrates Steam Market price checking integration       ║
║  with DMarket arbitrage scanner                             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Запускаем примеры
    try:
        # Пример 1: Базовое использование
        asyncio.run(example_steam_arbitrage())

        # Пример 2: Сравнение (закомментировано для экономии времени)
        # asyncio.run(example_compare_with_without_steam())

        # Пример 3: Управление настSwarmками
        asyncio.run(example_settings_control())

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        logger.error(f"Error in example: {e}", exc_info=True)
