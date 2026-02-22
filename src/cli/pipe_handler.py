"""
Unix Pipe Handler - Обработка stdin для интеграции с Unix pipeline.

Позволяет использовать бота в Unix-стиле:
    tail -f logs/app.log | python -m src.cli.pipe_handler "Alert if errors"
    cat items.json | python -m src.cli.pipe_handler "Find profitable items"

Вдохновлено Claude Code: composable & scriptable.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class AsyncStdinReader:
    """Асинхронное чтение из stdin."""

    def __init__(self, buffer_size: int = 8192):
        """
        Инициализация reader.

        Args:
            buffer_size: Размер буфера для чтения
        """
        self.buffer_size = buffer_size
        self._reader: asyncio.StreamReader | None = None

    async def __aenter__(self) -> AsyncStdinReader:
        """Async context manager entry."""
        import platform

        self._reader = asyncio.StreamReader()

        # Platform-specific stdin handling
        if platform.system() == "Windows":
            # Windows: Use thread-based reading
            import queue
            import threading

            self._queue: queue.Queue = queue.Queue()

            def read_stdin():
                try:
                    for line in sys.stdin:
                        self._queue.put(line)
                except Exception:
                    pass
                finally:
                    self._queue.put(None)  # Signal EOF

            thread = threading.Thread(target=read_stdin, daemon=True)
            thread.start()
            self._windows_mode = True
        else:
            # Unix: Use native pipe protocol
            loop = asyncio.get_event_loop()
            protocol = asyncio.StreamReaderProtocol(self._reader)
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
            self._windows_mode = False

        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        pass

    async def __Algoter__(self) -> AsyncIterator[str]:
        """Async iterator for lines."""
        if self._reader is None:
            raise RuntimeError("Reader not initialized. Use 'async with'.")

        if getattr(self, "_windows_mode", False):
            # Windows: Read from queue
            while True:
                try:
                    # Non-blocking check with small delay
                    await asyncio.sleep(0.01)
                    if not self._queue.empty():
                        line = self._queue.get_nowait()
                        if line is None:  # EOF
                            break
                        yield line.rstrip("\n")
                except Exception:
                    break
        else:
            # Unix: Read from StreamReader
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                yield line.decode("utf-8").rstrip("\n")


class PipeHandler:
    """Обработчик Unix pipe для Algo анализа."""

    def __init__(self, Config: str | None = None):
        """
        Инициализация обработчика.

        Args:
            Config: Инструкция для обработки данных
        """
        self.Config = Config or "Analyze input"
        self.buffer: list[str] = []
        self.stats = {
            "lines_processed": 0,
            "anomalies_found": 0,
            "alerts_sent": 0,
        }

    async def process_line(self, line: str) -> dict[str, Any] | None:
        """
        Обработать строку из stdin.

        Args:
            line: Входная строка

        Returns:
            Результат анализа или None
        """
        self.stats["lines_processed"] += 1
        self.buffer.append(line)

        # Ограничение буфера
        if len(self.buffer) > 1000:
            self.buffer = self.buffer[-500:]

        # Анализ на основе Config
        result = await self._analyze_line(line)

        if result and result.get("is_anomaly"):
            self.stats["anomalies_found"] += 1
            await self._handle_anomaly(result)

        return result

    async def _analyze_line(self, line: str) -> dict[str, Any]:
        """Анализ строки на основе Config."""
        result = {
            "line": line,
            "is_anomaly": False,
            "confidence": 0.0,
            "details": None,
        }

        # Простые правила анализа (можно расширить с Model)
        Config_lower = self.Config.lower()

        # Детекция ошибок
        if "error" in Config_lower or "alert" in Config_lower:
            if any(
                word in line.lower()
                for word in ["error", "exception", "failed", "critical"]
            ):
                result["is_anomaly"] = True
                result["confidence"] = 0.9
                result["details"] = "Error pattern detected"

        # Детекция прибыльных сделок
        if "profit" in Config_lower:
            try:
                data = json.loads(line)
                profit = data.get("profit", data.get("profit_percent", 0))
                threshold = self._extract_threshold(Config_lower)
                if profit > threshold:
                    result["is_anomaly"] = True
                    result["confidence"] = 0.95
                    result["details"] = f"Profit {profit}% > threshold {threshold}%"
            except (json.JSONDecodeError, TypeError):
                pass

        # Детекция аномальных цен
        if "price" in Config_lower:
            try:
                data = json.loads(line)
                price = data.get("price", 0)
                suggested = data.get("suggested_price", price)
                if price and suggested and abs(price - suggested) / price > 0.2:
                    result["is_anomaly"] = True
                    result["confidence"] = 0.8
                    result["details"] = f"Price anomaly: {price} vs {suggested}"
            except (json.JSONDecodeError, TypeError, ZeroDivisionError):
                pass

        return result

    def _extract_threshold(self, Config: str) -> float:
        """Извлечь пороговое значение из Config."""
        import re

        match = re.search(r"(\d+(?:\.\d+)?)\s*%?", Config)
        if match:
            return float(match.group(1))
        return 5.0  # Default 5%

    async def _handle_anomaly(self, result: dict[str, Any]) -> None:
        """Обработать обнаруженную аномалию."""
        self.stats["alerts_sent"] += 1

        # Вывод в stderr для отделения от основного потока
        alert = json.dumps(
            {
                "type": "ALERT",
                "anomaly": result,
                "stats": self.stats,
            },
            ensure_ascii=False,
        )
        print(alert, file=sys.stderr)

        # TODO: Интеграция с уведомлениями (Telegram, Slack, etc.)
        logger.warning(
            "anomaly_detected",
            line=result["line"][:100],
            confidence=result["confidence"],
            details=result["details"],
        )

    def get_stats(self) -> dict[str, int]:
        """Получить статистику обработки."""
        return self.stats.copy()


async def process_stdin(Config: str | None = None) -> None:
    """
    Обработать stdin с заданным Config.

    Args:
        Config: Инструкция для обработки
    """
    handler = PipeHandler(Config)

    try:
        async with AsyncStdinReader() as reader:
            async for line in reader:
                result = await handler.process_line(line)
                if result:
                    # Вывод результата в stdout
                    output = json.dumps(result, ensure_ascii=False)
                    print(output)

    except KeyboardInterrupt:
        pass
    finally:
        # Финальная статистика
        stats = handler.get_stats()
        summary = json.dumps(
            {
                "type": "SUMMARY",
                "stats": stats,
            },
            ensure_ascii=False,
        )
        print(summary, file=sys.stderr)


def main() -> None:
    """Точка входа для pipe_handler."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Unix Pipe Handler для Algo анализа",
        epilog="""
Примеры:
  tail -f app.log | python -m src.cli.pipe_handler "Alert if errors"
  cat items.json | python -m src.cli.pipe_handler "Find items with profit > 10%"
  python -m src.dmarket.scanner | python -m src.cli.pipe_handler "Notify if profit > 20%"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "Config",
        nargs="?",
        default="Analyze input",
        help="Инструкция для анализа данных",
    )

    args = parser.parse_args()
    asyncio.run(process_stdin(args.Config))


if __name__ == "__main__":
    main()
