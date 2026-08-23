---
name: logging-observability
description: 'Use when implementing structured logging, distributed tracing, metrics, or monitoring for production applications. Trigger keywords: "logging", "observability", "tracing", "metrics", "OpenTelemetry", "Grafana", "Prometheus", "structured logging", "log level". Essential for production DMarket bot monitoring.'
---

# Logging & Observability

Structured logging, distributed tracing, and metrics for production applications.

## When to Use

- Adding logging to new modules
- Debugging production issues
- Setting up monitoring and alerting
- Implementing distributed tracing
- Designing log aggregation

## Core Patterns

### 1. Structured Logging

```python
import logging
import json
from datetime import datetime
from typing import Any

class StructuredLogger:
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        handler = logging.StreamHandler()
        handler.setFormatter(self._formatter())
        self.logger.addHandler(handler)

    def _formatter(self):
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }
                if hasattr(record, "extra_data"):
                    log_data.update(record.extra_data)
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_data)
        return JSONFormatter()

    def _log(self, level: int, msg: str, **kwargs):
        extra = {"extra_data": kwargs} if kwargs else {}
        self.logger.log(level, msg, extra=extra)

    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)
```

### 2. Trade Event Logger

```python
class TradeLogger:
    def __init__(self):
        self.logger = StructuredLogger("dmarket.trades")

    def log_candidate(self, item_id: str, price: float, margin: float):
        self.logger.info(
            "Trade candidate found",
            event="trade_candidate",
            item_id=item_id,
            price=price,
            margin=margin
        )

    def log_execution(self, item_id: str, price: float, quantity: int, order_id: str):
        self.logger.info(
            "Trade executed",
            event="trade_executed",
            item_id=item_id,
            price=price,
            quantity=quantity,
            order_id=order_id
        )

    def log_rejection(self, item_id: str, reason: str):
        self.logger.warning(
            "Trade rejected",
            event="trade_rejected",
            item_id=item_id,
            reason=reason
        )

    def log_drawdown_freeze(self, balance: float, peak: float, threshold: float):
        self.logger.warning(
            "Drawdown freeze triggered",
            event="drawdown_freeze",
            balance=balance,
            peak=balance,
            threshold=threshold
        )
```

### 3. Performance Metrics

```python
import time
from contextlib import contextmanager
from typing import Generator

class MetricsCollector:
    def __init__(self):
        self._metrics: dict[str, list[float]] = {}

    @contextmanager
    def measure(self, name: str) -> Generator[None, None, None]:
        start = time.monotonic()
        try:
            yield
        finally:
            duration = time.monotonic() - start
            self._metrics.setdefault(name, []).append(duration)

    def get_stats(self, name: str) -> dict:
        values = self._metrics.get(name, [])
        if not values:
            return {}
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p95": sorted(values)[int(len(values) * 0.95)]
        }

    def reset(self):
        self._metrics.clear()

# Usage
metrics = MetricsCollector()

async def trading_cycle():
    with metrics.measure("trading_cycle"):
        await scan_market()
        await process_items()

# Get stats
stats = metrics.get_stats("trading_cycle")
print(f"Cycle avg: {stats['avg']:.3f}s, p95: {stats['p95']:.3f}s")
```

### 4. Correlation IDs

```python
import contextvars
import uuid

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)

def get_correlation_id() -> str:
    cid = correlation_id.get()
    if not cid:
        cid = str(uuid.uuid4())[:8]
        correlation_id.set(cid)
    return cid

# In logger
class CorrelatedLogger(StructuredLogger):
    def _log(self, level: int, msg: str, **kwargs):
        kwargs["correlation_id"] = get_correlation_id()
        super()._log(level, msg, **kwargs)
```

## Log Levels Strategy

| Level | When to Use | Example |
|---|---|---|
| DEBUG | Detailed diagnostic info | API request/response details |
| INFO | Normal operations | Trade executed, cycle completed |
| WARNING | Recoverable issues | Rate limit hit, retrying |
| ERROR | Failures requiring attention | API auth failed, trade rejected |
| CRITICAL | System-wide failures | Database corruption, network down |

## DMarket Bot Integration

```python
# Global logger instances
trade_logger = TradeLogger()
api_logger = StructuredLogger("dmarket.api")
risk_logger = StructuredLogger("dmarket.risk")

# In trading loop
async def trading_cycle():
    correlation_id.set(str(uuid.uuid4())[:8])

    api_logger.info("Starting trading cycle")
    items = await fetch_market_items()
    api_logger.info(f"Fetched {len(items)} items")

    for item in items:
        margin = calculate_margin(item)
        if margin > MIN_SPREAD:
            trade_logger.log_candidate(item.id, item.price, margin)
            try:
                await execute_trade(item)
                trade_logger.log_execution(item.id, item.price, 1, order_id)
            except Exception as e:
                trade_logger.log_rejection(item.id, str(e))
```

## Anti-patterns

### Using print() for logging
**Symptom:** No log levels, no structure, no rotation
**Fix:** Use `logging` module with structured formatter

### Logging sensitive data
**Symptom:** API keys, passwords in logs
**Fix:** Mask sensitive fields before logging

### Too verbose logging in production
**Symptom:** Disk full, performance degradation
**Fix:** Use appropriate log levels, DEBUG for dev only

### No correlation IDs
**Symptom:** Can't trace request across services
**Fix:** Add correlation_id to all log entries
