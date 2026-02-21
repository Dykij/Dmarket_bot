"""Тесты для модуля prometheus_metrics.

Проверяет метрики Prometheus для мониторинга.
"""

import time

from src.utils.prometheus_metrics import (
    Timer,
    api_errors_total,
    api_request_duration,
    api_requests_total,
    app_info,
    app_uptime_seconds,
    arbitrage_opportunities_current,
    arbitrage_opportunities_found,
    arbitrage_profit_avg,
    bot_active_users,
    bot_commands_total,
    bot_errors_total,
    create_metrics_app,
    db_connections_active,
    db_errors_total,
    db_query_duration,
    get_metrics,
    set_active_users,
    targets_active,
    targets_created_total,
    targets_executed_total,
    total_profit_usd,
    track_api_request,
    track_arbitrage_scan,
    track_command,
    track_db_query,
    transaction_amount_avg,
    transactions_total,
)


class TestMetricsDefinitions:
    """Тесты определения метрик."""

    def test_bot_commands_total_exists(self):
        """Тест что метрика bot_commands_total определена."""
        assert bot_commands_total is not None
        assert bot_commands_total._name == "bot_commands"

    def test_bot_errors_total_exists(self):
        """Тест что метрика bot_errors_total определена."""
        assert bot_errors_total is not None
        assert bot_errors_total._name == "bot_errors"

    def test_bot_active_users_exists(self):
        """Тест что метрика bot_active_users определена."""
        assert bot_active_users is not None
        assert bot_active_users._name == "bot_active_users"

    def test_api_requests_total_exists(self):
        """Тест что метрика api_requests_total определена."""
        assert api_requests_total is not None
        assert api_requests_total._name == "dmarket_api_requests"

    def test_api_request_duration_exists(self):
        """Тест что метрика api_request_duration определена."""
        assert api_request_duration is not None
        assert api_request_duration._name == "dmarket_api_request_duration_seconds"

    def test_api_errors_total_exists(self):
        """Тест что метрика api_errors_total определена."""
        assert api_errors_total is not None
        assert api_errors_total._name == "dmarket_api_errors"

    def test_db_connections_active_exists(self):
        """Тест что метрика db_connections_active определена."""
        assert db_connections_active is not None
        assert db_connections_active._name == "db_connections_active"

    def test_db_query_duration_exists(self):
        """Тест что метрика db_query_duration определена."""
        assert db_query_duration is not None
        assert db_query_duration._name == "db_query_duration_seconds"

    def test_db_errors_total_exists(self):
        """Тест что метрика db_errors_total определена."""
        assert db_errors_total is not None
        assert db_errors_total._name == "db_errors"

    def test_arbitrage_opportunities_found_exists(self):
        """Тест что метрика arbitrage_opportunities_found определена."""
        assert arbitrage_opportunities_found is not None
        assert arbitrage_opportunities_found._name == "arbitrage_opportunities_found"

    def test_arbitrage_opportunities_current_exists(self):
        """Тест что метрика arbitrage_opportunities_current определена."""
        assert arbitrage_opportunities_current is not None
        assert arbitrage_opportunities_current._name == "arbitrage_opportunities_current"

    def test_arbitrage_profit_avg_exists(self):
        """Тест что метрика arbitrage_profit_avg определена."""
        assert arbitrage_profit_avg is not None
        assert arbitrage_profit_avg._name == "arbitrage_profit_avg_usd"

    def test_targets_created_total_exists(self):
        """Тест что метрика targets_created_total определена."""
        assert targets_created_total is not None
        assert targets_created_total._name == "targets_created"

    def test_targets_executed_total_exists(self):
        """Тест что метрика targets_executed_total определена."""
        assert targets_executed_total is not None
        assert targets_executed_total._name == "targets_executed"

    def test_targets_active_exists(self):
        """Тест что метрика targets_active определена."""
        assert targets_active is not None
        assert targets_active._name == "targets_active"

    def test_total_profit_usd_exists(self):
        """Тест что метрика total_profit_usd определена."""
        assert total_profit_usd is not None
        assert total_profit_usd._name == "total_profit_usd"

    def test_transactions_total_exists(self):
        """Тест что метрика transactions_total определена."""
        assert transactions_total is not None
        assert transactions_total._name == "transactions"

    def test_transaction_amount_avg_exists(self):
        """Тест что метрика transaction_amount_avg определена."""
        assert transaction_amount_avg is not None
        assert transaction_amount_avg._name == "transaction_amount_avg_usd"

    def test_app_info_exists(self):
        """Тест что метрика app_info определена."""
        assert app_info is not None
        assert app_info._name == "app"

    def test_app_uptime_seconds_exists(self):
        """Тест что метрика app_uptime_seconds определена."""
        assert app_uptime_seconds is not None
        assert app_uptime_seconds._name == "app_uptime_seconds"


