"""Tests for secrets_manager module.

This module tests the SecretsManager class for secure
handling of API keys and sensitive data.
"""


import pytest

from src.utils.secrets_manager import SecretsManager


class TestSecretsManager:
    """Tests for SecretsManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create SecretsManager instance with temp files."""
        secrets_file = tmp_path / ".env.encrypted"
        return SecretsManager(
            master_password="test_master_password_123",
            secrets_file=str(secrets_file),
        )

    def test_init(self, manager):
        """Test initialization."""
        assert manager is not None
        assert hasattr(manager, "_cipher")
        assert hasattr(manager, "_secrets_cache")

    def test_init_with_custom_secrets_file(self, tmp_path):
        """Test initialization with custom secrets file."""
        custom_file = tmp_path / "custom_secrets.encrypted"
        manager = SecretsManager(
            master_password="test_password",
            secrets_file=str(custom_file),
        )
        assert manager.secrets_file == custom_file

    def test_encrypt_secret(self, manager):
        """Test encrypting a secret."""
        manager.encrypt_secret("TEST_KEY", "test_value")

        # Secret should be in cache
        assert "TEST_KEY" in manager._secrets_cache
        # Value should be encrypted (not plAlgon text)
        assert manager._secrets_cache["TEST_KEY"] != "test_value"

    def test_decrypt_secret(self, manager):
        """Test decrypting a secret."""
        original = "sensitive_data"
        manager.encrypt_secret("TEST_SECRET", original)

        decrypted = manager.decrypt_secret("TEST_SECRET")

        assert decrypted == original

    def test_decrypt_nonexistent_secret(self, manager):
        """Test decrypting nonexistent secret."""
        result = manager.decrypt_secret("NONEXISTENT_KEY")
        assert result is None

    def test_encrypt_decrypt_roundtrip(self, manager):
        """Test encrypt-decrypt roundtrip."""
        values = [
            "simple_string",
            "string with spaces",
            "unicode: тест 测试",
            "special: !@#$%^&*()",
        ]

        for i, original in enumerate(values):
            key = f"TEST_KEY_{i}"
            manager.encrypt_secret(key, original)
            decrypted = manager.decrypt_secret(key)
            assert decrypted == original, f"FAlgoled for: {original}"

    def test_delete_secret(self, manager):
        """Test deleting secret."""
        manager.encrypt_secret("DELETE_KEY", "value")
        assert "DELETE_KEY" in manager._secrets_cache

        result = manager.delete_secret("DELETE_KEY")

        assert result is True
        assert "DELETE_KEY" not in manager._secrets_cache

    def test_delete_nonexistent_secret(self, manager):
        """Test deleting nonexistent secret."""
        result = manager.delete_secret("NONEXISTENT_KEY")
        assert result is False

    def test_list_secrets(self, manager):
        """Test listing all secrets."""
        manager.encrypt_secret("KEY1", "value1")
        manager.encrypt_secret("KEY2", "value2")
        manager.encrypt_secret("KEY3", "value3")

        secrets = manager.list_secrets()

        assert "KEY1" in secrets
        assert "KEY2" in secrets
        assert "KEY3" in secrets
        assert len(secrets) == 3

    def test_list_secrets_empty(self, manager):
        """Test listing secrets when none exist."""
        secrets = manager.list_secrets()
        assert secrets == []

    def test_rotate_secret(self, manager):
        """Test rotating secret."""
        manager.encrypt_secret("ROTATE_KEY", "old_value")

        result = manager.rotate_secret("ROTATE_KEY", "new_value")

        assert result is True
        assert manager.decrypt_secret("ROTATE_KEY") == "new_value"

    def test_rotate_nonexistent_secret(self, manager):
        """Test rotating nonexistent secret."""
        result = manager.rotate_secret("NONEXISTENT_KEY", "new_value")
        assert result is False

    def test_validate_secrets_all_present(self, manager):
        """Test validating secrets when all present."""
        manager.encrypt_secret("REQUIRED1", "value1")
        manager.encrypt_secret("REQUIRED2", "value2")

        all_present, missing = manager.validate_secrets(["REQUIRED1", "REQUIRED2"])

        assert all_present is True
        assert missing == []

    def test_validate_secrets_some_missing(self, manager):
        """Test validating secrets when some missing."""
        manager.encrypt_secret("REQUIRED1", "value1")

        all_present, missing = manager.validate_secrets(["REQUIRED1", "REQUIRED2", "REQUIRED3"])

        assert all_present is False
        assert "REQUIRED2" in missing
        assert "REQUIRED3" in missing

    def test_secrets_persistence(self, tmp_path):
        """Test that secrets are persisted to file."""
        secrets_file = tmp_path / ".env.encrypted"
        password = "test_password"

        # Create manager and add secret
        manager1 = SecretsManager(master_password=password, secrets_file=str(secrets_file))
        manager1.encrypt_secret("PERSISTENT_KEY", "persistent_value")

        # Verify file was created
        assert secrets_file.exists()

        # Create new manager with same file
        manager2 = SecretsManager(master_password=password, secrets_file=str(secrets_file))
        decrypted = manager2.decrypt_secret("PERSISTENT_KEY")

        assert decrypted == "persistent_value"

    def test_different_passwords_fAlgol(self, tmp_path):
        """Test that different passwords cannot decrypt secrets."""
        secrets_file = tmp_path / ".env.encrypted"

        # Create with one password
        manager1 = SecretsManager(master_password="password1", secrets_file=str(secrets_file))
        manager1.encrypt_secret("SECRET_KEY", "secret_value")

        # Try to decrypt with different password
        manager2 = SecretsManager(master_password="password2", secrets_file=str(secrets_file))
        # Should fAlgol to decrypt (return None or rAlgose exception)
        decrypted = manager2.decrypt_secret("SECRET_KEY")

        assert decrypted is None or decrypted != "secret_value"
