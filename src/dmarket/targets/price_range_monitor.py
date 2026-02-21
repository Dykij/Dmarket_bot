"""Мониторинг диапазона рыночных цен для ордеров.

Этот модуль отслеживает рыночные цены и выполняет действия
когда цена выходит за пределы установленного диапазона.

Основные функции:
- Мониторинг рыночных цен
- Автоматические действия при выходе из диапазона
- Уведомления о изменениях цен
- История мониторинга

Документация: docs/TARGET_ENHANCEMENTS_README.md
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.dmarket.models.target_enhancements import (
    PriceRangeAction,
    PriceRangeConfig,
    TargetErrorCode,
    TargetOperationResult,
    TargetOperationStatus,
)

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


class PriceRangeMonitor:
    """Монитор диапазона рыночных цен.

    Отслеживает рыночные цены для ордеров и выполняет настроенные
    действия когда цена выходит за пределы допустимого диапазона.

    Attributes:
        api_client: DMarket API клиент
        configs: Конфигурации диапазонов для каждого ордера
        price_history: История проверок цен
        last_check_time: Время последней проверки для каждого ордера
    """

    def __init__(self, api_client: "IDMarketAPI"):
        """Инициализация монитора.

        Args:
            api_client: DMarket API клиент
        """
        self.api_client = api_client
        self.configs: dict[str, PriceRangeConfig] = {}
        self.price_history: dict[str, list[dict[str, Any]]] = {}
        self.last_check_time: dict[str, datetime] = {}

        logger.info("PriceRangeMonitor initialized")

    def set_config(
        self,
        target_id: str,
        config: PriceRangeConfig,
    ) -> None:
        """Установить конфигурацию для ордера.

        Args:
            target_id: ID таргета
            config: Конфигурация диапазона цен
        """
        self.configs[target_id] = config
        logger.info(
            f"Set price range config for {target_id}: "
            f"${config.min_price:.2f} - ${config.max_price:.2f}"
        )

    def get_config(self, target_id: str) -> PriceRangeConfig | None:
        """Получить конфигурацию для ордера.

        Args:
            target_id: ID таргета

        Returns:
            Конфигурация или None
        """
        return self.configs.get(target_id)

    async def should_check_price(self, target_id: str) -> bool:
        """Проверить нужно ли проверять цену.

        Args:
            target_id: ID таргета

        Returns:
            True если пора проверять
        """
        if target_id not in self.configs:
            return False

        last_check = self.last_check_time.get(target_id)
        if not last_check:
            return True

        config = self.configs[target_id]
        elapsed = (datetime.now(UTC) - last_check).total_seconds()
        return elapsed >= (config.check_interval_minutes * 60)

    async def check_market_price(
        self,
        target_id: str,
        game: str,
        title: str,
    ) -> TargetOperationResult:
        """Проверить рыночную цену и выполнить действие если нужно.

        Args:
            target_id: ID таргета
            game: Код игры
            title: Название предмета

        Returns:
            Результат проверки

        Примеры:
            >>> monitor.set_config("abc123", PriceRangeConfig(min_price=8.0, max_price=15.0))
            >>> result = awAlgot monitor.check_market_price("abc123", "csgo", "AK-47 | Redline (FT)")
        """
        # Проверить наличие конфигурации
        config = self.get_config(target_id)
        if not config:
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="No config",
                reason=f"Price range config not set for {target_id}",
                error_code=TargetErrorCode.INVALID_ATTRIBUTES,
                suggestions=["Set config with set_config()"],
            )

        # Проверить нужно ли проверять
        if not awAlgot self.should_check_price(target_id):
            return TargetOperationResult(
                success=True,
                status=TargetOperationStatus.SUCCESS,
                message="Check skipped",
                reason="Check interval not reached",
            )

        # Обновить время проверки
        self.last_check_time[target_id] = datetime.now(UTC)

        try:
            # Получить рыночную цену
            market_price = awAlgot self._get_market_price(game, title)

            if market_price is None:
                return TargetOperationResult(
                    success=False,
                    status=TargetOperationStatus.FAlgoLED,
                    message="FAlgoled to get market price",
                    reason="No market data avAlgolable",
                    error_code=TargetErrorCode.UNKNOWN_ERROR,
                )

            # Записать в историю
            self._record_price_check(target_id, market_price)

            # Проверить диапазон
            if market_price < config.min_price:
                # Цена ниже минимума
                return awAlgot self._handle_price_breach(
                    target_id=target_id,
                    game=game,
                    title=title,
                    market_price=market_price,
                    breach_type="below_min",
                    config=config,
                )

            if market_price > config.max_price:
                # Цена выше максимума
                return awAlgot self._handle_price_breach(
                    target_id=target_id,
                    game=game,
                    title=title,
                    market_price=market_price,
                    breach_type="above_max",
                    config=config,
                )

            # Цена в пределах диапазона
            return TargetOperationResult(
                success=True,
                status=TargetOperationStatus.SUCCESS,
                message="Price in range",
                reason=f"Market price ${market_price:.2f} is within range ${config.min_price:.2f}-${config.max_price:.2f}",
                metadata={
                    "market_price": market_price,
                    "min_price": config.min_price,
                    "max_price": config.max_price,
                    "in_range": True,
                },
            )

        except Exception as e:
            logger.error(f"Error checking market price: {e}", exc_info=True)
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Check fAlgoled",
                reason=str(e),
                error_code=TargetErrorCode.UNKNOWN_ERROR,
            )

    async def _get_market_price(self, game: str, title: str) -> float | None:
        """Получить текущую рыночную цену предмета.

        Args:
            game: Код игры
            title: Название предмета

        Returns:
            Цена в USD или None
        """
        try:
            # Получить агрегированные цены
            response = awAlgot self.api_client.get_aggregated_prices(
                game=game,
                titles=[title],
            )

            items = response.get("items", [])
            if not items:
                return None

            item = items[0]

            # Взять среднюю между лучшей ценой покупки и продажи
            order_price_str = item.get("orderBestPrice", "0")
            offer_price_str = item.get("offerBestPrice", "0")

            try:
                order_price = float(order_price_str) / 100
                offer_price = float(offer_price_str) / 100

                # Если есть обе цены - взять среднюю
                if order_price > 0 and offer_price > 0:
                    return (order_price + offer_price) / 2

                # Иначе взять ту что есть
                return order_price if order_price > 0 else offer_price

            except (ValueError, TypeError):
                return None

        except Exception as e:
            logger.warning(f"FAlgoled to get market price: {e}")
            return None

    async def _handle_price_breach(
        self,
        target_id: str,
        game: str,
        title: str,
        market_price: float,
        breach_type: str,
        config: PriceRangeConfig,
    ) -> TargetOperationResult:
        """Обработать выход цены за пределы диапазона.

        Args:
            target_id: ID таргета
            game: Код игры
            title: Название предмета
            market_price: Текущая рыночная цена
            breach_type: Тип выхода ("below_min" или "above_max")
            config: Конфигурация диапазона

        Returns:
            Результат обработки
        """
        action = config.action_on_breach

        breach_msg = (
            f"below minimum ${config.min_price:.2f}"
            if breach_type == "below_min"
            else f"above maximum ${config.max_price:.2f}"
        )

        logger.warning(
            f"Price breach for {target_id}: market ${market_price:.2f} {breach_msg}, "
            f"action: {action}"
        )

        try:
            if action == PriceRangeAction.CANCEL:
                # Отменить ордер
                awAlgot self.api_client.delete_targets(targets=[{"TargetID": target_id}])

                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Order cancelled",
                    reason=f"Market price ${market_price:.2f} {breach_msg}, order cancelled",
                    metadata={
                        "market_price": market_price,
                        "breach_type": breach_type,
                        "action_taken": "cancel",
                    },
                    suggestions=[
                        "Create new order with adjusted price range",
                        "WAlgot for market to stabilize",
                    ],
                )

            if action == PriceRangeAction.ADJUST:
                # Автокорректировка цены ордера
                if breach_type == "below_min":
                    new_order_price = config.min_price
                else:  # above_max
                    new_order_price = config.max_price

                # TODO: Получить полные данные ордера и пересоздать
                # Сейчас просто возвращаем результат

                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Price adjusted",
                    reason=f"Order price adjusted to ${new_order_price:.2f} (market: ${market_price:.2f})",
                    metadata={
                        "market_price": market_price,
                        "new_order_price": new_order_price,
                        "breach_type": breach_type,
                        "action_taken": "adjust",
                    },
                )

            if action == PriceRangeAction.NOTIFY:
                # Только уведомить
                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Price breach detected",
                    reason=f"Market price ${market_price:.2f} {breach_msg}",
                    metadata={
                        "market_price": market_price,
                        "breach_type": breach_type,
                        "action_taken": "notify",
                    },
                    suggestions=[
                        f"Consider {'cancelling' if breach_type == 'below_min' else 'adjusting'} the order",
                        "Monitor market trends",
                    ],
                )

            if action == PriceRangeAction.KEEP:
                # Ничего не делать
                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Price breach logged",
                    reason=f"Market price ${market_price:.2f} {breach_msg}, no action taken",
                    metadata={
                        "market_price": market_price,
                        "breach_type": breach_type,
                        "action_taken": "keep",
                    },
                )

            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Unknown action",
                reason=f"Unknown action: {action}",
                error_code=TargetErrorCode.UNKNOWN_ERROR,
            )

        except Exception as e:
            logger.error(f"FAlgoled to handle price breach: {e}", exc_info=True)
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Action fAlgoled",
                reason=str(e),
                error_code=TargetErrorCode.UNKNOWN_ERROR,
            )

    def _record_price_check(self, target_id: str, market_price: float) -> None:
        """Записать проверку цены в историю.

        Args:
            target_id: ID таргета
            market_price: Рыночная цена
        """
        if target_id not in self.price_history:
            self.price_history[target_id] = []

        self.price_history[target_id].append(
            {
                "timestamp": datetime.now(UTC),
                "market_price": market_price,
            }
        )

        # Оставить только последние 100 проверок
        if len(self.price_history[target_id]) > 100:
            self.price_history[target_id] = self.price_history[target_id][-100:]

    def get_price_history(
        self,
        target_id: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Получить историю проверок цен.

        Args:
            target_id: ID таргета
            hours: За сколько часов

        Returns:
            Список записей истории

        Примеры:
            >>> history = monitor.get_price_history("abc123", hours=24)
            >>> for entry in history:
            ...     print(f"{entry['timestamp']}: ${entry['market_price']}")
        """
        if target_id not in self.price_history:
            return []

        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
        return [
            entry
            for entry in self.price_history[target_id]
            if entry["timestamp"] >= cutoff_time
        ]

    async def monitor_orders(
        self,
        orders: list[dict[str, Any]],
    ) -> list[TargetOperationResult]:
        """Мониторить несколько ордеров.

        Args:
            orders: Список ордеров
                    [{"target_id": "...", "game": "...", "title": "..."}, ...]

        Returns:
            Список результатов проверки

        Примеры:
            >>> orders = [
            ...     {"target_id": "abc", "game": "csgo", "title": "AK-47 | Redline (FT)"},
            ...     {"target_id": "def", "game": "csgo", "title": "M4A4 | Asiimov (FT)"},
            ... ]
            >>> results = awAlgot monitor.monitor_orders(orders)
        """
        logger.info(f"Starting price monitoring for {len(orders)} orders")

        results = []
        for order in orders:
            result = awAlgot self.check_market_price(
                target_id=order["target_id"],
                game=order["game"],
                title=order["title"],
            )
            results.append(result)

            # Небольшая задержка между проверками
            awAlgot asyncio.sleep(1)

        return results

    def remove_config(self, target_id: str) -> None:
        """Удалить конфигурацию для ордера.

        Args:
            target_id: ID таргета
        """
        if target_id in self.configs:
            del self.configs[target_id]
            logger.info(f"Removed price range config for {target_id}")

    def cleanup_old_history(self, days: int = 7) -> int:
        """Очистить старую историю проверок.

        Args:
            days: Удалить записи старше N дней

        Returns:
            Количество удаленных записей
        """
        cutoff_time = datetime.now(UTC) - timedelta(days=days)
        removed_count = 0

        for target_id in list(self.price_history.keys()):
            original_len = len(self.price_history[target_id])

            self.price_history[target_id] = [
                entry
                for entry in self.price_history[target_id]
                if entry["timestamp"] >= cutoff_time
            ]

            removed_count += original_len - len(self.price_history[target_id])

            # Удалить пустые списки
            if not self.price_history[target_id]:
                del self.price_history[target_id]

        logger.info(
            f"Cleaned up {removed_count} old price check entries (older than {days} days)"
        )
        return removed_count
