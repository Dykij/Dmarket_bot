"""
Автоматический сканер Steam-арбитража.

Работает в фоновом режиме, сканируя DMarket и сравнивая цены со Steam.
Отправляет уведомления при нахождении выгодных возможностей.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from telegram import Bot

from src.dmarket.dmarket_api import DMarketAPI
from src.dmarket.steam_arbitrage_enhancer import SteamArbitrageEnhancer

logger = logging.getLogger(__name__)


class AutoSteamArbitrageScanner:
    """
    Автоматический сканер арбитража DMarket <-> Steam.

    Функциональность:
    - Сканирует предметы на DMarket каждые N минут
    - Проверяет их цены в Steam
    - Отправляет уведомления при нахождении профита > min_roi%
    - Использует rate limiting для защиты от блокировки
    """

    def __init__(
        self,
        dmarket_api: DMarketAPI,
        telegram_bot: Bot,
        admin_chat_id: int,
        scan_interval_minutes: int = 10,
        min_roi_percent: float = 5.0,
        max_items_per_scan: int = 50,
        game: str = "csgo",
    ):
        """
        Инициализация автоматического сканера.

        Args:
            dmarket_api: Клиент DMarket API
            telegram_bot: Telegram бот для уведомлений
            admin_chat_id: Telegram ID администратора
            scan_interval_minutes: Интервал сканирования (по умолчанию 10 минут)
            min_roi_percent: Минимальный ROI для уведомления (по умолчанию 5%)
            max_items_per_scan: Максимум предметов за одно сканирование
            game: Игра для сканирования (csgo, dota2, rust, tf2)
        """
        self.dmarket_api = dmarket_api
        self.telegram_bot = telegram_bot
        self.admin_chat_id = admin_chat_id
        self.scan_interval = scan_interval_minutes * 60  # в секунды
        self.min_roi = min_roi_percent
        self.max_items = max_items_per_scan
        self.game = game

        # Steam enhancer для проверки цен
        self.steam_enhancer = SteamArbitrageEnhancer()

        # Статистика
        self.scans_completed = 0
        self.opportunities_found = 0
        self.last_scan_time: datetime | None = None

        # Флаг работы
        self._running = False
        self._task: asyncio.Task | None = None

        logger.info(
            f"AutoSteamArbitrageScanner initialized: game={game}, "
            f"interval={scan_interval_minutes}min, min_roi={min_roi_percent}%"
        )

    async def start(self) -> None:
        """Запустить автоматическое сканирование."""
        if self._running:
            logger.warning("Scanner already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info("Auto Steam Arbitrage Scanner started")

        # Отправить уведомление администратору
        try:
            await self.telegram_bot.send_message(
                chat_id=self.admin_chat_id,
                text=(
                    "🤖 <b>Steam Арбитраж Сканер запущен</b>\n\n"
                    f"🎮 Игра: {self.game}\n"
                    f"⏱ Интервал: {self.scan_interval // 60} минут\n"
                    f"📊 Минимальный ROI: {self.min_roi}%\n"
                    f"🔢 Макс. предметов: {self.max_items}"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.exception(f"Failed to send start notification: {e}")

    async def stop(self) -> None:
        """Остановить автоматическое сканирование."""
        if not self._running:
            logger.warning("Scanner is not running")
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Auto Steam Arbitrage Scanner stopped")

        # Отправить статистику
        try:
            await self.telegram_bot.send_message(
                chat_id=self.admin_chat_id,
                text=(
                    "🛑 <b>Steam Арбитраж Сканер остановлен</b>\n\n"
                    f"📊 Статистика:\n"
                    f"• Сканирований: {self.scans_completed}\n"
                    f"• Найдено возможностей: {self.opportunities_found}"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.exception(f"Failed to send stop notification: {e}")

    async def _scan_loop(self) -> None:
        """Основной цикл сканирования."""
        while self._running:
            try:
                await self._perform_scan()
                self.scans_completed += 1
                self.last_scan_time = datetime.now()

                # Ждать до следующего сканирования
                logger.info(f"Next scan in {self.scan_interval // 60} minutes")
                await asyncio.sleep(self.scan_interval)

            except asyncio.CancelledError:
                logger.info("Scan loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scan loop: {e}", exc_info=True)
                # Ждать 5 минут перед retry
                await asyncio.sleep(300)

    async def _perform_scan(self) -> None:
        """Выполнить одно сканирование."""
        logger.info(f"Starting scan #{self.scans_completed + 1} for {self.game}")

        try:
            # 1. Получить предметы с DMarket
            logger.debug("Fetching items from DMarket...")
            dmarket_response = await self.dmarket_api.get_aggregated_prices(
                game_id=self.game,
                limit=self.max_items,
            )

            if not dmarket_response or "aggregatedPrices" not in dmarket_response:
                logger.warning("No items returned from DMarket")
                return

            dmarket_items = dmarket_response["aggregatedPrices"]
            logger.info(f"Fetched {len(dmarket_items)} items from DMarket")

            # 2. Обогатить данными Steam
            logger.debug("Enhancing items with Steam data...")
            enhanced_items = await self.steam_enhancer.enhance_items(dmarket_items)
            logger.info(f"Enhanced {len(enhanced_items)} items with Steam data")

            # 3. Фильтровать по ROI
            opportunities = [item for item in enhanced_items if item.get("roi", 0) >= self.min_roi]

            if not opportunities:
                logger.info("No arbitrage opportunities found")
                return

            # 4. Отсортировать по ROI (лучшие первыми)
            opportunities.sort(key=lambda x: x.get("roi", 0), reverse=True)

            # 5. Отправить уведомления (топ-5)
            self.opportunities_found += len(opportunities)
            await self._send_opportunities_notification(opportunities[:5])

        except Exception as e:
            logger.error(f"Error performing scan: {e}", exc_info=True)

    async def _send_opportunities_notification(self, opportunities: list[dict[str, Any]]) -> None:
        """
        Отправить уведомление о найденных возможностях.

        Args:
            opportunities: Список возможностей (отсортированных по ROI)
        """
        if not opportunities:
            return

        # Формирование сообщения
        message_parts = [
            "🔥 <b>Найдены возможности Steam-арбитража!</b>\n",
        ]

        for i, item in enumerate(opportunities, 1):
            item_name = item.get("title", "Unknown")
            dmarket_price = item.get("dmarket_price", 0)
            steam_price = item.get("steam_price", 0)
            profit = item.get("profit", 0)
            roi = item.get("roi", 0)
            volume = item.get("volume", 0)

            message_parts.append(
                f"\n<b>{i}. {item_name}</b>\n"
                f"💰 DMarket: ${dmarket_price:.2f}\n"
                f"📈 Steam: ${steam_price:.2f}\n"
                f"💵 Профит: ${profit:.2f} ({roi:.1f}%)\n"
                f"📊 Объем: {volume} продаж/день"
            )

        message = "".join(message_parts)

        # Отправка уведомления
        try:
            await self.telegram_bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(f"Sent notification with {len(opportunities)} opportunities")
        except Exception as e:
            logger.exception(f"Failed to send opportunities notification: {e}")

    def get_status(self) -> dict[str, Any]:
        """
        Получить статус сканера.

        Returns:
            Словарь со статистикой
        """
        return {
            "running": self._running,
            "scans_completed": self.scans_completed,
            "opportunities_found": self.opportunities_found,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "config": {
                "game": self.game,
                "scan_interval_minutes": self.scan_interval // 60,
                "min_roi_percent": self.min_roi,
                "max_items_per_scan": self.max_items,
            },
        }
