---
name: monitoring-alerting
description: 'Use when designing monitoring, alerting, SLI/SLO, or dashboards for production services. Trigger keywords: "monitoring", "alerting", "Grafana", "Prometheus", "SLI", "SLO", "dashboard", "alert rules", "burn rate". Essential for production DMarket bot monitoring.'
---

# Monitoring & Alerting

Monitoring and alerting design for production backend services.

## When to Use

- Setting up monitoring for the bot
- Designing alert rules
- Creating dashboards
- Defining SLIs and SLOs
- Debugging production issues

## Core Patterns

### 1. SLI/SLO Definition

```python
from dataclasses import dataclass
from enum import Enum

class SLIType(Enum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"

@dataclass
class SLO:
    name: str
    sli_type: SLIType
    target: float  # e.g., 0.999 for 99.9%
    window: str  # e.g., "30d", "7d"
    description: str

# DMarket Bot SLOs
SLOS = [
    SLO(
        name="API Availability",
        sli_type=SLIType.AVAILABILITY,
        target=0.999,
        window="30d",
        description="DMarket API calls should succeed 99.9% of the time"
    ),
    SLO(
        name="Trade Execution Latency",
        sli_type=SLIType.LATENCY,
        target=0.95,
        window="7d",
        description="95% of trades should execute within 2 seconds"
    ),
    SLO(
        name="Error Rate",
        sli_type=SLIType.ERROR_RATE,
        target=0.01,
        window="7d",
        description="Less than 1% of operations should result in errors"
    ),
]
```

### 2. Metrics Collector

```python
import time
from collections import defaultdict
from typing import Any

class MetricsCollector:
    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, value: int = 1):
        self._counters[name] += value

    def gauge(self, name: str, value: float):
        self._gauges[name] = value

    def histogram(self, name: str, value: float):
        self._histograms[name].append(value)

    def get_metrics(self) -> dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                name: {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "p50": sorted(values)[len(values) // 2],
                    "p95": sorted(values)[int(len(values) * 0.95)],
                    "p99": sorted(values)[int(len(values) * 0.99)],
                }
                for name, values in self._histograms.items()
            }
        }

# Global metrics
metrics = MetricsCollector()

# Usage
metrics.increment("trades.executed")
metrics.increment("trades.rejected", 1)
metrics.gauge("balance.current", 150.50)
metrics.histogram("api.latency", 0.234)
```

### 3. Alert Rules

```python
from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class AlertRule:
    name: str
    condition: Callable[[dict], bool]
    severity: str  # critical, warning, info
    message: str
    cooldown: int  # seconds between alerts

class AlertManager:
    def __init__(self):
        self.rules: list[AlertRule] = []
        self._last_alert: dict[str, float] = {}

    def add_rule(self, rule: AlertRule):
        self.rules.append(rule)

    def evaluate(self, metrics: dict) -> list[str]:
        alerts = []
        now = time.time()

        for rule in self.rules:
            last = self._last_alert.get(rule.name, 0)
            if now - last < rule.cooldown:
                continue

            if rule.condition(metrics):
                alerts.append(f"[{rule.severity.upper()}] {rule.message}")
                self._last_alert[rule.name] = now

        return alerts

# Define alerts
alert_manager = AlertManager()

alert_manager.add_rule(AlertRule(
    name="high_error_rate",
    condition=lambda m: m.get("counters", {}).get("errors.total", 0) > 10,
    severity="critical",
    message="Error rate exceeded 10 in the last cycle",
    cooldown=300
))

alert_manager.add_rule(AlertRule(
    name="low_balance",
    condition=lambda m: m.get("gauges", {}).get("balance.current", 0) < 10,
    severity="warning",
    message="Balance below $10",
    cooldown=600
))

alert_manager.add_rule(AlertRule(
    name="api_latency_high",
    condition=lambda m: m.get("histograms", {}).get("api.latency", {}).get("p95", 0) > 5.0,
    severity="warning",
    message="API p95 latency above 5 seconds",
    cooldown=300
))
```

### 4. Health Check Endpoint

```python
from aiohttp import web
import asyncio

class HealthChecker:
    def __init__(self):
        self.checks: dict[str, Callable] = {}

    def register(self, name: str, check: Callable):
        self.checks[name] = check

    async def check_all(self) -> dict:
        results = {}
        for name, check in self.checks.items():
            try:
                result = await check()
                results[name] = {"status": "healthy", "details": result}
            except Exception as e:
                results[name] = {"status": "unhealthy", "error": str(e)}

        all_healthy = all(r["status"] == "healthy" for r in results.values())
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": results
        }

# Setup
health = HealthChecker()

async def check_api():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.dmarket.com/exchange/v2/market/games") as resp:
            if not resp.ok:
                raise Exception(f"API returned {resp.status}")
            return {"status_code": resp.status}

async def check_database():
    with get_connection("data/dmarket_trading.db") as conn:
        conn.execute("SELECT 1")
    return {"connected": True}

health.register("api", check_api)
health.register("database", check_database)

# HTTP endpoint
async def health_handler(request):
    result = await health.check_all()
    status = 200 if result["status"] == "healthy" else 503
    return web.json_response(result, status=status)
```

### 5. Dashboard Design

```markdown
## DMarket Bot Dashboard

### Row 1: Overview
- **Balance** (gauge): Current balance, peak balance, drawdown %
- **Trades Today** (counter): Executed, rejected, pending
- **API Health** (status): DMarket API, MultiSourceOracle, Telegram

### Row 2: Performance
- **Cycle Duration** (histogram): p50, p95, p99
- **API Latency** (histogram): Per endpoint
- **Error Rate** (counter): Errors per hour

### Row 3: Trading
- **Profit/Loss** (time series): Daily P&L
- **Position Size** (histogram): Distribution of trade sizes
- **Success Rate** (gauge): % of profitable trades

### Row 4: System
- **Memory Usage** (gauge): RSS, heap
- **CPU Usage** (gauge): Per core
- **Disk Usage** (gauge): Data directory size
```

## Anti-patterns

### Alert fatigue
**Symptom:** Too many alerts, all ignored
**Fix:** Use cooldown periods, severity levels, and only alert on actionable issues

### No SLOs
**Symptom:** No clear definition of "healthy"
**Fix:** Define SLIs and SLOs before building alerts

### Monitoring everything
**Symptom:** Dashboard overload, noise
**Fix:** Focus on key metrics: balance, trades, errors, latency

### No runbooks
**Symptom:** On-call doesn't know what to do
**Fix:** Write runbooks for each critical alert
