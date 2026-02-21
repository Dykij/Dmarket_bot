"""Модуль для анализа цен и истории продаж предметов на DMarket.

Включает функции для:
- Получения исторических данных о ценах
- Расчета статистических показателей (средние цены, волатильность)
- Выявления недооцененных предметов
- Анализа спроса и предложения
- ML-based выбор оптимального порога скидки
"""

import logging
import operator
import statistics
import time
from datetime import datetime
from typing import Any

# Импортируем DMarketAPI для взаимодействия с API
from src.dmarket.dmarket_api import DMarketAPI

# Настраиваем логирование
logger = logging.getLogger(__name__)

# Кэш для хранения истории цен
# Структура: {item_id: {"prices": [...], "last_update": timestamp}}
_price_history_cache = {}
_CACHE_TTL = 3600  # Время жизни кэша в секундах (1 час)


async def get_item_price_history(
    api: DMarketAPI,
    item_id: str,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Получает историю цен предмета за указанный период.

    Args:
        api: Экземпляр DMarketAPI
        item_id: ID предмета
        days: Количество дней для истории

    Returns:
        Список записей с историей цен [{"date": datetime, "price": float, "volume": int}, ...]

    """
    cache_key = f"{item_id}_{days}"

    # Проверяем кэш
    if cache_key in _price_history_cache:
        cache_data = _price_history_cache[cache_key]
        if time.time() - cache_data["last_update"] < _CACHE_TTL:
            logger.debug("Использую кэшированную историю цен для %s", item_id)
            return cache_data["data"]

    try:
        logger.info("Запрашиваю историю цен для предмета %s за %s дней", item_id, days)

        # Используем API для получения данных о продажах
        # Путь к API может отличаться в зависимости от документации DMarket
        history_data = await api._request(
            "GET",
            f"/market/items/{item_id}/history",
            params={"days": days},
        )

        if not history_data or "sales" not in history_data:
            logger.warning("Не удалось получить историю цен для %s", item_id)
            return []

        # Преобразуем данные в удобный формат
        price_history = []
        for sale in history_data.get("sales", []):
            try:
                date = datetime.fromisoformat(sale.get("date", ""))
                price = float(sale.get("price", 0)) / 100  # цены обычно в центах

                price_history.append(
                    {
                        "date": date,
                        "price": price,
                        "volume": sale.get("volume", 1),
                    },
                )
            except (ValueError, TypeError) as e:
                logger.exception(f"Ошибка при обработке записи истории: {e}")

        # Сохраняем в кэш
        _price_history_cache[cache_key] = {
            "data": price_history,
            "last_update": time.time(),
        }

        return price_history

    except Exception as e:
        logger.exception(f"Ошибка при получении истории цен: {e}")
        return []


def calculate_price_statistics(
    price_history: list[dict[str, Any]],
) -> dict[str, float]:
    """Рассчитывает статистические показатели на основе истории цен.

    Args:
        price_history: Список записей с историей цен

    Returns:
        Словарь статистических показателей

    """
    if not price_history:
        return {
            "avg_price": 0.0,
            "min_price": 0.0,
            "max_price": 0.0,
            "volatility": 0.0,
            "volume": 0,
        }

    prices = [entry["price"] for entry in price_history]
    volumes = [entry.get("volume", 1) for entry in price_history]

    # Рассчитываем статистику
    try:
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        volatility = statistics.stdev(prices) if len(prices) > 1 else 0
        total_volume = sum(volumes)

        # Рассчитываем взвешенную среднюю цену
        weighted_avg = (
            sum(p * v for p, v in zip(prices, volumes, strict=False)) / sum(volumes)
            if sum(volumes) > 0
            else 0
        )

        return {
            "avg_price": avg_price,
            "weighted_avg_price": weighted_avg,
            "min_price": min_price,
            "max_price": max_price,
            "volatility": volatility,
            "volume": total_volume,
        }
    except Exception as e:
        logger.exception(f"Ошибка при расчете статистики цен: {e}")
        return {
            "avg_price": 0.0,
            "weighted_avg_price": 0.0,
            "min_price": 0.0,
            "max_price": 0.0,
            "volatility": 0.0,
            "volume": 0,
        }


async def calculate_price_trend(
    api: DMarketAPI,
    item_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """Анализирует тренд цены предмета.

    Args:
        api: Экземпляр DMarketAPI
        item_id: ID предмета
        days: Количество дней для анализа

    Returns:
        Словарь с информацией о тренде

    """
    # Получаем историю цен
    price_history = await get_item_price_history(api, item_id, days)

    if not price_history:
        return {"trend": "unknown", "confidence": 0.0}

    # Сортируем по дате (от старых к новым)
    price_history.sort(key=operator.itemgetter("date"))

    # Разбиваем на периоды для анализа тренда
    periods = min(len(price_history), 4)  # Используем до 4 периодов
    if periods < 2:
        return {"trend": "stable", "confidence": 0.0}

    chunk_size = len(price_history) // periods
    period_prices = []

    for i in range(periods):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size if i < periods - 1 else len(price_history)
        chunk = price_history[start_idx:end_idx]
        avg_price = sum(item["price"] for item in chunk) / len(chunk)
        period_prices.append(avg_price)

    # Определяем тренд
    increases = sum(
        1
        for i in range(1, len(period_prices))
        if period_prices[i] > period_prices[i - 1]
    )
    decreases = sum(
        1
        for i in range(1, len(period_prices))
        if period_prices[i] < period_prices[i - 1]
    )

    trend_direction = "stable"
    if increases > decreases and increases >= len(period_prices) // 2:
        trend_direction = "upward"
    elif decreases > increases and decreases >= len(period_prices) // 2:
        trend_direction = "downward"

    # Рассчитываем силу тренда как процент изменения от начала к концу
    if period_prices[0] > 0:
        change_percent = (period_prices[-1] - period_prices[0]) / period_prices[0] * 100
    else:
        change_percent = 0

    # Считаем абсолютное изменение
    absolute_change = period_prices[-1] - period_prices[0]

    # Оцениваем уверенность в тренде
    confidence = min(abs(change_percent) / 20, 1.0)  # 20% изменения = 100% уверенность

    return {
        "trend": trend_direction,
        "confidence": confidence,
        "change_percent": change_percent,
        "absolute_change": absolute_change,
        "period_prices": period_prices,
    }


async def find_undervalued_items(
    api: DMarketAPI,
    game: str = "csgo",
    price_from: float = 1.0,
    price_to: float = 100.0,
    discount_threshold: float = 20.0,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Ищет недооцененные предметы на основе исторических данных.

    Args:
        api: Экземпляр DMarketAPI
        game: Код игры (csgo, dota2, etc)
        price_from: Минимальная цена в USD
        price_to: Максимальная цена в USD
        discount_threshold: Минимальный процент скидки для считания предмета недооцененным
        max_results: Максимальное количество результатов

    Returns:
        Список недооцененных предметов

    """
    logger.info(
        f"Поиск недооцененных предметов: {game}, ${price_from}-${price_to}, "
        f"скидка > {discount_threshold}%",
    )

    try:
        # Получаем предметы из маркета в указанном диапазоне цен
        items = await api.get_market_items(
            game=game,
            limit=100,  # Получаем больше предметов для анализа
            price_from=int(price_from * 100),  # Конвертируем в центы
            price_to=int(price_to * 100),
        )

        if not items or "objects" not in items:
            logger.warning("Не удалось получить предметы для анализа")
            return []

        # Анализируем каждый предмет
        undervalued_items = []

        for item in items.get("objects", []):
            item_id = item.get("itemId")
            if not item_id:
                continue

            title = item.get("title", "Unknown item")
            current_price = float(item.get("price", {}).get("amount", 0)) / 100

            # Получаем историю цен для сравнения
            price_history = await get_item_price_history(api, item_id, days=30)

            if not price_history:
                logger.debug("Нет данных об истории цен для %s", title)
                continue

            # Рассчитываем статистику
            stats = calculate_price_statistics(price_history)
            avg_price = stats["weighted_avg_price"] or stats["avg_price"]

            if avg_price <= 0:
                continue

            # Рассчитываем скидку
            discount = (avg_price - current_price) / avg_price * 100

            # Если скидка больше порогового значения, добавляем в результаты
            if discount >= discount_threshold:
                trend_info = await calculate_price_trend(api, item_id)

                undervalued_items.append(
                    {
                        "item_id": item_id,
                        "title": title,
                        "current_price": current_price,
                        "avg_price": avg_price,
                        "discount": discount,
                        "volatility": stats["volatility"],
                        "volume": stats["volume"],
                        "trend": trend_info["trend"],
                        "trend_confidence": trend_info["confidence"],
                        "game": game,
                    },
                )

                logger.info(
                    f"Найден недооцененный предмет: {title}, текущая цена: ${current_price:.2f}, "
                    f"средняя цена: ${avg_price:.2f}, скидка: {discount:.2f}%",
                )

        # Сортируем по размеру скидки (от большей к меньшей)
        undervalued_items.sort(key=operator.itemgetter("discount"), reverse=True)

        return undervalued_items[:max_results]

    except Exception as e:
        logger.exception(f"Ошибка при поиске недооцененных предметов: {e}")
        return []


async def analyze_supply_demand(
    api: DMarketAPI,
    item_id: str,
) -> dict[str, Any]:
    """Анализирует спрос и предложение для предмета.

    Args:
        api: Экземпляр DMarketAPI
        item_id: ID предмета

    Returns:
        Словарь с информацией о спросе и предложении

    """
    try:
        # Получаем предложения на покупку и продажу
        offers_data = await api._request(
            "GET",
            f"/exchange/v1/offers/{item_id}",
            params={},
        )

        if not offers_data:
            return {
                "liquidity": "unknown",
                "supply_count": 0,
                "demand_count": 0,
                "spread": 0,
            }

        # Анализируем предложения на продажу (offers)
        sell_offers = offers_data.get("offers", [])
        sell_count = len(sell_offers)
        min_sell_price = (
            float(sell_offers[0].get("price", 0)) / 100 if sell_offers else 0
        )

        # Анализируем предложения на покупку (targets)
        buy_offers = offers_data.get("targets", [])
        buy_count = len(buy_offers)
        max_buy_price = float(buy_offers[0].get("price", 0)) / 100 if buy_offers else 0

        # Рассчитываем спред между лучшими ценами покупки и продажи
        spread = (
            min_sell_price - max_buy_price
            if min_sell_price > 0 and max_buy_price > 0
            else 0
        )
        spread_percent = (spread / min_sell_price * 100) if min_sell_price > 0 else 0

        # Определяем ликвидность
        liquidity = "low"
        if buy_count > 5 and sell_count > 5 and spread_percent < 10:
            liquidity = "high"
        elif buy_count > 2 and sell_count > 2 and spread_percent < 20:
            liquidity = "medium"

        return {
            "liquidity": liquidity,
            "supply_count": sell_count,
            "demand_count": buy_count,
            "min_sell_price": min_sell_price,
            "max_buy_price": max_buy_price,
            "spread": spread,
            "spread_percent": spread_percent,
        }

    except Exception as e:
        logger.exception(f"Ошибка при анализе спроса и предложения: {e}")
        return {
            "liquidity": "unknown",
            "supply_count": 0,
            "demand_count": 0,
            "spread": 0,
        }


async def get_investment_recommendations(
    api: DMarketAPI,
    game: str = "csgo",
    budget: float = 100.0,
    risk_level: str = "medium",
) -> list[dict[str, Any]]:
    """Формирует рекомендации по инвестициям на основе анализа рынка.

    Args:
        api: Экземпляр DMarketAPI
        game: Код игры
        budget: Бюджет в USD
        risk_level: Уровень риска (low, medium, high)

    Returns:
        Список рекомендуемых предметов с обоснованием

    """
    # Настройки в зависимости от уровня риска
    if risk_level == "low":
        discount_threshold = 15.0
        min_volume = 5
        price_range = (5.0, min(50.0, budget))
        min_liquidity = "medium"
    elif risk_level == "high":
        discount_threshold = 10.0
        min_volume = 1
        price_range = (1.0, budget)
        min_liquidity = "low"
    else:  # medium
        discount_threshold = 12.0
        min_volume = 3
        price_range = (3.0, min(100.0, budget))
        min_liquidity = "low"

    # Ищем недооцененные предметы
    undervalued_items = await find_undervalued_items(
        api,
        game=game,
        price_from=price_range[0],
        price_to=price_range[1],
        discount_threshold=discount_threshold,
        max_results=20,
    )

    # Оцениваем ликвидность каждого предмета
    recommendations = []

    for item in undervalued_items:
        # Анализируем спрос и предложение
        supply_demand = await analyze_supply_demand(api, item["item_id"])

        # Объединяем данные
        item_data = {**item, **supply_demand}

        # Если ликвидность соответствует требуемой и объем достаточный
        if supply_demand["liquidity"] >= min_liquidity and item["volume"] >= min_volume:
            # Рассчитываем оценку инвестиционной привлекательности
            score = item["discount"] * 0.5

            if supply_demand["liquidity"] == "high":
                score += 20
            elif supply_demand["liquidity"] == "medium":
                score += 10

            if item["trend"] == "upward":
                score += 15 * item["trend_confidence"]
            elif item["trend"] == "downward":
                score -= 10 * item["trend_confidence"]

            # Добавляем рекомендацию
            recommendations.append(
                {
                    **item_data,
                    "investment_score": score,
                    "reason": get_investment_reason(item_data),
                },
            )

    # Сортируем по инвестиционной оценке
    recommendations.sort(key=operator.itemgetter("investment_score"), reverse=True)

    return recommendations[:10]  # Возвращаем топ-10 рекомендаций


def get_investment_reason(item_data: dict[str, Any]) -> str:
    """Формирует текстовое объяснение инвестиционной рекомендации.

    Args:
        item_data: Данные о предмете

    Returns:
        Строка с обоснованием рекомендации

    """
    reasons = []

    # Оцениваем скидку
    if item_data["discount"] > 25:
        reasons.append(f"Значительная скидка ({item_data['discount']:.1f}%)")
    elif item_data["discount"] > 15:
        reasons.append(f"Хорошая скидка ({item_data['discount']:.1f}%)")
    else:
        reasons.append(f"Скидка {item_data['discount']:.1f}%")

    # Оцениваем ликвидность
    if item_data["liquidity"] == "high":
        reasons.append("Высокая ликвидность")
    elif item_data["liquidity"] == "medium":
        reasons.append("Средняя ликвидность")
    else:
        reasons.append("Низкая ликвидность")

    # Оцениваем тренд
    if item_data["trend"] == "upward" and item_data["trend_confidence"] > 0.5:
        reasons.append("Восходящий тренд цены")
    elif item_data["trend"] == "downward" and item_data["trend_confidence"] > 0.5:
        reasons.append("Нисходящий тренд цены (риск)")

    # Оцениваем спрос
    if item_data["demand_count"] > 10:
        reasons.append(f"Высокий спрос ({item_data['demand_count']} заявок)")
    elif item_data["demand_count"] > 5:
        reasons.append(f"Умеренный спрос ({item_data['demand_count']} заявок)")

    return ". ".join(reasons)


async def get_ml_discount_threshold(
    game: str = "csgo",
) -> tuple[float, str]:
    """Get ML-predicted optimal discount threshold.

    Uses the trained DiscountThresholdPredictor model to determine
    the optimal discount threshold based on current market conditions.

    Args:
        game: Game code (csgo, dota2, tf2, rust)

    Returns:
        Tuple of (threshold_percent, reasoning)

    Example:
        >>> threshold, reason = await get_ml_discount_threshold("csgo")
        >>> print(f"Optimal threshold: {threshold}% - {reason}")
    """
    try:
        from src.ml.discount_threshold_predictor import get_discount_threshold_predictor

        predictor = get_discount_threshold_predictor()
        prediction = predictor.predict(game=game)

        logger.info(
            f"ML-predicted discount threshold for {game}: "
            f"{prediction.optimal_threshold:.1f}% (confidence: {prediction.confidence:.0%})"
        )

        return prediction.optimal_threshold, prediction.reasoning

    except ImportError:
        logger.warning("ML predictor not available, using default threshold")
        default_thresholds = {
            "csgo": 15.0,
            "dota2": 10.0,
            "tf2": 12.0,
            "rust": 14.0,
        }
        threshold = default_thresholds.get(game.lower(), 15.0)
        return threshold, "Using default threshold (ML model not available)"


async def find_undervalued_items_with_ml_threshold(
    api: DMarketAPI,
    game: str = "csgo",
    price_from: float = 1.0,
    price_to: float = 100.0,
    max_results: int = 10,
    use_ml_threshold: bool = True,
) -> dict[str, Any]:
    """Find undervalued items using ML-predicted discount threshold.

    This is an enhanced version of find_undervalued_items that uses
    machine learning to determine the optimal discount threshold
    based on current market conditions.

    Args:
        api: DMarketAPI instance
        game: Game code (csgo, dota2, etc)
        price_from: Minimum price in USD
        price_to: Maximum price in USD
        max_results: Maximum number of results
        use_ml_threshold: Whether to use ML-predicted threshold

    Returns:
        Dictionary containing:
        - items: List of undervalued items
        - threshold_used: The discount threshold that was used
        - threshold_source: "ml" or "default"
        - reasoning: Explanation of threshold selection
        - confidence: Confidence in the threshold (0-1)

    Example:
        >>> result = await find_undervalued_items_with_ml_threshold(api, "csgo")
        >>> print(f"Found {len(result['items'])} items with {result['threshold_used']}% threshold")
    """
    # Get ML-predicted threshold
    if use_ml_threshold:
        try:
            from src.ml.discount_threshold_predictor import (
                get_discount_threshold_predictor,
            )

            predictor = get_discount_threshold_predictor()
            prediction = predictor.predict(game=game)

            discount_threshold = prediction.optimal_threshold
            threshold_source = "ml"
            reasoning = prediction.reasoning
            confidence = prediction.confidence

            logger.info(
                f"Using ML threshold for {game}: {discount_threshold:.1f}% "
                f"(confidence: {confidence:.0%})"
            )

        except Exception as e:
            logger.warning(f"ML threshold prediction failed: {e}, using default")
            discount_threshold = 15.0
            threshold_source = "default"
            reasoning = f"ML prediction failed: {e}"
            confidence = 0.3
    else:
        # Use game-specific defaults
        default_thresholds = {
            "csgo": 15.0,
            "dota2": 10.0,
            "tf2": 12.0,
            "rust": 14.0,
        }
        discount_threshold = default_thresholds.get(game.lower(), 15.0)
        threshold_source = "default"
        reasoning = "Using predefined default threshold"
        confidence = 0.5

    # Find undervalued items using the determined threshold
    items = await find_undervalued_items(
        api=api,
        game=game,
        price_from=price_from,
        price_to=price_to,
        discount_threshold=discount_threshold,
        max_results=max_results,
    )

    return {
        "items": items,
        "threshold_used": discount_threshold,
        "threshold_source": threshold_source,
        "reasoning": reasoning,
        "confidence": confidence,
        "game": game,
        "price_range": (price_from, price_to),
    }


async def train_threshold_model_from_api(
    api: DMarketAPI,
    game: str = "csgo",
) -> dict[str, Any]:
    """Train the ML discount threshold model using real API prices.

    Collects real prices from DMarket API and uses them to train
    the discount threshold prediction model.

    Args:
        api: DMarketAPI instance
        game: Game to train on

    Returns:
        Dictionary with training statistics:
        - success: Whether training was successful
        - examples_collected: Number of training examples
        - message: Status message

    Example:
        >>> result = await train_threshold_model_from_api(api, "csgo")
        >>> print(f"Training: {result['message']}")
    """
    try:
        from src.ml.discount_threshold_predictor import get_discount_threshold_predictor
        from src.ml.real_price_collector import GameType, RealPriceCollector

        predictor = get_discount_threshold_predictor()

        # Create collector with the API
        collector = RealPriceCollector(dmarket_api=api)

        # Convert game string to GameType enum
        game_type = GameType(game.lower())

        # Collect historical prices for comparison
        # In a real scenario, we'd have historical data from previous API calls
        historical_prices: dict[str, float] = {}

        # Get current market items to extract historical data
        items_response = await api.get_market_items(game=game, limit=100)
        if items_response and "objects" in items_response:
            for item in items_response.get("objects", []):
                title = item.get("title", "")
                suggested = item.get("suggestedPrice", {})
                if suggested:
                    suggested_usd = float(suggested.get("USD", 0)) / 100
                    if suggested_usd > 0:
                        historical_prices[title] = suggested_usd

        # Train from collector with real prices
        examples_count = await predictor.train_from_collector(
            collector=collector,
            game=game_type,
            historical_prices=historical_prices,
        )

        logger.info(f"Model trained on {examples_count} examples from real API prices")

        return {
            "success": True,
            "examples_collected": examples_count,
            "message": f"Successfully trained on {examples_count} real price examples from {game.upper()}",
            "game": game,
            "is_model_trained": predictor._is_trained,
        }

    except ImportError as e:
        logger.warning(f"Required modules not available: {e}")
        return {
            "success": False,
            "examples_collected": 0,
            "message": f"Training failed: required modules not available ({e})",
            "game": game,
        }
    except Exception as e:
        logger.exception(f"Training failed: {e}")
        return {
            "success": False,
            "examples_collected": 0,
            "message": f"Training failed: {e}",
            "game": game,
        }


async def add_trade_outcome_for_training(
    item_name: str,
    game: str,
    buy_price: float,
    sell_price: float,
    historical_avg_price: float,
    source: str = "dmarket",
) -> bool:
    """Add a real trade outcome to train the ML model.

    Call this function after completing a trade to improve
    the ML model's accuracy over time.

    Args:
        item_name: Name of the traded item
        game: Game code
        buy_price: Price item was bought at
        sell_price: Price item was sold at
        historical_avg_price: Historical average price
        source: Price source (dmarket, waxpeer, steam)

    Returns:
        True if example was added successfully

    Example:
        >>> success = await add_trade_outcome_for_training(
        ...     item_name="AK-47 | Redline (FT)",
        ...     game="csgo",
        ...     buy_price=10.50,
        ...     sell_price=12.00,
        ...     historical_avg_price=11.00,
        ... )
    """
    try:
        from src.ml.discount_threshold_predictor import get_discount_threshold_predictor

        predictor = get_discount_threshold_predictor()

        # Calculate trade metrics
        if historical_avg_price > 0:
            actual_discount = (
                (historical_avg_price - buy_price) / historical_avg_price
            ) * 100
        else:
            actual_discount = 0.0

        was_profitable = sell_price > buy_price
        profit_percent = (
            ((sell_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
        )

        # Add training example
        predictor.add_training_example(
            item_name=item_name,
            game=game,
            current_price=buy_price,
            historical_avg_price=historical_avg_price,
            actual_discount=actual_discount,
            was_profitable=was_profitable,
            profit_percent=profit_percent,
            source=source,
        )

        logger.info(
            f"Trade outcome added for training: {item_name}, "
            f"discount={actual_discount:.1f}%, profitable={was_profitable}"
        )

        return True

    except Exception as e:
        logger.exception(f"Failed to add trade outcome: {e}")
        return False
