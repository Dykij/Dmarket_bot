"""Генератор графиков для статистики бота.

Этот модуль использует QuickChart.io API для создания графиков
без необходимости установки matplotlib на сервере.
"""

import json
from typing import Any
from urllib.parse import quote

import httpx

from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)

# QuickChart.io API endpoint
QUICKCHART_API = "https://quickchart.io/chart"


class ChartGenerator:
    """Генератор графиков для Telegram бота."""

    def __init__(self, width: int = 800, height: int = 400):
        """Инициализация генератора графиков.

        Args:
            width: Ширина графика в пикселях
            height: Высота графика в пикселях

        """
        self.width = width
        self.height = height

    async def generate_profit_chart(
        self,
        data: list[dict[str, Any]],
    ) -> str | None:
        """Сгенерировать график прибыли.

        Args:
            data: Список данных с полями 'date' и 'profit'

        Returns:
            URL сгенерированного графика или None при ошибке

        """
        if not data:
            logger.warning("Нет данных для графика прибыли")
            return None

        labels = [item.get("date", "") for item in data]
        profits = [item.get("profit", 0.0) for item in data]

        chart_config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Прибыль ($)",
                        "data": profits,
                        "borderColor": "rgb(75, 192, 192)",
                        "backgroundColor": "rgba(75, 192, 192, 0.2)",
                        "fill": True,
                    },
                ],
            },
            "options": {
                "title": {
                    "display": True,
                    "text": "График прибыли",
                },
                "scales": {
                    "yAxes": [
                        {
                            "ticks": {
                                "beginAtZero": True,
                            },
                        },
                    ],
                },
            },
        }

        return await self._generate_chart_url(chart_config)

    async def generate_scan_history_chart(
        self,
        data: list[dict[str, Any]],
    ) -> str | None:
        """Сгенерировать график истории сканирований.

        Args:
            data: Список данных с полями 'date' и 'count'

        Returns:
            URL сгенерированного графика или None при ошибке

        """
        if not data:
            logger.warning("Нет данных для графика истории")
            return None

        labels = [item.get("date", "") for item in data]
        counts = [item.get("count", 0) for item in data]

        chart_config = {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Сканирования",
                        "data": counts,
                        "backgroundColor": "rgba(54, 162, 235, 0.5)",
                        "borderColor": "rgb(54, 162, 235)",
                        "borderWidth": 1,
                    },
                ],
            },
            "options": {
                "title": {
                    "display": True,
                    "text": "История сканирований",
                },
                "scales": {
                    "yAxes": [
                        {
                            "ticks": {
                                "beginAtZero": True,
                                "stepSize": 1,
                            },
                        },
                    ],
                },
            },
        }

        return await self._generate_chart_url(chart_config)

    async def generate_level_distribution_chart(
        self,
        data: dict[str, int],
    ) -> str | None:
        """Сгенерировать круговую диаграмму распределения по уровням.

        Args:
            data: Словарь с уровнями и их количеством

        Returns:
            URL сгенерированного графика или None при ошибке

        """
        if not data:
            logger.warning("Нет данных для диаграммы распределения")
            return None

        labels = list(data.keys())
        values = list(data.values())

        # Цвета для разных уровней
        colors = [
            "rgba(255, 99, 132, 0.7)",
            "rgba(54, 162, 235, 0.7)",
            "rgba(255, 206, 86, 0.7)",
            "rgba(75, 192, 192, 0.7)",
            "rgba(153, 102, 255, 0.7)",
        ]

        chart_config = {
            "type": "pie",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "data": values,
                        "backgroundColor": colors[: len(labels)],
                    },
                ],
            },
            "options": {
                "title": {
                    "display": True,
                    "text": "Распределение по уровням",
                },
                "legend": {
                    "position": "bottom",
                },
            },
        }

        return await self._generate_chart_url(chart_config)

    async def generate_profit_comparison_chart(
        self,
        levels: list[str],
        avg_profits: list[float],
        max_profits: list[float],
    ) -> str | None:
        """Сгенерировать график сравнения прибыли по уровням.

        Args:
            levels: Список названий уровней
            avg_profits: Список средних прибылей
            max_profits: Список максимальных прибылей

        Returns:
            URL сгенерированного графика или None при ошибке

        """
        if not levels or not avg_profits:
            logger.warning("Нет данных для графика сравнения")
            return None

        chart_config = {
            "type": "bar",
            "data": {
                "labels": levels,
                "datasets": [
                    {
                        "label": "Средняя прибыль ($)",
                        "data": avg_profits,
                        "backgroundColor": "rgba(75, 192, 192, 0.5)",
                    },
                    {
                        "label": "Макс. прибыль ($)",
                        "data": max_profits,
                        "backgroundColor": "rgba(255, 99, 132, 0.5)",
                    },
                ],
            },
            "options": {
                "title": {
                    "display": True,
                    "text": "Сравнение прибыли по уровням",
                },
                "scales": {
                    "yAxes": [
                        {
                            "ticks": {
                                "beginAtZero": True,
                            },
                        },
                    ],
                },
            },
        }

        return await self._generate_chart_url(chart_config)

    async def _generate_chart_url(self, chart_config: dict) -> str | None:
        """Сгенерировать URL графика через QuickChart API.

        Args:
            chart_config: Конфигурация графика в формате Chart.js

        Returns:
            URL сгенерированного графика или None при ошибке

        """
        try:
            # Преобразуем конфигурацию в JSON
            config_json = json.dumps(chart_config)

            # Создаем URL с параметрами

            # Формируем полный URL
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Используем GET запрос с параметрами
                url = f"{QUICKCHART_API}?chart={quote(config_json)}&width={self.width}&height={self.height}&format=png&backgroundColor=white"

                # Проверяем, что URL корректный
                logger.debug(f"Generating chart, URL length: {len(url)}")

                # Для больших конфигураций используем POST
                if len(url) > 2000:
                    response = await client.post(
                        QUICKCHART_API,
                        json={
                            "chart": chart_config,
                            "width": self.width,
                            "height": self.height,
                            "format": "png",
                            "backgroundColor": "white",
                        },
                    )

                    if response.status_code == 200:
                        # API возвращает URL короткого графика
                        result = response.json()
                        chart_url = result.get("url", url)
                    else:
                        logger.error(
                            f"QuickChart API error: {response.status_code}",
                        )
                        return None
                else:
                    chart_url = url

                logger.info("График успешно сгенерирован")
                return chart_url

        except httpx.TimeoutException:
            logger.exception("Timeout при генерации графика")
            return None
        except httpx.RequestError as e:
            logger.exception(f"Ошибка запроса при генерации графика: {e}")
            return None
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при генерации графика: {e}")
            return None


