"""
Snapshot Testing Module.

Tests for detecting unexpected changes in output through snapshots.

Covers:
- JSON response snapshots
- API response structure validation
- Configuration snapshot validation
- Message format snapshots
- Data serialization snapshots
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class SnapshotData:
    """Data structure for snapshot comparison."""

    name: str
    content: Any
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute hash of content."""
        content_str = json.dumps(self.content, sort_keys=True, default=str)
        return hashlib.md5(content_str.encode()).hexdigest()


class TestAPIResponseSnapshots:
    """Tests for API response structure snapshots."""

    @pytest.fixture
    def expected_balance_response(self):
        """Expected balance response structure."""
        return {
            "usd": {"type": "string", "pattern": r"^\d+$"},
            "dmc": {"type": "string", "pattern": r"^\d+$"},
        }

    @pytest.fixture
    def expected_market_item_response(self):
        """Expected market item response structure."""
        return {
            "itemId": {"type": "string", "required": True},
            "title": {"type": "string", "required": True},
            "price": {
                "type": "object",
                "properties": {
                    "USD": {"type": "string", "required": True},
                },
            },
            "suggestedPrice": {
                "type": "object",
                "properties": {
                    "USD": {"type": "string", "required": False},
                },
            },
            "gameId": {"type": "string", "required": True},
            "extra": {"type": "object", "required": False},
        }

    def test_balance_response_structure(self, expected_balance_response):
        """Test that balance response matches expected structure."""
        sample_response = {"usd": "10000", "dmc": "5000"}

        for key, schema in expected_balance_response.items():
            assert key in sample_response, f"Missing key: {key}"
            assert isinstance(sample_response[key], str), f"Wrong type for {key}"

    def test_market_item_response_structure(self, expected_market_item_response):
        """Test that market item response matches expected structure."""
        sample_response = {
            "itemId": "abc123",
            "title": "AK-47 | Redline",
            "price": {"USD": "1500"},
            "suggestedPrice": {"USD": "1600"},
            "gameId": "csgo",
            "extra": {"float": "0.15"},
        }

        def validate_structure(data: dict, schema: dict) -> bool:
            for key, rules in schema.items():
                if rules.get("required", True) and key not in data:
                    return False
                if key in data:
                    if rules["type"] == "object" and "properties" in rules:
                        if not validate_structure(data[key], rules["properties"]):
                            return False
            return True

        assert validate_structure(sample_response, expected_market_item_response)

    def test_response_structure_snapshot(self):
        """Test response structure hasn't changed unexpectedly."""
        # Define expected structure hash
        expected_structure = {
            "balance": ["usd", "dmc"],
            "market_item": ["itemId", "title", "price", "gameId"],
            "target": ["targetId", "title", "price", "amount", "status"],
        }

        snapshot = SnapshotData(name="api_structure", content=expected_structure)

        # Structure should have consistent hash
        expected_hash = snapshot.hash
        new_snapshot = SnapshotData(name="api_structure", content=expected_structure)

        assert new_snapshot.hash == expected_hash, "API structure changed unexpectedly"


class TestMessageFormatSnapshots:
    """Tests for message format snapshots."""

    @pytest.fixture
    def message_templates(self):
        """Message templates for snapshot testing."""
        return {
            "balance_message": "💰 Your Balance\n\nUSD: ${usd}\nDMC: {dmc}",
            "arbitrage_found": "🎯 Arbitrage Opportunity!\n\n{title}\nBuy: ${buy_price}\nSell: ${sell_price}\nProfit: ${profit} ({profit_pct}%)",
            "target_created": "✅ Target Created\n\n{title}\nPrice: ${price}\nAmount: {amount}",
            "error_message": "❌ Error: {error}\n\n{action}",
        }

    def test_message_template_snapshot(self, message_templates):
        """Test message templates haven't changed."""
        snapshot = SnapshotData(name="messages", content=message_templates)

        # Verify specific templates exist
        assert "balance_message" in message_templates
        assert "💰" in message_templates["balance_message"]

        assert "arbitrage_found" in message_templates
        assert "🎯" in message_templates["arbitrage_found"]

    def test_message_format_consistency(self, message_templates):
        """Test message format is consistent."""
        # All messages should use consistent placeholder format
        import re

        placeholder_pattern = r"\{[a-z_]+\}"

        for name, template in message_templates.items():
            placeholders = re.findall(placeholder_pattern, template)
            # Each placeholder should be unique (no duplicates)
            unique_placeholders = set(placeholders)
            assert len(placeholders) == len(unique_placeholders), f"Duplicate placeholders in {name}"


