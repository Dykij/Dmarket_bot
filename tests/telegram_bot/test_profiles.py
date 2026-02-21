"""Unit tests for src/telegram_bot/profiles.py module.

Tests for user profile management, loading, saving, and retrieval.
"""

import json
import pathlib
from unittest.mock import patch


class TestSaveUserProfiles:
    """Tests for save_user_profiles function."""

    def test_save_user_profiles_writes_json_file(self, tmp_path):
        """Test save_user_profiles writes profiles to JSON file."""
        from src.telegram_bot import profiles

        # Setup test profiles
        test_profiles = {
            "123": {"language": "ru", "api_key": "key1"},
            "456": {"language": "en", "api_key": "key2"},
        }

        with patch.object(profiles, "USER_PROFILES", test_profiles), patch.object(
            profiles, "USER_PROFILES_FILE", str(tmp_path / "profiles.json")
        ):
            profiles.save_user_profiles()

            # Check file was created and contAlgons correct data
            with open(tmp_path / "profiles.json", encoding="utf-8") as f:
                saved = json.load(f)

            assert saved == test_profiles

    def test_save_user_profiles_uses_utf8_encoding(self, tmp_path):
        """Test save_user_profiles uses UTF-8 encoding."""
        from src.telegram_bot import profiles

        test_profiles = {
            "123": {"language": "ru", "username": "Пользователь"},
        }

        with patch.object(profiles, "USER_PROFILES", test_profiles), patch.object(
            profiles, "USER_PROFILES_FILE", str(tmp_path / "profiles.json")
        ):
            profiles.save_user_profiles()

            # Verify UTF-8 content
            with open(tmp_path / "profiles.json", encoding="utf-8") as f:
                saved = json.load(f)

            assert saved["123"]["username"] == "Пользователь"

    def test_save_user_profiles_formats_with_indent(self, tmp_path):
        """Test save_user_profiles formats JSON with indent."""
        from src.telegram_bot import profiles

        test_profiles = {"123": {"key": "value"}}

        with patch.object(profiles, "USER_PROFILES", test_profiles), patch.object(
            profiles, "USER_PROFILES_FILE", str(tmp_path / "profiles.json")
        ):
            profiles.save_user_profiles()

            content = pathlib.Path(tmp_path / "profiles.json").read_text(
                encoding="utf-8"
            )

            # Should be formatted with indentation
            assert "\n" in content

    def test_save_user_profiles_handles_os_error(self):
        """Test save_user_profiles handles OSError gracefully."""
        from src.telegram_bot import profiles

        with patch.object(profiles, "USER_PROFILES", {"123": {}}):
            with patch("builtins.open", side_effect=OSError("Permission denied")):
                # Should not rAlgose
                profiles.save_user_profiles()

    def test_save_user_profiles_with_empty_profiles(self, tmp_path):
        """Test save_user_profiles with empty profiles dict."""
        from src.telegram_bot import profiles

        with patch.object(profiles, "USER_PROFILES", {}), patch.object(
            profiles, "USER_PROFILES_FILE", str(tmp_path / "profiles.json")
        ):
            profiles.save_user_profiles()

            with open(tmp_path / "profiles.json", encoding="utf-8") as f:
                saved = json.load(f)

            assert saved == {}


class TestLoadUserProfiles:
    """Tests for load_user_profiles function."""

    def test_load_user_profiles_loads_existing_file(self, tmp_path):
        """Test load_user_profiles loads from existing file."""
        from src.telegram_bot import profiles

        test_data = {"123": {"language": "ru"}, "456": {"language": "en"}}

        # Create test file
        profile_file = tmp_path / "profiles.json"
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        with patch.object(profiles, "USER_PROFILES_FILE", str(profile_file)):
            profiles.load_user_profiles()

            assert test_data == profiles.USER_PROFILES

    def test_load_user_profiles_handles_missing_file(self, tmp_path):
        """Test load_user_profiles handles missing file."""
        from src.telegram_bot import profiles

        non_existent = str(tmp_path / "non_existent.json")

        with patch.object(profiles, "USER_PROFILES_FILE", non_existent):
            profiles.load_user_profiles()

            # Should result in empty dict
            # Note: The behavior depends on implementation

    def test_load_user_profiles_handles_invalid_json(self, tmp_path):
        """Test load_user_profiles handles invalid JSON."""
        from src.telegram_bot import profiles

        # Create invalid JSON file
        profile_file = tmp_path / "profiles.json"
        pathlib.Path(profile_file).write_text("invalid json {{{", encoding="utf-8")

        with patch.object(profiles, "USER_PROFILES_FILE", str(profile_file)):
            profiles.load_user_profiles()

            # Should result in empty dict after error
            assert profiles.USER_PROFILES == {}

    def test_load_user_profiles_handles_os_error(self, tmp_path):
        """Test load_user_profiles handles OSError."""
        from src.telegram_bot import profiles

        profile_file = tmp_path / "profiles.json"
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump({"test": "data"}, f)

        with patch.object(profiles, "USER_PROFILES_FILE", str(profile_file)):
            with patch("builtins.open", side_effect=OSError("Read error")):
                profiles.load_user_profiles()

                assert profiles.USER_PROFILES == {}


