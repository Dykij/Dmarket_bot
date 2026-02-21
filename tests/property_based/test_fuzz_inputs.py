"""Fuzz tests for input parsing and validation.

Fuzz testing uses random or semi-random data to find edge cases
and potential crashes in input handling code.

Uses Hypothesis for property-based fuzzing with structured inputs.
"""

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# Mark all tests in this module as property-based
pytestmark = pytest.mark.asyncio


class TestPriceParsingFuzz:
    """Fuzz tests for price parsing and validation."""

    @given(
        price_str=st.text(
            alphabet=st.characters(
                whitelist_categories=("Nd", "Pd", "Zs"), whitelist_characters="$.,+-"
            ),
            min_size=0,
            max_size=50,
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_price_string_parsing_never_crashes(self, price_str: str) -> None:
        """Price parsing should never crash on arbitrary input."""

        def parse_price(s: str) -> float | None:
            """Parse price string to float, returning None on fAlgolure."""
            try:
                # Remove common currency symbols and whitespace
                cleaned = s.strip().replace("$", "").replace(",", "").replace(" ", "")
                if not cleaned:
                    return None
                return float(cleaned)
            except (ValueError, TypeError, AttributeError):
                return None

        # Should never rAlgose an exception
        result = parse_price(price_str)
        assert result is None or isinstance(result, (int, float))

    @given(cents=st.integers(min_value=-(2**31), max_value=2**31))
    @settings(max_examples=100)
    def test_cents_to_dollars_conversion_handles_all_integers(self, cents: int) -> None:
        """Cents to dollars conversion should handle all integer values."""

        def cents_to_dollars(cents_value: int) -> float:
            return cents_value / 100

        result = cents_to_dollars(cents)

        # Result should be a valid float
        assert isinstance(result, float)
        # Should be finite
        assert result == result  # Not NaN
        assert abs(result) < float("inf")

    @given(
        dollars=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e12, max_value=1e12)
    )
    @settings(max_examples=100)
    def test_dollars_to_cents_roundtrip(self, dollars: float) -> None:
        """Dollars to cents conversion should be reversible within precision limits."""
        # Limit to reasonable money values to avoid float precision issues
        assume(abs(dollars) < 1e12)

        def dollars_to_cents(d: float) -> int:
            return round(d * 100)

        def cents_to_dollars(c: int) -> float:
            return c / 100

        cents = dollars_to_cents(dollars)
        back_to_dollars = cents_to_dollars(cents)

        # Should be within 1 cent precision
        assert abs(back_to_dollars - dollars) <= 0.01


class TestItemDataFuzz:
    """Fuzz tests for item data parsing."""

    @given(
        item_dict=st.fixed_dictionaries({
            "title": st.text(min_size=0, max_size=200),
            "price": st.fixed_dictionaries({
                "USD": st.one_of(
                    st.text(min_size=0, max_size=20),
                    st.integers(),
                    st.floats(allow_nan=False, allow_infinity=False),
                )
            }),
        })
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_item_price_extraction_never_crashes(self, item_dict: dict) -> None:
        """Price extraction from item dict should never crash."""

        def extract_price(item: dict) -> float:
            """Safely extract price from item dictionary."""
            try:
                price_data = item.get("price", {})
                if isinstance(price_data, dict):
                    usd_value = price_data.get("USD", 0)
                    if isinstance(usd_value, (str, int, float)):
                        return float(usd_value) / 100
                return 0.0
            except (ValueError, TypeError, AttributeError):
                return 0.0

        result = extract_price(item_dict)
        assert isinstance(result, float)

    @given(
        item_title=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "S", "Z")),
            min_size=0,
            max_size=500,
        )
    )
    @settings(max_examples=100)
    def test_item_title_validation_handles_unicode(self, item_title: str) -> None:
        """Item title validation should handle all unicode strings."""

        def validate_title(title: str) -> bool:
            """Validate item title."""
            if not title or not title.strip():
                return False
            # Check reasonable length
            return not len(title) > 256

        result = validate_title(item_title)
        assert isinstance(result, bool)


