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
        Retrieves a secret from Vault KV v2.
        Example: get_secret('dmarket', 'secret_key')
        """
        if not self.client:
            if not self.connect():
                return None
        
        try:
            # kv.v2.read_secret_version is the correct method for KV v2
            read_response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=mount_point
            )
            # data structure for KV2 is response['data']['data']
            data = read_response.get('data', {}).get('data', {})
            secret = data.get(key)
            if not secret:
                logger.error(f"Key '{key}' not found in secret path '{mount_point}/{path}'")
            return secret
        except Exception as e:
            logger.error(f"Failed to read secret '{key}' from '{mount_point}/{path}': {e}")
            return None
