import os
import sys
from typing import Any
from src.config import Config

class ConfigManager:
    """
    Bridge between older src.core references and the new centralized src.config.
    Provides a dictionary-like interface for get() operations.
    """
    _config = Config

    def __init__(self):
        pass

    def get(self, key: str, default: Any = None) -> Any:
        # Convert lowercase keys to uppercase to match Config attributes
        attr_name = key.upper()
        if hasattr(self._config, attr_name):
            return getattr(self._config, attr_name)
        
        # Fallback to environment variables
        return os.getenv(attr_name, default)

    @property
    def api_url(self) -> str:
        return "https://api.dmarket.com"

    @property
    def target_games(self) -> list:
        # Default games as defined in roadmap
        return [self._config.GAME_ID] # Currently CS2: a8db
