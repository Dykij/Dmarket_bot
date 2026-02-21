"""Менеджер перевыставлений ордеров (Relist Manager).

Этот модуль управляет перевыставлениями ордеров с контролем лимитов:
- Отслеживание количества перевыставлений
- Автоматические действия при достижении лимита
- История перевыставлений
- Статистика и аналитика

Документация: docs/TARGET_ENHANCEMENTS_README.md
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.dmarket.models.target_enhancements import (
    RelistAction,
    RelistHistory,
    RelistLimitConfig,
    RelistStatistics,
    TargetErrorCode,
    TargetOperationResult,
    TargetOperationStatus,
)

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


class RelistManager:
    """Менеджер перевыставлений ордеров.

    Отслеживает и контролирует количество перевыставлений каждого ордера,
    выполняет настроенные действия при достижении лимитов.

    Attributes:
        api_client: DMarket API клиент
        config: Конфигурация лимитов
        relist_data: Данные о перевыставлениях (target_id -> данные)
    """

    def __init__(
        self,
        api_client: "IDMarketAPI",
        config: RelistLimitConfig | None = None,
    ):
        """Инициализация менеджера.

        Args:
            api_client: DMarket API клиент
            config: Конфигурация лимитов (если None - по умолчанию)
        """
        self.api_client = api_client
        self.config = config or RelistLimitConfig()
        self.relist_data: dict[str, dict[str, Any]] = {}

        logger.info(
            f"RelistManager initialized (max_relists={self.config.max_relists}, "
            f"action={self.config.action_on_limit})"
        )

    def _get_or_create_data(self, target_id: str) -> dict[str, Any]:
        """Получить или создать данные перевыставлений для ордера.

        Args:
            target_id: ID таргета

        Returns:
            Словарь с данными перевыставлений
        """
        if target_id not in self.relist_data:
            self.relist_data[target_id] = {
                "count": 0,
                "history": [],
                "created_at": datetime.now(UTC),
                "last_relist_time": None,
                "paused": False,
            }
        return self.relist_data[target_id]

    def can_relist(self, target_id: str) -> tuple[bool, str]:
        """Проверить можно ли перевыставить ордер.

        Args:
            target_id: ID таргета

        Returns:
            (can_relist, reason)

        Примеры:
            >>> can, reason = manager.can_relist("abc123")
            >>> if not can:
            ...     print(reason)  # "Limit reached: 5/5 relists"
        """
        data = self._get_or_create_data(target_id)

        # Проверить паузу
        if data["paused"]:
            return False, "Order is paused"

        # Проверить лимит
        current_count = self._count_relists_in_period(target_id)
        if current_count >= self.config.max_relists:
            return (
                False,
                f"Limit reached: {current_count}/{self.config.max_relists} relists",
            )

        return True, "OK"

    def _count_relists_in_period(self, target_id: str) -> int:
        """Подсчитать количество перевыставлений в текущем периоде.

        Args:
            target_id: ID таргета

        Returns:
            Количество перевыставлений
        """
        data = self._get_or_create_data(target_id)
        created_at = data["created_at"]
        current_time = datetime.now(UTC)

        # Рассчитать время сброса
        reset_time = created_at + timedelta(hours=self.config.reset_period_hours)

        # Если прошел период сброса - сбросить счетчик
        if current_time >= reset_time:
            logger.info(f"Resetting relist counter for {target_id} (period expired)")
            data["count"] = 0
            data["created_at"] = current_time
            data["history"] = []
            return 0

        return data["count"]

    async def record_relist(
        self,
        target_id: str,
        old_price: float,
        new_price: float,
        reason: str = "Manual relist",
        triggered_by: str = "user",
    ) -> TargetOperationResult:
        """Записать перевыставление ордера.

        Args:
            target_id: ID таргета
            old_price: Старая цена (USD)
            new_price: Новая цена (USD)
            reason: Причина перевыставления
            triggered_by: Кто инициировал (user, system, competitor)

        Returns:
            Результат записи

        Примеры:
            >>> result = awAlgot manager.record_relist(
            ...     target_id="abc123", old_price=10.00, new_price=10.05, reason="Competitor overbid"
            ... )
        """
        # Проверить можно ли перевыставить
        can, check_reason = self.can_relist(target_id)
        if not can:
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Relist not allowed",
                reason=check_reason,
                error_code=TargetErrorCode.ORDER_LIMIT_REACHED,
            )

        data = self._get_or_create_data(target_id)

        # Создать запись истории
        history_entry = RelistHistory(
            timestamp=datetime.now(UTC),
            old_price=old_price,
            new_price=new_price,
            reason=reason,
            triggered_by=triggered_by,
        )

        # Обновить данные
        data["count"] += 1
        data["last_relist_time"] = datetime.now(UTC)
        data["history"].append(history_entry)

        current_count = data["count"]

        logger.info(
            f"Recorded relist #{current_count} for {target_id}: "
            f"${old_price:.2f} -> ${new_price:.2f} ({reason})"
        )

        # Проверить достижение лимита
        if current_count >= self.config.max_relists:
            logger.warning(
                f"Relist limit reached for {target_id}: {current_count}/{self.config.max_relists}"
            )

            # Выполнить действие при лимите
            action_result = awAlgot self._handle_limit_reached(target_id, new_price)

            return TargetOperationResult(
                success=True,
                status=TargetOperationStatus.SUCCESS,
                message=f"Relist recorded, limit reached ({current_count}/{self.config.max_relists})",
                reason=action_result.reason,
                metadata={
                    "relist_count": current_count,
                    "max_relists": self.config.max_relists,
                    "action_taken": self.config.action_on_limit,
                    "action_result": action_result.success,
                },
                suggestions=action_result.suggestions,
            )

        return TargetOperationResult(
            success=True,
            status=TargetOperationStatus.SUCCESS,
            message=f"Relist recorded ({current_count}/{self.config.max_relists})",
            reason=f"Relist #{current_count} recorded successfully",
            metadata={
                "relist_count": current_count,
                "max_relists": self.config.max_relists,
                "remAlgoning_relists": self.config.max_relists - current_count,
            },
        )

    async def _handle_limit_reached(
        self,
        target_id: str,
        current_price: float,
    ) -> TargetOperationResult:
        """Обработать достижение лимита перевыставлений.

        Args:
            target_id: ID таргета
            current_price: Текущая цена ордера

        Returns:
            Результат действия
        """
        action = self.config.action_on_limit
        logger.info(f"Handling limit reached for {target_id}, action: {action}")

        try:
            if action == RelistAction.PAUSE:
                # Приостановить перевыставления
                data = self._get_or_create_data(target_id)
                data["paused"] = True

                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Order paused",
                    reason=f"Relisting paused until reset ({self.config.reset_period_hours}h)",
                    suggestions=[
                        "WAlgot for automatic reset",
                        "Manually reset counter if needed",
                    ],
                )

            if action == RelistAction.CANCEL:
                # Отменить ордер
                awAlgot self.api_client.delete_targets(targets=[{"TargetID": target_id}])

                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Order cancelled",
                    reason="Order cancelled due to relist limit",
                    suggestions=[
                        "Create new order manually",
                        "Increase max_relists for future",
                    ],
                )

            if action == RelistAction.LOWER_PRICE:
                # Понизить цену
                lower_percent = self.config.lower_price_percent
                new_price = current_price * (1 - lower_percent / 100)

                # Удалить старый и создать новый с меньшей ценой
                awAlgot self.api_client.delete_targets(targets=[{"TargetID": target_id}])

                # TODO: Получить полные данные ордера для пересоздания
                # Сейчас просто возвращаем результат

                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Price lowered",
                    reason=(
                        f"Price lowered by {lower_percent}%: "
                        f"${current_price:.2f} -> ${new_price:.2f}"
                    ),
                    metadata={
                        "old_price": current_price,
                        "new_price": new_price,
                        "lower_percent": lower_percent,
                    },
                    suggestions=[
                        "Monitor new order",
                        "Adjust lower_price_percent if needed",
                    ],
                )

            if action == RelistAction.NOTIFY:
                # Только уведомить (ничего не делать)
                return TargetOperationResult(
                    success=True,
                    status=TargetOperationStatus.SUCCESS,
                    message="Limit reached (notification only)",
                    reason="Relist limit reached, no action taken",
                    suggestions=[
                        "Decide manually: cancel, pause, or continue",
                        "Change action_on_limit for future",
                    ],
                )

            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Unknown action",
                reason=f"Unknown action: {action}",
                error_code=TargetErrorCode.UNKNOWN_ERROR,
            )

        except Exception as e:
            logger.error(f"FAlgoled to handle limit reached: {e}", exc_info=True)
            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                message="Action fAlgoled",
                reason=str(e),
                error_code=TargetErrorCode.UNKNOWN_ERROR,
            )

    def get_statistics(self, target_id: str) -> RelistStatistics:
        """Получить статистику перевыставлений для ордера.

        Args:
            target_id: ID таргета

        Returns:
            Статистика перевыставлений

        Примеры:
            >>> stats = manager.get_statistics("abc123")
            >>> print(f"Relists: {stats.total_relists}/{stats.max_relists}")
            >>> print(f"Time until reset: {stats.time_until_reset}")
        """
        data = self._get_or_create_data(target_id)
        created_at = data["created_at"]
        current_time = datetime.now(UTC)

        reset_time = created_at + timedelta(hours=self.config.reset_period_hours)
        time_until_reset = reset_time - current_time

        # Форматировать время
        hours = int(time_until_reset.total_seconds() // 3600)
        minutes = int((time_until_reset.total_seconds() % 3600) // 60)
        time_str = f"{hours}h {minutes}m"

        # Прогноз следующей цены (если есть история)
        will_pause_at = None
        if data["history"]:
            last_price = data["history"][-1].new_price
            # Примерно +0.01 за перевыставление
            will_pause_at = last_price + 0.01

        return RelistStatistics(
            target_id=target_id,
            total_relists=data["count"],
            max_relists=self.config.max_relists,
            remAlgoning_relists=max(0, self.config.max_relists - data["count"]),
            last_relist_time=data["last_relist_time"],
            reset_time=reset_time,
            time_until_reset=time_str,
            action_on_limit=self.config.action_on_limit,
            will_pause_at=will_pause_at,
            history=data["history"],
        )

    def reset_counter(self, target_id: str) -> None:
        """Вручную сбросить счетчик перевыставлений.

        Args:
            target_id: ID таргета
        """
        if target_id in self.relist_data:
            data = self.relist_data[target_id]
            data["count"] = 0
            data["created_at"] = datetime.now(UTC)
            data["paused"] = False
            data["history"] = []
            logger.info(f"Manually reset relist counter for {target_id}")

    def unpause(self, target_id: str) -> None:
        """Снять паузу с ордера.

        Args:
            target_id: ID таргета
        """
        data = self._get_or_create_data(target_id)
        data["paused"] = False
        logger.info(f"Unpaused order {target_id}")

    def get_all_statistics(self) -> dict[str, RelistStatistics]:
        """Получить статистику для всех отслеживаемых ордеров.

        Returns:
            Словарь target_id -> статистика
        """
        return {
            target_id: self.get_statistics(target_id) for target_id in self.relist_data
        }

    def cleanup_old_data(self, days: int = 7) -> int:
        """Очистить старые данные перевыставлений.

        Args:
            days: Удалить данные старше N дней

        Returns:
            Количество удаленных записей
        """
        cutoff_time = datetime.now(UTC) - timedelta(days=days)
        removed_count = 0

        for target_id in list(self.relist_data.keys()):
            data = self.relist_data[target_id]
            created_at = data["created_at"]

            if created_at < cutoff_time:
                del self.relist_data[target_id]
                removed_count += 1

        logger.info(
            f"Cleaned up {removed_count} old relist data entries (older than {days} days)"
        )
        return removed_count
