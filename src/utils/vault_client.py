import logging
import hvac
import os
from typing import Optional

logger = logging.getLogger("VaultClient")

class VaultClient:
    """
    Real HashiCorp Vault Client Integration.
    Replaces MockMemoryVault for Production use.
    """
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.client: Optional[hvac.Client] = None

    def connect(self):
        try:
            self.client = hvac.Client(url=self.url, token=self.token)
            if not self.client.is_authenticated():
                logger.error("Vault authentication failed!")
                return False
            logger.info(f"Successfully connected to Vault at {self.url}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to Vault: {e}")
            return False

    def get_secret(self, path: str, key: str, mount_point: str = "secret") -> Optional[str]:
        """
        Retrieves a secret from Vault.
        Example: get_secret('dmarket', 'api_key')
        """
        if not self.client:
            if not self.connect():
                return None
        
        try:
            read_response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=mount_point
            )
            return read_response['data']['data'].get(key)
        except Exception as e:
            logger.error(f"Error reading secret '{key}' from path '{path}': {e}")
            return None
