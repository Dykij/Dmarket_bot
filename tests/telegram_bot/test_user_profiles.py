"""Tests for user_profiles.py module.

This module tests:
- UserProfileManager singleton
- Profile encryption/decryption
- API key management
- Access level checks
- Profile persistence
- Decorator for access control
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.telegram_bot.user_profiles import (
    ACCESS_LEVELS,
    FEATURE_ACCESS_LEVELS,
    UserProfileManager,
    check_user_access,
    get_api_keys,
    get_user_settings,
    profile_manager,
    require_access_level,
    set_api_keys,
    update_user_settings,
)

# ============================================================================
# Test Constants
# ============================================================================


class TestAccessLevels:
    """Tests for access level constants."""

    def test_access_levels_defined(self) -> None:
        """Test that all access levels are defined."""
        assert "admin" in ACCESS_LEVELS
        assert "premium" in ACCESS_LEVELS
        assert "regular" in ACCESS_LEVELS
        assert "basic" in ACCESS_LEVELS
        assert "restricted" in ACCESS_LEVELS
        assert "blocked" in ACCESS_LEVELS

    def test_access_levels_hierarchy(self) -> None:
        """Test that access levels have proper hierarchy."""
        assert ACCESS_LEVELS["admin"] > ACCESS_LEVELS["premium"]
        assert ACCESS_LEVELS["premium"] > ACCESS_LEVELS["regular"]
        assert ACCESS_LEVELS["regular"] > ACCESS_LEVELS["basic"]
        assert ACCESS_LEVELS["basic"] > ACCESS_LEVELS["restricted"]
        assert ACCESS_LEVELS["restricted"] > ACCESS_LEVELS["blocked"]

    def test_blocked_level_is_zero(self) -> None:
        """Test that blocked level is zero."""
        assert ACCESS_LEVELS["blocked"] == 0


class TestFeatureAccessLevels:
    """Tests for feature access level mappings."""

    def test_feature_levels_defined(self) -> None:
        """Test that feature access levels are defined."""
        assert "view_balance" in FEATURE_ACCESS_LEVELS
        assert "search_items" in FEATURE_ACCESS_LEVELS
        assert "basic_arbitrage" in FEATURE_ACCESS_LEVELS
        assert "admin_tools" in FEATURE_ACCESS_LEVELS

    def test_admin_tools_requires_admin(self) -> None:
        """Test that admin tools require admin access."""
        assert FEATURE_ACCESS_LEVELS["admin_tools"] == ACCESS_LEVELS["admin"]


# ============================================================================
# Test UserProfileManager
# ============================================================================


class TestUserProfileManager:
    """Tests for UserProfileManager class."""

    @pytest.fixture()
    def clean_manager(self) -> UserProfileManager:
        """Create a clean UserProfileManager instance."""
        # Reset the singleton
        UserProfileManager._instance = None
        return UserProfileManager()

    def test_singleton_pattern(self) -> None:
        """Test that UserProfileManager uses singleton pattern."""
        manager1 = UserProfileManager()
        manager2 = UserProfileManager()

        assert manager1 is manager2

    def test_init_creates_data_dir(self) -> None:
        """Test that initialization creates data directory."""
        UserProfileManager()

        # DATA_DIR should exist (created during init)
        from src.telegram_bot.user_profiles import DATA_DIR

        assert DATA_DIR.exists()

    def test_get_profile_creates_default(self) -> None:
        """Test that get_profile creates default for new user."""
        manager = UserProfileManager()
        user_id = 999888777666  # Unlikely to exist

        profile = manager.get_profile(user_id)

        assert isinstance(profile, dict)
        assert "access_level" in profile
        assert profile["access_level"] == "basic"

    def test_get_profile_returns_existing(self) -> None:
        """Test that get_profile returns existing profile."""
        manager = UserProfileManager()
        user_id = 111222333444

        # Create profile
        profile1 = manager.get_profile(user_id)
        profile1["custom_field"] = "test_value"

        # Get agAlgon
        profile2 = manager.get_profile(user_id)

        assert profile2.get("custom_field") == "test_value"

    def test_create_default_profile_structure(self) -> None:
        """Test default profile has correct structure."""
        manager = UserProfileManager()

        profile = manager._create_default_profile()

        assert "created_at" in profile
        assert "last_activity" in profile
        assert "access_level" in profile
        assert "settings" in profile
        assert "api_keys" in profile
        assert "stats" in profile

    def test_update_profile_updates_data(self) -> None:
        """Test that update_profile updates profile data."""
        manager = UserProfileManager()
        user_id = 555666777888

        manager.update_profile(user_id, {"custom_key": "custom_value"})

        profile = manager.get_profile(user_id)
        assert profile.get("custom_key") == "custom_value"

    def test_update_profile_updates_last_activity(self) -> None:
        """Test that update_profile updates last_activity."""
        manager = UserProfileManager()
        user_id = 444555666777

        profile = manager.get_profile(user_id)
        old_activity = profile.get("last_activity", 0)

        time.sleep(0.1)  # Small delay
        manager.update_profile(user_id, {"test": "value"})

        new_profile = manager.get_profile(user_id)
        assert new_profile["last_activity"] >= old_activity

    def test_set_api_key(self) -> None:
        """Test setting API key."""
        manager = UserProfileManager()
        user_id = 333444555666

        manager.set_api_key(user_id, "test_key", "test_value")

        retrieved = manager.get_api_key(user_id, "test_key")
        assert retrieved == "test_value"

    def test_get_api_key_not_found(self) -> None:
        """Test getting non-existent API key."""
        manager = UserProfileManager()
        user_id = 222333444555

        result = manager.get_api_key(user_id, "nonexistent_key")

        assert result == ""

    def test_has_access_basic_user(self) -> None:
        """Test has_access for basic user."""
        manager = UserProfileManager()
        user_id = 111222333

        # Set up basic user
        manager.update_profile(user_id, {"access_level": "basic"})

        # Should have access to basic features
        assert manager.has_access(user_id, "view_balance")

        # Should not have access to premium features
        assert not manager.has_access(user_id, "advanced_arbitrage")

    def test_has_access_admin_user(self) -> None:
        """Test has_access for admin user."""
        manager = UserProfileManager()
        user_id = 999888777

        # Set up admin user
        manager.update_profile(user_id, {"access_level": "admin"})

        # Admin should have access to everything
        assert manager.has_access(user_id, "admin_tools")
        assert manager.has_access(user_id, "advanced_arbitrage")
        assert manager.has_access(user_id, "view_balance")

    def test_set_access_level_valid(self) -> None:
        """Test setting valid access level."""
        manager = UserProfileManager()
        user_id = 888777666

        result = manager.set_access_level(user_id, "premium")

        assert result is True
        profile = manager.get_profile(user_id)
        assert profile["access_level"] == "premium"

    def test_set_access_level_invalid(self) -> None:
        """Test setting invalid access level."""
        manager = UserProfileManager()
        user_id = 777666555

        result = manager.set_access_level(user_id, "invalid_level")

        assert result is False

    def test_set_access_level_admin_adds_to_admin_ids(self) -> None:
        """Test that setting admin level adds user to admin_ids."""
        manager = UserProfileManager()
        user_id = 666555444

        manager.set_access_level(user_id, "admin")

        admin_ids = manager.get_admin_ids()
        assert user_id in admin_ids

    def test_get_admin_ids_returns_copy(self) -> None:
        """Test that get_admin_ids returns a copy."""
        manager = UserProfileManager()

        admin_ids = manager.get_admin_ids()
        original_size = len(admin_ids)

        # Modify the returned set
        admin_ids.add(999999999)

        # Original should not be affected
        assert len(manager.get_admin_ids()) == original_size

    def test_track_stat_increments(self) -> None:
        """Test that track_stat increments counters."""
        manager = UserProfileManager()
        user_id = 555444333222  # Unique user ID to avoid conflicts

        # Get initial value
        profile = manager.get_profile(user_id)
        initial_val = profile.get("stats", {}).get("test_stat_inc", 0)

        manager.track_stat(user_id, "test_stat_inc", 1)
        manager.track_stat(user_id, "test_stat_inc", 2)

        profile = manager.get_profile(user_id)
        assert profile["stats"]["test_stat_inc"] == initial_val + 3

    def test_track_stat_creates_counter(self) -> None:
        """Test that track_stat creates counter if not exists."""
        manager = UserProfileManager()
        user_id = 444333222111  # Unique user ID
        unique_stat = f"new_stat_{int(time.time() * 1000)}"  # Unique stat name

        manager.track_stat(user_id, unique_stat)

        profile = manager.get_profile(user_id)
        assert profile["stats"][unique_stat] == 1


# ============================================================================
# Test Encryption
# ============================================================================


class TestEncryption:
    """Tests for encryption functionality."""

    def test_encrypt_empty_string(self) -> None:
        """Test encrypting empty string."""
        manager = UserProfileManager()

        result = manager._encrypt("")

        assert result == ""

    def test_decrypt_empty_string(self) -> None:
        """Test decrypting empty string."""
        manager = UserProfileManager()

        result = manager._decrypt("")

        assert result == ""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test encryption/decryption roundtrip."""
        manager = UserProfileManager()
        original = "test_api_key_12345"

        encrypted = manager._encrypt(original)
        decrypted = manager._decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_encrypt_produces_different_output(self) -> None:
        """Test that encryption produces different output than input."""
        manager = UserProfileManager()
        original = "my_secret_key"

        encrypted = manager._encrypt(original)

        assert encrypted != original


