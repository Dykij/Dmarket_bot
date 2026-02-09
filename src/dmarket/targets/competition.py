"""Анализ конкуренции для таргетов (buy orders).

Содержит функции для оценки конкуренции и фильтрации предметов.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from .validators import GAME_IDS

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI

logger = logging.getLogger(__name__)


async def analyze_target_competition(
    api: "IDMarketAPI",
    game: str,
    title: str,
) -> dict[str, Any]:
    """Анализ конкуренции для создания таргета (API v1.1.0).

    Использует новый эндпоинт targets-by-title для анализа
    существующих buy orders и определения оптимальной цены таргета.

    Args:
        api: DMarket API клиент
        game: Код игры
        title: Название предмета

    Returns:
        Словарь с анализом конкуренции

    """
    logger.info(f"Анализ конкуренции для '{title}' в {game}")

    try:
        # Получаем существующие таргеты для предмета
        game_id = GAME_IDS.get(game.lower(), game)
        existing_targets = await api.get_targets_by_title(game=game_id, title=title)

        # Получаем агрегированные данные о ценах
        aggregated = await api.get_aggregated_prices_bulk(
            game=game,
            titles=[title],
            limit=1,
        )

        analysis: dict[str, Any] = {
            "title": title,
            "game": game,
            "total_orders": len(existing_targets),
            "best_price": 0.0,
            "average_price": 0.0,
            "market_offer_price": 0.0,
            "recommended_price": 0.0,
            "competition_level": "low",
            "strategy": "",
        }

        best_price = 0.0

        # Анализируем существующие таргеты
        if existing_targets:
            prices = [float(t["price"]) for t in existing_targets]
            best_price = max(prices)
            analysis["best_price"] = best_price
            analysis["average_price"] = sum(prices) / len(prices)

            # Определяем уровень конкуренции
            if len(existing_targets) < 5:
                analysis["competition_level"] = "low"
            elif len(existing_targets) < 15:
                analysis["competition_level"] = "medium"
            else:
                analysis["competition_level"] = "high"

        # Получаем рыночную цену
        if aggregated and "aggregatedPrices" in aggregated:
            price_data = aggregated["aggregatedPrices"][0]
            market_offer_price = float(price_data["offerBestPrice"]) / 100
            analysis["market_offer_price"] = market_offer_price

            # Рассчитываем рекомендуемую цену
            if best_price > 0:
                # Если есть конкуренты, ставим чуть выше лучшей цены
                analysis["recommended_price"] = round(
                    min(
                        best_price + 0.10,
                        market_offer_price * 0.95,
                    ),
                    2,
                )
                analysis["strategy"] = (
                    f"Рекомендуется цена выше лучшего таргета (${best_price:.2f}) но ниже рынка"
                )
            else:
                # Нет конкурентов, ставим на 5-7% ниже рынка
                analysis["recommended_price"] = round(market_offer_price * 0.93, 2)
                analysis["strategy"] = "Конкурентов нет, рекомендуется 7% снижение от рыночной цены"

        logger.info(
            f"Анализ завершен: конкурентов {analysis['total_orders']}, "
            f"рекомендуемая цена ${analysis['recommended_price']:.2f}"
        )

        return analysis

    except Exception as e:
        logger.exception(f"Ошибка при анализе конкуренции для '{title}': {e!s}")
        return {
            "title": title,
            "error": str(e),
        }


async def assess_competition(
    api: "IDMarketAPI",
    game: str,
    title: str,
    max_competition: int = 3,
    price_threshold: float | None = None,
) -> dict[str, Any]:
    """Оценить уровень конкуренции для создания buy order.

    Args:
        api: DMarket API клиент
        game: Код игры (csgo, dota2, tf2, rust)
        title: Название предмета
        max_competition: Максимально допустимое количество конкурирующих ордеров
        price_threshold: Порог цены для фильтрации (в USD)

    Returns:
        Результат оценки конкуренции

    """
    logger.info(
        f"Оценка конкуренции для '{title}' (игра: {game}, макс. конкуренция: {max_competition})"
    )

    game_id = GAME_IDS.get(game.lower(), game)

    try:
        # Получаем данные о конкуренции через API
        competition = await api.get_buy_orders_competition(
            game_id=game_id,
            title=title,
            price_threshold=price_threshold,
        )

        # Извлекаем ключевые метрики
        total_orders = competition.get("total_orders", 0)
        total_amount = competition.get("total_amount", 0)
        competition_level = competition.get("competition_level", "unknown")
        best_price = competition.get("best_price", 0.0)
        average_price = competition.get("average_price", 0.0)

        # Определяем, стоит ли продолжать
        should_proceed = total_orders <= max_competition

        # Формируем рекомендацию
        if total_orders == 0:
            recommendation = "Нет конкурентов - отличная возможность для таргета"
            suggested_price = None
        elif should_proceed:
            recommendation = (
                f"Низкая конкуренция ({total_orders} ордеров) - рекомендуется создать таргет"
            )
            suggested_price = round(best_price + 0.05, 2) if best_price > 0 else None
        else:
            recommendation = (
                f"Высокая конкуренция ({total_orders} ордеров, "
                f"{total_amount} заявок) - рекомендуется пропустить или "
                f"увеличить цену выше ${best_price:.2f}"
            )
            suggested_price = round(best_price * 1.03, 2) if best_price > 0 else None

        result = {
            "title": title,
            "game": game,
            "should_proceed": should_proceed,
            "competition_level": competition_level,
            "total_orders": total_orders,
            "total_amount": total_amount,
            "best_price": best_price,
            "average_price": average_price,
            "recommendation": recommendation,
            "suggested_price": suggested_price,
            "max_competition_threshold": max_competition,
            "raw_data": competition,
        }

        logger.info(
            f"Результат оценки для '{title}': "
            f"proceed={should_proceed}, level={competition_level}, "
            f"orders={total_orders}"
        )

        return result

    except Exception as e:
        logger.exception(f"Ошибка при оценке конкуренции для '{title}': {e}")
        return {
            "title": title,
            "game": game,
            "should_proceed": False,
            "competition_level": "unknown",
            "total_orders": 0,
            "total_amount": 0,
            "best_price": 0.0,
            "average_price": 0.0,
            "recommendation": f"Ошибка при оценке: {e}. Рекомендуется повторить позже.",
            "suggested_price": None,
            "error": str(e),
        }


async def filter_low_competition_items(
    api: "IDMarketAPI",
    game: str,
    items: list[dict[str, Any]],
    max_competition: int = 3,
    request_delay: float = 0.3,
) -> list[dict[str, Any]]:
    """Фильтрует список предметов, оставляя только с низкой конкуренцией.

    Args:
        api: DMarket API клиент
        game: Код игры
        items: Список предметов для проверки
        max_competition: Максимально допустимое количество ордеров
        request_delay: Задержка между запросами в секундах

    Returns:
        Список предметов с низкой конкуренцией

    """
    logger.info(f"Фильтрация {len(items)} предметов по конкуренции (макс: {max_competition})")

    filtered_items = []

    for item in items:
        title = item.get("title")
        if not title:
            logger.warning(f"Пропущен предмет без названия: {item}")
            continue

        # Оцениваем конкуренцию для каждого предмета
        competition = await assess_competition(
            api=api,
            game=game,
            title=title,
            max_competition=max_competition,
        )

        if competition.get("should_proceed", False):
            item_with_competition = {**item, "competition": competition}
            filtered_items.append(item_with_competition)
            logger.debug(
                f"✓ Предмет '{title}' прошел фильтр: {competition['total_orders']} ордеров"
            )
        else:
            logger.debug(
                f"✗ Предмет '{title}' отфильтрован: "
                f"{competition['total_orders']} ордеров (> {max_competition})"
            )

        # Задержка для rate limiting
        if request_delay > 0:
            await asyncio.sleep(request_delay)

    logger.info(
        f"Фильтрация завершена: {len(filtered_items)}/{len(items)} предметов с низкой конкуренцией"
    )

    return filtered_items


__all__ = [
    "analyze_target_competition",
    "assess_competition",
    "filter_low_competition_items",
]
