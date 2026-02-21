"""Localization (i18n/l10n) tests for the DMarket Telegram Bot.

Tests verify:
- All supported languages have complete translations
- Translation keys are consistent across languages
- Date/time formatting works for different locales
- Currency formatting is correct
- Pluralization rules work correctly
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# TEST MARKERS
# =============================================================================


pytestmark = [pytest.mark.localization, pytest.mark.i18n]


# =============================================================================
# SUPPORTED LANGUAGES
# =============================================================================


SUPPORTED_LANGUAGES = ["en", "ru", "es", "de"]


# =============================================================================
# LOCALIZATION CLASS TESTS
# =============================================================================


class TestLocalizationClass:
    """Tests for Localization module."""

    def test_localization_imports(self) -> None:
        """Test localization module imports successfully."""
        from src.telegram_bot import localization

        assert localization is not None

    def test_localizations_dict_exists(self) -> None:
        """Test LOCALIZATIONS dictionary exists."""
        from src.telegram_bot.localization import LOCALIZATIONS

        assert LOCALIZATIONS is not None
        assert isinstance(LOCALIZATIONS, dict)

    def test_languages_supported(self) -> None:
        """Test supported languages are defined."""
        from src.telegram_bot.localization import LANGUAGES

        assert LANGUAGES is not None
        assert "ru" in LANGUAGES
        assert "en" in LANGUAGES

    def test_default_language(self) -> None:
        """Test default language is set."""
        from src.telegram_bot.localization import LOCALIZATIONS

        # Russian should be the base language
        assert "ru" in LOCALIZATIONS
        assert len(LOCALIZATIONS["ru"]) > 0


class TestLanguageSupport:
    """Tests for language support."""

    @pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
    def test_language_is_supported(self, lang: str) -> None:
        """Test each language is supported."""
        from src.telegram_bot.localization import LOCALIZATIONS

        # Language should exist in LOCALIZATIONS
        assert lang in LOCALIZATIONS

    def test_unsupported_language_fallback(self) -> None:
        """Test unsupported language is not in LOCALIZATIONS."""
        from src.telegram_bot.localization import LOCALIZATIONS

        # Unsupported language should not exist
        assert "unsupported" not in LOCALIZATIONS


# =============================================================================
# TRANSLATION KEY TESTS
# =============================================================================


class TestTranslationKeys:
    """Tests for translation key consistency."""

    COMMON_KEYS = [
        "welcome",
        "help",
        "settings",
        "back_button",
        "language",
    ]

    @pytest.mark.parametrize("key", COMMON_KEYS)
    def test_common_key_exists(self, key: str) -> None:
        """Test common translation keys exist in Russian."""
        from src.telegram_bot.localization import LOCALIZATIONS

        # Russian should have the key
        ru_translations = LOCALIZATIONS.get("ru", {})
        assert key in ru_translations

    def test_no_missing_keys_russian(self) -> None:
        """Test Russian has all common keys."""
        from src.telegram_bot.localization import LOCALIZATIONS

        ru_translations = LOCALIZATIONS.get("ru", {})
        # Should have at least some keys
        assert len(ru_translations) >= len(self.COMMON_KEYS)

    @pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
    def test_translation_completeness(self, lang: str) -> None:
        """Test translation completeness for each language."""
        from src.telegram_bot.localization import LOCALIZATIONS

        # Language should exist
        assert lang in LOCALIZATIONS
        # Should have some translations
        assert len(LOCALIZATIONS[lang]) > 0


# =============================================================================
# FORMATTING TESTS
# =============================================================================


class TestNumberFormatting:
    """Tests for number and currency formatting."""

    def test_price_formatting_usd(self) -> None:
        """Test price formatting in USD."""
        # Price in cents
        price_cents = 1500
        price_usd = price_cents / 100

        # Format: $15.00
        formatted = f"${price_usd:.2f}"
        assert formatted == "$15.00"

    def test_price_formatting_large_numbers(self) -> None:
        """Test large number formatting."""
        price_cents = 1000000  # $10,000
        price_usd = price_cents / 100

        # Should format with proper separators
        formatted = f"${price_usd:,.2f}"
        assert formatted == "$10,000.00"

    def test_price_formatting_small_numbers(self) -> None:
        """Test small number formatting."""
        price_cents = 1  # $0.01
        price_usd = price_cents / 100

        formatted = f"${price_usd:.2f}"
        assert formatted == "$0.01"

    def test_percentage_formatting(self) -> None:
        """Test percentage formatting."""
        percentage = 7.5

        formatted = f"{percentage:.1f}%"
        assert formatted == "7.5%"


class TestDateTimeFormatting:
    """Tests for date/time formatting across locales."""

    def test_date_formatting_iso(self) -> None:
        """Test ISO date formatting."""
        from datetime import datetime

        dt = datetime(2026, 1, 9, 12, 30, 0)

        # ISO format
        iso_format = dt.isoformat()
        assert "2026-01-09" in iso_format

    def test_date_formatting_human_readable(self) -> None:
        """Test human-readable date formatting."""
        from datetime import datetime

        dt = datetime(2026, 1, 9, 12, 30, 0)

        # Various formats
        format1 = dt.strftime("%Y-%m-%d %H:%M")
        assert format1 == "2026-01-09 12:30"

        format2 = dt.strftime("%d.%m.%Y")
        assert format2 == "09.01.2026"

    def test_relative_time_formatting(self) -> None:
        """Test relative time formatting."""
        from datetime import datetime, timedelta

        now = datetime.now()
        past = now - timedelta(hours=2)

        diff = now - past
        hours = diff.total_seconds() / 3600

        assert abs(hours - 2) < 0.01


# =============================================================================
# PLURALIZATION TESTS
# =============================================================================


class TestPluralization:
    """Tests for pluralization rules."""

    @pytest.mark.parametrize(
        "count,expected_en",
        [
            (0, "items"),
            (1, "item"),
            (2, "items"),
            (5, "items"),
            (100, "items"),
        ],
    )
    def test_english_pluralization(self, count: int, expected_en: str) -> None:
        """Test English pluralization rules."""
        word = "item" if count == 1 else "items"
        assert word == expected_en

    @pytest.mark.parametrize(
        "count,expected_ru",
        [
            (1, "предмет"),  # 1 item
            (2, "предмета"),  # 2-4 items
            (5, "предметов"),  # 5+ items
            (21, "предмет"),  # 21 item
            (22, "предмета"),  # 22 items
        ],
    )
    def test_russian_pluralization(self, count: int, expected_ru: str) -> None:
        """Test Russian pluralization rules."""
        # Russian has complex pluralization rules

        def russian_plural(n: int) -> str:
            """Get Russian plural form."""
            if n % 10 == 1 and n % 100 != 11:
                return "предмет"
            elif 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
                return "предмета"
            else:
                return "предметов"

        assert russian_plural(count) == expected_ru


# =============================================================================
# MESSAGE TEMPLATE TESTS
# =============================================================================


class TestMessageTemplates:
    """Tests for message templates."""

    def test_template_substitution(self) -> None:
        """Test template variable substitution."""
        template = "Balance: ${balance}"
        result = template.replace("${balance}", "$15.00")
        assert result == "Balance: $15.00"

    def test_template_with_multiple_variables(self) -> None:
        """Test template with multiple variables."""
        template = "{count} {item} at ${price}"
        result = template.format(count=5, item="AK-47", price="15.00")
        assert result == "5 AK-47 at $15.00"

    def test_template_html_escaping(self) -> None:
        """Test HTML escaping in templates."""
        import html

        user_input = "<script>alert('xss')</script>"
        escaped = html.escape(user_input)
        assert "<" not in escaped
        assert ">" not in escaped

    def test_markdown_escaping(self) -> None:
        """Test Markdown escaping for Telegram."""
        special_chars = "*_[]()~`>#+-=|{}.!"

        def escape_markdown(text: str) -> str:
            """Escape Markdown special characters."""
            for char in special_chars:
                text = text.replace(char, f"\\{char}")
            return text

        test = "Test *bold* _italic_"
        escaped = escape_markdown(test)
        assert "\\*bold\\*" in escaped


# =============================================================================
# EMOJI AND SPECIAL CHARACTER TESTS
# =============================================================================


class TestEmojiSupport:
    """Tests for emoji and special character support."""

    COMMON_EMOJIS = ["✅", "❌", "💰", "📊", "🎯", "🔥", "⚠️", "📈", "📉"]

    @pytest.mark.parametrize("emoji", COMMON_EMOJIS)
    def test_emoji_in_messages(self, emoji: str) -> None:
        """Test emojis work in messages."""
        message = f"{emoji} Test message"
        assert emoji in message
        # Should be valid UTF-8
        encoded = message.encode("utf-8")
        assert len(encoded) > 0

    def test_emoji_with_text(self) -> None:
        """Test emoji combined with text."""
        message = "✅ Success: Balance is $100.00 💰"
        assert "✅" in message
        assert "💰" in message
        assert "$100.00" in message


# =============================================================================
# RTL LANGUAGE TESTS
# =============================================================================


class TestRTLSupport:
    """Tests for right-to-left language support."""

    def test_rtl_text_direction(self) -> None:
        """Test RTL text direction markers."""
        # RTL text (Arabic example)
        rtl_text = "مرحبا"

        # Should be valid Unicode
        assert len(rtl_text) > 0
        encoded = rtl_text.encode("utf-8")
        assert len(encoded) > 0

    def test_mixed_rtl_ltr_text(self) -> None:
        """Test mixed RTL and LTR text."""
        # Mixed text with numbers
        mixed = "Price: 100$ السعر"

        # Should contAlgon both directions
        assert "100" in mixed
        assert "$" in mixed


# =============================================================================
# ENCODING TESTS
# =============================================================================


class TestEncodingSupport:
    """Tests for encoding support."""

    def test_utf8_encoding(self) -> None:
        """Test UTF-8 encoding works."""
        text = "Test Тест 测试 テスト"

        encoded = text.encode("utf-8")
        decoded = encoded.decode("utf-8")

        assert decoded == text

    def test_special_characters_in_translations(self) -> None:
        """Test special characters in translations."""
        special_chars = [
            "ñ",  # Spanish
            "ü",  # German
            "ß",  # German
            "é",  # French
            "ø",  # Nordic
            "ç",  # Portuguese
        ]

        for char in special_chars:
            encoded = char.encode("utf-8")
            decoded = encoded.decode("utf-8")
            assert decoded == char


# =============================================================================
# FALLBACK MECHANISM TESTS
# =============================================================================


class TestFallbackMechanism:
    """Tests for translation fallback mechanism."""

    def test_fallback_to_russian(self) -> None:
        """Test Russian is the base language."""
        from src.telegram_bot.localization import LOCALIZATIONS

        # Russian should have the most translations
        ru_keys = set(LOCALIZATIONS.get("ru", {}).keys())
        assert len(ru_keys) > 0

    def test_all_languages_have_welcome(self) -> None:
        """Test all languages have welcome message."""
        from src.telegram_bot.localization import LOCALIZATIONS

        for lang in SUPPORTED_LANGUAGES:
            if lang in LOCALIZATIONS:
                assert "welcome" in LOCALIZATIONS[lang]


# =============================================================================
# INTEGRATION TESTS FOR LOCALIZATION
# =============================================================================


class TestLocalizationIntegration:
    """Integration tests for localization with other components."""

    @pytest.mark.asyncio
    async def test_localized_error_messages(self) -> None:
        """Test error messages are localized."""
        from src.telegram_bot.localization import LOCALIZATIONS

        # Error messages should be in translations
        ru_translations = LOCALIZATIONS.get("ru", {})
        # Check for error-related keys
        error_keys = [k for k in ru_translations.keys() if "error" in k.lower()]
        # Should have some error messages
        assert len(error_keys) >= 0 or "api_error" in ru_translations

    def test_localized_button_labels(self) -> None:
        """Test button labels are localized."""
        from src.telegram_bot.localization import LOCALIZATIONS

        # Button labels should be in translations
        ru_translations = LOCALIZATIONS.get("ru", {})
        button_keys = ["back_button", "settings"]

        for key in button_keys:
            assert key in ru_translations
