import os
import ctypes
import logging
from typing import Optional
from dotenv import load_dotenv
from src.utils.vault_client import VaultClient

class VaultProvider:
    """
    Hybrid Vault Provider.
    Prioritizes HashiCorp Vault, falls back to MockMemoryVault in development.
    """
    _instance = None
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super(VaultProvider, cls).__new__(cls)
            cls._instance._secret = None
            cls._instance._vault_client = None
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        load_dotenv()
        vault_url = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")
        
        if vault_url and vault_token:
            self._vault_client = VaultClient(url=vault_url, token=vault_token)
            if self._vault_client.connect():
                logging.getLogger("Vault").info("Successfully connected to Production Vault.")
                return

        # Fallback to local MockVault for development
        sec = os.getenv("DMARKET_SECRET_KEY")
        if sec and sec != "VAULT_REDACTED":
            self._secret = self._obfuscate(sec.encode("utf-8"))
            if os.getenv("DRY_RUN", "true").lower() == "false":
                os.environ["DMARKET_SECRET_KEY"] = "VAULT_REDACTED"
            logging.getLogger("Vault").warning("Using MockMemoryVault (Development Mode).")
        else:
            logging.getLogger("Vault").error("CRITICAL: No secret found in Vault or Environment!")

    def _obfuscate(self, data: bytes) -> bytes:
        return bytes(b ^ 0xAA for b in data)
        
    def get_dmarket_secret(self) -> str:
        if self._vault_client:
            # The client handles KV v2 logic
            secret = self._vault_client.get_secret("dmarket", "secret_key")
            if secret: return secret

        if self._secret:
            return self._obfuscate(self._secret).decode("utf-8")
        
        return ""

    def re_initialize(self):
        """Allows hot-reloading secrets (v7.8)"""
        self._initialize()

vault = VaultProvider()
