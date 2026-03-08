"""Тесты для Prometheus экспорта метрик."""

import pytest

from src.utils.prometheus_exporter import MetricsCollector


class TestMetricsCollector:
    """Тесты для MetricsCollector."""

    def test_record_command(self):
        """Тест записи команды."""
        MetricsCollector.record_command("/start", 123456)
        # Метрика должна увеличиться
        # В реальном тесте проверяли бы значение через REGISTRY

    def test_record_api_request(self):
        """Тест записи API запроса."""
        MetricsCollector.record_api_request(
            endpoint="/market/items", method="GET", status=200, duration=0.5
        )

    def test_record_error(self):
        """Тест записи ошибки."""
        MetricsCollector.record_error("ValueError", "dmarket_api")

    def test_record_arbitrage_scan(self):
        """Тест записи сканирования арбитража."""
        MetricsCollector.record_arbitrage_scan(
            level="standard", game="csgo", duration=2.5, found=15
        )

    def test_record_target_created(self):
        """Тест записи создания таргета."""
        MetricsCollector.record_target_created("csgo", 123456)

    def test_record_trade(self):
        """Тест записи сделки."""
        MetricsCollector.record_trade("buy", "csgo", 10.50)

    def test_update_active_users(self):
        """Тест обновления активных пользователей."""
        MetricsCollector.update_active_users(1250)

    def test_update_balance(self):
        """Тест обновления баланса."""
        MetricsCollector.update_balance(123456, 5000.50)

    def test_get_metrics(self):
        """Тест получения метрик."""
        metrics = MetricsCollector.get_metrics()
        assert isinstance(metrics, bytes)
        assert b"dmarket_bot" in metrics


@pytest.mark.asyncio()
async def test_prometheus_server_creation():
    """Тест создания Prometheus сервера."""
    from src.utils.prometheus_server import PrometheusServer

    server = PrometheusServer(port=8001)
    assert server.port == 8001
    assert server.app is not None
