"""HTTP сервер для экспорта Prometheus метрик."""

import asyncio

import structlog
from aiohttp import web

from src.utils.prometheus_exporter import MetricsCollector

logger = structlog.get_logger(__name__)


class PrometheusServer:
    """HTTP сервер для Prometheus метрик."""

    def __init__(
        self,
        host: str = "127.0.0.1",  # По умолчанию localhost для безопасности
        port: int = 9090,
    ) -> None:
        """
        Инициализация сервера.

        Args:
            host: Хост для биндинга (default: 127.0.0.1 для безопасности)
            port: Порт для HTTP сервера

        Security:
            - Default host is 127.0.0.1 (localhost) to prevent external access
            - In production, set host to "0.0.0.0" only behind reverse proxy/firewall
            - Use PROMETHEUS_HOST environment variable to configure
        """
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

        # Роуты
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.app.router.add_get("/health", self.health_handler)

    async def metrics_handler(self, request: web.Request) -> web.Response:
        """Обработчик /metrics endpoint."""
        try:
            import psutil

            from src.utils.prometheus_metrics import cpu_usage, ram_usage
            cpu_usage.set(psutil.cpu_percent())
            ram_usage.set(psutil.virtual_memory().percent)
        except ImportError:
            logger.warning("psutil_not_found_metrics_degraded")
        except Exception as e:
            logger.error("metrics_update_failed", error=str(e))

        metrics = MetricsCollector.get_metrics()
        return web.Response(body=metrics, content_type="text/plain", charset="utf-8")

    async def health_handler(self, request: web.Request) -> web.Response:
        """Обработчик /health endpoint."""
        return web.json_response({"status": "ok"})

    async def start(self) -> None:
        """Запустить сервер."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        logger.info("prometheus_server_started", host=self.host, port=self.port)

    async def stop(self) -> None:
        """Остановить сервер."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

        logger.info("prometheus_server_stopped")


async def run_prometheus_server(port: int = 8000) -> None:
    """
    Запустить Prometheus сервер.

    Args:
        port: Порт для сервера
    """
    server = PrometheusServer(port)
    await server.start()

    try:
        # Держать сервер запущенным
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await server.stop()
