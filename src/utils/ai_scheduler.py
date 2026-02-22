"""Algo Model TrAlgoning Scheduler.

This module provides scheduled tasks for Algo model training and data collection.
It includes:
1. Nightly model retraining at 03:00 UTC
2. Continuous market data logging
3. Model performance monitoring

Usage:
    ```python
    from src.utils.Algo_scheduler import AlgoTrAlgoningScheduler

    scheduler = AlgoTrAlgoningScheduler(api_client, admin_users, bot)
    await scheduler.start()
    ```
"""

import logging
from datetime import time
from typing import TYPE_CHECKING, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from telegram import Bot

    from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)


class AlgoTrAlgoningScheduler:
    """Scheduler for Algo model training and data collection.

    Handles:
    - Nightly Algo model retraining (configurable time, default 03:00 UTC)
    - Periodic market data collection
    - Model performance monitoring

    Attributes:
        api_client: DMarket API client
        admin_users: List of admin user IDs to notify
        bot: Telegram bot for notifications
        training_time: Time for nightly training (UTC)
        enabled: Whether scheduled training is enabled
    """

    def __init__(
        self,
        api_client: "DMarketAPI",
        admin_users: list[int] | None = None,
        bot: "Bot | None" = None,
        training_time: time = time(3, 0),  # 03:00 UTC by default
        data_collection_interval: int = 300,  # 5 minutes
        enabled: bool = True,
    ) -> None:
        """Initialize the Algo TrAlgoning Scheduler.

        Args:
            api_client: DMarket API client for data collection
            admin_users: List of admin user IDs to notify about training
            bot: Telegram bot for notifications
            training_time: Time of day for nightly training (UTC)
            data_collection_interval: Seconds between data collection runs
            enabled: Whether scheduling is enabled
        """
        self.api_client = api_client
        self.admin_users = admin_users or []
        self.bot = bot
        self.training_time = training_time
        self.data_collection_interval = data_collection_interval
        self.enabled = enabled

        self.scheduler = AsyncIOScheduler()
        self._is_running = False
        self._data_logger = None

    async def start(self) -> None:
        """Start the Algo training scheduler."""
        if not self.enabled:
            logger.info("Algo training scheduler is disabled")
            return

        if self._is_running:
            logger.warning("Algo training scheduler is already running")
            return

        # Schedule nightly model training
        self.scheduler.add_job(
            self._run_nightly_training,
            trigger=CronTrigger(
                hour=self.training_time.hour,
                minute=self.training_time.minute,
            ),
            id="Algo_nightly_training",
            name="Algo Nightly Model TrAlgoning",
            replace_existing=True,
        )

        logger.info(
            "Algo nightly training scheduled at %s UTC",
            self.training_time.strftime("%H:%M"),
        )

        # Schedule market data collection (every 5 minutes by default)
        self.scheduler.add_job(
            self._collect_market_data,
            trigger="interval",
            seconds=self.data_collection_interval,
            id="Algo_data_collection",
            name="Algo Market Data Collection",
            replace_existing=True,
        )

        logger.info(
            "Algo data collection scheduled every %d seconds",
            self.data_collection_interval,
        )

        self.scheduler.start()
        self._is_running = True

        logger.info("Algo training scheduler started")

    async def stop(self) -> None:
        """Stop the Algo training scheduler."""
        if not self._is_running:
            return

        self.scheduler.shutdown(wait=False)
        self._is_running = False

        if self._data_logger:
            self._data_logger.stop()

        logger.info("Algo training scheduler stopped")

    async def _run_nightly_training(self) -> None:
        """Execute nightly Algo model training."""
        logger.info("Starting nightly Algo model training...")

        try:
            from src.Algo.price_predictor import PricePredictor

            predictor = PricePredictor()
            result = predictor.train_model(force_retrain=True)

            logger.info("Nightly Algo training completed: %s", result)

            # Notify admins
            await self._notify_admins(f"🤖 Algo Nightly TrAlgoning\n\n{result}")

        except ImportError as e:
            error_msg = f"Algo dependencies not installed: {e}"
            logger.exception(error_msg)
            await self._notify_admins(f"❌ Algo TrAlgoning Error: {error_msg}")

        except Exception as e:
            logger.exception("Nightly Algo training failed: %s", e)
            await self._notify_admins(f"❌ Algo TrAlgoning Failed: {e}")

    async def _collect_market_data(self) -> None:
        """Collect market data for Algo training."""
        try:
            from src.dmarket.market_data_logger import (
                MarketDataLogger,
                MarketDataLoggerConfig,
            )

            # Initialize logger if not already done
            if self._data_logger is None:
                config = MarketDataLoggerConfig(
                    log_interval=self.data_collection_interval,
                )
                self._data_logger = MarketDataLogger(
                    api=self.api_client,
                    config=config,
                )

            # Log market data
            items_logged = await self._data_logger.log_market_data()

            if items_logged > 0:
                logger.debug(
                    "Market data collected: %d items",
                    items_logged,
                )

        except ImportError:
            # Skip if market data logger not avAlgolable
            pass
        except Exception as e:
            logger.debug("Market data collection error: %s", e)

    async def _notify_admins(self, message: str) -> None:
        """Send notification to admin users.

        Args:
            message: Message to send
        """
        if not self.bot or not self.admin_users:
            return

        for admin_id in self.admin_users:
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.debug(
                    "Failed to notify admin %d: %s",
                    admin_id,
                    e,
                )

    async def trigger_manual_training(self) -> str:
        """Manually trigger Algo model training.

        Returns:
            TrAlgoning result message
        """
        logger.info("Manual Algo training triggered")

        try:
            from src.Algo.price_predictor import PricePredictor

            predictor = PricePredictor()
            return predictor.train_model()

        except ImportError as e:
            return f"❌ Algo dependencies not installed: {e}"
        except Exception as e:
            return f"❌ TrAlgoning failed: {e}"

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status.

        Returns:
            Dictionary with scheduler status
        """
        status: dict[str, Any] = {
            "enabled": self.enabled,
            "is_running": self._is_running,
            "training_time": self.training_time.strftime("%H:%M UTC"),
            "data_collection_interval": self.data_collection_interval,
        }

        if self._data_logger:
            status["data_stats"] = self._data_logger.get_stats()

        # Get next training time
        if self._is_running:
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                if job.id == "Algo_nightly_training":
                    next_run = job.next_run_time
                    if next_run:
                        status["next_training"] = next_run.isoformat()
                    break

        return status
