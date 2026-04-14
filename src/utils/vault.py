import os
import ctypes
import logging

class MockMemoryVault:
    """
    Iteration 36-38: Mocking High-Security Memory Vault.
    Isolates and encrypts DMARKET_SECRET_KEY in-memory protecting it from memory dumps.
    """
    _instance = None
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super(MockMemoryVault, cls).__new__(cls)
            cls._instance._secret = None
            cls._instance._initialize()
        return cls._instance
        
    def _initialize(self):
        # Fetch from env immediately and scrub it out of the env 
        sec = os.getenv("DMARKET_SECRET_KEY", "")
        if sec:
            self._secret = self._obfuscate(sec.encode("utf-8"))
            os.environ["DMARKET_SECRET_KEY"] = "VAULT_REDACTED"
            logging.getLogger("Vault").info("Secret Key successfully injected into Vault memory.")

    def _obfuscate(self, data: bytes) -> bytes:
        # Simple XOR mask to protect against basic memory scanning
        return bytes(b ^ 0xAA for b in data)
        
    def get_dmarket_secret(self) -> str:
        if not self._secret: return ""
        return self._obfuscate(self._secret).decode("utf-8")

vault = MockMemoryVault()
