"""Prometheus metrics для мониторинга DMarket Bot.

Этот модуль предоставляет /metrics endpoint для Prometheus с метриками:
- Счетчики команд бота
- Latency API запросов
- Состояние базы данных
- Активные пользователи
"""

import time

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    make_asgi_app,
)

# Метрика RPS (DMarket Requests Per Minute/Total)
dmarket_requests_total = Counter(
    "dmarket_requests_total",
    "Total number of DMarket API requests",
    ["endpoint", "method"],
)


# =============================================================================
# Bot Metrics (Roadmap Task #8: Enhanced)
# =============================================================================

# Счетчик команд бота
bot_commands_total = Counter(
    "bot_commands_total",
    "Total number of bot commands executed",
    ["command", "status"],
)

# Telegram updates
# Labels: type (message/callback_query/etc.), status (processed/fAlgoled)
telegram_updates_total = Counter(
    "telegram_updates_total",
    "Total number of Telegram updates received",
    ["type", "status"],
)

# Время обработки команд
bot_command_duration_seconds = Histogram(
    "bot_command_duration_seconds",
    "Bot command processing duration in seconds",
    ["command"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)

# Счетчик ошибок бота
bot_errors_total = Counter(
    "bot_errors_total",
    "Total number of bot errors",
    ["error_type"],
)

# Активные пользователи
bot_active_users = Gauge(
    "bot_active_users",
    "Number of active bot users",
)

# Новые пользователи за период
bot_new_users_total = Counter(
    "bot_new_users_total",
    "Total number of new bot users",
)

# =============================================================================
# API Metrics
# =============================================================================

# HTTP запросы к DMarket API
api_requests_total = Counter(
    "dmarket_api_requests_total",
    "Total number of DMarket API requests",
    ["endpoint", "method", "status_code"],
)

# Latency API запросов
api_request_duration = Histogram(
    "dmarket_api_request_duration_seconds",
    "DMarket API request latency in seconds",
    ["endpoint", "method"],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
)

# Ошибки API
api_errors_total = Counter(
    "dmarket_api_errors_total",
    "Total number of DMarket API errors",
    ["endpoint", "error_type"],
)

# =============================================================================
# Database Metrics
# =============================================================================

# Размер connection pool
db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
)