# ============================================================================
# Test Helper Functions
# ============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    @pytest.mark.asyncio()
    async def test_check_user_access_with_access(self) -> None:
        """Test check_user_access when user has access."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123456789
        context = MagicMock()

        # Set up profile with access
        profile_manager.update_profile(123456789, {"access_level": "admin"})

        result = await check_user_access(update, context, "admin_tools")

        assert result is True

    @pytest.mark.asyncio()
    async def test_check_user_access_no_user(self) -> None:
        """Test check_user_access with no effective user."""
        update = MagicMock()
        update.effective_user = None
        context = MagicMock()

        result = await check_user_access(update, context, "view_balance")

        assert result is False

    @pytest.mark.asyncio()
    async def test_get_api_keys_existing(self) -> None:
        """Test get_api_keys when keys exist."""
        user_id = 987654321
        profile_manager.set_api_key(user_id, "dmarket_public_key", "pub_key")
        profile_manager.set_api_key(user_id, "dmarket_secret_key", "sec_key")

        public, secret = await get_api_keys(user_id)

        assert public == "pub_key"
        assert secret == "sec_key"

    @pytest.mark.asyncio()
    async def test_get_api_keys_missing(self) -> None:
        """Test get_api_keys when keys don't exist."""
        user_id = 876543210

        public, secret = await get_api_keys(user_id)

        assert public is None
        assert secret is None

    @pytest.mark.asyncio()
    async def test_set_api_keys_success(self) -> None:
        """Test set_api_keys successfully."""
        user_id = 765432109

        result = await set_api_keys(user_id, "new_pub", "new_sec")

        assert result is True
        public, secret = await get_api_keys(user_id)
        assert public == "new_pub"
        assert secret == "new_sec"

    @pytest.mark.asyncio()
    async def test_set_api_keys_empty_values(self) -> None:
        """Test set_api_keys with empty values."""
        user_id = 654321098

        result = await set_api_keys(user_id, "", "secret")

        assert result is False

    @pytest.mark.asyncio()
    async def test_get_user_settings(self) -> None:
        """Test get_user_settings returns settings dict."""
        user_id = 543210987

        settings = await get_user_settings(user_id)

        assert isinstance(settings, dict)

    @pytest.mark.asyncio()
    async def test_update_user_settings(self) -> None:
        """Test update_user_settings updates settings."""
        user_id = 432109876

        await update_user_settings(user_id, {"custom_setting": "value"})

        settings = await get_user_settings(user_id)
        assert settings.get("custom_setting") == "value"


