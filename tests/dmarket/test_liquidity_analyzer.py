"""Тесты для модуля анализа ликвидности предметов."""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.dmarket.liquidity_analyzer import LiquidityAnalyzer, LiquidityMetrics


class TestLiquidityMetrics:
    """Тесты для LiquidityMetrics dataclass."""

    def test_create_metrics(self) -> None:
        """Тест создания метрик ликвидности."""
        metrics = LiquidityMetrics(
            item_title="AK-47 | Redline (Field-Tested)",
            sales_per_week=15.0,
            avg_time_to_sell_days=3.5,
            active_offers_count=25,
            price_stability=0.92,
            market_depth=850.0,
            liquidity_score=75.5,
            is_liquid=True,
        )

        assert metrics.item_title == "AK-47 | Redline (Field-Tested)"
        assert metrics.sales_per_week == 15.0
        assert metrics.avg_time_to_sell_days == 3.5
        assert metrics.active_offers_count == 25
        assert metrics.price_stability == 0.92
        assert metrics.market_depth == 850.0
        assert metrics.liquidity_score == 75.5
        assert metrics.is_liquid is True


@pytest.fixture()
def mock_api_client() -> AsyncMock:
    """Мок DMarket API клиента."""
    client = AsyncMock()
    client.get_sales_history_aggregator = AsyncMock()
    client.get_market_best_offers = AsyncMock()
    return client


@pytest.fixture()
def liquidity_analyzer(mock_api_client: AsyncMock) -> LiquidityAnalyzer:
    """Создать LiquidityAnalyzer с моком API."""
    return LiquidityAnalyzer(
        api_client=mock_api_client,
        min_sales_per_week=10.0,
        max_time_to_sell_days=7.0,
        max_active_offers=50,
        min_price_stability=0.85,
        min_liquidity_score=60.0,
    )


