from src.config import Config
import base64
import logging
import os

from dotenv import load_dotenv

from src.utils.vault_client import VaultClient

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[assignment,misc]

logger = logging.getLogger("Vault")

class VaultProvider:
    """
    Hybrid Vault Provider.
    Prioritizes HashiCorp Vault, falls back to Fernet encryption in .env.

    v14.8: Fixed ENCRYPTION_KEY validation and generation. Now requires
    a proper 32-byte URL-safe base64-encoded Fernet key (44 chars).
    Old buggy ljust/pad behavior removed.
    """
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._secret = None
            cls._instance._vault_client = None
            cls._instance._fernet = None
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Clear old state before re-initializing to ensure new keys are used
        self._secret = None
        self._fernet = None
        self._vault_client = None

        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent.parent
        env_path = project_root / ".env"
        load_dotenv(dotenv_path=str(env_path), override=False)
        vault_url = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")

        if vault_url and vault_token:
            vc = VaultClient(url=vault_url, token=vault_token)
            if vc.connect():
                self._vault_client = vc
                logger.info("Successfully connected to Production Vault.")
                return

        is_production = not Config.DRY_RUN

        enc_key = os.getenv("ENCRYPTION_KEY", "").strip()
        if enc_key and Fernet is not None:
            self._fernet = self._init_fernet(enc_key)
            if self._fernet:
                logger.info("Using Fernet encryption (ENCRYPTION_KEY).")
        elif is_production:
            raise RuntimeError(
                "ENCRYPTION_KEY is REQUIRED in production mode (DRY_RUN=false). "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        else:
            logger.warning(
                "No ENCRYPTION_KEY set — using development-only in-memory storage. "
                "Set ENCRYPTION_KEY in .env for production."
            )

        sec = os.getenv("DMARKET_SECRET_KEY")
        if sec and sec != "VAULT_REDACTED":
            self._secret = self._encrypt(sec)
            if is_production:
                os.environ["DMARKET_SECRET_KEY"] = "VAULT_REDACTED"
            mode = "Fernet" if self._fernet else "PLAINTEXT_IN_MEMORY"
            logger.warning(
                f"Using {mode} vault (dev mode). "
                "Set VAULT_ADDR/VAULT_TOKEN for production."
            )
        else:
            logger.error(
                "CRITICAL: No secret found in Vault or Environment!"
            )

    def _init_fernet(self, key: str) -> "Fernet | None":
        """
        Validate and initialize Fernet from a key string.
        Accepts:
        - 44-char URL-safe base64 (standard Fernet.generate_key())
        - 32 raw bytes auto-wrapped in b64
        - 43 or 45 chars (padded b64) — corrected automatically
        """
        try:
            key_bytes = key.encode("utf-8")

            if len(key_bytes) == 32:
                actual_key = base64.urlsafe_b64encode(key_bytes)
                logger.warning(
                    "ENCRYPTION_KEY was 32 raw bytes (legacy format). "
                    "Regenerate with 'Fernet.generate_key()' for proper 44-char base64 format."
                )
            else:
                actual_key = key_bytes

            fernet = Fernet(actual_key)
            # Test round-trip
            test_data = b"vault_test"
            if fernet.decrypt(fernet.encrypt(test_data)) == test_data:
                return fernet
        except Exception as e:
            logger.warning(f"Fernet init failed with provided key: {e}")

        # If all else fails, generate a random one (dev mode only)
        if Config.DRY_RUN:
            new_key = Fernet.generate_key()
            logger.warning("Generated new random ENCRYPTION_KEY for dev mode (key masked)")
            return Fernet(new_key)

        raise RuntimeError(
            "Invalid ENCRYPTION_KEY. Generate a proper key with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    def _encrypt(self, plaintext: str) -> bytes:
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode("utf-8"))
        # In production without Fernet, refuse to store secrets unencrypted
        if not Config.DRY_RUN:
            raise RuntimeError(
                "Cannot encrypt secret: no Fernet key available. "
                "Set ENCRYPTION_KEY in .env or connect to Vault."
            )
        return plaintext.encode("utf-8")

    def _decrypt(self, data: bytes) -> str:
        if self._fernet:
            return self._fernet.decrypt(data).decode("utf-8")
        # In production without Fernet, refuse to decrypt
        if not Config.DRY_RUN:
            raise RuntimeError(
                "Cannot decrypt secret: no Fernet key available. "
                "Set ENCRYPTION_KEY in .env or connect to Vault."
            )
        return data.decode("utf-8")

    def get_dmarket_secret(self) -> str:
        if self._vault_client:
            secret = self._vault_client.get_secret("dmarket", "secret_key")
            if secret:
                return secret

        if self._secret:
            return self._decrypt(self._secret)

        return ""

    def re_initialize(self):
        """Allows hot-reloading secrets (v7.8)"""
        self._initialize()

vault = VaultProvider()
