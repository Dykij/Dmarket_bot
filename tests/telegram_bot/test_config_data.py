"""Тесты для модуля config_data.

Проверяет конфигурацию арбитражных режимов.
"""

from src.telegram_bot.config_data import ARBITRAGE_MODES


class TestArbitrageModes:
    """Тесты констант арбитражных режимов."""

    def test_arbitrage_modes_exist(self):
        """Тест наличия всех режимов арбитража."""
        assert "boost_low" in ARBITRAGE_MODES
        assert "mid_medium" in ARBITRAGE_MODES
        assert "pro_high" in ARBITRAGE_MODES

    def test_boost_low_mode_structure(self):
        """Тест структуры режима boost_low."""
        mode = ARBITRAGE_MODES["boost_low"]
        assert "name" in mode
        assert "min_price" in mode
        assert "max_price" in mode
        assert "min_profit_percent" in mode
        assert "min_profit_amount" in mode
        assert "trade_strategy" in mode

    def test_boost_low_mode_values(self):
        """Тест значений режима boost_low."""
        mode = ARBITRAGE_MODES["boost_low"]
        assert mode["min_price"] == 1.0
        assert mode["max_price"] == 50.0
        assert mode["min_profit_percent"] == 5.0
        assert mode["min_profit_amount"] == 0.5
        assert mode["trade_strategy"] == "fast_turnover"

    def test_mid_medium_mode_structure(self):
        """Тест структуры режима mid_medium."""
        mode = ARBITRAGE_MODES["mid_medium"]
        assert "name" in mode
        assert "min_price" in mode
        assert "max_price" in mode
        assert "min_profit_percent" in mode
        assert "min_profit_amount" in mode
        assert "trade_strategy" in mode

    def test_mid_medium_mode_values(self):
        """Тест значений режима mid_medium."""
        mode = ARBITRAGE_MODES["mid_medium"]
        assert mode["min_price"] == 10.0
        assert mode["max_price"] == 200.0
        assert mode["min_profit_percent"] == 10.0
        assert mode["min_profit_amount"] == 2.0
        assert mode["trade_strategy"] == "balanced"

    def test_pro_high_mode_structure(self):
        """Тест структуры режима pro_high."""
        mode = ARBITRAGE_MODES["pro_high"]
        assert "name" in mode
        assert "min_price" in mode
        assert "max_price" in mode
        assert "min_profit_percent" in mode
        assert "min_profit_amount" in mode
        assert "trade_strategy" in mode

    def test_pro_high_mode_values(self):
        """Тест значений режима pro_high."""
        mode = ARBITRAGE_MODES["pro_high"]
        assert mode["min_price"] == 50.0
        assert mode["max_price"] == 1000.0
        assert mode["min_profit_percent"] == 15.0
        assert mode["min_profit_amount"] == 5.0
        assert mode["trade_strategy"] == "high_profit"

    def test_price_ranges_are_ascending(self):
        """Тест что диапазоны цен увеличиваются."""
        boost = ARBITRAGE_MODES["boost_low"]
        mid = ARBITRAGE_MODES["mid_medium"]
        pro = ARBITRAGE_MODES["pro_high"]

        assert boost["max_price"] < mid["max_price"]
        assert mid["max_price"] < pro["max_price"]

    def test_profit_requirements_ascending(self):
        """Тест что требования к прибыли увеличиваются."""
        boost = ARBITRAGE_MODES["boost_low"]
        mid = ARBITRAGE_MODES["mid_medium"]
        pro = ARBITRAGE_MODES["pro_high"]

        assert boost["min_profit_percent"] < mid["min_profit_percent"]
        assert mid["min_profit_percent"] < pro["min_profit_percent"]

    def test_all_modes_have_trade_strategy(self):
        """Тест что у всех режимов есть стратегия торговли."""
        for mode_data in ARBITRAGE_MODES.values():
            assert "trade_strategy" in mode_data
            assert isinstance(mode_data["trade_strategy"], str)
            assert len(mode_data["trade_strategy"]) > 0

    def test_all_prices_positive(self):
        """Тест что все цены положительные."""
        for mode_data in ARBITRAGE_MODES.values():
            assert mode_data["min_price"] > 0
            assert mode_data["max_price"] > 0
            assert mode_data["min_price"] < mode_data["max_price"]

    def test_all_profit_values_positive(self):
        """Тест что все значения прибыли положительные."""
        for mode_data in ARBITRAGE_MODES.values():
            assert mode_data["min_profit_percent"] > 0
            assert mode_data["min_profit_amount"] > 0
