"""Модуль для отслеживания цен на DMarket в реальном времени.

Этот модуль использует WebSocket соединение для получения обновлений
о ценах предметов на маркетплейсе DMarket в режиме реального времени.

Документация DMarket API: https://docs.dmarket.com/v1/swagger.html
"""

import asyncio
import contextlib
import logging
import time
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.websocket_client import DMarketWebSocketClient

logger = logging.getLogger(__name__)


class PriceAlert:
    """Класс для представления оповещения о цене."""

    def __init__(
        self,
        item_id: str,
        market_hash_name: str,
        target_price: float,
        condition: str = "below",
        game: str = "csgo",
    ) -> None:
        """Инициализация оповещения о цене.

        Args:
            item_id: ID предмета в DMarket
            market_hash_name: Полное название предмета
            target_price: Целевая цена для оповещения
            condition: Условие срабатывания ('below' или 'above')
            game: Игра, к которой относится предмет

        """
        self.item_id = item_id
        self.market_hash_name = market_hash_name
        self.target_price = target_price
        self.condition = condition
        self.game = game
        self.is_triggered = False
        self.created_at = time.time()
        self.triggered_at = None

    def check_condition(self, current_price: float) -> bool:
        """Проверка условия срабатывания оповещения.

        Args:
            current_price: Текущая цена предмета

        Returns:
            bool: True если условие сработало, иначе False

        """
        if (self.condition == "below" and current_price <= self.target_price) or (
            self.condition == "above" and current_price >= self.target_price
        ):
            if not self.is_triggered:
                self.triggered_at = time.time()
            return True
        return False

    def reset(self) -> None:
        """Сбросить состояние оповещения для повторного использования."""
        self.is_triggered = False
        self.triggered_at = None