# ============================================================================
# Test Decorator
# ============================================================================


class TestRequireAccessLevelDecorator:
    """Tests for require_access_level decorator."""

    @pytest.mark.asyncio()
    async def test_decorator_allows_access(self) -> None:
        """Test decorator allows access for authorized user."""
        user_id = 111222333
        profile_manager.update_profile(user_id, {"access_level": "admin"})

        @require_access_level("admin_tools")
        async def test_handler(update, context):
            return "success"

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = user_id
        update.message = None
        context = MagicMock()

        await test_handler(update, context)
        # Should not raise

    @pytest.mark.asyncio()
    async def test_decorator_denies_access(self) -> None:
        """Test decorator denies access for unauthorized user."""
        user_id = 222333444
        profile_manager.update_profile(user_id, {"access_level": "basic"})

        @require_access_level("admin_tools")
        async def test_handler(update, context):
            return "success"

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = user_id
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await test_handler(update, context)

        # Should have sent access denied message
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_decorator_no_user(self) -> None:
        """Test decorator handles no effective user."""

        @require_access_level("view_balance")
        async def test_handler(update, context):
            return "success"

        update = MagicMock()
        update.effective_user = None
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await test_handler(update, context)

        update.message.reply_text.assert_called_once()


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_profile_with_special_characters(self) -> None:
        """Test profile with special characters in API key."""
        manager = UserProfileManager()
        user_id = 321654987
        special_key = "key!@#$%^&*()_+-=[]{}|;':\",./<>?"

        manager.set_api_key(user_id, "special", special_key)

        retrieved = manager.get_api_key(user_id, "special")
        assert retrieved == special_key

    def test_profile_with_unicode(self) -> None:
        """Test profile with unicode characters."""
        manager = UserProfileManager()
        user_id = 210987654
        unicode_value = "ключ_API_🔑_键"

        manager.set_api_key(user_id, "unicode", unicode_value)

        retrieved = manager.get_api_key(user_id, "unicode")
        assert retrieved == unicode_value

    def test_concurrent_profile_updates(self) -> None:
        """Test concurrent profile updates."""
        manager = UserProfileManager()
        user_id = 109876543

        # Multiple updates
        for i in range(10):
            manager.update_profile(user_id, {f"field_{i}": i})

        profile = manager.get_profile(user_id)

        # All fields should be present
        for i in range(10):
            assert profile.get(f"field_{i}") == i

    def test_save_profiles_rate_limiting(self) -> None:
        """Test that save_profiles has rate limiting."""
        manager = UserProfileManager()
        user_id = 998877665

        # First update (should save)
        manager.update_profile(user_id, {"first": True})

        # Quick successive update (may be rate limited)
        manager.update_profile(user_id, {"second": True})

        # Should not raise

    def test_decryption_invalid_data(self) -> None:
        """Test decryption with invalid data."""
        manager = UserProfileManager()

        # Invalid base64/encrypted data
        result = manager._decrypt("invalid_encrypted_data")

        # Should return empty string on error
        assert result == ""