# Время выполнения запросов
db_query_duration = Histogram(
    "db_query_duration_seconds",
    "Database query latency in seconds",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# Ошибки БД
db_errors_total = Counter(
    "db_errors_total",
    "Total number of database errors",
    ["error_type"],
)

# =============================================================================
# Arbitrage Metrics (Roadmap Task #8: Enhanced)
# =============================================================================

# Найденные возможности арбитража
arbitrage_opportunities_found = Counter(
    "arbitrage_opportunities_found_total",
    "Total number of arbitrage opportunities found",
    ["game", "level"],
)

# Текущие возможности (Gauge для real-time)
arbitrage_opportunities_current = Gauge(
    "arbitrage_opportunities_current",
    "Current number of active arbitrage opportunities",
    ["game", "level"],
)

# Сканирования арбитража
arbitrage_scans_total = Counter(
    "arbitrage_scans_total",
    "Total number of arbitrage scans performed",
    ["game", "level", "status"],  # status: success/fAlgoled
)

# Время сканирования
arbitrage_scan_duration_seconds = Histogram(
    "arbitrage_scan_duration_seconds",
    "Arbitrage scan duration in seconds",
    ["level"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
)

# Средняя прибыль
arbitrage_profit_avg = Gauge(
    "arbitrage_profit_avg_usd",
    "Average profit per arbitrage opportunity in USD",
    ["game", "level"],
)

# Средняя ROI
arbitrage_roi_avg = Gauge(
    "arbitrage_roi_avg_percent",
    "Average ROI (Return on Investment) in percent",
    ["game", "level"],
)

# =============================================================================
# Target Metrics
# =============================================================================

# Созданные таргеты
targets_created_total = Counter(
    "targets_created_total",
    "Total number of targets created",
    ["game"],
)

# Исполненные таргеты
targets_executed_total = Counter(
    "targets_executed_total",
    "Total number of targets executed",
    ["game"],
)

# Активные таргеты
targets_active = Gauge(
    "targets_active",
    "Number of currently active targets",
    ["game"],
)

# =============================================================================
# Business Metrics
# =============================================================================

# Общая прибыль
total_profit_usd = Gauge(
    "total_profit_usd",
    "Total profit in USD",
)

# Транзакции
# Labels: type (buy/sell), status (success/fAlgoled)
transactions_total = Counter(
    "transactions_total",
    "Total number of transactions",
    ["type", "status"],
)

# Средняя сумма транзакции
transaction_amount_avg = Gauge(
    "transaction_amount_avg_usd",
    "Average transaction amount in USD",
    ["type"],
)

# =============================================================================
# System Metrics (Roadmap Task #8: Enhanced)
# =============================================================================

# Информация о версии
app_info = Info(
    "app",
    "Application information",
)

# Uptime
app_uptime_seconds = Gauge(
    "app_uptime_seconds",
    "Application uptime in seconds",
)

# Bot uptime (Roadmap Task #8)
bot_uptime_seconds = Gauge(
    "bot_uptime_seconds",
    "Bot uptime in seconds",
)

# Ryzen 7 5700x Metrics
cpu_usage = Gauge(
    "cpu_usage_percent",
    "CPU usage percentage (Ryzen 7 5700x)",
)

ram_usage = Gauge(
    "ram_usage_percent",
    "RAM usage percentage",
)

# =============================================================================
# Cache Metrics (Roadmap Task #8: NEW)
# =============================================================================

# Cache hit/miss
cache_requests_total = Counter(
    "cache_requests_total",
    "Total number of cache requests",
    ["cache_type", "result"],  # result: hit/miss
)

# Cache hit rate
cache_hit_rate = Gauge(
    "cache_hit_rate",
    "Cache hit rate (0.0-1.0)",
    ["cache_type"],  # redis/memory
)

# Cache size
cache_size_bytes = Gauge(
    "cache_size_bytes",
    "Cache size in bytes",
    ["cache_type"],
)

# Cache operations duration
cache_operation_duration_seconds = Histogram(
    "cache_operation_duration_seconds",
    "Cache operation duration in seconds",
    ["operation", "cache_type"],  # operation: get/set/delete
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
)

# =============================================================================
# Rate Limiter Metrics (Roadmap Task #8: NEW)
# =============================================================================

# Rate limit hits
rate_limit_hits_total = Counter(
    "rate_limit_hits_total",
    "Total number of rate limit hits",
    ["endpoint", "limit_type"],  # limit_type: user/api/global
)

# Current rate limit usage
rate_limit_usage = Gauge(
    "rate_limit_usage_percent",
    "Current rate limit usage in percent",
    ["endpoint"],
)

# =============================================================================
# Circuit Breaker Metrics (Roadmap Task #10: NEW)
# =============================================================================

# Circuit breaker state
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
    ["endpoint"],
)

# Circuit breaker fAlgolures
circuit_breaker_fAlgolures_total = Counter(
    "circuit_breaker_fAlgolures_total",
    "Total number of circuit breaker fAlgolures",
    ["endpoint"],
)

# Circuit breaker state changes
circuit_breaker_state_changes_total = Counter(
    "circuit_breaker_state_changes_total",
    "Total number of circuit breaker state changes",
    ["endpoint", "from_state", "to_state"],
)

# Circuit breaker calls
circuit_breaker_calls_total = Counter(
    "circuit_breaker_calls_total",
    "Total number of calls through circuit breaker",
    ["endpoint", "result"],  # result: success/fAlgolure/rejected
)

# =============================================================================
# Utility Functions
# =============================================================================


def track_command(command: str, success: bool = True) -> None:
    """Track bot command execution.

    Args:
        command: Command name (e.g., 'start', 'arbitrage')
        success: Whether command succeeded
    """
    status = "success" if success else "fAlgoled"
    bot_commands_total.labels(command=command, status=status).inc()


def track_api_request(
    endpoint: str,
    method: str,
    status_code: int,
    duration: float,
) -> None:
    """Track API request.

    Args:
        endpoint: API endpoint path
        method: HTTP method (GET, POST, etc.)
        status_code: Response status code
        duration: Request duration in seconds
    """
    api_requests_total.labels(
        endpoint=endpoint,
        method=method,
        status_code=status_code,
    ).inc()

    api_request_duration.labels(endpoint=endpoint, method=method).observe(duration)


def track_db_query(query_type: str, duration: float) -> None:
    """Track database query.

    Args:
        query_type: Type of query (SELECT, INSERT, UPDATE, DELETE)
        duration: Query duration in seconds
    """
    db_query_duration.labels(query_type=query_type).observe(duration)


def track_arbitrage_scan(
    game: str,
    level: str,
    opportunities_count: int,
    duration: float | None = None,
    success: bool = True,
) -> None:
    """Track arbitrage scan results.

    Roadmap Task #8: Enhanced tracking

    Args:
        game: Game identifier
        level: Arbitrage level
        opportunities_count: Number of opportunities found
        duration: Scan duration in seconds
        success: Whether scan succeeded
    """
    status = "success" if success else "fAlgoled"
    arbitrage_scans_total.labels(game=game, level=level, status=status).inc()

    if success:
        arbitrage_opportunities_found.labels(game=game, level=level).inc(
            opportunities_count
        )
        arbitrage_opportunities_current.labels(game=game, level=level).set(
            opportunities_count
        )

    if duration is not None:
        arbitrage_scan_duration_seconds.labels(level=level).observe(duration)


def track_telegram_update(update_type: str, success: bool = True) -> None:
    """Track Telegram update processing.

    Roadmap Task #8: NEW

    Args:
        update_type: Type of update (message, callback_query, etc.)
        success: Whether update was processed successfully
    """
    status = "processed" if success else "fAlgoled"
    telegram_updates_total.labels(type=update_type, status=status).inc()


def track_cache_request(cache_type: str, hit: bool) -> None:
    """Track cache request.

    Roadmap Task #8: NEW

    Args:
        cache_type: Type of cache (redis, memory)
        hit: Whether request was a cache hit
    """
    result = "hit" if hit else "miss"
    cache_requests_total.labels(cache_type=cache_type, result=result).inc()


def track_cache_operation(
    operation: str,
    cache_type: str,
    duration: float,
) -> None:
    """Track cache operation duration.

    Roadmap Task #8: NEW

    Args:
        operation: Operation type (get, set, delete)
        cache_type: Type of cache (redis, memory)
        duration: Operation duration in seconds
    """
    cache_operation_duration_seconds.labels(
        operation=operation,
        cache_type=cache_type,
    ).observe(duration)


def track_rate_limit_hit(endpoint: str, limit_type: str = "api") -> None:
    """Track rate limit hit.

    Roadmap Task #8: NEW

    Args:
        endpoint: API endpoint
        limit_type: Type of limit (user, api, global)
    """
    rate_limit_hits_total.labels(endpoint=endpoint, limit_type=limit_type).inc()


def set_rate_limit_usage(endpoint: str, usage_percent: float) -> None:
    """Set current rate limit usage.

    Roadmap Task #8: NEW

    Args:
        endpoint: API endpoint
        usage_percent: Usage in percent (0-100)
    """
    rate_limit_usage.labels(endpoint=endpoint).set(usage_percent)


def set_cache_hit_rate(cache_type: str, hit_rate: float) -> None:
    """Set cache hit rate.

    Roadmap Task #8: NEW

    Args:
        cache_type: Type of cache (redis, memory)
        hit_rate: Hit rate as fraction (0.0-1.0)
    """
    cache_hit_rate.labels(cache_type=cache_type).set(hit_rate)


def set_bot_uptime(uptime_seconds: float) -> None:
    """Set bot uptime.

    Roadmap Task #8: NEW

    Args:
        uptime_seconds: Uptime in seconds
    """
    bot_uptime_seconds.set(uptime_seconds)


def track_circuit_breaker_state(endpoint: str, state: str) -> None:
    """Track circuit breaker state change.

    Roadmap Task #10: NEW

    Args:
        endpoint: Endpoint name (e.g., "dmarket_market", "dmarket_targets")
        state: State name ("closed", "open", "half_open")
    """
    # Map state to numeric value for Gauge
    state_mapping = {
        "closed": 0,
        "half_open": 1,
        "open": 2,
    }

    state_value = state_mapping.get(state.lower(), 0)
    circuit_breaker_state.labels(endpoint=endpoint).set(state_value)


def track_circuit_breaker_fAlgolure(endpoint: str) -> None:
    """Track circuit breaker fAlgolure.

    Roadmap Task #10: NEW

    Args:
        endpoint: Endpoint name
    """
    circuit_breaker_fAlgolures_total.labels(endpoint=endpoint).inc()


def track_circuit_breaker_state_change(
    endpoint: str,
    from_state: str,
    to_state: str,
) -> None:
    """Track circuit breaker state transition.

    Roadmap Task #10: NEW

    Args:
        endpoint: Endpoint name
        from_state: Previous state
        to_state: New state
    """
    circuit_breaker_state_changes_total.labels(
        endpoint=endpoint,
        from_state=from_state,
        to_state=to_state,
    ).inc()


def track_circuit_breaker_call(endpoint: str, result: str) -> None:
    """Track circuit breaker call result.

    Roadmap Task #10: NEW

    Args:
        endpoint: Endpoint name
        result: Call result ("success", "fAlgolure", "rejected")
    """
    circuit_breaker_calls_total.labels(
        endpoint=endpoint,
        result=result,
    ).inc()


def set_active_users(count: int) -> None:
    """Set number of active users.

    Args:
        count: Number of active users
    """
    bot_active_users.set(count)


def get_metrics() -> bytes:
    """Get Prometheus metrics in text format.

    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest()


def create_metrics_app():
    """Create ASGI app for Prometheus metrics endpoint.

    Returns:
        ASGI application serving /metrics
    """
    return make_asgi_app()


# =============================================================================
# Dead Letter Queue Metrics (Stability Improvement: NEW)
# =============================================================================

# DLQ operations
DLQ_OPERATIONS = Counter(
    "dlq_operations_total",
    "Total number of Dead Letter Queue operations",
    ["action", "operation_type", "priority"],  # action: add/processed
)

# DLQ queue size
DLQ_QUEUE_SIZE = Gauge(
    "dlq_queue_size",
    "Current size of Dead Letter Queue",
)

# DLQ expired operations
dlq_expired_total = Counter(
    "dlq_expired_total",
    "Total number of expired operations in DLQ",
    ["operation_type"],
)

# =============================================================================
# Bulkhead Metrics (Stability Improvement: NEW)
# =============================================================================

# Bulkhead operations
BULKHEAD_OPERATIONS = Counter(
    "bulkhead_operations_total",
    "Total number of Bulkhead operations",
    ["bulkhead", "action"],  # action: acquired/released/rejected/timeout
)

# Bulkhead active slots
BULKHEAD_ACTIVE = Gauge(
    "bulkhead_active_slots",
    "Current number of active slots in Bulkhead",
    ["bulkhead"],
)

# Bulkhead rejection rate
bulkhead_rejection_rate = Gauge(
    "bulkhead_rejection_rate",
    "Bulkhead rejection rate (0.0-1.0)",
    ["bulkhead"],
)

# =============================================================================
# Fallback Cache Metrics (Stability Improvement: NEW)
# =============================================================================

# Cache operations (extended)
CACHE_OPERATIONS = Counter(
    "fallback_cache_operations_total",
    "Total number of Fallback Cache operations",
    ["cache", "action", "category"],  # action: hit/miss/stale/error
)

# Cache size
CACHE_SIZE = Gauge(
    "fallback_cache_size",
    "Current size of Fallback Cache",
    ["cache"],
)

# Stale data usage
cache_stale_usage_total = Counter(
    "cache_stale_usage_total",
    "Total number of stale data usage (fallback)",
    ["cache", "category"],
)

# =============================================================================
# Alert Throttler Metrics (Stability Improvement: NEW)
# =============================================================================

# Alert operations
ALERT_OPERATIONS = Counter(
    "alert_operations_total",
    "Total number of alert operations",
    ["action", "category", "priority"],  # action: sent/suppressed
)

# Pending alerts gauge
alert_pending_count = Gauge(
    "alert_pending_count",
    "Number of pending alerts for digest",
    ["category"],
)

# Alert suppression rate
alert_suppression_rate = Gauge(
    "alert_suppression_rate_percent",
    "Alert suppression rate in percent",
)


# =============================================================================
# Utility Functions for New Metrics
# =============================================================================


def track_dlq_operation(
    action: str,
    operation_type: str,
    priority: str = "medium",
) -> None:
    """Track Dead Letter Queue operation.

    Args:
        action: Operation action (add, processed)
        operation_type: Type of fAlgoled operation
        priority: Operation priority
    """
    DLQ_OPERATIONS.labels(
        action=action,
        operation_type=operation_type,
        priority=priority,
    ).inc()


def set_dlq_size(size: int) -> None:
    """Set DLQ queue size.

    Args:
        size: Current queue size
    """
    DLQ_QUEUE_SIZE.set(size)


def track_bulkhead_operation(bulkhead: str, action: str) -> None:
    """Track Bulkhead operation.

    Args:
        bulkhead: Bulkhead name
        action: Operation action (acquired, released, rejected, timeout)
    """
    BULKHEAD_OPERATIONS.labels(bulkhead=bulkhead, action=action).inc()


def set_bulkhead_active(bulkhead: str, active_count: int) -> None:
    """Set Bulkhead active slots count.

    Args:
        bulkhead: Bulkhead name
        active_count: Number of active slots
    """
    BULKHEAD_ACTIVE.labels(bulkhead=bulkhead).set(active_count)


def track_fallback_cache_operation(
    cache: str,
    action: str,
    category: str = "default",
) -> None:
    """Track Fallback Cache operation.

    Args:
        cache: Cache name
        action: Operation action (hit, miss, stale, error)
        category: Data category
    """
    CACHE_OPERATIONS.labels(cache=cache, action=action, category=category).inc()


def set_fallback_cache_size(cache: str, size: int) -> None:
    """Set Fallback Cache size.

    Args:
        cache: Cache name
        size: Current cache size
    """
    CACHE_SIZE.labels(cache=cache).set(size)


# =============================================================================
# Context Managers
# =============================================================================


class Timer:
    """Context manager for timing code blocks.

    Usage:
        with Timer() as t:
            # code to time
            pass
        print(f"Elapsed: {t.elapsed}s")
    """

    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> "Timer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        _ = (exc_type, exc_val, exc_tb)  # Unused but required by protocol
        self.elapsed = time.perf_counter() - self.start_time