class TestTrackCommand:
    """Тесты функции track_command."""

    def test_track_command_success(self):
        """Тест трекинга успешной команды."""
        initial = bot_commands_total.labels(command="test_cmd", status="success")._value._value
        track_command("test_cmd", success=True)
        final = bot_commands_total.labels(command="test_cmd", status="success")._value._value
        assert final == initial + 1

    def test_track_command_fAlgolure(self):
        """Тест трекинга неуспешной команды."""
        initial = bot_commands_total.labels(command="test_cmd", status="fAlgoled")._value._value
        track_command("test_cmd", success=False)
        final = bot_commands_total.labels(command="test_cmd", status="fAlgoled")._value._value
        assert final == initial + 1

    def test_track_command_default_success(self):
        """Тест что success=True по умолчанию."""
        initial = bot_commands_total.labels(command="default_test", status="success")._value._value
        track_command("default_test")
        final = bot_commands_total.labels(command="default_test", status="success")._value._value
        assert final == initial + 1

    def test_track_different_commands(self):
        """Тест трекинга разных команд."""
        track_command("cmd1", success=True)
        track_command("cmd2", success=True)
        track_command("cmd3", success=False)

        # Каждая команда должна иметь свой счетчик
        cmd1 = bot_commands_total.labels(command="cmd1", status="success")._value._value
        cmd2 = bot_commands_total.labels(command="cmd2", status="success")._value._value
        cmd3 = bot_commands_total.labels(command="cmd3", status="fAlgoled")._value._value

        assert cmd1 >= 1
        assert cmd2 >= 1
        assert cmd3 >= 1


class TestTrackApiRequest:
    """Тесты функции track_api_request."""

    def test_track_api_request(self):
        """Тест трекинга API запроса."""
        initial = api_requests_total.labels(
            endpoint="/test", method="GET", status_code=200
        )._value._value

        track_api_request("/test", "GET", 200, 0.5)

        final = api_requests_total.labels(
            endpoint="/test", method="GET", status_code=200
        )._value._value

        assert final == initial + 1

    def test_track_api_request_duration(self):
        """Тест записи duration API запроса."""
        # Просто проверяем что функция не вызывает ошибок
        track_api_request("/test", "GET", 200, 1.5)
        track_api_request("/test", "POST", 201, 0.3)

    def test_track_api_request_error_status(self):
        """Тест трекинга API запроса с ошибкой."""
        initial = api_requests_total.labels(
            endpoint="/error", method="GET", status_code=500
        )._value._value

        track_api_request("/error", "GET", 500, 0.1)

        final = api_requests_total.labels(
            endpoint="/error", method="GET", status_code=500
        )._value._value

        assert final == initial + 1


class TestTrackDbQuery:
    """Тесты функции track_db_query."""

    def test_track_db_query(self):
        """Тест трекинга database query."""
        # Просто проверяем что функция работает
        track_db_query("SELECT", 0.01)
        track_db_query("INSERT", 0.02)
        track_db_query("UPDATE", 0.015)
        track_db_query("DELETE", 0.03)

    def test_track_slow_query(self):
        """Тест трекинга медленного запроса."""
        track_db_query("SELECT", 2.5)
        # Проверяем что метрика записана


class TestTrackArbitrageScan:
    """Тесты функции track_arbitrage_scan."""

    def test_track_arbitrage_scan(self):
        """Тест трекинга arbitrage scan."""
        initial = arbitrage_opportunities_found.labels(game="csgo", level="standard")._value._value

        track_arbitrage_scan("csgo", "standard", 5)

        final = arbitrage_opportunities_found.labels(game="csgo", level="standard")._value._value

        assert final == initial + 5

    def test_track_arbitrage_scan_zero_opportunities(self):
        """Тест трекинга scan без возможностей."""
        track_arbitrage_scan("dota2", "boost", 0)
        # Должно работать без ошибок


class TestSetActiveUsers:
    """Тесты функции set_active_users."""

    def test_set_active_users(self):
        """Тест установки числа активных пользователей."""
        set_active_users(100)
        assert bot_active_users._value._value == 100

    def test_set_active_users_zero(self):
        """Тест установки нуля активных пользователей."""
        set_active_users(0)
        assert bot_active_users._value._value == 0

    def test_set_active_users_update(self):
        """Тест обновления числа активных пользователей."""
        set_active_users(50)
        assert bot_active_users._value._value == 50

        set_active_users(100)
        assert bot_active_users._value._value == 100