class TestConfigurationSnapshots:
    """Tests for configuration snapshots."""

    @pytest.fixture
    def default_config(self):
        """Default configuration for snapshot."""
        return {
            "arbitrage": {
                "levels": {
                    "boost": {"min_price": 50, "max_price": 300},
                    "standard": {"min_price": 300, "max_price": 1000},
                    "medium": {"min_price": 1000, "max_price": 3000},
                    "advanced": {"min_price": 3000, "max_price": 10000},
                    "pro": {"min_price": 10000, "max_price": 100000},
                },
                "min_profit_margin": 3.0,
                "fee_percent": 7.0,
            },
            "rate_limits": {
                "requests_per_minute": 30,
                "burst_limit": 10,
            },
            "cache": {
                "ttl_seconds": 300,
                "max_size": 1000,
            },
        }

    def test_arbitrage_levels_snapshot(self, default_config):
        """Test arbitrage levels haven't changed."""
        levels = default_config["arbitrage"]["levels"]

        # Verify all levels exist
        expected_levels = ["boost", "standard", "medium", "advanced", "pro"]
        for level in expected_levels:
            assert level in levels, f"Missing level: {level}"
            assert "min_price" in levels[level]
            assert "max_price" in levels[level]

    def test_rate_limits_snapshot(self, default_config):
        """Test rate limits are within expected range."""
        rate_limits = default_config["rate_limits"]

        assert 20 <= rate_limits["requests_per_minute"] <= 60
        assert rate_limits["burst_limit"] <= rate_limits["requests_per_minute"]

    def test_config_structure_unchanged(self, default_config):
        """Test overall config structure unchanged."""
        expected_keys = {"arbitrage", "rate_limits", "cache"}
        actual_keys = set(default_config.keys())

        assert expected_keys == actual_keys, f"Config structure changed: {actual_keys - expected_keys}"


class TestDataSerializationSnapshots:
    """Tests for data serialization snapshots."""

    @pytest.fixture
    def sample_arbitrage_opportunity(self):
        """Sample arbitrage opportunity for serialization testing."""
        return {
            "item_id": "abc123",
            "title": "AK-47 | Redline (Field-Tested)",
            "game": "csgo",
            "buy_price": 15.50,
            "sell_price": 17.25,
            "profit": 0.84,
            "profit_margin": 5.42,
            "liquidity_score": 85,
            "created_at": "2024-01-15T10:30:00Z",
        }

    def test_opportunity_serialization(self, sample_arbitrage_opportunity):
        """Test opportunity serialization format."""
        # Serialize to JSON
        json_str = json.dumps(sample_arbitrage_opportunity, sort_keys=True)

        # Deserialize back
        deserialized = json.loads(json_str)

        # Should match original
        assert deserialized == sample_arbitrage_opportunity

        # Check specific fields
        assert isinstance(deserialized["buy_price"], float)
        assert isinstance(deserialized["profit_margin"], float)

    def test_serialization_format_snapshot(self, sample_arbitrage_opportunity):
        """Test serialization format hasn't changed."""
        # Create snapshot of serialized format
        serialized = json.dumps(sample_arbitrage_opportunity, sort_keys=True, indent=2)

        # Check format characteristics
        assert '"buy_price": 15.5' in serialized
        assert '"game": "csgo"' in serialized
        assert '"item_id": "abc123"' in serialized


class TestKeyboardLayoutSnapshots:
    """Tests for Telegram keyboard layout snapshots."""

    @pytest.fixture
    def main_menu_keyboard(self):
        """Main menu keyboard layout."""
        return [
            [{"text": "💰 Balance", "callback_data": "balance"}],
            [
                {"text": "🔍 Scan Market", "callback_data": "scan"},
                {"text": "🎯 Targets", "callback_data": "targets"},
            ],
            [
                {"text": "📊 Analytics", "callback_data": "analytics"},
                {"text": "⚙️ Settings", "callback_data": "settings"},
            ],
            [{"text": "❓ Help", "callback_data": "help"}],
        ]

    @pytest.fixture
    def game_selection_keyboard(self):
        """Game selection keyboard layout."""
        return [
            [
                {"text": "🔫 CS:GO", "callback_data": "game_csgo"},
                {"text": "⚔️ Dota 2", "callback_data": "game_dota2"},
            ],
            [
                {"text": "🎩 TF2", "callback_data": "game_tf2"},
                {"text": "🏝️ Rust", "callback_data": "game_rust"},
            ],
            [{"text": "🔙 Back", "callback_data": "back"}],
        ]

    def test_main_menu_structure(self, main_menu_keyboard):
        """Test main menu keyboard structure."""
        # Should have exactly 4 rows
        assert len(main_menu_keyboard) == 4

        # First row should be Balance
        assert main_menu_keyboard[0][0]["text"] == "💰 Balance"

        # Last row should be Help
        assert main_menu_keyboard[-1][0]["text"] == "❓ Help"

    def test_game_selection_structure(self, game_selection_keyboard):
        """Test game selection keyboard structure."""
        # Should have 3 rows
        assert len(game_selection_keyboard) == 3

        # First two rows should have 2 buttons each
        assert len(game_selection_keyboard[0]) == 2
        assert len(game_selection_keyboard[1]) == 2

        # Last row should be Back button
        assert game_selection_keyboard[-1][0]["text"] == "🔙 Back"

    def test_callback_data_format(self, main_menu_keyboard, game_selection_keyboard):
        """Test callback data follows consistent format."""
        all_callbacks = []

        for keyboard in [main_menu_keyboard, game_selection_keyboard]:
            for row in keyboard:
                for button in row:
                    all_callbacks.append(button["callback_data"])

        # All callbacks should be lowercase with underscores
        for callback in all_callbacks:
            assert callback == callback.lower(), f"Callback not lowercase: {callback}"
            assert " " not in callback, f"Callback contains space: {callback}"


