"""Тесты для модуля констант telegram_bot."""

from pathlib import Path


class TestNotificationTypes:
    """Тесты для NOTIFICATION_TYPES."""

    def test_notification_types_exists(self):
        """Тест существования константы."""
        from src.telegram_bot.constants import NOTIFICATION_TYPES

        assert NOTIFICATION_TYPES is not None
        assert isinstance(NOTIFICATION_TYPES, dict)

    def test_notification_types_has_all_required_keys(self):
        """Тест наличия всех необходимых ключей."""
        from src.telegram_bot.constants import NOTIFICATION_TYPES

        required_keys = [
            "price_drop",
            "price_rise",
            "volume_increase",
            "good_deal",
            "arbitrage",
            "trend_change",
            "buy_intent",
            "buy_success",
            "buy_failed",
            "sell_success",
            "sell_failed",
            "critical_shutdown",
        ]
        for key in required_keys:
            assert key in NOTIFICATION_TYPES

    def test_notification_types_values_are_strings(self):
        """Тест что все значения являются строками."""
        from src.telegram_bot.constants import NOTIFICATION_TYPES

        for key, value in NOTIFICATION_TYPES.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_notification_types_values_contain_emoji(self):
        """Тест что все значения содержат эмодзи."""
        from src.telegram_bot.constants import NOTIFICATION_TYPES

        for key, value in NOTIFICATION_TYPES.items():
            # Проверяем что первый символ - эмодзи (не ASCII)
            assert len(value) > 0
            # Эмодзи обычно имеют код > 127
            first_char_code = ord(value[0])
            assert (
                first_char_code > 127
            ), f"Key {key} value {value} does not start with emoji"


class TestPriceCacheTtl:
    """Тесты для _PRICE_CACHE_TTL."""

    def test_price_cache_ttl_exists(self):
        """Тест существования константы."""
        from src.telegram_bot.constants import _PRICE_CACHE_TTL

        assert _PRICE_CACHE_TTL is not None

    def test_price_cache_ttl_value(self):
        """Тест значения TTL."""
        from src.telegram_bot.constants import _PRICE_CACHE_TTL

        assert _PRICE_CACHE_TTL == 300  # 5 минут

    def test_price_cache_ttl_is_positive(self):
        """Тест что TTL положительный."""
        from src.telegram_bot.constants import _PRICE_CACHE_TTL

        assert _PRICE_CACHE_TTL > 0


class TestDefaultUserSettings:
    """Тесты для DEFAULT_USER_SETTINGS."""

    def test_default_user_settings_exists(self):
        """Тест существования константы."""
        from src.telegram_bot.constants import DEFAULT_USER_SETTINGS

        assert DEFAULT_USER_SETTINGS is not None
        assert isinstance(DEFAULT_USER_SETTINGS, dict)

    def test_default_user_settings_has_enabled(self):
        """Тест наличия enabled."""
        from src.telegram_bot.constants import DEFAULT_USER_SETTINGS

        assert "enabled" in DEFAULT_USER_SETTINGS
        assert DEFAULT_USER_SETTINGS["enabled"] is True

    def test_default_user_settings_has_language(self):
        """Тест наличия language."""
        from src.telegram_bot.constants import DEFAULT_USER_SETTINGS

        assert "language" in DEFAULT_USER_SETTINGS
        assert DEFAULT_USER_SETTINGS["language"] == "ru"

    def test_default_user_settings_has_min_interval(self):
        """Тест наличия min_interval."""
        from src.telegram_bot.constants import DEFAULT_USER_SETTINGS

        assert "min_interval" in DEFAULT_USER_SETTINGS
        assert DEFAULT_USER_SETTINGS["min_interval"] == 300

    def test_default_user_settings_has_quiet_hours(self):
        """Тест наличия quiet_hours."""
        from src.telegram_bot.constants import DEFAULT_USER_SETTINGS

        assert "quiet_hours" in DEFAULT_USER_SETTINGS
        quiet_hours = DEFAULT_USER_SETTINGS["quiet_hours"]
        assert isinstance(quiet_hours, dict)
        assert "start" in quiet_hours
        assert "end" in quiet_hours
        assert quiet_hours["start"] == 23
        assert quiet_hours["end"] == 7

    def test_default_user_settings_has_max_alerts_per_day(self):
        """Тест наличия max_alerts_per_day."""
        from src.telegram_bot.constants import DEFAULT_USER_SETTINGS

        assert "max_alerts_per_day" in DEFAULT_USER_SETTINGS
        assert DEFAULT_USER_SETTINGS["max_alerts_per_day"] == 50


