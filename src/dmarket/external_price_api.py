"""External Price Comparison API для кросс-платформенного арбитража.

Модуль для сравнения цен на DMarket с ценами на других площадках:
- Steam Community Market
- CSGOFloat Market
- Buff163 (опционально)

Это критически важно для настоящего арбитража, так как позволяет находить
предметы, которые дешевле на DMarket, чем на других платформах.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ExternalPriceAPI:
    """API для получения цен с внешних площадок."""

    def __init__(self) -> None:
        """Инициализация клиента внешних цен."""
        self.session: httpx.AsyncClient | None = None
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 минут

    async def _ensure_session(self) -> None:
        """Создать HTTP сессию если её нет."""
        if self.session is None:
            self.session = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(max_keepalive_connections=10),
                http2=True,
            )

    async def close(self) -> None:
        """Закрыть HTTP сессию."""
        if self.session:
            await self.session.aclose()
            self.session = None

    async def get_steam_price(self, item_name: str, app_id: int = 730) -> float | None:
        """Получить цену предмета на Steam Community Market.

        Args:
            item_name: Название предмета (например, "AK-47 | Redline (Field-Tested)")
            app_id: ID игры Steam (730 = CS:GO/CS2, 570 = Dota 2)

        Returns:
            Цена в USD или None если предмет не найден
        """
        cache_key = f"steam_{app_id}_{item_name}"

        # Проверяем кэш
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["timestamp"] < self._cache_ttl:
                return cached["price"]

        await self._ensure_session()

        try:
            # Steam API endpoint для получения цены
            url = "https://steamcommunity.com/market/priceoverview/"
            params = {
                "appid": app_id,
                "currency": 1,  # USD
                "market_hash_name": item_name,
            }

            response = await self.session.get(url, params=params)

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    # Steam возвращает строку вида "$12.34"
                    lowest_price_str = data.get("lowest_price", "")
                    if lowest_price_str:
                        # Убираем символ $ и конвертируем в float
                        price = float(lowest_price_str.replace("$", "").replace(",", ""))

                        # Кэшируем результат
                        self._cache[cache_key] = {
                            "price": price,
                            "timestamp": time.time(),
                        }

                        return price

            return None

        except Exception as e:
            logger.warning(f"Ошибка при получении цены Steam для {item_name}: {e}")
            return None

    async def get_csgofloat_price(self, item_name: str) -> float | None:
        """Получить цену предмета на CSGOFloat Market.

        CSGOFloat - это альтернативная площадка для CS:GO скинов с открытым API.

        Args:
            item_name: Название предмета

        Returns:
            Цена в USD или None если предмет не найден
        """
        cache_key = f"csgofloat_{item_name}"

        # Проверяем кэш
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["timestamp"] < self._cache_ttl:
                return cached["price"]

        await self._ensure_session()

        try:
            # CSGOFloat Market API
            url = "https://csgofloat.com/api/v1/listings"
            params = {
                "market_hash_name": item_name,
                "sort_by": "price",
                "order": "asc",
                "limit": 1,
            }

            response = await self.session.get(url, params=params)

            if response.status_code == 200:
                data = response.json()

                if data and len(data) > 0:
                    # Цена в центах, делим на 100
                    price = float(data[0]["price"]) / 100

                    # Кэшируем результат
                    self._cache[cache_key] = {
                        "price": price,
                        "timestamp": time.time(),
                    }

                    return price

            return None

        except Exception as e:
            logger.warning(f"Ошибка при получении цены CSGOFloat для {item_name}: {e}")
            return None

    async def calculate_arbitrage_margin(
        self,
        item_name: str,
        dmarket_price: float,
        game: str = "csgo",
    ) -> dict[str, Any]:
        """Рассчитать маржу арбитража между DMarket и другими платформами.

        Args:
            item_name: Название предмета
            dmarket_price: Цена на DMarket в USD
            game: Игра (csgo, dota2)

        Returns:
            Словарь с информацией о возможном арбитраже:
            {
                "has_opportunity": bool,
                "best_platform": str,
                "best_price": float,
                "profit_margin": float,  # В процентах
                "net_profit": float,     # С учетом комиссий
            }
        """
        result: dict[str, Any] = {
            "has_opportunity": False,
            "best_platform": None,
            "best_price": None,
            "profit_margin": 0.0,
            "net_profit": 0.0,
        }

        # Определяем app_id для Steam
        app_id = 730 if game == "csgo" else 570  # Dota 2

        # Получаем цены с разных площадок параллельно
        tasks = [
            self.get_steam_price(item_name, app_id),
            self.get_csgofloat_price(item_name) if game == "csgo" else asyncio.sleep(0),
        ]

        prices = await asyncio.gather(*tasks, return_exceptions=True)

        steam_price = prices[0] if not isinstance(prices[0], Exception) else None
        csgofloat_price = (
            prices[1] if not isinstance(prices[1], Exception) and game == "csgo" else None
        )

        # Находим лучшую цену для продажи
        best_price = None
        best_platform = None

        if steam_price and steam_price > dmarket_price:
            best_price = steam_price
            best_platform = "Steam"

        if csgofloat_price and csgofloat_price > (best_price or dmarket_price):
            best_price = csgofloat_price
            best_platform = "CSGOFloat"

        if best_price and best_platform:
            # Рассчитываем профит с учетом комиссий
            # DMarket: 7% комиссия при продаже
            # Steam: ~13% комиссия (2% Steam + ~11% fee)

            dmarket_cost = dmarket_price * 1.02  # +2% на покупку

            if best_platform == "Steam":
                sell_revenue = best_price * 0.87  # -13% комиссия Steam
            else:  # CSGOFloat
                sell_revenue = best_price * 0.95  # -5% комиссия CSGOFloat

            net_profit = sell_revenue - dmarket_cost
            profit_margin = (net_profit / dmarket_cost) * 100

            result.update({
                "has_opportunity": net_profit > 0,
                "best_platform": best_platform,
                "best_price": best_price,
                "profit_margin": round(profit_margin, 2),
                "net_profit": round(net_profit, 2),
            })

        return result

    async def batch_compare_prices(
        self,
        items: list[dict[str, Any]],
        game: str = "csgo",
    ) -> list[dict[str, Any]]:
        """Пакетное сравнение цен для списка предметов.

        Args:
            items: Список предметов с DMarket (должны содержать 'title' и 'price')
            game: Игра

        Returns:
            Список предметов с добавленной информацией об арбитраже
        """
        results = []

        # Создаем задачи для параллельной обработки
        tasks = []
        for item in items:
            item_name = item.get("title", "")
            # Цена может быть в центах или долларах - проверяем
            price = item.get("price", 0)
            if isinstance(price, dict):
                price = float(price.get("USD", 0)) / 100
            elif price > 1000:  # Если больше 1000, скорее всего в центах
                price /= 100

            tasks.append(self.calculate_arbitrage_margin(item_name, price, game))

        # Выполняем все запросы параллельно
        arbitrage_data = await asyncio.gather(*tasks, return_exceptions=True)

        # Объединяем результаты с исходными предметами
        for item, arb_data in zip(items, arbitrage_data, strict=False):
            if isinstance(arb_data, Exception):
                logger.warning(f"Ошибка при проверке арбитража для {item.get('title')}: {arb_data}")
                results.append(item)
            else:
                # Добавляем информацию об арбитраже к предмету
                enriched_item = {**item, "external_arbitrage": arb_data}
                results.append(enriched_item)

        return results


# Singleton instance
_external_price_api: ExternalPriceAPI | None = None


def get_external_price_api() -> ExternalPriceAPI:
    """Получить singleton экземпляр ExternalPriceAPI."""
    global _external_price_api
    if _external_price_api is None:
        _external_price_api = ExternalPriceAPI()
    return _external_price_api