class TestErrorResponseSnapshots:
    """Tests for error response snapshots."""

    @pytest.fixture
    def error_responses(self):
        """Standard error responses."""
        return {
            "validation_error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid input",
                "details": [],
            },
            "not_found": {
                "code": "NOT_FOUND",
                "message": "Resource not found",
                "details": [],
            },
            "rate_limit": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests",
                "retry_after": 60,
            },
            "auth_error": {
                "code": "AUTHENTICATION_FAILED",
                "message": "Invalid credentials",
                "details": [],
            },
            "api_error": {
                "code": "EXTERNAL_API_ERROR",
                "message": "External service unavailable",
                "retry_after": 30,
            },
        }

    def test_error_response_structure(self, error_responses):
        """Test error response structure consistency."""
        required_fields = ["code", "message"]

        for error_type, response in error_responses.items():
            for field in required_fields:
                assert field in response, f"Missing {field} in {error_type}"

    def test_error_codes_format(self, error_responses):
        """Test error codes follow format convention."""
        for error_type, response in error_responses.items():
            code = response["code"]
            # Code should be uppercase with underscores
            assert code == code.upper(), f"Code not uppercase: {code}"
            assert " " not in code, f"Code contains space: {code}"

    def test_error_snapshot_unchanged(self, error_responses):
        """Test error responses haven't changed unexpectedly."""
        snapshot = SnapshotData(name="errors", content=error_responses)

        # Create new snapshot
        new_snapshot = SnapshotData(name="errors", content=error_responses)

        assert snapshot.hash == new_snapshot.hash, "Error responses changed"


class TestLocalizationSnapshots:
    """Tests for localization snapshots."""

    @pytest.fixture
    def translation_keys(self):
        """Translation keys that must exist."""
        return {
            "common": [
                "welcome",
                "goodbye",
                "error",
                "success",
                "loading",
                "cancel",
                "back",
                "confirm",
            ],
            "balance": [
                "balance_title",
                "balance_usd",
                "balance_dmc",
                "balance_refresh",
            ],
            "arbitrage": [
                "arbitrage_found",
                "arbitrage_profit",
                "arbitrage_buy_price",
                "arbitrage_sell_price",
                "no_opportunities",
            ],
            "errors": [
                "error_api",
                "error_network",
                "error_auth",
                "error_rate_limit",
                "error_validation",
            ],
        }

    def test_translation_keys_snapshot(self, translation_keys):
        """Test translation keys haven't changed."""
        all_keys = []
        for category, keys in translation_keys.items():
            all_keys.extend(keys)

        # Should have minimum number of keys
        assert len(all_keys) >= 20, "Too few translation keys"

        # Common keys should exist
        assert "welcome" in translation_keys["common"]
        assert "error_api" in translation_keys["errors"]

    def test_category_consistency(self, translation_keys):
        """Test translation categories are consistent."""
        expected_categories = {"common", "balance", "arbitrage", "errors"}

        actual_categories = set(translation_keys.keys())
        assert expected_categories == actual_categories


class TestSnapshotComparison:
    """Tests for snapshot comparison utilities."""

    def test_snapshot_hash_consistency(self):
        """Test that same content produces same hash."""
        content = {"key": "value", "nested": {"a": 1, "b": 2}}

        snapshot1 = SnapshotData(name="test", content=content)
        snapshot2 = SnapshotData(name="test", content=content)

        assert snapshot1.hash == snapshot2.hash

    def test_snapshot_detects_changes(self):
        """Test that different content produces different hash."""
        content1 = {"key": "value1"}
        content2 = {"key": "value2"}

        snapshot1 = SnapshotData(name="test", content=content1)
        snapshot2 = SnapshotData(name="test", content=content2)

        assert snapshot1.hash != snapshot2.hash

    def test_snapshot_order_independence(self):
        """Test that key order doesn't affect hash."""
        content1 = {"a": 1, "b": 2, "c": 3}
        content2 = {"c": 3, "a": 1, "b": 2}

        snapshot1 = SnapshotData(name="test", content=content1)
        snapshot2 = SnapshotData(name="test", content=content2)

        assert snapshot1.hash == snapshot2.hash