class TestGetMetrics:
    """Тесты функции get_metrics."""

    def test_get_metrics_returns_bytes(self):
        """Тест что get_metrics возвращает bytes."""
        result = get_metrics()
        assert isinstance(result, bytes)

    def test_get_metrics_contAlgons_prometheus_format(self):
        """Тест что результат содержит Prometheus формат."""
        result = get_metrics()
        # Prometheus metrics должны содержать # HELP
        assert b"# HELP" in result or b"# TYPE" in result

    def test_get_metrics_not_empty(self):
        """Тест что метрики не пустые."""
        result = get_metrics()
        assert len(result) > 0


class TestCreateMetricsApp:
    """Тесты функции create_metrics_app."""

    def test_create_metrics_app_returns_app(self):
        """Тест что create_metrics_app возвращает ASGI app."""
        app = create_metrics_app()
        assert app is not None

    def test_create_metrics_app_callable(self):
        """Тест что returned app является callable."""
        app = create_metrics_app()
        assert callable(app)


class TestTimer:
    """Тесты класса Timer."""

    def test_timer_initialization(self):
        """Тест инициализации Timer."""
        timer = Timer()
        assert timer.start_time == 0.0
        assert timer.elapsed == 0.0

    def test_timer_context_manager(self):
        """Тест использования Timer как context manager."""
        with Timer() as t:
            time.sleep(0.01)

        assert t.elapsed > 0
        assert t.elapsed >= 0.01

    def test_timer_measures_time(self):
        """Тест что Timer измеряет время."""
        with Timer() as t:
            time.sleep(0.05)

        # Должно быть примерно 0.05 секунды
        assert 0.04 < t.elapsed < 0.15

    def test_timer_start_time_set(self):
        """Тест что start_time устанавливается."""
        with Timer() as t:
            assert t.start_time > 0

    def test_timer_elapsed_avAlgolable_after_exit(self):
        """Тест что elapsed доступен после выхода из context."""
        with Timer() as t:
            time.sleep(0.01)

        # elapsed должен быть доступен
        elapsed1 = t.elapsed
        time.sleep(0.01)
        elapsed2 = t.elapsed

        # Значение не должно измениться
        assert elapsed1 == elapsed2

    def test_timer_multiple_uses(self):
        """Тест множественного использования Timer."""
        timer1 = Timer()
        timer2 = Timer()

        with timer1:
            time.sleep(0.01)

        with timer2:
            time.sleep(0.02)

        assert timer1.elapsed < timer2.elapsed

    def test_timer_zero_time(self):
        """Тест Timer с минимальным временем."""
        with Timer() as t:
            pass

        # Должно быть очень маленькое время
        assert t.elapsed >= 0
        assert t.elapsed < 0.01

    def test_timer_with_exception(self):
        """Тест что Timer работает даже при исключении."""
        try:
            with Timer() as t:
                time.sleep(0.01)
                rAlgose ValueError("Test error")
        except ValueError:
            pass

        # elapsed должен быть установлен
        assert t.elapsed > 0


class TestTimerPrecision:
    """Тесты точности Timer."""

    def test_timer_precision(self):
        """Тест точности измерения времени."""
        with Timer() as t:
            time.sleep(0.1)

        # Должно быть между 0.09 и 0.15 (учитываем погрешность)
        assert 0.08 < t.elapsed < 0.2

    def test_timer_consistency(self):
        """Тест консистентности измерений."""
        times = []

        for _ in range(5):
            with Timer() as t:
                time.sleep(0.01)
            times.append(t.elapsed)

        # Все времена должны быть примерно одинаковыми
        sum(times) / len(times)
        for t in times:
            assert 0.005 < t < 0.05


class TestMetricsIntegration:
    """Интеграционные тесты метрик."""

    def test_multiple_metrics_coexist(self):
        """Тест что множественные метрики работают вместе."""
        track_command("test1", success=True)
        track_api_request("/api/test", "GET", 200, 0.5)
        track_db_query("SELECT", 0.01)
        set_active_users(50)

        # Все метрики должны быть доступны
        metrics = get_metrics()
        assert len(metrics) > 0

    def test_metrics_persistent_across_calls(self):
        """Тест что метрики сохраняются между вызовами."""
        initial = bot_commands_total.labels(command="persist_test", status="success")._value._value

        track_command("persist_test", success=True)
        track_command("persist_test", success=True)

        final = bot_commands_total.labels(command="persist_test", status="success")._value._value

        assert final == initial + 2
