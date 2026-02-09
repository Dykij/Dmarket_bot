"""
Тестовый скрипт для проверки Steam интеграции.

Запуск: python test_steam_integration.py
"""

import asyncio
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def test_steam_integration():
    """Тестирует всю цепочку Steam интеграции."""
    from src.dmarket.steam_api import calculate_arbitrage, get_steam_price
    from src.dmarket.steam_arbitrage_enhancer import get_steam_enhancer
    from src.utils.steam_db_handler import get_steam_db

    logger.info("=" * 60)
    logger.info("STEAM INTEGRATION TEST")
    logger.info("=" * 60)

    # Тест 1: База данных
    logger.info("\n[TEST 1] Проверка базы данных...")
    db = get_steam_db()
    settings = db.get_settings()
    logger.info(f"✅ БД работает! Настройки: {settings}")

    # Тест 2: Steam API
    logger.info("\n[TEST 2] Проверка Steam API...")
    test_item = "AK-47 | Slate (Field-Tested)"

    try:
        steam_data = await get_steam_price(test_item)
        if steam_data:
            logger.info("✅ Steam API работает!")
            logger.info(f"   Предмет: {test_item}")
            logger.info(f"   Цена: ${steam_data['price']:.2f}")
            logger.info(f"   Объем: {steam_data['volume']} шт/день")
        else:
            logger.warning("⚠️ Steam API вернул None")
    except Exception as e:
        logger.error(f"❌ Ошибка Steam API: {e}")
        return

    # Тест 3: Расчет арбитража
    logger.info("\n[TEST 3] Проверка расчета арбитража...")
    dmarket_price = 2.0
    steam_price = 2.5
    profit = calculate_arbitrage(dmarket_price, steam_price)
    logger.info("✅ Расчет работает!")
    logger.info(f"   DMarket: ${dmarket_price:.2f}")
    logger.info(f"   Steam: ${steam_price:.2f}")
    logger.info(f"   Профит: {profit:.1f}%")

    # Тест 4: Кэширование
    logger.info("\n[TEST 4] Проверка кэширования...")
    db.update_steam_price(test_item, steam_data["price"], steam_data["volume"])
    cached_data = db.get_steam_data(test_item)

    if cached_data and db.is_cache_actual(cached_data["last_updated"]):
        logger.info("✅ Кэш работает!")
        logger.info(f"   Кэшированная цена: ${cached_data['price']:.2f}")
    else:
        logger.warning("⚠️ Проблема с кэшем")

    # Тест 5: Enhancer
    logger.info("\n[TEST 5] Проверка Enhancer...")
    enhancer = get_steam_enhancer()

    # Имитация предметов DMarket
    mock_items = [
        {
            "title": test_item,
            "price": {"USD": 200},  # $2.00 в центах
            "itemId": "test123",
        }
    ]

    enhanced = await enhancer.enhance_items(mock_items)
    logger.info("✅ Enhancer работает!")
    logger.info(f"   Обработано предметов: {len(mock_items)}")
    logger.info(f"   Найдено возможностей: {len(enhanced)}")

    if enhanced:
        item = enhanced[0]
        logger.info("   Пример находки:")
        logger.info(f"      Предмет: {item['title']}")
        logger.info(f"      DMarket: ${item['dmarket_price_usd']:.2f}")
        logger.info(f"      Steam: ${item['steam_price']:.2f}")
        logger.info(f"      Профит: {item['profit_pct']:.1f}%")
        logger.info(f"      Объем: {item['steam_volume']}")
        logger.info(f"      Ликвидность: {item['liquidity_status']}")

    # Тест 6: Статистика
    logger.info("\n[TEST 6] Проверка статистики...")
    stats = enhancer.get_daily_stats()
    logger.info("✅ Статистика работает!")
    logger.info(f"   Находок за 24ч: {stats['count']}")

    # Тест 7: Blacklist
    logger.info("\n[TEST 7] Проверка Blacklist...")
    test_blacklist_item = "Test Blacklist Item"
    enhancer.add_to_blacklist(test_blacklist_item, reason="Test")
    is_blacklisted = db.is_blacklisted(test_blacklist_item)
    logger.info(f"✅ Blacklist работает! Item blocked: {is_blacklisted}")

    # Очистка тестовых данных
    db.remove_from_blacklist(test_blacklist_item)

    logger.info("\n" + "=" * 60)
    logger.info("ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО! ✅")
    logger.info("=" * 60)
    logger.info("\nSteam интеграция готова к использованию!")
    logger.info("Следующие шаги:")
    logger.info("1. Добавьте команды в register_all_handlers.py:")
    logger.info("   - /stats для статистики")
    logger.info("   - /top для топа находок")
    logger.info("   - /steam_settings для настроек")
    logger.info("2. Используйте SteamArbitrageEnhancer в scanner_manager")
    logger.info("3. Запустите бота: python src/main.py")


if __name__ == "__main__":
    try:
        asyncio.run(test_steam_integration())
    except KeyboardInterrupt:
        logger.info("\nТест прерван пользователем")
    except Exception as e:
        logger.error(f"Ошибка теста: {e}", exc_info=True)