class TestNotificationPriorities:
    """Тесты для NOTIFICATION_PRIORITIES."""

    def test_notification_priorities_exists(self):
        """Тест существования константы."""
        from src.telegram_bot.constants import NOTIFICATION_PRIORITIES

        assert NOTIFICATION_PRIORITIES is not None
        assert isinstance(NOTIFICATION_PRIORITIES, dict)

    def test_notification_priorities_values_are_integers(self):
        """Тест что все значения являются целыми числами."""
        from src.telegram_bot.constants import NOTIFICATION_PRIORITIES

        for value in NOTIFICATION_PRIORITIES.values():
            assert isinstance(value, int)

    def test_notification_priorities_critical_shutdown_highest(self):
        """Тест что critical_shutdown имеет высший приоритет."""
        from src.telegram_bot.constants import NOTIFICATION_PRIORITIES

        assert "critical_shutdown" in NOTIFICATION_PRIORITIES
        max_priority = max(NOTIFICATION_PRIORITIES.values())
        assert NOTIFICATION_PRIORITIES["critical_shutdown"] == max_priority

    def test_notification_priorities_ordering(self):
        """Тест правильного порядка приоритетов."""
        from src.telegram_bot.constants import NOTIFICATION_PRIORITIES

        # critical_shutdown > buy_success > good_deal > trend_change
        assert (
            NOTIFICATION_PRIORITIES["critical_shutdown"]
            > NOTIFICATION_PRIORITIES["buy_success"]
        )
        assert (
            NOTIFICATION_PRIORITIES["buy_success"]
            > NOTIFICATION_PRIORITIES["good_deal"]
        )
        assert (
            NOTIFICATION_PRIORITIES["good_deal"]
            > NOTIFICATION_PRIORITIES["trend_change"]
        )

    def test_notification_priorities_match_types(self):
        """Тест что приоритеты соответствуют типам уведомлений."""
        from src.telegram_bot.constants import (
            NOTIFICATION_PRIORITIES,
            NOTIFICATION_TYPES,
        )

        for key in NOTIFICATION_PRIORITIES:
            assert (
                key in NOTIFICATION_TYPES
            ), f"Priority key {key} not in NOTIFICATION_TYPES"


class TestPathConstants:
    """Тесты для Path констант."""

    def test_data_dir_exists(self):
        """Тест существования DATA_DIR."""
        from src.telegram_bot.constants import DATA_DIR

        assert DATA_DIR is not None
        assert isinstance(DATA_DIR, Path)
        assert str(DATA_DIR) == "data"

    def test_env_path_exists(self):
        """Тест существования ENV_PATH."""
        from src.telegram_bot.constants import ENV_PATH

        assert ENV_PATH is not None
        assert isinstance(ENV_PATH, Path)
        assert str(ENV_PATH) == ".env"

    def test_user_profiles_file_exists(self):
        """Тест существования USER_PROFILES_FILE."""
        from src.telegram_bot.constants import DATA_DIR, USER_PROFILES_FILE

        assert USER_PROFILES_FILE is not None
        assert isinstance(USER_PROFILES_FILE, Path)
        assert USER_PROFILES_FILE.parent == DATA_DIR


class TestPaginationConstants:
    """Тесты для констант пагинации."""

    def test_default_page_size(self):
        """Тест DEFAULT_PAGE_SIZE."""
        from src.telegram_bot.constants import DEFAULT_PAGE_SIZE

        assert DEFAULT_PAGE_SIZE == 10

    def test_max_items_per_page(self):
        """Тест MAX_ITEMS_PER_PAGE."""
        from src.telegram_bot.constants import MAX_ITEMS_PER_PAGE

        assert MAX_ITEMS_PER_PAGE == 50

    def test_max_message_length(self):
        """Тест MAX_MESSAGE_LENGTH."""
        from src.telegram_bot.constants import MAX_MESSAGE_LENGTH

        assert MAX_MESSAGE_LENGTH == 4096


class TestLanguages:
    """Тесты для LANGUAGES."""

    def test_languages_exists(self):
        """Тест существования константы."""
        from src.telegram_bot.constants import LANGUAGES

        assert LANGUAGES is not None
        assert isinstance(LANGUAGES, dict)

    def test_languages_has_russian(self):
        """Тест наличия русского языка."""
        from src.telegram_bot.constants import LANGUAGES

        assert "ru" in LANGUAGES
        assert "🇷🇺" in LANGUAGES["ru"]

    def test_languages_has_english(self):
        """Тест наличия английского языка."""
        from src.telegram_bot.constants import LANGUAGES

        assert "en" in LANGUAGES
        assert "🇬🇧" in LANGUAGES["en"]

    def test_languages_values_contain_emoji(self):
        """Тест что все языки имеют эмодзи флагов."""
        from src.telegram_bot.constants import LANGUAGES

        for display_name in LANGUAGES.values():
            assert len(display_name) > 0
            # Флаги - это комбинации региональных символов
            assert display_name[0].isalpha() is False or ord(display_name[0]) > 127


