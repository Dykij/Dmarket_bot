"""ArbitrageTrader class for automated trading operations.

This module contains the ArbitrageTrader class which handles:
- Balance checking
- Trading limits management
- Error handling and recovery
- Profitable item discovery
- Trade execution (buy/sell)
- Auto-trading loop
- Transaction history

Example:
    >>> from src.dmarket.arbitrage.trader import ArbitrageTrader
    >>> # Option 1: Pass api_client directly
    >>> trader = ArbitrageTrader(api_client)
    >>> # Option 2: Pass credentials (for backward compatibility)
    >>> trader = ArbitrageTrader(public_key="...", secret_key="...")
    >>> await trader.start_auto_trading(game="csgo", min_profit_percentage=5.0)
"""

from __future__ import annotations

import asyncio
import logging
import operator
import time
from typing import TYPE_CHECKING, Any

from src.dmarket.arbitrage.calculations import calculate_commission
from src.dmarket.arbitrage.constants import (
    DEFAULT_DAILY_LIMIT,
    DEFAULT_MAX_TRADE_VALUE,
    DEFAULT_MIN_BALANCE,
    DEFAULT_MIN_PROFIT_PERCENTAGE,
    GAMES,
)

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)

__all__ = [
    "ArbitrageTrader",
]


class ArbitrageTrader:
    """Класс для автоматической арбитражной торговли на DMarket.

    Предоставляет полный функционал для автоматизированной торговли:
    - Проверка и управление балансом
    - Управление лимитами торговли
    - Обработка ошибок с автоматическим восстановлением
    - Поиск выгодных предметов для арбитража
    - Выполнение сделок (покупка/продажа)
    - Автоматический торговый цикл

    Attributes:
        api: Клиент DMarket API
        public_key: Публичный ключ API (для обратной совместимости)
        secret_key: Секретный ключ API (для обратной совместимости)
        min_profit_percentage: Минимальный процент прибыли для сделки
        max_trade_value: Максимальная стоимость одной сделки
        daily_limit: Дневной лимит торговли
        active: Флаг активности автоторговли
        transaction_history: История совершенных сделок

    Example:
        >>> # Using api_client (recommended)
        >>> trader = ArbitrageTrader(api_client)
        >>> # Using credentials (backward compatible)
        >>> trader = ArbitrageTrader(public_key="...", secret_key="...")
        >>> trader.set_trading_limits(max_trade_value=50.0, daily_limit=300.0)
        >>> success, message = await trader.start_auto_trading("csgo")
        >>> print(f"Status: {trader.get_status()}")
    """

    def __init__(
        self,
        api_client: DMarketAPI | None = None,
        min_profit_percentage: float = DEFAULT_MIN_PROFIT_PERCENTAGE,
        max_trade_value: float = DEFAULT_MAX_TRADE_VALUE,
        daily_limit: float = DEFAULT_DAILY_LIMIT,
        *,
        public_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        """Инициализация ArbitrageTrader.

        Supports two ways of initialization:
        1. With api_client (recommended): ArbitrageTrader(api_client)
        2. With credentials (backward compatible): ArbitrageTrader(public_key=..., secret_key=...)

        Args:
            api_client: Клиент DMarket API для выполнения операций
            min_profit_percentage: Минимальный процент прибыли (по умолчанию 5%)
            max_trade_value: Максимальная стоимость сделки (по умолчанию $100)
            daily_limit: Дневной лимит (по умолчанию $500)
            public_key: Публичный ключ API (для обратной совместимости)
            secret_key: Секретный ключ API (для обратной совместимости)
        """
        # Store credentials for backward compatibility
        self.public_key = public_key
        self.secret_key = secret_key

        # Initialize API client
        if api_client is not None:
            self.api = api_client
        elif public_key is not None and secret_key is not None:
            # Backward compatibility: create API client from credentials
            from src.dmarket.dmarket_api import DMarketAPI

            self.api = DMarketAPI(public_key=public_key, secret_key=secret_key)
        else:
            msg = "ArbitrageTrader requires either api_client or (public_key and secret_key)"
            raise ValueError(msg)

        # Параметры торговли
        self.min_profit_percentage = min_profit_percentage
        self.max_trade_value = max_trade_value
        self.daily_limit = daily_limit

        # Управление рисками
        self.daily_traded: float = 0.0
        self.daily_reset_time = time.time()
        self.error_count: int = 0
        self.pause_until: float = 0.0

        # Состояние торговли
        self.active: bool = False
        self.current_game: str = "csgo"
        self.transaction_history: list[dict[str, Any]] = []

    async def check_balance(self) -> tuple[bool, float]:
        """Проверить баланс аккаунта.

        Returns:
            Кортеж (достаточно_средств, баланс_в_долларах)

        Example:
            >>> has_funds, balance = await trader.check_balance()
            >>> if has_funds:
            ...     print(f"Balance: ${balance:.2f}")
        """
        try:
            async with self.api:
                balance_data = await self.api.get_balance()

            # API возвращает balance в долларах напрямую
            balance_usd = float(balance_data.get("balance", 0))
            has_funds = balance_usd >= DEFAULT_MIN_BALANCE

            return has_funds, balance_usd

        except Exception as e:
            logger.exception(f"Ошибка при проверке баланса: {e}")
            return False, 0.0

    def _reset_daily_limits(self) -> None:
        """Сбросить дневные лимиты если прошло 24 часа."""
        current_time = time.time()
        hours_passed = (current_time - self.daily_reset_time) / 3600

        if hours_passed >= 24:
            self.daily_traded = 0.0
            self.daily_reset_time = current_time
            logger.info("Дневные лимиты сброшены")

    async def _check_trading_limits(self, trade_value: float) -> bool:
        """Проверить соответствие торговым лимитам.

        Args:
            trade_value: Стоимость планируемой сделки

        Returns:
            True если сделка разрешена, False если превышены лимиты
        """
        self._reset_daily_limits()

        # Проверка максимальной стоимости сделки
        if trade_value > self.max_trade_value:
            logger.warning(
                f"Стоимость сделки ${trade_value:.2f} превышает "
                f"максимум ${self.max_trade_value:.2f}",
            )
            return False

        # Проверка дневного лимита
        if self.daily_traded + trade_value > self.daily_limit:
            logger.warning(
                f"Превышен дневной лимит: ${self.daily_traded:.2f} + "
                f"${trade_value:.2f} > ${self.daily_limit:.2f}",
            )
            return False

        return True

    async def _handle_trading_error(self) -> None:
        """Обработать ошибку торговли и установить паузу при необходимости."""
        self.error_count += 1
        logger.warning(f"Ошибка торговли #{self.error_count}")

        if self.error_count >= 10:
            # После 10 ошибок - пауза на час и сброс счетчика
            self.pause_until = time.time() + 3600
            self.error_count = 0
            logger.error("Много ошибок! Пауза на 1 час")
        elif self.error_count >= 3:
            # После 3 ошибок - пауза на 15 минут
            self.pause_until = time.time() + 900
            logger.warning("Несколько ошибок подряд. Пауза на 15 минут")

    async def _can_trade_now(self) -> bool:
        """Проверить, возможна ли торговля в данный момент.

        Returns:
            True если торговля разрешена, False если на паузе
        """
        if time.time() < self.pause_until:
            remaining = int((self.pause_until - time.time()) / 60)
            logger.debug(f"Торговля на паузе. Осталось: {remaining} мин.")
            return False

        # Если пауза истекла - сбросить pause_until и error_count
        if self.pause_until > 0:
            self.pause_until = 0
            self.error_count = 0

        return True

    async def find_profitable_items(
        self,
        game: str = "csgo",
        min_profit_percentage: float | None = None,
        max_items: int = 100,
        min_price: float = 1.0,
        max_price: float = 100.0,
    ) -> list[dict[str, Any]]:
        """Найти выгодные предметы для арбитража.

        Args:
            game: Код игры (csgo, dota2, tf2, rust)
            min_profit_percentage: Минимальная прибыль в процентах
            max_items: Максимальное количество предметов для анализа
            min_price: Минимальная цена предмета
            max_price: Максимальная цена предмета

        Returns:
            Список выгодных предметов с данными для арбитража
        """
        min_profit = min_profit_percentage or self.min_profit_percentage

        try:
            async with self.api:
                response = await self.api.get_market_items(
                    game=game,
                    limit=max_items,
                    price_from=min_price,
                    price_to=max_price,
                    sort="price",
                )
                market_items = response.get("objects", []) if isinstance(response, dict) else []

            if not market_items:
                return []

            logger.info(f"Анализ {len(market_items)} предметов...")

            # Группируем по названию
            grouped: dict[str, list[dict[str, Any]]] = {}
            for item in market_items:
                name = item.get("title", "")
                if name:
                    if name not in grouped:
                        grouped[name] = []
                    grouped[name].append(item)

            # Ищем арбитражные возможности
            opportunities: list[dict[str, Any]] = []

            for name, items in grouped.items():
                if len(items) < 2:
                    continue

                items.sort(key=lambda x: x.get("price", {}).get("USD", 0))

                cheapest = items[0]
                buy_price = float(cheapest.get("price", {}).get("USD", 0)) / 100

                # Получаем характеристики для расчета комиссии
                extra = cheapest.get("extra", {})
                rarity = extra.get("rarity", "")
                item_type = extra.get("category", "")
                popularity = extra.get("popularity", 0.5)

                commission = calculate_commission(rarity, item_type, popularity, game)

                # Анализируем остальные предметы
                for item in items[1:]:
                    sell_price = float(item.get("price", {}).get("USD", 0)) / 100

                    commission_amount = sell_price * commission / 100
                    net_profit = sell_price - buy_price - commission_amount
                    profit_percent = (net_profit / buy_price) * 100 if buy_price > 0 else 0

                    if profit_percent >= min_profit and net_profit > 0:
                        opportunities.append({
                            "name": name,
                            "buy_price": buy_price,
                            "sell_price": sell_price,
                            "profit": net_profit,
                            "profit_percentage": profit_percent,
                            "commission_percent": commission,
                            "buy_item_id": cheapest.get("itemId"),
                            "sell_item_id": item.get("itemId"),
                            "game": game,
                        })
                        break  # Берем только лучшую цену для продажи

            # Сортируем по прибыльности
            opportunities.sort(key=operator.itemgetter("profit_percentage"), reverse=True)
            logger.info(f"Найдено {len(opportunities)} выгодных возможностей")

            return opportunities

        except Exception as e:
            logger.exception(f"Ошибка при поиске выгодных предметов: {e}")
            return []

    async def execute_arbitrage_trade(
        self,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        """Выполнить арбитражную сделку (покупка + выставление на продажу).

        Args:
            item: Данные о предмете для арбитража

        Returns:
            Результат операции с деталями сделки
        """
        result: dict[str, Any] = {
            "success": False,
            "item_name": item.get("name", "Unknown"),
            "buy_price": item.get("buy_price", 0),
            "sell_price": item.get("sell_price", 0),
            "errors": [],
        }

        try:
            # Проверка баланса
            has_funds, balance = await self.check_balance()
            if not has_funds or balance < item["buy_price"]:
                result["errors"].append(f"Недостаточно средств: ${balance:.2f}")
                return result

            # Проверка лимитов
            if not await self._check_trading_limits(item["buy_price"]):
                result["errors"].append("Превышены лимиты торговли")
                return result

            # Покупка
            buy_result = await self.purchase_item(
                item["buy_item_id"],
                item["buy_price"],
            )

            if not buy_result.get("success"):
                result["errors"].append(
                    f"Ошибка покупки: {buy_result.get('error', 'Unknown')}",
                )
                await self._handle_trading_error()
                return result

            new_item_id = buy_result.get("new_item_id")

            # Выставление на продажу
            sell_result = await self.list_item_for_sale(
                new_item_id,
                item["sell_price"],
            )

            if not sell_result.get("success"):
                result["errors"].append(
                    f"Ошибка выставления: {sell_result.get('error', 'Unknown')}",
                )
                return result

            # Успешная сделка
            result["success"] = True
            result["profit"] = item["profit"]
            result["profit_percentage"] = item["profit_percentage"]
            result["new_item_id"] = new_item_id

            # Обновляем статистику
            self.daily_traded += item["buy_price"]

            # Записываем в историю
            self.transaction_history.append({
                "item_name": item["name"],
                "buy_price": item["buy_price"],
                "sell_price": item["sell_price"],
                "profit": item["profit"],
                "profit_percentage": item["profit_percentage"],
                "game": item["game"],
                "timestamp": time.time(),
            })

            # Сбрасываем счетчик ошибок
            self.error_count = 0

            return result

        except Exception as e:
            logger.exception(f"Ошибка при выполнении сделки: {e}")
            result["errors"].append(f"Произошла ошибка: {e}")
            await self._handle_trading_error()
            return result

    async def start_auto_trading(
        self,
        game: str = "csgo",
        min_profit_percentage: float = 5.0,
        max_concurrent_trades: int = 1,
    ) -> tuple[bool, str]:
        """Запустить автоматическую торговлю.

        Args:
            game: Код игры (csgo, dota2, tf2, rust)
            min_profit_percentage: Минимальный процент прибыли
            max_concurrent_trades: Максимальное количество одновременных сделок

        Returns:
            Кортеж (успех, сообщение)

        Example:
            >>> success, msg = await trader.start_auto_trading("csgo", 5.0)
            >>> print(msg)
        """
        if self.active:
            return False, "Автоматическая торговля уже запущена"

        has_funds, balance = await self.check_balance()
        if not has_funds:
            return False, f"Недостаточно средств для торговли: ${balance:.2f}"

        self.active = True
        self.current_game = game
        self.min_profit_percentage = min_profit_percentage

        _ = asyncio.create_task(
            self._auto_trading_loop(game, min_profit_percentage, max_concurrent_trades),
        )

        return True, (
            f"Автоторговля запущена для {GAMES.get(game, game)}, "
            f"мин. прибыль: {min_profit_percentage}%"
        )

    async def stop_auto_trading(self) -> tuple[bool, str]:
        """Остановить автоматическую торговлю.

        Returns:
            Кортеж (успех, сообщение)
        """
        if not self.active:
            return False, "Автоматическая торговля не запущена"

        self.active = False
        return True, "Автоторговля остановлена"

    async def _auto_trading_loop(
        self,
        game: str,
        min_profit_percentage: float,
        max_concurrent_trades: int,
    ) -> None:
        """Основной цикл автоматической торговли.

        Args:
            game: Код игры
            min_profit_percentage: Минимальный процент прибыли
            max_concurrent_trades: Максимум одновременных сделок
        """
        while self.active:
            try:
                # Early continue if can't trade
                if not await self._can_trade_now():
                    await asyncio.sleep(60)
                    continue

                # Early continue if insufficient funds
                has_funds, balance = await self.check_balance()
                if not has_funds:
                    logger.warning(f"Недостаточно средств: ${balance:.2f}")
                    await asyncio.sleep(300)
                    continue

                # Find profitable items
                profitable_items = await self.find_profitable_items(
                    game=game,
                    min_profit_percentage=min_profit_percentage,
                    max_items=100,
                    min_price=1.0,
                    max_price=min(balance * 0.8, self.max_trade_value),
                )

                # Early continue if no items found
                if not profitable_items:
                    logger.info("Не найдено выгодных предметов")
                    await asyncio.sleep(60)
                    continue

                # Process profitable items
                logger.info(f"Найдено {len(profitable_items)} выгодных предметов")
                items_to_trade = await self._select_items_to_trade(
                    profitable_items, balance, max_concurrent_trades
                )

                # Execute trades
                await self._execute_trades_batch(items_to_trade)

                await asyncio.sleep(60)

            except Exception as e:
                logger.exception(f"Ошибка в цикле автоторговли: {e}")
                await asyncio.sleep(30)

    async def _select_items_to_trade(
        self,
        profitable_items: list[dict[str, Any]],
        balance: float,
        max_concurrent: int,
    ) -> list[dict[str, Any]]:
        """Select items to trade based on limits and balance.

        Phase 2 refactoring: Extract selection logic, reduce nesting.

        Args:
            profitable_items: List of profitable items
            balance: Available balance
            max_concurrent: Maximum concurrent trades

        Returns:
            List of items to trade

        """
        items_to_trade: list[dict[str, Any]] = []
        remaining_balance = balance

        for item in profitable_items:
            # Early continue if limits exceeded
            if not await self._check_trading_limits(item["buy_price"]):
                continue

            # Early continue if insufficient balance
            if item["buy_price"] > remaining_balance:
                continue

            # Add item
            items_to_trade.append(item)
            remaining_balance -= item["buy_price"]

            # Stop if reached max concurrent trades
            if len(items_to_trade) >= max_concurrent:
                break

        return items_to_trade

    async def _execute_trades_batch(self, items: list[dict[str, Any]]) -> None:
        """Execute batch of trades with delay.

        Args:
            items: Items to trade

        """
        for item in items:
            await self.execute_arbitrage_trade(item)
            await asyncio.sleep(5)

    def get_transaction_history(self) -> list[dict[str, Any]]:
        """Получить историю транзакций.

        Returns:
            Список транзакций
        """
        return self.transaction_history

    def set_trading_limits(
        self,
        max_trade_value: float | None = None,
        daily_limit: float | None = None,
    ) -> None:
        """Установить лимиты торговли.

        Args:
            max_trade_value: Максимальная стоимость одной сделки
            daily_limit: Дневной лимит торговли
        """
        if max_trade_value is not None:
            self.max_trade_value = max_trade_value

        if daily_limit is not None:
            self.daily_limit = daily_limit

        logger.info(
            f"Лимиты установлены: макс. сделка ${self.max_trade_value:.2f}, "
            f"дневной лимит ${self.daily_limit:.2f}",
        )

    def get_status(self) -> dict[str, Any]:
        """Получить текущий статус торговли.

        Returns:
            Словарь с информацией о статусе
        """
        total_profit = (
            sum(t["profit"] for t in self.transaction_history) if self.transaction_history else 0.0
        )

        on_pause = time.time() < self.pause_until
        pause_minutes = int((self.pause_until - time.time()) / 60) if on_pause else 0

        return {
            "active": self.active,
            "current_game": self.current_game,
            "game_name": GAMES.get(self.current_game, self.current_game),
            "min_profit_percentage": self.min_profit_percentage,
            "transactions_count": len(self.transaction_history),
            "total_profit": total_profit,
            "daily_traded": self.daily_traded,
            "daily_limit": self.daily_limit,
            "max_trade_value": self.max_trade_value,
            "error_count": self.error_count,
            "on_pause": on_pause,
            "pause_minutes": pause_minutes,
        }

    async def get_current_item_data(
        self,
        item_id: str,
        game: str = "csgo",
    ) -> dict[str, Any] | None:
        """Получить текущую информацию о предмете.

        Args:
            item_id: Идентификатор предмета
            game: Код игры

        Returns:
            Данные о предмете или None при ошибке
        """
        try:
            async with self.api:
                result = await self.api._request(
                    method="GET",
                    path="/exchange/v1/market/items",
                    params={"itemId": item_id, "gameId": game},
                )

            if not result or "objects" not in result or not result["objects"]:
                return None

            item_data = result["objects"][0]
            price = float(item_data.get("price", {}).get("USD", 0)) / 100

            return {
                "itemId": item_id,
                "price": price,
                "title": item_data.get("title", ""),
                "game": game,
            }

        except Exception as e:
            logger.exception(f"Ошибка при получении данных о предмете {item_id}: {e}")
            return None

    async def purchase_item(
        self,
        item_id: str,
        max_price: float,
        dmarket_api: DMarketAPI | None = None,
    ) -> dict[str, Any]:
        """Купить предмет на маркетплейсе.

        Args:
            item_id: Идентификатор предмета
            max_price: Максимальная цена покупки в USD
            dmarket_api: Опциональный API-клиент

        Returns:
            Результат операции покупки
        """
        api = dmarket_api or self.api

        try:
            async with api:
                purchase_data = await api._request(
                    method="POST",
                    path="/exchange/v1/offers/create",
                    data={
                        "targets": [
                            {
                                "itemId": item_id,
                                "price": {
                                    "amount": int(max_price * 100),
                                    "currency": "USD",
                                },
                            },
                        ],
                    },
                )

            if "error" in purchase_data:
                return {
                    "success": False,
                    "error": (
                        purchase_data.get("error", {}).get(
                            "message", "Неизвестная ошибка при покупке"
                        )
                    ),
                }

            if purchase_data.get("items"):
                return {
                    "success": True,
                    "new_item_id": purchase_data["items"][0].get("itemId", ""),
                    "price": max_price,
                    "purchase_data": purchase_data,
                }

            return {"success": False, "error": "Не удалось получить ID предмета"}

        except Exception as e:
            logger.exception(f"Ошибка при покупке предмета {item_id}: {e}")
            return {"success": False, "error": str(e)}

    async def list_item_for_sale(
        self,
        item_id: str,
        price: float,
        dmarket_api: DMarketAPI | None = None,
    ) -> dict[str, Any]:
        """Выставить предмет на продажу.

        Args:
            item_id: Идентификатор предмета
            price: Цена продажи в USD
            dmarket_api: Опциональный API-клиент

        Returns:
            Результат операции выставления
        """
        api = dmarket_api or self.api

        try:
            async with api:
                sell_data = await api._request(
                    method="POST",
                    path="/exchange/v1/user/items/sell",
                    data={
                        "itemId": item_id,
                        "price": {
                            "amount": int(price * 100),
                            "currency": "USD",
                        },
                    },
                )

            if "error" in sell_data:
                return {
                    "success": False,
                    "error": (
                        sell_data.get("error", {}).get(
                            "message", "Неизвестная ошибка при выставлении"
                        )
                    ),
                }

            return {"success": True, "price": price, "sell_data": sell_data}

        except Exception as e:
            logger.exception(f"Ошибка при выставлении предмета {item_id}: {e}")
            return {"success": False, "error": str(e)}
