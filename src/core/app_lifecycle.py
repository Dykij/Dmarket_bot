"""Application lifecycle management module.

This module handles application startup and shutdown sequences.
"""

import asyncio
import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from src.core.application import Application

logger = logging.getLogger(__name__)


class ApplicationLifecycle:
    """Manages application startup and shutdown lifecycle."""

    def __init__(self, app: "Application") -> None:
        """Initialize lifecycle manager.

        Args:
            app: Application instance to manage

        """
        self.app = app

    async def start_services(self) -> None:
        """Start all application services in correct order."""
        logger.info("Starting application services...")

        # Start Daily Report Scheduler
        if self.app.daily_report_scheduler:
            await self.app.daily_report_scheduler.start()
            logger.info("✅ Daily Report Scheduler started")

        # Start AI Training Scheduler
        if self.app.ai_scheduler:
            await self.app.ai_scheduler.start()
            logger.info("✅ AI Training Scheduler started (nightly training at 03:00 UTC)")

        # Start Scanner Manager
        if self.app.scanner_manager and not self.app.config.testing:
            await self._start_scanner()

        # Start Inventory Manager
        if self.app.inventory_manager and not self.app.config.testing:
            await self._start_inventory_manager()

        # Start WebSocket Listener
        if self.app.websocket_manager:
            await self.app.websocket_manager.start()
            logger.info("✅ WebSocket Listener started")

        # Start Health Check Monitor
        if self.app.health_check_monitor:
            asyncio.create_task(self.app.health_check_monitor.start())
            logger.info("✅ Health Check Monitor started")

        # Start Bot Integrator
        if hasattr(self.app, "bot_integrator") and self.app.bot_integrator:
            await self.app.bot_integrator.start()
            logger.info("✅ Bot Integrator started")

        # Start Prometheus Exporter
        if hasattr(self.app, "prometheus_server") and self.app.prometheus_server:
            await self.app.prometheus_server.start()
            logger.info("✅ Prometheus Metrics Exporter started")

    async def _start_scanner(self) -> None:
        """Start the scanner manager."""
        logger.info("Starting Scanner Manager...")

        games_to_scan = getattr(
            self.app.config, "arbitrage_games", ["csgo", "dota2", "rust", "tf2"]
        )
        arbitrage_level = getattr(self.app.config, "arbitrage_level", "medium")
        cleanup_interval = getattr(self.app.config, "cleanup_interval_hours", 6.0)

        self.app._scanner_task = asyncio.create_task(
            self.app.scanner_manager.run_continuous(
                games=games_to_scan,
                level=arbitrage_level,
                enable_cleanup=True,
                cleanup_interval_hours=cleanup_interval,
            )
        )

        logger.info(
            f"✅ Scanner Manager started: "
            f"games={games_to_scan}, level={arbitrage_level}"
        )

    async def _start_inventory_manager(self) -> None:
        """Start the inventory manager if undercutting is enabled."""
        undercut_enabled = (
            self.app.config.inventory.auto_sell
            if self.app.config and hasattr(self.app.config, "inventory")
            else False
        )

        if undercut_enabled:
            logger.info("Starting Inventory Manager (Undercutting)...")
            asyncio.create_task(self.app.inventory_manager.refresh_inventory_loop())
            logger.info("✅ Inventory Manager started")
        else:
            logger.info("Inventory Manager initialized but undercutting is disabled")

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown the application.

        Args:
            timeout: Maximum time to wait for graceful shutdown

        """
        from src.telegram_bot.health_check import health_check_server

        logger.info("=" * 60)
        logger.info("🛑 Initiating graceful shutdown...")
        logger.info("=" * 60)

        if health_check_server:
            health_check_server.update_status("stopping")

        start_time = asyncio.get_event_loop().time()

        try:
            # Step 1: Stop monitoring components
            await self._stop_monitoring_components()

            # Step 2: Stop Scanner Manager
            await self._stop_scanner()

            # Step 3: Stop Bot Integrator
            await self._stop_integrator()

            # Step 4: Stop accepting new updates
            await self._stop_updates()

            # Step 5: Wait for active tasks
            await self._wait_for_tasks(timeout, start_time)

            # Step 6: Stop schedulers
            await self._stop_schedulers()

            # Step 7: Stop Telegram Bot
            await self._stop_bot()

            # Step 8: Close API connections
            await self._close_api_connections()

            # Step 9: Close database
            await self._close_database()

            # Step 10: Stop health check server
            await self._stop_health_check_server()

            # Flush logs
            self._flush_logs()

        except Exception as e:
            logger.exception(f"❌ Error during shutdown: {e}")

        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info("=" * 60)
        logger.info(f"✅ Application shutdown complete in {elapsed:.2f}s")
        logger.info("=" * 60)

    async def _stop_monitoring_components(self) -> None:
        """Stop health check and websocket components."""
        logger.info("Stopping monitoring components...")

        if hasattr(self.app, "prometheus_server") and self.app.prometheus_server:
            try:
                await asyncio.wait_for(
                    self.app.prometheus_server.stop(),
                    timeout=5.0,
                )
                logger.info("✅ Prometheus Metrics Exporter stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping Prometheus Exporter: {e}")

        if self.app.health_check_monitor:
            try:
                await asyncio.wait_for(
                    self.app.health_check_monitor.stop(),
                    timeout=5.0,
                )
                logger.info("✅ Health Check Monitor stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping Health Check: {e}")

        if self.app.websocket_manager:
            try:
                await asyncio.wait_for(
                    self.app.websocket_manager.stop(),
                    timeout=5.0,
                )
                logger.info("✅ WebSocket Listener stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping WebSocket: {e}")

    async def _stop_scanner(self) -> None:
        """Stop scanner manager."""
        if not self.app.scanner_manager:
            return

        logger.info("Stopping Scanner Manager...")
        try:
            await asyncio.wait_for(
                self.app.scanner_manager.stop(),
                timeout=10.0,
            )
            if self.app._scanner_task:
                self.app._scanner_task.cancel()
                try:
                    await self.app._scanner_task
                except asyncio.CancelledError:
                    pass
            logger.info("✅ Scanner Manager stopped")
        except Exception as e:
            logger.warning(f"⚠️ Error stopping Scanner Manager: {e}")

    async def _stop_integrator(self) -> None:
        """Stop Bot Integrator."""
        if not hasattr(self.app, "bot_integrator") or not self.app.bot_integrator:
            return

        logger.info("Stopping Bot Integrator...")
        try:
            await asyncio.wait_for(
                self.app.bot_integrator.stop(),
                timeout=10.0,
            )
            logger.info("✅ Bot Integrator stopped")
        except Exception as e:
            logger.warning(f"⚠️ Error stopping Bot Integrator: {e}")

    async def _stop_updates(self) -> None:
        """Stop accepting new Telegram updates."""
        if not self.app.bot:
            return

        logger.info("Stopping new updates...")
        try:
            if self.app.bot.updater and self.app.bot.updater.running:
                await asyncio.wait_for(
                    self.app.bot.updater.stop(),
                    timeout=5.0,
                )
                logger.info("✅ Stopped accepting new updates")
        except Exception as e:
            logger.warning(f"⚠️ Error stopping updater: {e}")

    async def _wait_for_tasks(self, timeout: float, start_time: float) -> None:
        """Wait for active tasks to complete."""
        logger.info("Waiting for active tasks...")
        active_tasks = [
            task
            for task in asyncio.all_tasks()
            if not task.done() and task != asyncio.current_task()
        ]

        if not active_tasks:
            return

        logger.info(f"  Found {len(active_tasks)} active tasks")
        try:
            elapsed = asyncio.get_event_loop().time() - start_time
            await asyncio.wait_for(
                asyncio.gather(*active_tasks, return_exceptions=True),
                timeout=min(10.0, timeout - elapsed),
            )
            logger.info("✅ All tasks completed")
        except TimeoutError:
            logger.warning("⚠️ Timeout waiting for tasks, cancelling...")
            for task in active_tasks:
                if not task.done():
                    task.cancel()

    async def _stop_schedulers(self) -> None:
        """Stop scheduler components."""
        logger.info("Stopping schedulers...")

        if self.app.daily_report_scheduler:
            try:
                await asyncio.wait_for(
                    self.app.daily_report_scheduler.stop(),
                    timeout=5.0,
                )
                logger.info("✅ Daily Report Scheduler stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping scheduler: {e}")

        if self.app.ai_scheduler:
            try:
                await asyncio.wait_for(
                    self.app.ai_scheduler.stop(),
                    timeout=5.0,
                )
                logger.info("✅ AI Training Scheduler stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping AI scheduler: {e}")

    async def _stop_bot(self) -> None:
        """Stop Telegram bot."""
        if not self.app.bot:
            return

        logger.info("Stopping Telegram Bot...")
        try:
            if self.app.bot.running:
                await asyncio.wait_for(
                    self.app.bot.stop(),
                    timeout=5.0,
                )
            await asyncio.wait_for(
                self.app.bot.shutdown(),
                timeout=5.0,
            )
            logger.info("✅ Telegram Bot stopped")
        except Exception as e:
            logger.warning(f"⚠️ Error stopping bot: {e}")

    async def _close_api_connections(self) -> None:
        """Close DMarket API connections."""
        if not self.app.dmarket_api:
            return

        logger.info("Closing DMarket API connections...")
        try:
            await asyncio.wait_for(
                self.app.dmarket_api._close_client(),
                timeout=3.0,
            )
            logger.info("✅ DMarket API connections closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing API: {e}")

    async def _close_database(self) -> None:
        """Close database connections."""
        if not self.app.database:
            return

        logger.info("Closing database connections...")
        try:
            await asyncio.wait_for(
                self.app.database.close(),
                timeout=5.0,
            )
            logger.info("✅ Database connections closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing database: {e}")

    async def _stop_health_check_server(self) -> None:
        """Stop health check server."""
        from src.telegram_bot.health_check import health_check_server

        logger.info("Stopping health check server...")
        try:
            if health_check_server:
                await health_check_server.stop()
            logger.info("✅ Health check server stopped")
        except Exception as e:
            logger.warning(f"⚠️ Error stopping health check: {e}")

    def _flush_logs(self) -> None:
        """Flush all log handlers."""
        logger.info("Flushing logs...")
        for handler in logging.root.handlers:
            try:
                handler.flush()
            except Exception:
                pass