class RealtimePriceWatcher:
    """Класс для отслеживания цен в реальном времени."""

    def __init__(self, api_client: DMarketAPI) -> None:
        """Инициализация наблюдателя за ценами.

        Args:
            api_client: Экземпляр DMarketAPI для работы с API

        """
        self.api_client = api_client
        self.websocket_client = DMarketWebSocketClient(api_client)

        # Словарь для отслеживания цен {item_id: latest_price}
        self.price_cache = {}

        # Исторические данные о ценах {item_id: [(timestamp, price), ...]}
        self.price_history = defaultdict(list)
        self.max_history_points = 100  # Максимальное количество сохраняемых точек истории цен

        # Словарь для хранения оповещений {item_id: [alert1, alert2, ...]}
        self.price_alerts = defaultdict(list)

        # Список обработчиков событий изменения цен {item_id: [handler1, handler2, ...]}
        self.price_change_handlers = defaultdict(list)

        # Список обработчиков срабатывания оповещений
        self.alert_handlers = []

        # Множество отслеживаемых предметов
        self.watched_items = set()

        # Словарь для хранения метаданных предметов
        self.item_metadata = {}

        # Задачи
        self.ws_task = None
        self.price_update_task = None
        self.is_running = False

        # Настройки
        self.price_update_interval = (
            300  # Обновление цен каждые 5 минут для отслеживаемых предметов
        )

    async def start(self) -> bool:
        """Запуск наблюдателя за ценами.

        Returns:
            bool: True если запуск успешен, иначе False

        """
        if self.is_running:
            logger.warning("Наблюдатель за ценами уже запущен")
            return True

        # Регистрируем обработчик сообщений WebSocket
        self.websocket_client.register_handler(
            "market:update",
            self._handle_market_update,
        )
        self.websocket_client.register_handler(
            "items:update",
            self._handle_items_update,
        )

        # Подключаемся к WebSocket
        connected = await self.websocket_client.connect()
        if not connected:
            logger.error("Не удалось подключиться к WebSocket API DMarket")
            return False

        # Запускаем задачу прослушивания
        self.ws_task = asyncio.create_task(self.websocket_client.listen())

        # Запускаем периодическое обновление цен через REST API
        self.price_update_task = asyncio.create_task(self._periodic_price_updates())

        self.is_running = True

        logger.info("Наблюдатель за ценами успешно запущен")
        return True

    async def stop(self) -> None:
        """Остановка наблюдателя за ценами."""
        if not self.is_running:
            return

        self.is_running = False

        # Отменяем задачу прослушивания
        if self.ws_task and not self.ws_task.done():
            self.ws_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.ws_task

        # Отменяем задачу обновления цен
        if self.price_update_task and not self.price_update_task.done():
            self.price_update_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.price_update_task

        # Закрываем WebSocket соединение
        await self.websocket_client.close()

        logger.info("Наблюдатель за ценами остановлен")

    async def _handle_market_update(self, message: dict[str, Any]) -> None:
        """Обработка сообщения об обновлении рынка.

        Args:
            message: Сообщение от WebSocket API

        """
        try:
            data = message.get("data", {})

            # Обрабатываем обновления цен
            if "items" in data:
                for item in data["items"]:
                    item_id = item.get("itemId")
                    price_data = item.get("price", {})

                    if not item_id or not price_data:
                        continue

                    # Получаем цену в USD
                    price = price_data.get("USD")
                    if price is None:
                        continue

                    # Преобразуем цену в float
                    try:
                        price_float = float(price) / 100  # Цена в центах, конвертируем в доллары
                    except (ValueError, TypeError):
                        continue

                    # Если этот предмет отслеживается
                    if item_id in self.watched_items:
                        old_price = self.price_cache.get(item_id)
                        self.price_cache[item_id] = price_float

                        # Добавляем в историю цен
                        self._add_to_price_history(item_id, price_float)

                        # Запускаем обработчики изменения цены
                        await self._process_price_change(
                            item_id,
                            old_price,
                            price_float,
                        )

                        # Проверяем оповещения
                        await self._check_alerts(item_id, price_float)

        except Exception as e:
            logger.exception(f"Ошибка при обработке сообщения обновления рынка: {e}")

    async def _handle_items_update(self, message: dict[str, Any]) -> None:
        """Обработка сообщения об обновлении конкретных предметов.

        Args:
            message: Сообщение от WebSocket API

        """
        try:
            data = message.get("data", {})

            # Обрабатываем обновления предметов
            if "items" in data:
                for item in data["items"]:
                    item_id = item.get("itemId")
                    price_data = item.get("price", {})

                    if not item_id or not price_data:
                        continue

                    # Получаем цену в USD
                    price = price_data.get("USD")
                    if price is None:
                        continue

                    # Преобразуем цену в float
                    try:
                        price_float = float(price) / 100  # Цена в центах, конвертируем в доллары
                    except (ValueError, TypeError):
                        continue

                    # Если этот предмет отслеживается
                    if item_id in self.watched_items:
                        old_price = self.price_cache.get(item_id)
                        self.price_cache[item_id] = price_float

                        # Добавляем в историю цен
                        self._add_to_price_history(item_id, price_float)

                        # Запускаем обработчики изменения цены
                        await self._process_price_change(
                            item_id,
                            old_price,
                            price_float,
                        )

                        # Проверяем оповещения
                        await self._check_alerts(item_id, price_float)

                    # Сохраняем метаданные предмета
                    if "title" in item:
                        self.item_metadata[item_id] = {
                            "title": item["title"],
                            "gameId": item.get("gameId", ""),
                            "lastUpdated": time.time(),
                        }

        except Exception as e:
            logger.exception(f"Ошибка при обработке сообщения обновления предметов: {e}")

    def _add_to_price_history(self, item_id: str, price: float) -> None:
        """Добавление записи в историю цен предмета.

        Args:
            item_id: ID предмета
            price: Цена предмета

        """
        # Добавляем новую точку с текущим временем
        self.price_history[item_id].append((time.time(), price))

        # Ограничиваем размер истории
        if len(self.price_history[item_id]) > self.max_history_points:
            self.price_history[item_id] = self.price_history[item_id][-self.max_history_points :]

    async def _periodic_price_updates(self) -> None:
        """Периодическое обновление цен через REST API."""
        while self.is_running:
            try:
                await self._update_watched_items_prices()
                await asyncio.sleep(self.price_update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Ошибка при периодическом обновлении цен: {e}")
                await asyncio.sleep(60)  # Уменьшаем частоту обновлений при ошибках

    async def _update_watched_items_prices(self) -> None:
        """Обновление цен отслеживаемых предметов через REST API."""
        if not self.watched_items:
            return

        # Группируем предметы по играм для оптимизации запросов
        items_by_game = defaultdict(list)
        for item_id in self.watched_items:
            # Определяем игру из метаданных или используем csgo по умолчанию
            game = "csgo"
            if item_id in self.item_metadata and "gameId" in self.item_metadata[item_id]:
                game = self.item_metadata[item_id]["gameId"]
            items_by_game[game].append(item_id)

        # Обновляем цены для каждой игры
        for game, item_ids in items_by_game.items():  # noqa: PLR1702
            # Разбиваем на чанки по 50 предметов для избежания слишком длинных запросов
            chunk_size = 50
            for i in range(0, len(item_ids), chunk_size):
                chunk = item_ids[i : i + chunk_size]
                try:
                    # Формируем строку с ID предметов через запятую
                    item_ids_str = ",".join(chunk)

                    # Запрашиваем информацию о предметах через API
                    response = await self.api_client._request(
                        "GET",
                        "/exchange/v1/market/items",
                        params={
                            "gameId": game,
                            "itemIds": item_ids_str,
                            "currency": "USD",
                        },
                    )

                    if "items" in response:
                        # Обрабатываем полученные данные
                        for item in response["items"]:
                            item_id = item.get("itemId")
                            if not item_id:
                                continue

                            # Получаем цену
                            price_data = item.get("price", {})
                            if isinstance(price_data, dict) and "USD" in price_data:
                                price = (
                                    float(price_data["USD"]) / 100
                                )  # Цена в центах, конвертируем в доллары

                                # Сохраняем метаданные
                                self.item_metadata[item_id] = {
                                    "title": item.get("title", ""),
                                    "gameId": game,
                                    "lastUpdated": time.time(),
                                }

                                # Обрабатываем изменение цены
                                old_price = self.price_cache.get(item_id)
                                if old_price != price:
                                    self.price_cache[item_id] = price

                                    # Добавляем в историю цен
                                    self._add_to_price_history(item_id, price)

                                    # Запускаем обработчики изменения цены
                                    await self._process_price_change(
                                        item_id,
                                        old_price,
                                        price,
                                    )

                                    # Проверяем оповещения
                                    await self._check_alerts(item_id, price)

                except Exception as e:
                    logger.exception(f"Ошибка при обновлении цен для игры {game}: {e}")

                # Задержка между запросами чанков
                await asyncio.sleep(1)

    async def _process_price_change(
        self,
        item_id: str,
        old_price: float | None,
        new_price: float,
    ) -> None:
        """Обработка изменения цены предмета.

        Args:
            item_id: ID предмета
            old_price: Предыдущая цена предмета
            new_price: Новая цена предмета

        """
        # Если цена не изменилась, ничего не делаем
        if old_price == new_price:
            return

        # Выполняем все обработчики изменения цены для данного предмета
        handlers = self.price_change_handlers.get(item_id, [])
        handlers.extend(
            self.price_change_handlers.get("*", []),
        )  # Глобальные обработчики

        for handler in handlers:
            try:
                await handler(item_id, old_price, new_price)
            except Exception as e:
                logger.exception(f"Ошибка в обработчике изменения цены: {e}")

    async def _check_alerts(self, item_id: str, current_price: float) -> None:
        """Проверка оповещений для предмета.

        Args:
            item_id: ID предмета
            current_price: Текущая цена предмета

        """
        alerts = self.price_alerts.get(item_id, [])

        for alert in alerts:
            # Проверяем условие и не сработало ли оповещение ранее
            if not alert.is_triggered and alert.check_condition(current_price):
                alert.is_triggered = True

                # Запускаем обработчики оповещений
                for handler in self.alert_handlers:
                    try:
                        await handler(alert, current_price)
                    except Exception as e:
                        logger.exception(f"Ошибка в обработчике оповещения: {e}")

    async def subscribe_to_item(self, item_id: str, game: str = "csgo") -> bool:
        """Подписаться на обновления конкретного предмета.

        Args:
            item_id: ID предмета для отслеживания
            game: Игра, к которой относится предмет

        Returns:
            bool: True если подписка успешна, иначе False

        """
        if not self.is_running:
            logger.error("Наблюдатель за ценами не запущен")
            return False

        # Добавляем предмет для отслеживания
        self.watch_item(item_id)

        # Получаем текущую цену предмета
        current_price = await self._fetch_item_price(item_id, game)
        if current_price:
            self.price_cache[item_id] = current_price
            self._add_to_price_history(item_id, current_price)

        # Подписываемся на обновления через WebSocket
        return await self.websocket_client.subscribe_to_item_updates([item_id])

    async def subscribe_to_market_updates(self, game: str = "csgo") -> bool:
        """Подписаться на обновления рынка для конкретной игры.

        Args:
            game: Игра для подписки

        Returns:
            bool: True если подписка успешна, иначе False

        """
        if not self.is_running:
            logger.error("Наблюдатель за ценами не запущен")
            return False

        return await self.websocket_client.subscribe_to_market_updates(game)

    async def _fetch_item_price(self, item_id: str, game: str = "csgo") -> float | None:
        """Получение текущей цены предмета.

        Args:
            item_id: ID предмета
            game: Игра, к которой относится предмет

        Returns:
            Optional[float]: Текущая цена предмета или None в случае ошибки

        """
        try:
            response = await self.api_client._request(
                "GET",
                "/exchange/v1/market/items",
                params={
                    "gameId": game,
                    "itemIds": item_id,
                    "currency": "USD",
                },
            )

            if response.get("items"):
                item = response["items"][0]
                price_data = item.get("price", {})

                if isinstance(price_data, dict) and "USD" in price_data:
                    # Сохраняем метаданные предмета
                    self.item_metadata[item_id] = {
                        "title": item.get("title", ""),
                        "gameId": game,
                        "lastUpdated": time.time(),
                    }

                    return float(price_data["USD"]) / 100  # Цена в центах, конвертируем в доллары

            return None

        except Exception as e:
            logger.exception(f"Ошибка при получении цены предмета {item_id}: {e}")
            return None

    def watch_item(self, item_id: str, initial_price: float | None = None) -> None:
        """Добавить предмет для отслеживания.

        Args:
            item_id: ID предмета для отслеживания
            initial_price: Начальная цена предмета (если известна)

        """
        self.watched_items.add(item_id)

        if initial_price is not None:
            self.price_cache[item_id] = initial_price
            self._add_to_price_history(item_id, initial_price)

        logger.debug(f"Предмет {item_id} добавлен для отслеживания")

    def unwatch_item(self, item_id: str) -> None:
        """Удалить предмет из отслеживания.

        Args:
            item_id: ID предмета для удаления из отслеживания

        """
        if item_id in self.watched_items:
            self.watched_items.remove(item_id)

        # Удаляем из кеша цен
        if item_id in self.price_cache:
            del self.price_cache[item_id]

        logger.debug(f"Предмет {item_id} удален из отслеживания")

    def add_price_alert(self, alert: PriceAlert) -> None:
        """Добавить оповещение о цене.

        Args:
            alert: Оповещение о цене для добавления

        """
        self.price_alerts[alert.item_id].append(alert)

        # Добавляем предмет для отслеживания
        self.watch_item(alert.item_id)

        logger.info(
            f"Добавлено оповещение для {alert.market_hash_name} "
            f"({alert.condition} {alert.target_price})",
        )

    def remove_price_alert(self, alert: PriceAlert) -> None:
        """Удалить оповещение о цене.

        Args:
            alert: Оповещение о цене для удаления

        """
        if alert.item_id in self.price_alerts:
            if alert in self.price_alerts[alert.item_id]:
                self.price_alerts[alert.item_id].remove(alert)

            # Если больше нет оповещений для этого предмета, удаляем ключ
            if not self.price_alerts[alert.item_id]:
                del self.price_alerts[alert.item_id]

        logger.debug(f"Удалено оповещение для {alert.market_hash_name}")

    def register_price_change_handler(
        self,
        handler: Callable[[str, float | None, float], None],
        item_id: str = "*",
    ) -> None:
        """Регистрация обработчика изменения цены.

        Args:
            handler: Функция-обработчик, которая будет вызвана при изменении цены
            item_id: ID предмета для отслеживания или "*" для всех предметов

        """
        self.price_change_handlers[item_id].append(handler)

    def register_alert_handler(
        self,
        handler: Callable[[PriceAlert, float], Coroutine[Any, Any, None] | None],
    ) -> None:
        """Регистрация обработчика срабатывания оповещения.

        Args:
            handler: Функция-обработчик, которая будет вызвана при срабатывании оповещения

        """
        self.alert_handlers.append(handler)

    def get_current_price(self, item_id: str) -> float | None:
        """Получить текущую цену предмета из кеша.

        Args:
            item_id: ID предмета

        Returns:
            Optional[float]: Текущая цена предмета или None, если предмет не отслеживается

        """
        return self.price_cache.get(item_id)

    def get_price_history(
        self,
        item_id: str,
        limit: int | None = None,
    ) -> list[tuple[float, float]]:
        """Получить историю цен предмета.

        Args:
            item_id: ID предмета
            limit: Ограничение на количество точек истории

        Returns:
            List[Tuple[float, float]]: Список точек истории цен [(timestamp, price), ...]

        """
        history = self.price_history.get(item_id, [])
        if limit:
            return history[-limit:]
        return history

    def get_all_alerts(self) -> dict[str, list[PriceAlert]]:
        """Получить все активные оповещения.

        Returns:
            Dict[str, List[PriceAlert]]: Словарь оповещений по ID предметов

        """
        return self.price_alerts

    def get_triggered_alerts(self) -> list[PriceAlert]:
        """Получить все сработавшие оповещения.

        Returns:
            List[PriceAlert]: Список сработавших оповещений

        """
        triggered = []
        for alerts in self.price_alerts.values():
            for alert in alerts:
                if alert.is_triggered:
                    triggered.append(alert)
        return triggered

    def reset_triggered_alerts(self) -> int:
        """Сбросить состояние всех сработавших оповещений.

        Returns:
            int: Количество сброшенных оповещений

        """
        reset_count = 0
        for alerts in self.price_alerts.values():
            for alert in alerts:
                if alert.is_triggered:
                    alert.reset()
                    reset_count += 1
        return reset_count

    def get_item_metadata(self, item_id: str) -> dict[str, Any]:
        """Получить метаданные предмета.

        Args:
            item_id: ID предмета

        Returns:
            Dict[str, Any]: Метаданные предмета или пустой словарь

        """
        return self.item_metadata.get(item_id, {})


# Пример использования:
"""
async def main():
    from src.dmarket.dmarket_api import DMarketAPI
    from src.utils.canonical_logging import setup_logging

    # Настройка логирования
    setup_logging()

    # Инициализация API клиента
    api_client = DMarketAPI(public_key="your_public_key", secret_key="your_secret_key")

    # Создание наблюдателя за ценами
    watcher = RealtimePriceWatcher(api_client)

    # Обработчик изменения цены
    async def on_price_change(item_id, old_price, new_price):
        change = ((new_price - old_price) / old_price) * 100 if old_price else 0
        print(f"Цена изменилась: {item_id}, {old_price} -> {new_price} ({change:.2f}%)")

    # Обработчик срабатывания оповещения
    async def on_alert_triggered(alert, current_price):
        print(f"Оповещение сработало! {alert.market_hash_name}: {alert.target_price} {alert.condition} {current_price}")

    # Регистрация обработчиков
    watcher.register_price_change_handler(on_price_change)
    watcher.register_alert_handler(on_alert_triggered)

    # Добавление оповещений
    alert1 = PriceAlert(
        item_id="123456",
        market_hash_name="AWP | Asiimov (Field-Tested)",
        target_price=50.0,
        condition="below"
    )
    watcher.add_price_alert(alert1)

    # Запуск наблюдателя
    await watcher.start()

    try:
        # Ожидаем событий
        await asyncio.sleep(3600)  # 1 час
    finally:
        # Останавливаем наблюдатель
        await watcher.stop()

if __name__ == "__main__":
    asyncio.run(main())
"""
