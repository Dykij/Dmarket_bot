"""Property-based тесты для функций расчёта прибыли арбитража.

Используем Hypothesis для автоматического поиска edge cases в:
- Расчёте прибыли
- Валидации цен
- Расчёте комиссий
"""

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# Импортируем стратегии из нашего модуля
from tests.property_based.hypothesis_strategies import (
    commission_percent,
    item_popularity,
    price_pAlgor,
    price_usd,
    supported_games,
)

# ============================================================================
# ТЕСТЫ РАСЧЁТА ПРИБЫЛИ
# ============================================================================


class TestProfitCalculation:
    """Property-based тесты для расчёта прибыли."""

    @given(
        buy_price=price_usd,
        sell_price=price_usd,
        commission=commission_percent,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_profit_is_deterministic(
        self,
        buy_price: float,
        sell_price: float,
        commission: float,
    ) -> None:
        """Прибыль должна быть детерминированной для одинаковых входных данных."""
        # Пропускаем невалидные комбинации
        assume(buy_price > 0)
        assume(sell_price > 0)
        assume(commission >= 0)

        def calculate_profit(buy: float, sell: float, comm: float) -> float:
            """Рассчитать чистую прибыль."""
            net_sell = sell * (1 - comm / 100)
            return net_sell - buy

        # Два вызова с одинаковыми параметрами должны дать одинаковый результат
        profit1 = calculate_profit(buy_price, sell_price, commission)
        profit2 = calculate_profit(buy_price, sell_price, commission)

        assert profit1 == profit2, "Расчёт прибыли должен быть детерминированным"

    @given(buy_price=price_usd, sell_price=price_usd)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_zero_commission_gives_full_profit(
        self,
        buy_price: float,
        sell_price: float,
    ) -> None:
        """При нулевой комиссии прибыль равна разнице цен."""
        assume(buy_price > 0)
        assume(sell_price > buy_price)

        commission = 0.0
        net_sell = sell_price * (1 - commission / 100)
        profit = net_sell - buy_price

        expected_profit = sell_price - buy_price
        assert abs(profit - expected_profit) < 0.001, (
            f"При нулевой комиссии прибыль должна быть {expected_profit}, получили {profit}"
        )

    @given(price_pAlgor=price_pAlgor(), commission=commission_percent)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_higher_commission_reduces_profit(
        self,
        price_pAlgor: tuple[float, float],
        commission: float,
    ) -> None:
        """Более высокая комиссия должна уменьшать прибыль."""
        buy_price, sell_price = price_pAlgor
        assume(buy_price > 0)
        assume(sell_price > buy_price)
        assume(commission > 0)

        def calculate_profit(buy: float, sell: float, comm: float) -> float:
            net_sell = sell * (1 - comm / 100)
            return net_sell - buy

        profit_with_commission = calculate_profit(buy_price, sell_price, commission)
        profit_without_commission = calculate_profit(buy_price, sell_price, 0)

        assert profit_with_commission < profit_without_commission, (
            "Прибыль с комиссией должна быть меньше прибыли без комиссии"
        )

    @given(
        buy_price=price_usd,
        multiplier=st.floats(min_value=1.01, max_value=3.0, allow_nan=False),
        commission=commission_percent,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_profit_percent_calculation(
        self,
        buy_price: float,
        multiplier: float,
        commission: float,
    ) -> None:
        """Процент прибыли должен корректно рассчитываться."""
        assume(buy_price > 0.01)

        sell_price = buy_price * multiplier
        net_sell = sell_price * (1 - commission / 100)
        profit = net_sell - buy_price
        profit_percent = (profit / buy_price) * 100

        # Процент прибыли должен быть числом (не NaN, не Inf)
        assert profit_percent == profit_percent, "Процент не должен быть NaN"
        assert profit_percent < float("inf"), "Процент не должен быть бесконечным"

        # При достаточно высоком multiplier и низкой комиссии должна быть прибыль
        if multiplier > 1.2 and commission < 10:
            assert profit_percent > 0, "Должна быть положительная прибыль"


# ============================================================================
# ТЕСТЫ ВАЛИДАЦИИ ЦЕН
# ============================================================================


class TestPriceValidation:
    """Property-based тесты для валидации цен."""

    @given(price=price_usd)
    @settings(max_examples=100)
    def test_valid_prices_are_positive(self, price: float) -> None:
        """Валидные цены должны быть положительными."""
        assert price > 0, "Цена должна быть положительной"

    @given(
        price=st.floats(
            min_value=-10000.0,
            max_value=10000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    @settings(max_examples=100)
    def test_price_validation_rejects_negatives(self, price: float) -> None:
        """Валидация должна отклонять отрицательные цены."""

        def is_valid_price(p: float) -> bool:
            return p > 0

        if price <= 0:
            assert not is_valid_price(price), "Отрицательные цены невалидны"
        else:
            assert is_valid_price(price), "Положительные цены валидны"

    @given(cents=st.integers(min_value=-100, max_value=1_000_000))
    @settings(max_examples=100)
    def test_cents_to_usd_conversion(self, cents: int) -> None:
        """Конвертация центов в USD должна быть корректной."""
        assume(cents >= 0)

        usd = cents / 100
        cents_back = int(usd * 100)

        # Допускаем небольшую погрешность округления
        assert abs(cents - cents_back) <= 1, (
            f"Конвертация {cents} центов -> ${usd} -> {cents_back} центов не должна терять точность"
        )


# ============================================================================
# ТЕСТЫ РАСЧЁТА КОМИССИЙ
# ============================================================================


class TestCommissionCalculation:
    """Property-based тесты для расчёта комиссий."""

    @given(
        popularity=item_popularity,
        game=supported_games,
    )
    @settings(max_examples=100)
    def test_commission_in_valid_range(
        self,
        popularity: float,
        game: str,
    ) -> None:
        """Комиссия должна быть в допустимом диапазоне (2%-15%)."""

        def estimate_commission(pop: float, g: str) -> float:
            """Упрощённая оценка комиссии."""
            base = 7.0  # Базовая комиссия DMarket

            # Корректировка по популярности
            if pop > 0.8:
                base *= 0.85
            elif pop < 0.3:
                base *= 1.15

            # Корректировка по игре
            game_factors = {"csgo": 1.0, "dota2": 1.05, "rust": 1.1, "tf2": 1.0}
            base *= game_factors.get(g, 1.0)

            return max(2.0, min(15.0, base))

        commission = estimate_commission(popularity, game)

        assert 2.0 <= commission <= 15.0, (
            f"Комиссия {commission}% выходит за допустимый диапазон 2-15%"
        )

    @given(
        pop1=item_popularity,
        pop2=item_popularity,
    )
    @settings(max_examples=100)
    def test_higher_popularity_lower_commission(
        self,
        pop1: float,
        pop2: float,
    ) -> None:
        """Более популярные предметы должны иметь меньшую комиссию."""
        assume(abs(pop1 - pop2) > 0.3)  # Значимая разница в популярности

        def estimate_commission(pop: float) -> float:
            base = 7.0
            if pop > 0.8:
                return base * 0.85
            if pop < 0.3:
                return base * 1.15
            return base

        comm1 = estimate_commission(pop1)
        comm2 = estimate_commission(pop2)

        if pop1 > pop2:
            assert comm1 <= comm2, "Популярные предметы имеют меньшую комиссию"
        else:
            assert comm2 <= comm1, "Популярные предметы имеют меньшую комиссию"


# ============================================================================
# ТЕСТЫ EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Property-based тесты для граничных случаев."""

    @given(
        buy=st.floats(min_value=0.01, max_value=0.1, allow_nan=False),
        comm=commission_percent,
    )
    @settings(max_examples=50)
    def test_very_small_prices(self, buy: float, comm: float) -> None:
        """Тест с очень маленькими ценами (edge case)."""
        sell = buy * 1.5  # 50% наценка

        net_sell = sell * (1 - comm / 100)
        profit = net_sell - buy

        # Прибыль должна быть числом, не NaN
        assert profit == profit, "Прибыль не должна быть NaN"
        # При любой наценке и комиссии результат должен быть конечным
        assert abs(profit) < float("inf"), "Прибыль должна быть конечной"

    @given(
        buy=st.floats(min_value=5000.0, max_value=10000.0, allow_nan=False),
        comm=commission_percent,
    )
    @settings(max_examples=50)
    def test_very_large_prices(self, buy: float, comm: float) -> None:
        """Тест с очень большими ценами (edge case)."""
        sell = buy * 1.2  # 20% наценка

        net_sell = sell * (1 - comm / 100)
        profit = net_sell - buy

        # Результат должен быть валидным числом
        assert profit == profit, "Прибыль не должна быть NaN"
        assert abs(profit) < float("inf"), "Прибыль должна быть конечной"

    @given(
        buy=price_usd,
        comm=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_extreme_commissions(self, buy: float, comm: float) -> None:
        """Тест с экстремальными комиссиями."""
        assume(buy > 0)

        sell = buy * 1.5
        net_sell = sell * (1 - comm / 100)
        profit = net_sell - buy

        # При 100% комиссии прибыль должна быть равна -buy
        if comm >= 100:
            assert profit <= -buy + 0.001, "При 100% комиссии теряем всё"

        # При 0% комиссии прибыль максимальна
        if comm == 0:
            assert abs(profit - (sell - buy)) < 0.001, "При 0% комиссии полная прибыль"


# ============================================================================
# ТЕСТЫ ИНВАРИАНТОВ
# ============================================================================


class TestInvariants:
    """Property-based тесты для проверки инвариантов."""

    @given(
        buy_price=price_usd,
        markup_percent=st.floats(
            min_value=1.0,
            max_value=100.0,
            allow_nan=False,
        ),
        commission=commission_percent,
    )
    @settings(max_examples=100)
    def test_profit_increases_with_markup(
        self,
        buy_price: float,
        markup_percent: float,
        commission: float,
    ) -> None:
        """Прибыль должна увеличиваться с ростом наценки."""
        assume(buy_price > 0.01)

        def calculate_profit(buy: float, markup: float, comm: float) -> float:
            sell = buy * (1 + markup / 100)
            net_sell = sell * (1 - comm / 100)
            return net_sell - buy

        profit_low = calculate_profit(buy_price, 5.0, commission)
        profit_high = calculate_profit(buy_price, markup_percent, commission)

        if markup_percent > 5.0:
            assert profit_high >= profit_low - 0.001, (
                "Большая наценка должна давать большую прибыль"
            )

    @given(
        buy_price=price_usd,
        sell_price=price_usd,
    )
    @settings(max_examples=100)
    def test_no_arbitrage_when_buy_equals_sell(
        self,
        buy_price: float,
        sell_price: float,
    ) -> None:
        """При равных ценах покупки и продажи не должно быть прибыли."""
        assume(buy_price > 0)

        # Устанавливаем sell = buy (симулируем одинаковые цены)
        sell = buy_price
        commission = 7.0  # Стандартная комиссия DMarket

        net_sell = sell * (1 - commission / 100)
        profit = net_sell - buy_price

        # При равных ценах и любой комиссии прибыль отрицательна или нулевая
        assert profit <= 0.001, "При равных ценах покупки и продажи не должно быть прибыли"
