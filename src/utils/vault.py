import os
import ctypes
import logging
from typing import Optional
from src.utils.vault_client import VaultClient

class VaultProvider:
    """
    Hybrid Vault Provider.
    Prioritizes HashiCorp Vault, falls back to MockMemoryVault.
    """
    _instance = None
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super(VaultProvider, cls).__new__(cls)
            cls._instance._secret = None
            cls._instance._vault_client = None
            cls._instance._initialize()
        return cls._instance

    def re_initialize(self):
        """Force re-initialization from current environment (used after .env loading)."""
        self._initialize()
        
    def _initialize(self):
        # 1. Try real HashiCorp Vault first
        vault_url = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")
        
        if vault_url and vault_token:
            self._vault_client = VaultClient(url=vault_url, token=vault_token)
            if self._vault_client.connect():
                logging.getLogger("Vault").info("Connected to HashiCorp Vault.")
                return

        # 2. Fallback to MockMemoryVault logic
        sec = os.getenv("DMARKET_SECRET_KEY", "")
        if sec:
            self._secret = self._obfuscate(sec.encode("utf-8"))
            # Scrub from env for security
            if os.getenv("DRY_RUN", "false").lower() != "true":
                os.environ["DMARKET_SECRET_KEY"] = "VAULT_REDACTED"
            logging.getLogger("Vault").info("Secret Key successfully injected into MockVault memory.")

    def _obfuscate(self, data: bytes) -> bytes:
        # Simple XOR mask to protect against basic memory scanning
        return bytes(b ^ 0xAA for b in data)
        
    def get_dmarket_secret(self) -> str:
        # Try real vault first
        if self._vault_client:
            secret = self._vault_client.get_secret("secret/dmarket", "secret_key")
            if secret: return secret

        # Fallback to internal obfuscated secret
        if not self._secret: return ""
        return self._obfuscate(self._secret).decode("utf-8")

vault = VaultProvider()