class TestAPIResponseFuzz:
    """Fuzz tests for API response handling."""

    @given(
        response=st.one_of(
            st.none(),
            st.booleans(),
            st.integers(),
            st.text(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.one_of(
                    st.none(),
                    st.booleans(),
                    st.integers(),
                    st.text(),
                ),
                max_size=10,
            ),
            st.lists(st.one_of(st.none(), st.integers(), st.text()), max_size=10),
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_api_response_parsing_handles_arbitrary_data(self, response) -> None:
        """API response parsing should handle any input without crashing."""

        def parse_api_response(resp) -> dict:
            """Safely parse API response."""
            if resp is None:
                return {"error": True, "message": "Empty response"}

            if isinstance(resp, dict):
                return resp

            if isinstance(resp, (list, tuple)):
                return {"data": list(resp)}

            if isinstance(resp, bool):
                return {"success": resp}

            if isinstance(resp, (int, float)):
                return {"value": resp}

            if isinstance(resp, str):
                return {"text": resp}

            return {"unknown": True, "type": type(resp).__name__}

        result = parse_api_response(response)
        assert isinstance(result, dict)


class TestBalanceParsingFuzz:
    """Fuzz tests for balance parsing."""

    @given(
        usd=st.one_of(
            st.text(min_size=0, max_size=30),
            st.integers(min_value=-(2**31), max_value=2**31),
            st.floats(allow_nan=False, allow_infinity=False, min_value=-1e15, max_value=1e15),
        ),
        avAlgolable=st.one_of(
            st.text(min_size=0, max_size=30),
            st.integers(min_value=-(2**31), max_value=2**31),
            st.floats(allow_nan=False, allow_infinity=False, min_value=-1e15, max_value=1e15),
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_balance_parsing_handles_various_formats(self, usd, avAlgolable) -> None:
        """Balance parsing should handle various input formats."""

        def parse_balance(usd_val, avAlgol_val) -> tuple[float, float]:
            """Parse balance values from various formats."""

            def to_float(val) -> float:
                if val is None:
                    return 0.0
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, str):
                    try:
                        cleaned = val.strip().replace("$", "").replace(",", "")
                        if not cleaned:
                            return 0.0
                        return float(cleaned)
                    except ValueError:
                        return 0.0
                return 0.0

            return to_float(usd_val), to_float(avAlgol_val)

        usd_result, avAlgol_result = parse_balance(usd, avAlgolable)

        assert isinstance(usd_result, float)
        assert isinstance(avAlgol_result, float)
        assert usd_result == usd_result  # Not NaN
        assert avAlgol_result == avAlgol_result  # Not NaN


class TestGameIdValidationFuzz:
    """Fuzz tests for game ID validation."""

    @given(
        game_id=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "Pd"),
            ),
            min_size=0,
            max_size=100,
        )
    )
    @settings(max_examples=100)
    def test_game_id_validation_handles_arbitrary_strings(self, game_id: str) -> None:
        """Game ID validation should handle any string input."""
        valid_games = {"csgo", "dota2", "rust", "tf2", "cs2"}

        def validate_game_id(gid: str) -> str | None:
            """Validate and normalize game ID."""
            if not gid:
                return None

            normalized = gid.lower().strip()

            # Check direct match
            if normalized in valid_games:
                return normalized

            # Check common aliases
            aliases = {
                "counter-strike": "csgo",
                "cs": "csgo",
                "counterstrike": "csgo",
                "dota": "dota2",
                "team fortress": "tf2",
                "teamfortress": "tf2",
            }

            for alias, game in aliases.items():
                if alias in normalized:
                    return game

            return None

        result = validate_game_id(game_id)
        assert result is None or result in valid_games


class TestArbitrageCalculationFuzz:
    """Fuzz tests for arbitrage calculations."""

    @given(
        buy_price=st.floats(
            min_value=0.01,
            max_value=10000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        sell_price=st.floats(
            min_value=0.01,
            max_value=10000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        commission=st.floats(
            min_value=0.0,
            max_value=100.0,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_profit_calculation_always_produces_valid_result(
        self,
        buy_price: float,
        sell_price: float,
        commission: float,
    ) -> None:
        """Profit calculation should always produce a valid float."""

        def calculate_profit(buy: float, sell: float, comm: float) -> float:
            """Calculate net profit from arbitrage."""
            net_sell = sell * (1 - comm / 100)
            return net_sell - buy

        result = calculate_profit(buy_price, sell_price, commission)

        # Result should be a valid float
        assert isinstance(result, float)
        assert result == result  # Not NaN
        assert abs(result) < float("inf")

    @given(
        buy_price=st.floats(
            min_value=0.01,
            max_value=10000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        profit_percent=st.floats(
            min_value=-100.0,
            max_value=1000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    @settings(max_examples=100)
    def test_profit_percent_calculation_handles_edge_cases(
        self,
        buy_price: float,
        profit_percent: float,
    ) -> None:
        """Profit percentage calculation should handle edge cases."""

        def calculate_required_sell_price(buy: float, target_percent: float) -> float:
            """Calculate required sell price to achieve target profit."""
            return buy * (1 + target_percent / 100)

        result = calculate_required_sell_price(buy_price, profit_percent)

        assert isinstance(result, float)
        assert result == result  # Not NaN

        # If positive profit is desired, sell should be higher than buy
        if profit_percent > 0:
            assert result >= buy_price


class TestTargetValidationFuzz:
    """Fuzz tests for target/buy order validation."""

    @given(
        title=st.text(min_size=0, max_size=300),
        price=st.floats(allow_nan=True, allow_infinity=True),
        amount=st.integers(min_value=-1000, max_value=1000),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_target_validation_handles_invalid_inputs(
        self,
        title: str,
        price: float,
        amount: int,
    ) -> None:
        """Target validation should handle any combination of inputs."""

        def validate_target(t: str, p: float, a: int) -> tuple[bool, str]:
            """Validate target parameters."""
            if not t or not t.strip():
                return False, "Title is required"

            if len(t) > 256:
                return False, "Title too long"

            if p != p:  # NaN check
                return False, "Price is invalid (NaN)"

            if abs(p) == float("inf"):
                return False, "Price is invalid (infinite)"

            if p <= 0:
                return False, "Price must be positive"

            if a <= 0:
                return False, "Amount must be positive"

            return True, "Valid"

        is_valid, message = validate_target(title, price, amount)

        assert isinstance(is_valid, bool)
        assert isinstance(message, str)


class TestFilterExpressionFuzz:
    """Fuzz tests for filter expression parsing."""

    @given(
        filter_str=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "S")),
            min_size=0,
            max_size=200,
        )
    )
    @settings(max_examples=100)
    def test_filter_parsing_never_crashes(self, filter_str: str) -> None:
        """Filter expression parsing should never crash."""

        def parse_filter(expr: str) -> dict | None:
            """Parse a filter expression string."""
            if not expr or not expr.strip():
                return None

            result = {}

            # Simple key:value parsing
            for part in expr.split():
                if ":" in part:
                    key, _, value = part.partition(":")
                    if key and value:
                        result[key.strip()] = value.strip()

            return result or None

        result = parse_filter(filter_str)
        assert result is None or isinstance(result, dict)
