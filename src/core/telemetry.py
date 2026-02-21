import time
import logging
import functools
from typing import Callable, Any, Dict

logger = logging.getLogger(__name__)

class LatencyMonitor:
    def __init__(self):
        self.measurements = {}

    def monitor_latency(self, func: Callable) -> Callable:
        """
        Decorator to measure and log function execution latency.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                func_name = func.__name__
                if func_name not in self.measurements:
                    self.measurements[func_name] = []
                self.measurements[func_name].append(latency_ms)
                logger.info(f"[Latency] {func_name}: {latency_ms:.4f} ms")
        return wrapper

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        stats = {}
        for func_name, latencies in self.measurements.items():
            stats[func_name] = {
                "avg": sum(latencies) / len(latencies),
                "min": min(latencies),
                "max": max(latencies),
                "count": len(latencies)
            }
        return stats

telemetry_monitor = LatencyMonitor()
monitor_latency = telemetry_monitor.monitor_latency
