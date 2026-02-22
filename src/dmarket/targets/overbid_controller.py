"""Контроллер автоматического перебития ордеров.

Этот модуль управляет автоматическим повышением цены ордеров
когда конкуренты создают ордера с более высокой ценой.

Основные функции:
- Мониторинг конкуренции по ценам
- Автоматическое перебитие с учетом лимитов
- Отслеживание истории перебитий
- Уведомления о перебитиях

Документация: docs/TARGET_ENHANCEMENTS_README.md
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.dmarket.models.target_enhancements import (
    RelistHistory,
    TargetErrorCode,
    TargetOperationResult,
    TargetOperationStatus,
    TargetOverbidConfig,
)

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


class OverbidController:
    """Контроллер автоматического перебития ордеров.

    Отслеживает конкуренцию и автоматически повышает цену ордеров
    с учетом заданных лимитов и правил.

    Attributes:
        api_client: DMarket API клиент
        config: Конфигурация перебития
        overbid_history: История перебитий (target_id -> список RelistHistory)
        last_check_time: Время последней проверки для каждого ордера
    """

    def __init__(
        self,
        api_client: "IDMarketAPI",
        config: TargetOverbidConfig | None = None,
    ):
        """Инициализация контроллера.

        Args:
            api_client: DMarket API клиент
            config: Конфигурация перебития (если None - по умолчанию)
        """
        self.api_client = api_client
        self.config = config or TargetOverbidConfig()
        self.overbid_history: dict[str, list[RelistHistory]] = {}
        self.last_check_time: dict[str, datetime] = {}
        self.initial_prices: dict[str, float] = {}  # Начальные цены ордеров

        logger.info(
            f"OverbidController initialized (enabled={self.config.enabled}, "
            f"max_percent={self.config.max_overbid_percent}%)"
        )

    async def should_check_competition(self, target_id: str) -> bool:
        """Проверить нужно ли проверять конкуренцию для ордера.

        Args:
            target_id: ID таргета

        Returns:
            True если пора проверять
        """
        if not self.config.enabled:
            return False

        last_check = self.last_check_time.get(target_id)
        if not last_check:
            return True

        elapsed = (datetime.now(UTC) - last_check).total_seconds()
        return elapsed >= self.config.check_interval_seconds

    async def check_and_overbid(
        self,
        target_id: str,
        game: str,
        title: str,
        current_price: float,
        attrs: dict[str, Any] | None = None,
    ) -> TargetOperationResult:
        """Проверить конкуренцию и перебить если нужно.

        Args:
            target_id: ID таргета
            game: Код игры
            title: Название предмета
            current_price: Текущая цена ордера (USD)
            attrs: Атрибуты ордера

        Returns:
            Результат проверки и перебития

        Примеры:
            >>> result = await controller.check_and_overbid(
            ...     target_id="abc123", game="csgo", title="AK-47 | Redline (FT)", current_price=10.00
            ... )
            >>> if result.success:
            ...     print(f"Overbid to ${result.metadata['new_price']}")
        """
        # Сохранить начальную цену
        if target_id not in self.initial_prices:
            self.initial_prices[target_id] = current_price

        initial_price = self.initial_prices[target_id]

        # Проверить нужно ли проверять
        if not await self.should_check_competition(target_id):
            return TargetOperationResult(
                success=True,
                status=TargetOperationStatus.SUCCESS,
                message="Check skipped",
                reason="Check interval not reached",
            )

        # Обновить время проверки
        self.last_check_time[target_id] = datetime.now(UTC)

        # Проверить лимит перебитий за день
        overbids_today = self._count_overbids_today(target_id)
        if overbids_today >= self.config.max_overbids_per_day:
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Overbid limit reached",
                reason=f"Already made {overbids_today} overbids today (max: {self.config.max_overbids_per_day})",
                error_code=TargetErrorCode.ORDER_LIMIT_REACHED,
                suggestions=["WAlgot 24h for reset", "Increase max_overbids_per_day"],
            )

        try:
            # Получить конкурирующие ордера
            market_orders = await self.api_client.get_targets_by_title(
                game_id=game,
                title=title,
            )

            orders = market_orders.get("orders", [])
            if not orders:
                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="No competition",
                    reason="No other orders found",
                )

            # Найти лучшую цену среди конкурентов
            competitor_prices = []
            for order in orders:
                try:
                    price = float(order.get("price", "0")) / 100
                    # Исключить свой ордер (примерное сравнение)
                    if abs(price - current_price) > 0.001:
                        competitor_prices.append(price)
                except (ValueError, TypeError):
                    continue

            if not competitor_prices:
                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="No competition",
                    reason="No competing orders found",
                )

            best_competitor_price = max(competitor_prices)

            # Проверить нужно ли перебивать
            if current_price >= best_competitor_price:
                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Already best price",
                    reason=f"Your price ${current_price:.2f} >= competitor ${best_competitor_price:.2f}",
                )

            # Рассчитать новую цену
            new_price = best_competitor_price + self.config.min_price_gap

            # Проверить лимит процента от начальной цены
            max_allowed_price = initial_price * (
                1 + self.config.max_overbid_percent / 100
            )
            if new_price > max_allowed_price:
                return TargetOperationResult(
                    success=False,
                    status=TargetOperationStatus.FAlgoLED,
                    message="Overbid limit exceeded",
                    reason=(
                        f"New price ${new_price:.2f} exceeds max allowed "
                        f"${max_allowed_price:.2f} ({self.config.max_overbid_percent}% from ${initial_price:.2f})"
                    ),
                    error_code=TargetErrorCode.PRICE_TOO_HIGH,
                    suggestions=[
                        f"Increase max_overbid_percent (current: {self.config.max_overbid_percent}%)",
                        "Cancel order manually",
                    ],
                )

            # Выполнить перебитие
            return await self._execute_overbid(
                target_id=target_id,
                game=game,
                title=title,
                old_price=current_price,
                new_price=new_price,
                attrs=attrs,
            )

        except Exception as e:
            logger.error(f"Error checking competition: {e}", exc_info=True)
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Check failed",
                reason=str(e),
                error_code=TargetErrorCode.UNKNOWN_ERROR,
            )

    async def _execute_overbid(
        self,
        target_id: str,
        game: str,
        title: str,
        old_price: float,
        new_price: float,
        attrs: dict[str, Any] | None = None,
    ) -> TargetOperationResult:
        """Выполнить перебитие ордера.

        Args:
            target_id: ID таргета
            game: Код игры
            title: Название предмета
            old_price: Старая цена
            new_price: Новая цена
            attrs: Атрибуты

        Returns:
            Результат перебития
        """
        logger.info(
            f"Overbidding order {target_id}: ${old_price:.2f} -> ${new_price:.2f}"
        )

        try:
            # 1. Удалить старый ордер
            await self.api_client.delete_targets(targets=[{"TargetID": target_id}])

            # 2. Создать новый с новой ценой
            target_data = {
                "Title": title,
                "Amount": 1,
                "Price": {
                    "Amount": int(new_price * 100),  # В центах
                    "Currency": "USD",
                },
            }

            if attrs:
                target_data["Attrs"] = attrs

            response = await self.api_client.create_targets(
                game=game,
                targets=[target_data],
            )

            result_items = response.get("Result", [])
            if result_items and result_items[0].get("Status") == "Created":
                new_target_id = result_items[0].get("TargetID")

                # Записать в историю
                history_entry = RelistHistory(
                    timestamp=datetime.now(UTC),
                    old_price=old_price,
                    new_price=new_price,
                    reason=f"Overbid competitor (was ${old_price:.2f})",
                    triggered_by="system",
                )

                if target_id not in self.overbid_history:
                    self.overbid_history[target_id] = []
                self.overbid_history[target_id].append(history_entry)

                # Обновить начальную цену для нового ордера
                if new_target_id:
                    self.initial_prices[new_target_id] = self.initial_prices.get(
                        target_id, old_price
                    )

                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Order overbid successfully",
                    reason=f"Price increased from ${old_price:.2f} to ${new_price:.2f}",
                    target_id=new_target_id,
                    metadata={
                        "old_target_id": target_id,
                        "old_price": old_price,
                        "new_price": new_price,
                        "increase_amount": new_price - old_price,
                        "increase_percent": ((new_price - old_price) / old_price) * 100,
                        "overbids_today": self._count_overbids_today(target_id) + 1,
                    },
                )
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Failed to create new order",
                reason="API returned non-Created status",
                error_code=TargetErrorCode.UNKNOWN_ERROR,
            )

        except Exception as e:
            logger.error(f"Failed to execute overbid: {e}", exc_info=True)
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Overbid execution failed",
                reason=str(e),
                error_code=TargetErrorCode.UNKNOWN_ERROR,
            )

    def _count_overbids_today(self, target_id: str) -> int:
        """Подсчитать количество перебитий за сегодня.

        Args:
            target_id: ID таргета

        Returns:
            Количество перебитий за последние 24 часа
        """
        if target_id not in self.overbid_history:
            return 0

        cutoff_time = datetime.now(UTC) - timedelta(hours=24)
        return sum(
            1
            for entry in self.overbid_history[target_id]
            if entry.timestamp >= cutoff_time
        )

    def get_overbid_history(self, target_id: str) -> list[RelistHistory]:
        """Получить историю перебитий для ордера.

        Args:
            target_id: ID таргета

        Returns:
            Список записей истории
        """
        return self.overbid_history.get(target_id, [])

    def reset_overbid_counter(self, target_id: str) -> None:
        """Сбросить счетчик перебитий для ордера.

        Args:
            target_id: ID таргета
        """
        if target_id in self.overbid_history:
            self.overbid_history[target_id] = []
        logger.info(f"Reset overbid counter for {target_id}")

    async def monitor_orders(
        self,
        orders: list[dict[str, Any]],
        check_interval: int | None = None,
    ) -> list[TargetOperationResult]:
        """Мониторить несколько ордеров и перебивать при необходимости.

        Args:
            orders: Список ордеров для мониторинга
                    [{"target_id": "...", "game": "...", "title": "...", "price": ...}, ...]
            check_interval: Интервал проверки в секундах (если None - из config)

        Returns:
            Список результатов проверки

        Примеры:
            >>> orders = [
            ...     {
            ...         "target_id": "abc",
            ...         "game": "csgo",
            ...         "title": "AK-47 | Redline (FT)",
            ...         "price": 10.0,
            ...     },
            ...     {"target_id": "def", "game": "csgo", "title": "M4A4 | Asiimov (FT)", "price": 25.0},
            ... ]
            >>> results = await controller.monitor_orders(orders)
        """
        interval = check_interval or self.config.check_interval_seconds

        logger.info(
            f"Starting monitoring for {len(orders)} orders (interval: {interval}s)"
        )

        results = []
        for order in orders:
            result = await self.check_and_overbid(
                target_id=order["target_id"],
                game=order["game"],
                title=order["title"],
                current_price=order["price"],
                attrs=order.get("attrs"),
            )
            results.append(result)

            # Небольшая задержка между проверками
            await asyncio.sleep(1)

        return results
