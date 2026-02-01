"""Tests for NLP Command Handler.

Tests Phase 2 implementation of natural language processing.
"""

import pytest

from src.telegram_bot.nlp_handler import (
    NLPCommandHandler,
    IntentResult,
    create_nlp_handler,
)


class TestNLPCommandHandler:
    """Tests for NLPCommandHandler class."""

    def test_initialization(self):
        """Test handler initialization."""
        nlp = NLPCommandHandler()

        assert nlp is not None
        assert nlp.INTENT_PATTERNS is not None

    def test_factory_function(self):
        """Test factory function creates valid handler."""
        nlp = create_nlp_handler()

        assert isinstance(nlp, NLPCommandHandler)

    @pytest.mark.asyncio
    async def test_parse_simple_balance_command_russian(self):
        """Test parsing Russian balance command."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent("Какой мой баланс?", user_id=123)

        assert result.intent == "show_balance"
        assert result.language == "ru"
        assert result.confidence > 0.5

    @pytest.mark.asyncio
    async def test_parse_simple_balance_command_english(self):
        """Test parsing English balance command."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent("What's my balance?", user_id=123)

        assert result.intent == "show_balance"
        assert result.language == "en"
        assert result.confidence > 0.5

    @pytest.mark.asyncio
    async def test_parse_arbitrage_with_game_russian(self):
        """Test parsing arbitrage command with game (Russian)."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent(
            "Найди арбитраж в CS:GO", user_id=123
        )

        assert result.intent == "scan_arbitrage"
        assert result.language == "ru"
        assert result.params.get("game") == "csgo"

    @pytest.mark.asyncio
    async def test_parse_arbitrage_with_game_english(self):
        """Test parsing arbitrage command with game (English)."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent(
            "Find arbitrage in Dota 2", user_id=123
        )

        assert result.intent == "scan_arbitrage"
        assert result.language == "en"
        assert result.params.get("game") == "dota2"

    @pytest.mark.asyncio
    async def test_parse_arbitrage_with_price_limit(self):
        """Test parsing arbitrage with price limit."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent(
            "Найди арбитраж в CS:GO до $10", user_id=123
        )

        assert result.intent == "scan_arbitrage"
        assert result.params.get("game") == "csgo"
        assert result.params.get("max_price") == 10.0

    @pytest.mark.asyncio
    async def test_parse_create_target_russian(self):
        """Test parsing create target command (Russian)."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent(
            "Создай таргет для AK-47 за $15", user_id=123
        )

        assert result.intent == "create_target"
        assert result.language == "ru"
        assert result.params.get("price") == 15.0
        assert "ak-47" in result.params.get("item_name", "").lower()

    @pytest.mark.asyncio
    async def test_parse_create_target_english(self):
        """Test parsing create target command (English)."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent(
            "Create target for AWP Dragon Lore at $20", user_id=123
        )

        assert result.intent == "create_target"
        assert result.language == "en"
        assert result.params.get("price") == 20.0

    @pytest.mark.asyncio
    async def test_parse_list_targets(self):
        """Test parsing list targets command."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent("Покажи все таргеты", user_id=123)

        assert result.intent == "list_targets"
        assert result.language == "ru"

    @pytest.mark.asyncio
    async def test_parse_delete_target(self):
        """Test parsing delete target command."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent("Delete target", user_id=123)

        assert result.intent == "delete_target"
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_parse_show_stats(self):
        """Test parsing statistics command."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent("Покажи статистику", user_id=123)

        assert result.intent == "show_stats"
        assert result.language == "ru"

    @pytest.mark.asyncio
    async def test_parse_help_command(self):
        """Test parsing help command."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent("Помощь", user_id=123)

        assert result.intent == "help"
        assert result.language == "ru"

    @pytest.mark.asyncio
    async def test_parse_unknown_command(self):
        """Test parsing unknown command."""
        nlp = NLPCommandHandler()

        result = await nlp.parse_user_intent(
            "Random gibberish xyz123", user_id=123
        )

        assert result.intent == "unknown"
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_parse_with_context(self):
        """Test parsing with previous context."""
        nlp = NLPCommandHandler()

        # First message establishes context
        context = {"previous_game": "csgo"}

        result = await nlp.parse_user_intent(
            "Найди арбитраж", user_id=123, context=context
        )

        assert result.intent == "scan_arbitrage"
        # Context should be merged
        assert "previous_game" in result.params

    def test_detect_language_russian(self):
        """Test Russian language detection."""
        nlp = NLPCommandHandler()

        lang = nlp.detect_language("Привет, как дела?")

        assert lang == "ru"

    def test_detect_language_english(self):
        """Test English language detection."""
        nlp = NLPCommandHandler()

        lang = nlp.detect_language("Hello, how are you?")

        assert lang == "en"

    def test_detect_language_spanish(self):
        """Test Spanish language detection."""
        nlp = NLPCommandHandler()

        lang = nlp.detect_language("Hola, para crear algo")

        assert lang == "es"

    def test_detect_language_german(self):
        """Test German language detection."""
        nlp = NLPCommandHandler()

        lang = nlp.detect_language("Hallo, für etwas")

        assert lang == "de"

    def test_extract_entities_game(self):
        """Test extracting game entity."""
        nlp = NLPCommandHandler()

        params = nlp.extract_entities("найди арбитраж в CS:GO", "scan_arbitrage")

        assert params.get("game") == "csgo"

    def test_extract_entities_price(self):
        """Test extracting price entity."""
        nlp = NLPCommandHandler()

        params = nlp.extract_entities("найди под $25", "scan_arbitrage")

        assert params.get("max_price") == 25.0

    def test_extract_entities_item_name(self):
        """Test extracting item name entity."""
        nlp = NLPCommandHandler()

        params = nlp.extract_entities(
            "создать таргет для AK-47 Redline за $15", "create_target"
        )

        assert "AK-47 Redline" in params.get("item_name", "")
        assert params.get("price") == 15.0

    def test_extract_entities_multiple_games(self):
        """Test extracting different game IDs."""
        nlp = NLPCommandHandler()

        # Test CS:GO
        params1 = nlp.extract_entities("in csgo", "scan_arbitrage")
        assert params1.get("game") == "csgo"

        # Test Dota 2
        params2 = nlp.extract_entities("in dota 2", "scan_arbitrage")
        assert params2.get("game") == "dota2"

        # Test TF2
        params3 = nlp.extract_entities("in tf2", "scan_arbitrage")
        assert params3.get("game") == "tf2"

        # Test Rust
        params4 = nlp.extract_entities("in rust", "scan_arbitrage")
        assert params4.get("game") == "rust"


class TestIntentResult:
    """Tests for IntentResult dataclass."""

    def test_intent_result_creation(self):
        """Test creating intent result."""
        result = IntentResult(
            intent="scan_arbitrage",
            params={"game": "csgo"},
            confidence=0.85,
            language="ru",
            alternatives=[],
        )

        assert result.intent == "scan_arbitrage"
        assert result.confidence == 0.85
        assert result.language == "ru"
        assert result.params["game"] == "csgo"

    def test_intent_result_default_values(self):
        """Test intent result default values."""
        result = IntentResult(intent="help")

        assert result.params == {}
        assert result.confidence == 0.0
        assert result.language == "en"
        assert result.alternatives == []