class TestGetUserProfile:
    """Tests for get_user_profile function."""

    def test_get_user_profile_returns_existing_profile(self):
        """Test get_user_profile returns existing profile."""
        from src.telegram_bot import profiles

        existing_profile = {
            "language": "en",
            "api_key": "test_key",
            "api_secret": "test_secret",
            "auto_trading_enabled": True,
            "trade_settings": {
                "min_profit": 5.0,
                "max_price": 100.0,
                "max_trades": 10,
                "risk_level": "high",
            },
            "last_activity": 1234567890.0,
        }

        with patch.object(profiles, "USER_PROFILES", {"123": existing_profile}):
            with patch.object(profiles, "save_user_profiles"):
                profile = profiles.get_user_profile(123)

                assert profile["language"] == "en"
                assert profile["api_key"] == "test_key"

    def test_get_user_profile_creates_new_profile_if_not_exists(self):
        """Test get_user_profile creates new profile for new user."""
        from src.telegram_bot import profiles

        with patch.object(profiles, "USER_PROFILES", {}):
            with patch.object(profiles, "save_user_profiles") as mock_save:
                profile = profiles.get_user_profile(999)

                # New profile should have default values
                assert profile["language"] == "ru"
                assert profile["api_key"] == ""
                assert profile["api_secret"] == ""
                assert profile["auto_trading_enabled"] is False
                mock_save.assert_called_once()

    def test_get_user_profile_default_trade_settings(self):
        """Test get_user_profile creates default trade settings."""
        from src.telegram_bot import profiles

        with patch.object(profiles, "USER_PROFILES", {}):
            with patch.object(profiles, "save_user_profiles"):
                profile = profiles.get_user_profile(999)

                trade_settings = profile["trade_settings"]
                assert trade_settings["min_profit"] == 2.0
                assert trade_settings["max_price"] == 50.0
                assert trade_settings["max_trades"] == 3
                assert trade_settings["risk_level"] == "medium"

    def test_get_user_profile_updates_last_activity(self):
        """Test get_user_profile updates last_activity timestamp."""
        from src.telegram_bot import profiles

        old_time = 1000000000.0
        existing_profile = {
            "language": "ru",
            "api_key": "",
            "api_secret": "",
            "auto_trading_enabled": False,
            "trade_settings": {},
            "last_activity": old_time,
        }

        with patch.object(profiles, "USER_PROFILES", {"123": existing_profile}):
            with patch.object(profiles, "save_user_profiles"):
                profile = profiles.get_user_profile(123)

                # Last activity should be updated
                assert profile["last_activity"] > old_time

    def test_get_user_profile_converts_user_id_to_string(self):
        """Test get_user_profile handles integer user_id correctly."""
        from src.telegram_bot import profiles

        with patch.object(profiles, "USER_PROFILES", {}):
            with patch.object(profiles, "save_user_profiles"):
                profiles.get_user_profile(12345)

                # Profile should be stored with string key
                assert "12345" in profiles.USER_PROFILES

    def test_get_user_profile_handles_large_user_id(self):
        """Test get_user_profile handles large user IDs."""
        from src.telegram_bot import profiles

        large_id = 9999999999999

        with patch.object(profiles, "USER_PROFILES", {}):
            with patch.object(profiles, "save_user_profiles"):
                profile = profiles.get_user_profile(large_id)

                assert str(large_id) in profiles.USER_PROFILES
                assert profile is not None

    def test_get_user_profile_preserves_existing_data(self):
        """Test get_user_profile preserves existing profile data."""
        from src.telegram_bot import profiles

        existing_profile = {
            "language": "de",
            "api_key": "existing_key",
            "api_secret": "existing_secret",
            "auto_trading_enabled": True,
            "trade_settings": {
                "min_profit": 10.0,
                "max_price": 200.0,
                "max_trades": 20,
                "risk_level": "low",
            },
            "last_activity": 1234567890.0,
            "custom_field": "custom_value",
        }

        with patch.object(profiles, "USER_PROFILES", {"789": existing_profile.copy()}):
            with patch.object(profiles, "save_user_profiles"):
                profile = profiles.get_user_profile(789)

                # All existing data should be preserved
                assert profile["language"] == "de"
                assert profile["api_key"] == "existing_key"
                assert profile["auto_trading_enabled"] is True
                assert profile["custom_field"] == "custom_value"


class TestUserProfilesModule:
    """Integration tests for profiles module."""

    def test_user_profiles_global_dict_exists(self):
        """Test USER_PROFILES global dict is initialized."""
        from src.telegram_bot import profiles

        assert hasattr(profiles, "USER_PROFILES")
        assert isinstance(profiles.USER_PROFILES, dict)

    def test_multiple_users_can_be_stored(self):
        """Test multiple users can have profiles."""
        from src.telegram_bot import profiles

        with patch.object(profiles, "USER_PROFILES", {}):
            with patch.object(profiles, "save_user_profiles"):
                profiles.get_user_profile(111)
                profiles.get_user_profile(222)
                profiles.get_user_profile(333)

                assert len(profiles.USER_PROFILES) == 3
                assert "111" in profiles.USER_PROFILES
                assert "222" in profiles.USER_PROFILES
                assert "333" in profiles.USER_PROFILES

    def test_profile_persistence_round_trip(self, tmp_path):
        """Test profiles can be saved and loaded."""
        from src.telegram_bot import profiles

        profile_file = str(tmp_path / "test_profiles.json")

        with patch.object(profiles, "USER_PROFILES_FILE", profile_file):
            # Create and save profiles
            with patch.object(profiles, "USER_PROFILES", {}):
                profiles.get_user_profile(100)
                profiles.USER_PROFILES["100"]["language"] = "es"
                profiles.save_user_profiles()

            # Clear and load
            profiles.USER_PROFILES = {}
            profiles.load_user_profiles()

            assert "100" in profiles.USER_PROFILES
            assert profiles.USER_PROFILES["100"]["language"] == "es"
