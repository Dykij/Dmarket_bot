#!/usr/bin/env python3
"""
Базовый пример: Простое сканирование арбитражных возможностей.

Этот пример показывает минимальный код для получения топ-10 арбитражных
возможностей с использованием AI-прогнозирования.
"""

import asyncio
import os

# Add src to path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.dmarket.ai_arbitrage_predictor import AIArbitragePredictor
from src.dmarket.dmarket_api import DMarketAPI
from src.ml.enhanced_predictor import EnhancedPricePredictor


async def main():
    """Простое сканирование CS:GO рынка."""
    
    # 1. Инициализация API клиента
    api = DMarketAPI(
        public_key=os.getenv("DMARKET_PUBLIC_KEY"),
        secret_key=os.getenv("DMARKET_SECRET_KEY")
    )
    
    # 2. Инициализация AI-предиктора
    ml_predictor = EnhancedPricePredictor()
    ai_arbitrage = AIArbitragePredictor(ml_predictor)
    
    print("🔍 Сканирование CS:GO рынка...")
    
    # 3. Получение рыночных данных
    market_items = await api.get_market_items(
        game="csgo",
        limit=100  # Первые 100 items для быстрого теста
    )
    
    print(f"📦 Получено {len(market_items)} предметов")
    
    # 4. AI-прогнозирование
    opportunities = await ai_arbitrage.predict_best_opportunities(
        items=market_items,
        current_balance=100.0,  # $100 USD available
        risk_level="medium"  # Средний risk level
    )
    
    # 5. Вывод топ-10 результатов
    print("\n🎯 Топ-10 арбитражных возможностей:\n")
    print("=" * 80)
    
    for i, opp in enumerate(opportunities[:10], 1):
        print(f"\n{i}. {opp['title']}")
        print(f"   Текущая цена: ${opp['price']['USD'] / 100:.2f}")
        print(f"   Прогноз прибыли: ${opp['predicted_profit']:.2f}")
        print(f"   Уверенность: {opp['confidence']:.1%}")
        print(f"   Risk Score: {opp['risk_score']:.1f}/100")
        print(f"   ROI: {opp['roi_percent']:.1f}%")
    
    print("\n" + "=" * 80)
    print(f"✅ Найдено {len(opportunities)} возможностей")
    
    # Cleanup
    await api.close()


if __name__ == "__main__":
    # Проверка .env
    if not os.getenv("DMARKET_PUBLIC_KEY"):
        print("❌ Ошибка: DMARKET_PUBLIC_KEY не найден")
        print("💡 Создайте .env файл с API ключами")
        sys.exit(1)
    
    asyncio.run(main())
