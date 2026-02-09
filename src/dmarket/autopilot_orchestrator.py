"""Autopilot Orchestrator - координатор всех автономных систем.

Реализует концепцию "Одна кнопка - нажал и забыл":
- Автоматическое сканирование рынка
- Автоматическая покупка при выгодных условиях
- Автоматическая продажа с прибылью
- Мониторинг баланса и управление рисками
- Статистика и отчеты

Created: January 2, 2026
"""

import asyncio
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class AutopilotStats:
    """Статистика работы автопилота."""

    def __init__(self):
        self.start_time: datetime | None = None
        self.purchases: int = 0
        self.sales: int = 0
        self.total_spent_usd: float = 0.0
        self.total_earned_usd: float = 0.0
        self.failed_purchases: int = 0
        self.failed_sales: int = 0
        self.opportunities_found: int = 0
        self.opportunities_skipped: int = 0
        self.balance_checks: int = 0
        self.low_balance_warnings: int = 0

    def record_purchase(self, amount_usd: float, success: bool):
        """Записать покупку."""
        if success:
            self.purchases += 1
            self.total_spent_usd += amount_usd
        else:
            self.failed_purchases += 1

    def record_sale(self, amount_usd: float, success: bool):
        """Записать продажу."""
        if success:
            self.sales += 1
            self.total_earned_usd += amount_usd
        else:
            self.failed_sales += 1

    def record_opportunity(self, taken: bool):
        """Записать найденную возможность."""
        self.opportunities_found += 1
        if not taken:
            self.opportunities_skipped += 1

    @property
    def net_profit_usd(self) -> float:
        """Чистая прибыль."""
        return self.total_earned_usd - self.total_spent_usd

    @property
    def roi_percent(self) -> float:
        """Return on Investment в процентах."""
        if self.total_spent_usd == 0:
            return 0.0
        return (self.net_profit_usd / self.total_spent_usd) * 100

    @property
    def uptime_minutes(self) -> int:
        """Время работы в минутах."""
        if not self.start_time:
            return 0
        return int((datetime.now() - self.start_time).total_seconds() / 60)

    def to_dict(self) -> dict[str, Any]:
        """Конвертировать в словарь."""
        return {
            "uptime_minutes": self.uptime_minutes,
            "purchases": self.purchases,
            "sales": self.sales,
            "total_spent_usd": self.total_spent_usd,
            "total_earned_usd": self.total_earned_usd,
            "net_profit_usd": self.net_profit_usd,
            "roi_percent": self.roi_percent,
            "failed_purchases": self.failed_purchases,
            "failed_sales": self.failed_sales,
            "opportunities_found": self.opportunities_found,
            "opportunities_skipped": self.opportunities_skipped,
            "balance_checks": self.balance_checks,
            "low_balance_warnings": self.low_balance_warnings,
        }


class AutopilotConfig:
    """Конфигурация автопилота."""

    def __init__(
        self,
        games: list[str] | None = None,
        min_discount_percent: float = 30.0,
        max_price_usd: float = 100.0,
        min_balance_threshold_usd: float = 10.0,
        balance_check_interval_minutes: int = 5,
        status_report_interval_minutes: int = 60,
        auto_sell_markup_percent: float = 15.0,
        inventory_check_interval_minutes: int = 2,
    ):
        """Initialize autopilot configuration.

        Args:
            games: Список игр для сканирования
            min_discount_percent: Минимальная скидка для покупки
            max_price_usd: Максимальная цена для покупки
            min_balance_threshold_usd: Минимальный баланс для продолжения
            balance_check_interval_minutes: Интервал проверки баланса
            status_report_interval_minutes: Интервал отправки статуса
            auto_sell_markup_percent: Наценка при продаже
            inventory_check_interval_minutes: Интервал проверки инвентаря
        """
        self.games = games or ["csgo", "dota2", "rust", "tf2"]
        self.min_discount_percent = min_discount_percent
        self.max_price_usd = max_price_usd
        self.min_balance_threshold_usd = min_balance_threshold_usd
        self.balance_check_interval = balance_check_interval_minutes * 60
        self.status_report_interval = status_report_interval_minutes * 60
        self.auto_sell_markup_percent = auto_sell_markup_percent
        self.inventory_check_interval = inventory_check_interval_minutes * 60


