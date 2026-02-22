"""
Secrets Management Module.

Provides secure secrets handling with encryption, rotation, and audit logging.
"""

import base64
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class SecretsManager:
    """Manage encrypted secrets with rotation and audit logging."""

    def __init__(self, master_password: str, secrets_file: str = ".env.encrypted"):
        """Initialize secrets manager.

        Args:
            master_password: Master password for encryption
            secrets_file: Path to encrypted secrets file
        """
        self.secrets_file = Path(secrets_file)
        self.audit_log_file = Path("secrets_audit.log")
        self._cipher = self._create_cipher(master_password)
        self._secrets_cache: dict[str, str] = {}

    def _create_cipher(self, password: str) -> Fernet:
        """Create encryption cipher from password."""
        # Derive key from password using PBKDF2HMAC
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"dmarket-bot-salt",  # In production, use random salt stored separately
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)

    def encrypt_secret(self, name: str, value: str) -> None:
        """Encrypt and store a secret.

        Args:
            name: Secret name
            value: Secret value (plain text)
        """
        encrypted = self._cipher.encrypt(value.encode())
        self._secrets_cache[name] = encrypted.decode()

        # Save to file
        self._save_secrets()

        # Audit log
        self._audit_log("ENCRYPT", name)
        logger.info(f"Secret encrypted: {name}")

    def decrypt_secret(self, name: str) -> str | None:
        """Decrypt and retrieve a secret.

        Args:
            name: Secret name

        Returns:
            Decrypted secret value or None if not found
        """
        if not self._secrets_cache:
            self._load_secrets()

        encrypted = self._secrets_cache.get(name)
        if not encrypted:
            logger.warning(f"Secret not found: {name}")
            return None

        try:
            decrypted = self._cipher.decrypt(encrypted.encode())
            self._audit_log("DECRYPT", name)
            return decrypted.decode()
        except Exception as e:
            logger.exception(f"Failed to decrypt secret {name}: {e}")
            return None

    def rotate_secret(self, name: str, new_value: str) -> bool:
        """Rotate a secret (update with new value).

        Args:
            name: Secret name
            new_value: New secret value

        Returns:
            True if rotation succeeded
        """
        old_value = self.decrypt_secret(name)
        if not old_value:
            return False

        # Encrypt new value
        self.encrypt_secret(name, new_value)

        # Audit log
        self._audit_log("ROTATE", name)
        logger.info(f"Secret rotated: {name}")

        return True

    def delete_secret(self, name: str) -> bool:
        """Delete a secret.

        Args:
            name: Secret name

        Returns:
            True if deletion succeeded
        """
        if name in self._secrets_cache:
            del self._secrets_cache[name]
            self._save_secrets()
            self._audit_log("DELETE", name)
            logger.info(f"Secret deleted: {name}")
            return True

        return False

    def list_secrets(self) -> list[str]:
        """List all secret names (not values)."""
        if not self._secrets_cache:
            self._load_secrets()

        return list(self._secrets_cache.keys())

    def validate_secrets(self, required_secrets: list[str]) -> tuple[bool, list[str]]:
        """Validate that all required secrets exist.

        Args:
            required_secrets: List of required secret names

        Returns:
            Tuple of (all_present, missing_secrets)
        """
        if not self._secrets_cache:
            self._load_secrets()

        missing = [name for name in required_secrets if name not in self._secrets_cache]
        return (len(missing) == 0, missing)

    def _save_secrets(self) -> None:
        """Save encrypted secrets to file."""
        try:
            with open(self.secrets_file, "w", encoding="utf-8") as f:
                json.dump(self._secrets_cache, f, indent=2)
            logger.debug(f"Secrets saved to {self.secrets_file}")
        except Exception as e:
            logger.exception(f"Failed to save secrets: {e}")
            raise

    def _load_secrets(self) -> None:
        """Load encrypted secrets from file."""
        if not self.secrets_file.exists():
            logger.warning(f"Secrets file not found: {self.secrets_file}")
            return

        try:
            with open(self.secrets_file, encoding="utf-8") as f:
                self._secrets_cache = json.load(f)
            logger.debug(f"Secrets loaded from {self.secrets_file}")
        except Exception as e:
            logger.exception(f"Failed to load secrets: {e}")
            raise

    def _audit_log(self, action: str, secret_name: str) -> None:
        """Log secret access for audit trail.

        Args:
            action: Action performed (ENCRYPT, DECRYPT, ROTATE, DELETE)
            secret_name: Name of the secret
        """
        timestamp = datetime.now(UTC).isoformat()
        log_entry = f"{timestamp} | {action} | {secret_name}\n"

        try:
            with open(self.audit_log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.exception(f"Failed to write audit log: {e}")


def migrate_env_to_encrypted(
    env_file: str = ".env",
    master_password: str | None = None,
    output_file: str = ".env.encrypted",
) -> None:
    """Migrate plain .env file to encrypted format.

    Args:
        env_file: Path to .env file
        master_password: Master password (Configs if not provided)
        output_file: Output encrypted file path
    """
    if not master_password:
        import getpass

        master_password = getpass.getpass("Enter master password: ")

    manager = SecretsManager(master_password, output_file)

    # Read .env file
    env_path = Path(env_file)
    if not env_path.exists():
        logger.error(f".env file not found: {env_file}")
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                # Encrypt secret
                manager.encrypt_secret(key, value)
                logger.info(f"Migrated: {key}")

    logger.info(f"Migration complete. Secrets saved to {output_file}")
    logger.info("IMPORTANT: Delete .env file after verifying encrypted file works")


if __name__ == "__main__":
    # Example: Migrate .env to encrypted format
    migrate_env_to_encrypted()
