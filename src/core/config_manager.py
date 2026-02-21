import os
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
import jsonschema

logger = logging.getLogger(__name__)

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "api_url": {"type": "string", "default": "https://api.dmarket.com"},
        "log_dir": {"type": "string", "default": "logs/"},
        "dmarket_api_key": {"type": "string"},
        "dmarket_secret_key": {"type": "string"},
        "telegram_bot_token": {"type": "string"},
    },
    "required": ["api_url"]
}


class ConfigManager:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        # Load .env
        load_dotenv()

        # Defaults
        self._config = {
            "api_url": "https://api.dmarket.com",
            "log_dir": "logs/",
        }

        # Load openclaw.json if exists
        config_path = Path("openclaw.json")
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    json_config = json.load(f)
                    self._config.update(json_config)
            except Exception as e:
                logger.error(f"Failed to load openclaw.json: {e}")

        # Override with env vars (mapped keys)
        if os.getenv("DMARKET_API_URL"):
            self._config["api_url"] = os.getenv("DMARKET_API_URL")
        if os.getenv("LOG_DIR"):
            self._config["log_dir"] = os.getenv("LOG_DIR")

        # Validate
        try:
            jsonschema.validate(instance=self._config, schema=CONFIG_SCHEMA)
        except jsonschema.ValidationError as e:
            logger.error(f"Config validation error: {e}")
            raise

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        if cls._instance is None:
            cls()
        return cls._instance._config.get(key, default)

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        if cls._instance is None:
            cls()
        return cls._instance._config