class AutopilotOrchestrator:
    """Оркестратор автономных торговых систем."""

    def __init__(
        self,
        scanner_manager,
        auto_buyer,
        auto_seller,
        api_client,
        config: AutopilotConfig | None = None,
    ):
        """Initialize orchestrator.

        Args:
            scanner_manager: Менеджер сканирования
            auto_buyer: Модуль автопокупки
            auto_seller: Модуль автопродажи
            api_client: DMarket API клиент
            config: Конфигурация автопилота
        """
        self.scanner = scanner_manager
        self.buyer = auto_buyer
        self.seller = auto_seller
        self.api = api_client
        self.config = config or AutopilotConfig()

        self.is_running = False
        self.stats = AutopilotStats()
        self.telegram_bot = None
        self.user_id = None
        self._tasks: list[asyncio.Task] = []

        # Link auto-buyer with auto-seller for the "bridge" functionality
        # This enables automatic sale scheduling after purchase
        if hasattr(self.buyer, "set_auto_seller") and self.seller:
            self.buyer.set_auto_seller(self.seller)
            logger.info("autopilot_buyer_seller_linked")

        logger.info(
            "autopilot_orchestrator_initialized",
            games=self.config.games,
            min_discount=self.config.min_discount_percent,
            max_price=self.config.max_price_usd,
        )

    async def start(self, telegram_bot=None, user_id: int | None = None):
        """Запустить автопилот.

        Args:
            telegram_bot: Telegram bot instance для отправки уведомлений
            user_id: ID пользователя для уведомлений
        """
        if self.is_running:
            logger.warning("autopilot_already_running")
            return

        self.is_running = True
        self.stats.start_time = datetime.now()
        self.telegram_bot = telegram_bot
        self.user_id = user_id

        logger.info(
            "autopilot_starting",
            games=self.config.games,
            min_discount=self.config.min_discount_percent,
        )

        # Настроить автопокупку
        self.buyer.config.enabled = True
        self.buyer.config.min_discount_percent = self.config.min_discount_percent
        self.buyer.config.max_price_usd = self.config.max_price_usd

        # Настроить автопродажу
        if hasattr(self.seller, "enabled"):
            self.seller.enabled = True

        # Запустить фоновые задачи
        self._tasks = [
            asyncio.create_task(self._balance_monitor()),
            asyncio.create_task(self._status_reporter()),
            asyncio.create_task(self._inventory_monitor()),
        ]

        # Запустить сканер если он не запущен (безопасная проверка)
        try:
            if hasattr(self.scanner, "is_scanning") and not self.scanner.is_scanning:
                await self.scanner.start_continuous_scanning(
                    games=self.config.games, level="medium"
                )
            elif hasattr(self.scanner, "start_continuous_scanning"):
                # Просто вызываем старт, сканер сам проверит состояние
                await self.scanner.start_continuous_scanning(
                    games=self.config.games, level="medium"
                )
        except Exception as e:
            logger.warning(f"scanner_start_warning: {e}")

        logger.info("autopilot_started", tasks=len(self._tasks))

        # Отправить уведомление пользователю
        if self.telegram_bot and self.user_id:
            await self._notify_user(
                "🚀 <b>АВТОПИЛОТ ЗАПУЩЕН!</b>\n\n"
                f"✅ Сканирование: {', '.join(self.config.games).upper()}\n"
                f"✅ Автопокупка: Скидка ≥ {self.config.min_discount_percent}%\n"
                f"✅ Макс. цена: ${self.config.max_price_usd:.2f}\n"
                f"✅ Автопродажа: +{self.config.auto_sell_markup_percent}% profit\n"
                f"✅ Мониторинг баланса: каждые {self.config.balance_check_interval // 60} мин\n\n"
                "Для остановки: /autopilot_stop"
            )

    async def stop(self):
        """Остановить автопилот."""
        if not self.is_running:
            logger.warning("autopilot_not_running")
            return

        self.is_running = False

        logger.info("autopilot_stopping")

        # Остановить сканер
        if hasattr(self.scanner, "stop_scanning"):
            await self.scanner.stop_scanning()

        # Отключить автопокупку и автопродажу
        self.buyer.config.enabled = False
        if hasattr(self.seller, "enabled"):
            self.seller.enabled = False

        # Отменить фоновые задачи
        for task in self._tasks:
            task.cancel()

        # Дождаться завершения задач
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("autopilot_stopped", stats=self.stats.to_dict())

        # Отправить финальную статистику
        if self.telegram_bot and self.user_id:
            await self._send_final_stats()

    async def _balance_monitor(self):
        """Мониторинг баланса каждые N минут."""
        logger.info("balance_monitor_started", interval=self.config.balance_check_interval)

        while self.is_running:
            try:
                await asyncio.sleep(self.config.balance_check_interval)

                # Получить баланс
                balance_data = await self.api.get_balance()
                # get_balance() returns {"balance": float} in USD (already converted from cents)
                usd = (
                    float(balance_data.get("balance", 0)) if isinstance(balance_data, dict) else 0.0
                )

                self.stats.balance_checks += 1

                logger.info("balance_checked", balance_usd=usd)

                # Проверить порог
                if usd < self.config.min_balance_threshold_usd:
                    self.stats.low_balance_warnings += 1

                    logger.warning(
                        "low_balance_detected",
                        balance=usd,
                        threshold=self.config.min_balance_threshold_usd,
                    )

                    # Приостановить покупки
                    self.buyer.config.enabled = False

                    # Уведомить пользователя
                    await self._notify_user(
                        f"⚠️ <b>НИЗКИЙ БАЛАНС!</b>\n\n"
                        f"Текущий баланс: ${usd:.2f}\n"
                        f"Порог: ${self.config.min_balance_threshold_usd:.2f}\n\n"
                        f"❌ Автопокупка приостановлена\n"
                        f"✅ Автопродажа продолжает работу\n\n"
                        f"Пополните баланс для продолжения."
                    )
                # Возобновить покупки если были приостановлены
                elif not self.buyer.config.enabled and self.is_running:
                    self.buyer.config.enabled = True
                    await self._notify_user(
                        f"✅ <b>Баланс восстановлен</b>\n\n"
                        f"Текущий баланс: ${usd:.2f}\n"
                        f"Автопокупка возобновлена!"
                    )

            except Exception as e:
                logger.exception("balance_monitor_error", error=str(e))
                await asyncio.sleep(60)  # Подождать минуту при ошибке

    async def _status_reporter(self):
        """Отправка периодических отчетов."""
        logger.info("status_reporter_started", interval=self.config.status_report_interval)

        while self.is_running:
            try:
                await asyncio.sleep(self.config.status_report_interval)

                # Отправить статистику
                await self._send_status_report()

            except Exception as e:
                logger.exception("status_reporter_error", error=str(e))

    async def _inventory_monitor(self):
        """Мониторинг инвентаря для автопродажи."""
        logger.info("inventory_monitor_started", interval=self.config.inventory_check_interval)

        while self.is_running:
            try:
                await asyncio.sleep(self.config.inventory_check_interval)

                # Проверить инвентарь и выставить предметы на продажу
                if hasattr(self.seller, "process_inventory"):
                    result = await self.seller.process_inventory()
                    if result:
                        logger.info("inventory_processed", items_listed=result)

            except Exception as e:
                logger.exception("inventory_monitor_error", error=str(e))

    async def _send_status_report(self):
        """Отправить отчет о статусе."""
        if not self.telegram_bot or not self.user_id:
            return

        stats = self.stats.to_dict()

        message = (
            f"📊 <b>Отчет автопилота</b>\n\n"
            f"⏱️ Работает: {stats['uptime_minutes']} минут\n\n"
            f"<b>Покупки:</b>\n"
            f"• Успешных: {stats['purchases']}\n"
            f"• Неудачных: {stats['failed_purchases']}\n"
            f"• Потрачено: ${stats['total_spent_usd']:.2f}\n\n"
            f"<b>Продажи:</b>\n"
            f"• Успешных: {stats['sales']}\n"
            f"• Неудачных: {stats['failed_sales']}\n"
            f"• Выручка: ${stats['total_earned_usd']:.2f}\n\n"
            f"<b>Итого:</b>\n"
            f"💰 Прибыль: ${stats['net_profit_usd']:.2f}\n"
            f"📈 ROI: {stats['roi_percent']:.1f}%\n\n"
            f"<b>Возможности:</b>\n"
            f"• Найдено: {stats['opportunities_found']}\n"
            f"• Пропущено: {stats['opportunities_skipped']}\n\n"
            f"<b>Баланс:</b>\n"
            f"• Проверок: {stats['balance_checks']}\n"
            f"• Предупреждений: {stats['low_balance_warnings']}"
        )

        await self._notify_user(message)

    async def _send_final_stats(self):
        """Отправить финальную статистику при остановке."""
        stats = self.stats.to_dict()

        message = (
            f"⏸️ <b>АВТОПИЛОТ ОСТАНОВЛЕН</b>\n\n"
            f"⏱️ Работал: {stats['uptime_minutes']} минут\n\n"
            f"<b>Результаты:</b>\n"
            f"• Куплено: {stats['purchases']} предметов\n"
            f"• Продано: {stats['sales']} предметов\n"
            f"• Потрачено: ${stats['total_spent_usd']:.2f}\n"
            f"• Выручка: ${stats['total_earned_usd']:.2f}\n"
            f"• Прибыль: ${stats['net_profit_usd']:.2f}\n"
            f"• ROI: {stats['roi_percent']:.1f}%\n\n"
            f"{'✅' if stats['net_profit_usd'] > 0 else '❌'} "
            f"{'Прибыльная' if stats['net_profit_usd'] > 0 else 'Убыточная'} сессия"
        )

        await self._notify_user(message)

    async def _notify_user(self, message: str):
        """Отправить уведомление пользователю.

        Args:
            message: Текст сообщения (HTML)
        """
        if not self.telegram_bot or not self.user_id:
            return

        try:
            from telegram.constants import ParseMode

            await self.telegram_bot.send_message(
                chat_id=self.user_id, text=message, parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.exception("failed_to_send_notification", error=str(e))

    def get_stats(self) -> dict[str, Any]:
        """Получить текущую статистику.

        Returns:
            Словарь со статистикой
        """
        return self.stats.to_dict()

    def is_active(self) -> bool:
        """Проверить активен ли автопилот.

        Returns:
            True если автопилот работает
        """
        return self.is_running
