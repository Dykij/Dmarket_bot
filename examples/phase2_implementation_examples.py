"""Phase 2 Implementation Examples.

Примеры использования новых Algo модулей из Фазы 2.

Показывает как использовать:
1. Algo Arbitrage Predictor
2. NLP Command Handler
3. Интеграцию обоих модулей
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import Phase 2 modules
from src.dmarket.Algo_arbitrage_predictor import AlgoArbitragePredictor
from src.telegram_bot.nlp_handler import NLPCommandHandler


async def example_1_Algo_arbitrage():
    """Пример 1: Использование Algo Arbitrage Predictor.

    Показывает как Algo прогнозирует лучшие арбитражные возможности.
    """
    print("\n" + "=" * 60)
    print("ПРИМЕР 1: Algo Arbitrage Predictor")
    print("=" * 60)

    # Инициализация
    predictor = AlgoArbitragePredictor()

    # Mock данные рынка (в реальности - из DMarket API)
    market_items = [
        {
            "title": "AK-47 | Redline (Field-Tested)",
            "itemId": "item_123",
            "gameId": "csgo",
            "price": {"USD": 1000},  # $10.00
            "suggestedPrice": {"USD": 1500},  # $15.00
        },
        {
            "title": "AWP | Asiimov (Field-Tested)",
            "itemId": "item_456",
            "gameId": "csgo",
            "price": {"USD": 3000},  # $30.00
            "suggestedPrice": {"USD": 3800},  # $38.00
        },
        {
            "title": "M4A4 | Howl (Factory New)",
            "itemId": "item_789",
            "gameId": "csgo",
            "price": {"USD": 50000},  # $500.00 (too expensive)
            "suggestedPrice": {"USD": 55000},
        },
    ]

    # Прогнозирование возможностей
    print("\n📊 Анализ рынка...")
    opportunities = await predictor.predict_best_opportunities(
        items=market_items,
        current_balance=50.0,  # $50 доступно
        risk_level="medium",
    )

    # Вывод результатов
    print(f"\n✅ Найдено {len(opportunities)} возможностей:")
    for i, opp in enumerate(opportunities, 1):
        print(f"\n{i}. {opp.title}")
        print(f"   Цена покупки: ${opp.current_price:.2f}")
        print(f"   Прогнозируемая прибыль: ${opp.predicted_profit:.2f}")
        print(f"   ROI: {opp.roi_percent:.1f}%")
        print(f"   Уверенность ML: {opp.confidence:.1%}")
        print(f"   Риск: {opp.risk_score:.1f}/100")


async def example_2_nlp_handler():
    """Пример 2: Использование NLP Command Handler.

    Показывает как NLP распознает естественные команды.
    """
    print("\n" + "=" * 60)
    print("ПРИМЕР 2: NLP Command Handler")
    print("=" * 60)

    # Инициализация
    nlp = NLPCommandHandler()

    # Тестовые команды на разных языках
    test_commands = [
        ("Найди арбитраж в CS:GO до $10", "Русский"),
        ("What's my balance?", "English"),
        ("Create target for AK-47 at $15", "English"),
        ("Показать все таргеты", "Русский"),
        ("Buscar arbitraje en Dota 2", "Español"),
    ]

    print("\n🗣️ Обработка естественных команд:")
    for command, lang_name in test_commands:
        result = await nlp.parse_user_intent(command, user_id=123)

        print(f"\n📝 Команда: \"{command}\" ({lang_name})")
        print(f"   ├─ Intent: {result.intent}")
        print(f"   ├─ Язык: {result.language}")
        print(f"   ├─ Уверенность: {result.confidence:.1%}")
        if result.params:
            print(f"   └─ Параметры: {result.params}")


async def example_3_integration():
    """Пример 3: Интеграция NLP + Algo Arbitrage.

    Показывает полный workflow:
    1. Пользователь отправляет текстовую команду
    2. NLP распознает намерение
    3. Algo Arbitrage ищет возможности
    """
    print("\n" + "=" * 60)
    print("ПРИМЕР 3: NLP + Algo Arbitrage Integration")
    print("=" * 60)

    # Инициализация модулей
    nlp = NLPCommandHandler()
    predictor = AlgoArbitragePredictor()

    # Симуляция команды пользователя
    user_command = "Найди арбитраж в Dota 2 под $20"
    print(f"\n👤 Пользователь: \"{user_command}\"")

    # Шаг 1: NLP распознает команду
    print("\n🧠 Шаг 1: NLP анализ...")
    intent_result = await nlp.parse_user_intent(user_command, user_id=123)

    if intent_result.intent != "scan_arbitrage":
        print(f"❌ Неожиданное намерение: {intent_result.intent}")
        return

    print(f"✅ Распознано: {intent_result.intent}")
    print(f"   Игра: {intent_result.params.get('game', 'не указано')}")
    print(f"   Макс. цена: ${intent_result.params.get('max_price', 'не указано')}")

    # Шаг 2: Получение данных рынка (mock)
    print("\n📡 Шаг 2: Получение данных рынка...")
    market_items = [
        {
            "title": "Arcana: Demon Eater",
            "itemId": "dota_item_1",
            "gameId": "dota2",
            "price": {"USD": 1200},  # $12.00
            "suggestedPrice": {"USD": 1600},  # $16.00
        },
        {
            "title": "Dragonclaw Hook",
            "itemId": "dota_item_2",
            "gameId": "dota2",
            "price": {"USD": 1800},  # $18.00
            "suggestedPrice": {"USD": 2200},  # $22.00
        },
    ]

    # Шаг 3: Algo прогнозирование
    print("\n🤖 Шаг 3: Algo прогнозирование...")
    max_price = intent_result.params.get("max_price", 100.0)

    opportunities = await predictor.predict_best_opportunities(
        items=market_items,
        current_balance=max_price,
        risk_level="medium",
    )

    # Шаг 4: Вывод рекомендаций
    print(f"\n✅ Найдено {len(opportunities)} возможностей:")
    for opp in opportunities:
        print(f"\n💎 {opp.title}")
        print(f"   💰 Цена: ${opp.current_price:.2f}")
        print(f"   📈 Прибыль: ${opp.predicted_profit:.2f} ({opp.roi_percent:.1f}% ROI)")
        print(f"   🎯 Уверенность: {opp.confidence:.1%}")
        print(f"   ⚠️ Риск: {opp.risk_score:.0f}/100")


async def main():
    """Запуск всех примеров."""
    print("\n" + "=" * 60)
    print("🚀 PHASE 2 IMPLEMENTATION EXAMPLES")
    print("=" * 60)
    print("\nДемонстрация новых Algo модулей:")
    print("1. Algo Arbitrage Predictor - ML-прогнозирование арбитража")
    print("2. NLP Command Handler - Обработка естественного языка")
    print("3. Integration - Полная интеграция модулей")

    # Запуск примеров
    await example_1_Algo_arbitrage()
    await example_2_nlp_handler()
    await example_3_integration()

    print("\n" + "=" * 60)
    print("✅ Все примеры выполнены успешно!")
    print("=" * 60)
    print("\n📚 Документация:")
    print("- Algo Arbitrage: src/dmarket/SKILL_Algo_ARBITRAGE.md")
    print("- NLP Handler: src/telegram_bot/SKILL_NLP_HANDLER.md")
    print("- Full Analysis: docs/SKILLS_MARKETPLACE_INTEGRATION_ANALYSIS.md")
    print()


if __name__ == "__main__":
    asyncio.run(main())