class TestArbitrageModes:
    """Тесты для ARBITRAGE_MODES."""

    def test_arbitrage_modes_exists(self):
        """Тест существования константы."""
        from src.telegram_bot.constants import ARBITRAGE_MODES

        assert ARBITRAGE_MODES is not None
        assert isinstance(ARBITRAGE_MODES, dict)

    def test_arbitrage_modes_has_all_levels(self):
        """Тест наличия всех уровней."""
        from src.telegram_bot.constants import ARBITRAGE_MODES

        expected_levels = ["boost", "standard", "medium", "advanced", "pro"]
        for level in expected_levels:
            assert level in ARBITRAGE_MODES

    def test_arbitrage_modes_values_contain_emoji(self):
        """Тест что все режимы имеют эмодзи."""
        from src.telegram_bot.constants import ARBITRAGE_MODES

        for mode, description in ARBITRAGE_MODES.items():
            assert len(description) > 0
            first_char = ord(description[0])
            assert (
                first_char > 127
            ), f"Mode {mode} description does not start with emoji"

    def test_arbitrage_modes_values_contain_price_range(self):
        """Тест что все режимы содержат ценовой диапазон."""
        from src.telegram_bot.constants import ARBITRAGE_MODES

        for mode, description in ARBITRAGE_MODES.items():
            assert (
                "$" in description
            ), f"Mode {mode} description does not contain price range"


class TestPriceAlertStorageKeys:
    """Тесты для ключей хранилища ценовых алертов."""

    def test_price_alert_storage_key(self):
        """Тест PRICE_ALERT_STORAGE_KEY."""
        from src.telegram_bot.constants import PRICE_ALERT_STORAGE_KEY

        assert PRICE_ALERT_STORAGE_KEY == "price_alerts"

    def test_price_alert_history_key(self):
        """Тест PRICE_ALERT_HISTORY_KEY."""
        from src.telegram_bot.constants import PRICE_ALERT_HISTORY_KEY

        assert PRICE_ALERT_HISTORY_KEY == "price_alert_history"


class TestModuleExports:
    """Тесты экспортов модуля."""

    def test_all_exports_defined(self):
        """Тест что __all__ определен."""
        from src.telegram_bot import constants

        assert hasattr(constants, "__all__")
        assert isinstance(constants.__all__, list)

    def test_all_exports_accessible(self):
        """Тест что все экспорты доступны."""
        from src.telegram_bot import constants

        for name in constants.__all__:
            assert hasattr(constants, name), f"Export {name} not found in module"

    def test_important_exports_included(self):
        """Тест что важные экспорты включены."""
        from src.telegram_bot.constants import __all__

        important_exports = [
            "NOTIFICATION_TYPES",
            "NOTIFICATION_PRIORITIES",
            "DEFAULT_USER_SETTINGS",
            "LANGUAGES",
            "ARBITRAGE_MODES",
        ]
        for export in important_exports:
            assert export in __all__, f"Export {export} not in __all__"


class TestConstantsIntegration:
    """Интеграционные тесты констант."""

    def test_notification_types_and_priorities_consistency(self):
        """Тест консистентности типов и приоритетов уведомлений."""
        from src.telegram_bot.constants import (
            NOTIFICATION_PRIORITIES,
            NOTIFICATION_TYPES,
        )

        # Все типы должны иметь приоритеты
        for ntype in NOTIFICATION_TYPES:
            assert ntype in NOTIFICATION_PRIORITIES, f"Type {ntype} has no priority"

    def test_all_languages_valid_codes(self):
        """Тест что все коды языков корректны."""
        from src.telegram_bot.constants import LANGUAGES

        for lang_code in LANGUAGES:
            assert len(lang_code) == 2, f"Invalid language code: {lang_code}"
            assert (
                lang_code.isalpha()
            ), f"Language code should be alphabetic: {lang_code}"
            assert (
                lang_code.islower()
            ), f"Language code should be lowercase: {lang_code}"

    def test_page_sizes_logical(self):
        """Тест логичности размеров страниц."""
        from src.telegram_bot.constants import DEFAULT_PAGE_SIZE, MAX_ITEMS_PER_PAGE

        assert DEFAULT_PAGE_SIZE <= MAX_ITEMS_PER_PAGE
        assert DEFAULT_PAGE_SIZE > 0
        assert MAX_ITEMS_PER_PAGE > 0