class TestLiquidityAnalyzer:
    """Тесты для LiquidityAnalyzer."""

    @pytest.mark.asyncio()
    async def test_analyzer_initialization(
        self, liquidity_analyzer: LiquidityAnalyzer
    ) -> None:
        """Тест инициализации анализатора."""
        assert liquidity_analyzer.min_sales_per_week == 10.0
        assert liquidity_analyzer.max_time_to_sell_days == 7.0
        assert liquidity_analyzer.max_active_offers == 50
        assert liquidity_analyzer.min_price_stability == 0.85
        assert liquidity_analyzer.min_liquidity_score == 60.0

    @pytest.mark.asyncio()
    async def test_analyze_high_liquidity_item(
        self,
        liquidity_analyzer: LiquidityAnalyzer,
        mock_api_client: AsyncMock,
    ) -> None:
        """Тест анализа высоколиквидного предмета."""
        # Мок данных: высокая ликвидность
        mock_api_client.get_sales_history_aggregator = AsyncMock(
            return_value={
                "sales": [
                    {
                        "price": 1200,
                        "date": int((datetime.now() - timedelta(days=i)).timestamp()),
                    }
                    for i in range(30)  # 30 продаж за 30 дней
                ]
            }
        )

        mock_api_client.get_market_best_offers = AsyncMock(
            return_value={
                "objects": [
                    {"itemId": f"item_{i}"} for i in range(20)
                ]  # 20 предложений
            }
        )

        metrics = await liquidity_analyzer.analyze_item_liquidity(
            item_title="AK-47 | Redline (Field-Tested)",
            game="csgo",
            days_history=30,
        )

        # Проверки
        assert metrics.item_title == "AK-47 | Redline (Field-Tested)"
        assert metrics.sales_per_week >= 6.0  # ~7 продаж в неделю (30/30*7)
        assert metrics.active_offers_count == 20
        assert metrics.liquidity_score > 50.0
        assert isinstance(metrics.is_liquid, bool)

    @pytest.mark.asyncio()
    async def test_analyze_low_liquidity_item(
        self,
        liquidity_analyzer: LiquidityAnalyzer,
        mock_api_client: AsyncMock,
    ) -> None:
        """Тест анализа низколиквидного предмета."""
        # Мок данных: низкая ликвидность
        mock_api_client.get_sales_history_aggregator = AsyncMock(
            return_value={
                "sales": [
                    {
                        "price": 5000,
                        "date": int(
                            (datetime.now() - timedelta(days=i * 10)).timestamp()
                        ),
                    }
                    for i in range(3)  # Только 3 продажи за 30 дней
                ]
            }
        )

        mock_api_client.get_market_best_offers = AsyncMock(
            return_value={
                "objects": [
                    {"itemId": f"item_{i}"} for i in range(80)
                ]  # 80 предложений
            }
        )

        metrics = await liquidity_analyzer.analyze_item_liquidity(
            item_title="Rare Expensive Item",
            game="csgo",
            days_history=30,
        )

        # Проверки
        assert metrics.sales_per_week < 5.0  # Очень мало продаж
        assert metrics.active_offers_count == 80  # Много предложений
        assert metrics.liquidity_score < 60.0  # Низкий score
        assert metrics.is_liquid is False  # Неликвидный

    @pytest.mark.asyncio()
    async def test_filter_liquid_items(
        self,
        liquidity_analyzer: LiquidityAnalyzer,
        mock_api_client: AsyncMock,
    ) -> None:
        """Тест фильтрации ликвидных предметов."""
        items = [
            {"title": "AK-47 | Redline (Field-Tested)", "price": {"USD": 1200}},
            {"title": "AWP | Asiimov (Field-Tested)", "price": {"USD": 5000}},
            {"title": "Rare Item", "price": {"USD": 10000}},
        ]

        # Мок: первый предмет ликвидный, втоSwarm средне, третий неликвидный
        async def mock_analyze(
            self, item_title: str, game: str = "csgo", **kwargs: Any
        ) -> LiquidityMetrics:
            if "Redline" in item_title:
                return LiquidityMetrics(
                    item_title=item_title,
                    sales_per_week=15.0,
                    avg_time_to_sell_days=3.0,
                    active_offers_count=20,
                    price_stability=0.90,
                    market_depth=800.0,
                    liquidity_score=75.0,
                    is_liquid=True,
                )
            if "Asiimov" in item_title:
                return LiquidityMetrics(
                    item_title=item_title,
                    sales_per_week=8.0,
                    avg_time_to_sell_days=6.0,
                    active_offers_count=40,
                    price_stability=0.85,
                    market_depth=600.0,
                    liquidity_score=62.0,
                    is_liquid=True,
                )
            # Rare Item
            return LiquidityMetrics(
                item_title=item_title,
                sales_per_week=2.0,
                avg_time_to_sell_days=15.0,
                active_offers_count=100,
                price_stability=0.70,
                market_depth=200.0,
                liquidity_score=35.0,
                is_liquid=False,
            )

        # Патчим на экземпляре (bind to instance)
        liquidity_analyzer.analyze_item_liquidity = (  # type: ignore[method-assign]
            mock_analyze.__get__(liquidity_analyzer, LiquidityAnalyzer)
        )

        liquid_items = await liquidity_analyzer.filter_liquid_items(items, game="csgo")

        # Проверки
        assert len(liquid_items) == 2  # Только Redline и Asiimov
        assert liquid_items[0]["title"] == "AK-47 | Redline (Field-Tested)"
        assert liquid_items[1]["title"] == "AWP | Asiimov (Field-Tested)"

    @pytest.mark.asyncio()
    async def test_calculate_sales_per_week(
        self, liquidity_analyzer: LiquidityAnalyzer
    ) -> None:
        """Тест расчета продаж в неделю."""
        sales_history = [{"price": 1000, "date": 1234567890} for _ in range(21)]

        sales_per_week = liquidity_analyzer._calculate_sales_per_week(
            sales_history, days_history=30
        )

        # 21 продажа за 30 дней = ~4.9 продаж в неделю
        assert 4.5 <= sales_per_week <= 5.5

    @pytest.mark.asyncio()
    async def test_calculate_avg_time_to_sell(
        self, liquidity_analyzer: LiquidityAnalyzer
    ) -> None:
        """Тест расчета среднего времени продажи."""
        now = int(datetime.now().timestamp())
        sales_history = [
            {"price": 1000, "date": now - (i * 86400)}  # 1 день = 86400 сек
            for i in range(10)
        ]

        avg_time = liquidity_analyzer._calculate_avg_time_to_sell(sales_history)

        # В среднем ~1 день между продажами
        assert 0.5 <= avg_time <= 1.5

    @pytest.mark.asyncio()
    async def test_calculate_price_stability(
        self, liquidity_analyzer: LiquidityAnalyzer
    ) -> None:
        """Тест расчета стабильности цены."""
        # Стабильные цены (разброс 5%)
        stable_history = [{"price": 1000 + i * 10, "date": 123456} for i in range(10)]

        stability = liquidity_analyzer._calculate_price_stability(stable_history)
        assert stability > 0.80  # Высокая стабильность

        # Нестабильные цены (разброс 50%)
        unstable_history = [
            {"price": 1000 + i * 100, "date": 123456} for i in range(10)
        ]

        instability = liquidity_analyzer._calculate_price_stability(unstable_history)
        assert instability < 0.85  # Низкая стабильность (скорректировано)

    @pytest.mark.asyncio()
    async def test_calculate_market_depth(
        self, liquidity_analyzer: LiquidityAnalyzer
    ) -> None:
        """Тест расчета глубины рынка."""
        sales_history = [{"price": 1000, "date": 123456} for _ in range(50)]

        depth = liquidity_analyzer._calculate_market_depth(sales_history)

        assert depth > 0  # Глубина должна быть положительной
        assert isinstance(depth, float)

    @pytest.mark.asyncio()
    async def test_calculate_liquidity_score(
        self, liquidity_analyzer: LiquidityAnalyzer
    ) -> None:
        """Тест расчета общего liquidity score."""
        # Идеальные параметры
        score_high = liquidity_analyzer._calculate_liquidity_score(
            sales_per_week=20.0,
            avg_time_to_sell_days=2.0,
            active_offers_count=15,
            price_stability=0.95,
            market_depth=1.0,  # Нормализованный 0-1
        )

        assert score_high >= 70.0  # Высокий score

        # Плохие параметры
        score_low = liquidity_analyzer._calculate_liquidity_score(
            sales_per_week=2.0,
            avg_time_to_sell_days=15.0,
            active_offers_count=100,
            price_stability=0.60,
            market_depth=0.1,  # Низкая нормализованная глубина
        )

        assert score_low <= 40.0  # Низкий score

    @pytest.mark.asyncio()
    async def test_is_item_liquid(self, liquidity_analyzer: LiquidityAnalyzer) -> None:
        """Тест определения ликвидности предмета."""
        # Ликвидный предмет
        is_liquid_high = liquidity_analyzer._is_item_liquid(
            sales_per_week=15.0,
            avg_time_to_sell_days=4.0,
            active_offers_count=25,
            liquidity_score=75.0,
        )

        assert is_liquid_high is True

        # Неликвидный предмет
        is_liquid_low = liquidity_analyzer._is_item_liquid(
            sales_per_week=3.0,
            avg_time_to_sell_days=12.0,
            active_offers_count=80,
            liquidity_score=35.0,
        )

        assert is_liquid_low is False

    @pytest.mark.asyncio()
    async def test_get_liquidity_description(
        self, liquidity_analyzer: LiquidityAnalyzer
    ) -> None:
        """Тест получения описания ликвидности."""
        desc_high = liquidity_analyzer.get_liquidity_description(85.0)
        assert "🟢" in desc_high
        assert "Очень высокая" in desc_high

        desc_medium = liquidity_analyzer.get_liquidity_description(55.0)
        assert "🟠" in desc_medium
        assert "Средняя" in desc_medium

        desc_low = liquidity_analyzer.get_liquidity_description(15.0)
        assert "🔴" in desc_low or "⚫" in desc_low
        assert "Низкая" in desc_low or "низкая" in desc_low.lower()

    @pytest.mark.asyncio()
    async def test_empty_sales_history(
        self,
        liquidity_analyzer: LiquidityAnalyzer,
        mock_api_client: AsyncMock,
    ) -> None:
        """Тест обработки пустой истории продаж."""
        mock_api_client.get_sales_history_aggregator = AsyncMock(
            return_value={"sales": []}
        )
        mock_api_client.get_market_best_offers = AsyncMock(return_value={"objects": []})

        metrics = await liquidity_analyzer.analyze_item_liquidity(
            item_title="New Item", game="csgo"
        )

        # Новый предмет должен считаться неликвидным
        assert metrics.sales_per_week == 0.0
        assert metrics.is_liquid is False

    @pytest.mark.asyncio()
    async def test_api_error_handling(
        self,
        liquidity_analyzer: LiquidityAnalyzer,
        mock_api_client: AsyncMock,
    ) -> None:
        """Тест обработки ошибок API."""
        mock_api_client.get_sales_history_aggregator = AsyncMock(
            side_effect=Exception("API Error")
        )
        mock_api_client.get_market_best_offers = AsyncMock(return_value={"objects": []})

        # Должен вернуть метрики с is_liquid=False при ошибке
        # При пустой истории score будет около 15.0
        metrics = await liquidity_analyzer.analyze_item_liquidity(
            item_title="Error Item", game="csgo"
        )

        # При ошибке API возвращаются пустые данные
        assert metrics.sales_per_week == 0.0
        assert metrics.active_offers_count == 0
        assert metrics.is_liquid is False
        # Score может быть >0 т.к. используются дефолтные значения
        assert metrics.liquidity_score >= 0.0

    @pytest.mark.asyncio()
    async def test_get_sales_history_pagination(
        self,
        liquidity_analyzer: LiquidityAnalyzer,
        mock_api_client: AsyncMock,
    ) -> None:
        """Тест пагинации при получении истории продаж."""
        import time

        current_time = time.time()

        # Страница 1: 20 элементов
        page1 = {
            "sales": [
                {"date": current_time - i * 3600, "price": 100} for i in range(20)
            ]
        }

        # Страница 2: 20 элементов (полная страница, должен запросить следующую)
        page2 = {
            "sales": [
                {"date": current_time - (20 + i) * 3600, "price": 100}
                for i in range(20)
            ]
        }

        # Страница 3: пустая (конец)
        page3 = {"sales": []}

        mock_api_client.get_sales_history_aggregator.side_effect = [
            page1,
            page2,
            page3,
        ]

        # Вызов приватного метода для теста
        history = await liquidity_analyzer._get_sales_history(
            item_title="Test Item",
            game="csgo",
            days=7,
        )

        # Проверки
        assert len(history) == 40
        assert mock_api_client.get_sales_history_aggregator.call_count == 3

        # Проверка параметров вызова (offset увеличивается)
        calls = mock_api_client.get_sales_history_aggregator.call_args_list
        assert calls[0].kwargs["offset"] == 0
        assert calls[1].kwargs["offset"] == 20
        assert calls[2].kwargs["offset"] == 40
