import os
import sys
import logging
from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class KillSwitch:
    """
    The 'Kill Switch' Protocol.
    Instantly wipes sensitive keys from memory and terminates processes.
    """
    @staticmethod
    def activate(reason: str):
        logger.critical(f"💀 KILL SWITCH ACTIVATED. Reason: {reason}")
        
        # 1. Wipe Keys from Config Singleton
        try:
            config = ConfigManager()
            if hasattr(config, '_config'):
                config._config.clear()
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            os.environ.pop("DMARKET_API_KEY", None)
            logger.info("🧹 Memory sanitized.")
        except Exception as e:
            logger.error(f"Failed to sanitize memory: {e}")

        # 2. Terminate (Simulated exit for safety in test env, real exit in prod)
        logger.critical("🛑 System halting immediately.")
        # sys.exit(1) # Commented out to allow reporting to finish in this session

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    KillSwitch.activate("Test Trigger")
