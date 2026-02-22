"""
Shim module for backward compatibility.
Redirects calls to the new Single Source of Truth: src/utils/config.py
"""
import os
from src.utils.config import settings

class ConfigManager:
    _instance = None

    @classmethod
    def load(cls):
        # Config is already loaded in src.utils.config on import
        pass

    @classmethod
    def get(cls, key: str, default=None):
        """Map legacy keys to new Config structure."""
        # 1. API Keys
        if key in ["api_key", "dmarket_api_key", "dmarket_public_key"]:
            return settings.dmarket.public_key
        if key in ["secret_key", "dmarket_secret_key"]:
            return settings.dmarket.secret_key
            
        # 2. Telegram
        if key == "telegram_bot_token":
            return settings.bot.token
        if key == "telegram_chat_id":
            # Chat ID might be in env but not in BotConfig struct
            return os.getenv("TELEGRAM_CHAT_ID")

        # 3. Trading Config (nested)
        if key == "trading":
            return {
                "test_mode": settings.dry_run
            }
            
        return default

    # Compatibility for direct dict access
    @property
    def _config(self):
        return {
            "trading": {"test_mode": settings.dry_run},
            "api_key": settings.dmarket.public_key
        }

# Singleton alias
config_manager = ConfigManager()