# Глобальный экземпляр генератора
chart_generator = ChartGenerator()


async def generate_profit_chart(data: list[dict[str, Any]]) -> str | None:
    """Удобная функция для генерации графика прибыли.

    Args:
        data: Список данных с полями 'date' и 'profit'

    Returns:
        URL графика или None

    """
    return await chart_generator.generate_profit_chart(data)


async def generate_scan_history_chart(data: list[dict[str, Any]]) -> str | None:
    """Удобная функция для генерации графика истории сканирований.

    Args:
        data: Список данных с полями 'date' и 'count'

    Returns:
        URL графика или None

    """
    return await chart_generator.generate_scan_history_chart(data)


async def generate_level_distribution_chart(data: dict[str, int]) -> str | None:
    """Удобная функция для генерации круговой диаграммы.

    Args:
        data: Словарь с уровнями и количеством

    Returns:
        URL графика или None

    """
    return await chart_generator.generate_level_distribution_chart(data)


async def generate_profit_comparison_chart(
    levels: list[str],
    avg_profits: list[float],
    max_profits: list[float],
) -> str | None:
    """Удобная функция для генерации графика сравнения.

    Args:
        levels: Список уровней
        avg_profits: Средние прибыли
        max_profits: Максимальные прибыли

    Returns:
        URL графика или None

    """
    return await chart_generator.generate_profit_comparison_chart(
        levels,
        avg_profits,
        max_profits,
    )
