import os
import base64
import logging
from dotenv import load_dotenv
from src.utils.vault_client import VaultClient

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[assignment,misc]

class VaultProvider:
    """
    Hybrid Vault Provider.
    Prioritizes HashiCorp Vault, falls back to Fernet encryption in .env.

    v12.9: XOR 0xAA fallback REMOVED for security. ENCRYPTION_KEY is now
    REQUIRED when DRY_RUN=false (production mode). The provider raises
    RuntimeError during initialization if no secure encryption is available.
    """
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(VaultProvider, cls).__new__(cls)
            cls._instance._secret = None
            cls._instance._vault_client = None
            cls._instance._fernet = None
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent.parent
        env_path = project_root / ".env"
        load_dotenv(dotenv_path=str(env_path), override=False)
        vault_url = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")

        if vault_url and vault_token:
            self._vault_client = VaultClient(url=vault_url, token=vault_token)
            if self._vault_client.connect():
                logging.getLogger("Vault").info("Successfully connected to Production Vault.")
                return

        is_production = os.getenv("DRY_RUN", "true").lower() == "false"

        enc_key = os.getenv("ENCRYPTION_KEY", "").strip()
        if enc_key and Fernet is not None:
            try:
                key_bytes = base64.urlsafe_b64encode(
                    enc_key.encode("utf-8").ljust(32, b"\x00")[:32]
                )
                self._fernet = Fernet(key_bytes)
                logging.getLogger("Vault").info("Using Fernet encryption (ENCRYPTION_KEY).")
            except Exception as e:
                raise RuntimeError(
                    f"Fernet init failed with ENCRYPTION_KEY: {e}. "
                    "Generate a valid key with: python -c \"from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())\""
                ) from e
        elif is_production:
            raise RuntimeError(
                "ENCRYPTION_KEY is REQUIRED in production mode (DRY_RUN=false). "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        else:
            logging.getLogger("Vault").warning(
                "No ENCRYPTION_KEY set — using development-only in-memory storage. "
                "Set ENCRYPTION_KEY in .env for production."
            )

        sec = os.getenv("DMARKET_SECRET_KEY")
        if sec and sec != "VAULT_REDACTED":
            self._secret = self._encrypt(sec)
            if is_production:
                os.environ["DMARKET_SECRET_KEY"] = "VAULT_REDACTED"
            mode = "Fernet" if self._fernet else "PLAINTEXT_IN_MEMORY"
            logging.getLogger("Vault").warning(
                f"Using {mode} vault (dev mode). "
                "Set VAULT_ADDR/VAULT_TOKEN for production."
            )
        else:
            logging.getLogger("Vault").error(
                "CRITICAL: No secret found in Vault or Environment!"
            )

    def _encrypt(self, plaintext: str) -> bytes:
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode("utf-8"))
        return plaintext.encode("utf-8")

    def _decrypt(self, data: bytes) -> str:
        if self._fernet:
            return self._fernet.decrypt(data).decode("utf-8")
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
