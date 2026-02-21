"""
Prometheus metrics для мониторинга бота.

Экспортирует метрики для Prometheus/Grafana.
"""

import time

from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest

# Информация о версии
bot_info = Info("dmarket_bot", "DMarket Telegram Bot информация")
bot_info.info(
    {
        "version": "1.0.0",
        "python_version": "3.11+",
    }
)

# Счетчики команд
commands_total = Counter(
    "dmarket_bot_commands_total",
    "Общее количество команд",
    ["command", "user_id"],
)

# Счетчики API запросов
api_requests_total = Counter(
    "dmarket_bot_api_requests_total",
    "Общее количество API запросов",
    ["endpoint", "method", "status"],
)

# Счетчики ошибок
errors_total = Counter(
    "dmarket_bot_errors_total",
    "Общее количество ошибок",
    ["error_type", "module"],
)

# Счетчики арбитража
arbitrage_scans_total = Counter(
    "dmarket_bot_arbitrage_scans_total",
    "Количество сканирований арбитража",
    ["level", "game"],
)

arbitrage_opportunities_found = Counter(
    "dmarket_bot_arbitrage_opportunities_found",
    "Найдено арбитражных возможностей",
    ["level", "game"],
)

# Счетчики таргетов
targets_created_total = Counter(
    "dmarket_bot_targets_created_total",
    "Созданные таргеты",
    ["game", "user_id"],
)

targets_hit_total = Counter(
    "dmarket_bot_targets_hit_total",
    "Сработавшие таргеты",
    ["game", "user_id"],
)

# Счетчики торговли
trades_total = Counter(
    "dmarket_bot_trades_total",
    "Общее количество сделок",
    ["type", "game"],  # trade type: buy/sell
)

trade_volume_usd = Counter(
    "dmarket_bot_trade_volume_usd",
    "Объем торговли в USD",
    ["type", "game"],  # trade type and game
)

# Гистограммы производительности
api_request_duration_seconds = Histogram(
    "dmarket_bot_api_request_duration_seconds",
    "Длительность API запросов",
    ["endpoint"],
)

arbitrage_scan_duration_seconds = Histogram(
    "dmarket_bot_arbitrage_scan_duration_seconds",
    "Длительность сканирования арбитража",
    ["level", "game"],
)

# Gauge метрики (текущее состояние)
active_users = Gauge(
    "dmarket_bot_active_users",
    "Количество активных пользователей",
)

active_targets = Gauge(
    "dmarket_bot_active_targets",
    "Количество активных таргетов",
    ["game"],
)

balance_usd = Gauge(
    "dmarket_bot_balance_usd",
    "Баланс в USD",
    ["user_id"],
)

cache_size = Gauge(
    "dmarket_bot_cache_size",
    "Размер кэша",
    ["cache_type"],
)

rate_limit_remAlgoning = Gauge(
    "dmarket_bot_rate_limit_remAlgoning",
    "Оставшиеся запросы rate limit",
    ["user_id"],
)


class MetricsCollector:
    """Коллектор метрик для бота."""

    @staticmethod
    def record_command(command: str, user_id: int) -> None:
        """Записать выполнение команды."""
        commands_total.labels(command=command, user_id=str(user_id)).inc()

    @staticmethod
    def record_api_request(
        endpoint: str, method: str, status: int, duration: float
    ) -> None:
        """Записать API запрос."""
        api_requests_total.labels(
            endpoint=endpoint,
            method=method,
            status=str(status),
        ).inc()

        api_request_duration_seconds.labels(endpoint=endpoint).observe(duration)

    @staticmethod
    def record_error(error_type: str, module: str) -> None:
        """Записать ошибку."""
        errors_total.labels(error_type=error_type, module=module).inc()

    @staticmethod
    def record_arbitrage_scan(
        level: str, game: str, duration: float, found: int
    ) -> None:
        """Записать сканирование арбитража."""
        arbitrage_scans_total.labels(level=level, game=game).inc()
        arbitrage_opportunities_found.labels(level=level, game=game).inc(found)
        arbitrage_scan_duration_seconds.labels(level=level, game=game).observe(duration)

    @staticmethod
    def record_target_created(game: str, user_id: int) -> None:
        """Записать создание таргета."""
        targets_created_total.labels(game=game, user_id=str(user_id)).inc()

    @staticmethod
    def record_target_hit(game: str, user_id: int) -> None:
        """Записать срабатывание таргета."""
        targets_hit_total.labels(game=game, user_id=str(user_id)).inc()

    @staticmethod
    def record_trade(trade_type: str, game: str, amount_usd: float) -> None:
        """Записать сделку."""
        trades_total.labels(type=trade_type, game=game).inc()
        trade_volume_usd.labels(type=trade_type, game=game).inc(amount_usd)

    @staticmethod
    def update_active_users(count: int) -> None:
        """Обновить количество активных пользователей."""
        active_users.set(count)

    @staticmethod
    def update_active_targets(game: str, count: int) -> None:
        """Обновить количество активных таргетов."""
        active_targets.labels(game=game).set(count)

    @staticmethod
    def update_balance(user_id: int, balance: float) -> None:
        """Обновить баланс."""
        balance_usd.labels(user_id=str(user_id)).set(balance)

    @staticmethod
    def update_cache_size(cache_type: str, size: int) -> None:
        """Обновить размер кэша."""
        cache_size.labels(cache_type=cache_type).set(size)

    @staticmethod
    def update_rate_limit(user_id: int, remAlgoning: int) -> None:
        """Обновить оставшиеся запросы."""
        rate_limit_remAlgoning.labels(user_id=str(user_id)).set(remAlgoning)

    @staticmethod
    def get_metrics() -> bytes:
        """Получить метрики в формате Prometheus."""
        return generate_latest()


def measure_time(metric: Histogram, labels: dict[str, str] | None = None):
    """
    Декоратор для измерения времени выполнения.

    Args:
        metric: Histogram метрика
        labels: Лейблы для метрики
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return awAlgot func(*args, **kwargs)
            finally:
                duration = time.time() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)

        return wrapper

    return decorator
