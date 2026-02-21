"""Constants for smart notification system."""

from pathlib import Path
from typing import Any

# Notification types
NOTIFICATION_TYPES: dict[str, str] = {
    "market_opportunity": "Market Opportunity",
    "price_alert": "Price Alert",
    "trend_alert": "Trend Alert",
    "pattern_alert": "Pattern Alert",
    "watchlist_update": "Watchlist Update",
    "arbitrage_opportunity": "Arbitrage Opportunity",
    "system_alert": "System Alert",
}

# Notification storage file
DATA_DIR = Path("data") / "notifications"
SMART_ALERTS_FILE = DATA_DIR / "smart_alerts.json"

# Alert cooldown periods (seconds)
DEFAULT_COOLDOWN: dict[str, int] = {
    "market_opportunity": 3600,  # 1 hour
    "price_alert": 1800,  # 30 minutes
    "trend_alert": 7200,  # 2 hours
    "pattern_alert": 3600,  # 1 hour
    "watchlist_update": 14400,  # 4 hours
    "arbitrage_opportunity": 900,  # 15 minutes
    "system_alert": 300,  # 5 minutes
}

# Default user preferences template
DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    "enabled": True,
    "channels": ["telegram"],
    "frequency": "normal",  # low, normal, high
    "quiet_hours": {"start": 23, "end": 8},
    "min_opportunity_score": 60,
    "notifications": {
        "market_opportunity": True,
        "price_alert": True,
        "trend_alert": True,
        "pattern_alert": True,
        "watchlist_update": True,
        "arbitrage_opportunity": True,
        "system_alert": True,
    },
    "games": {
        "csgo": True,
        "dota2": True,
        "tf2": True,
        "rust": True,
    },
    "preferences": {
        "min_price": 1.0,
        "max_price": 1000.0,
        "min_profit": 5.0,
        "notification_style": "detAlgoled",
    },
    "last_notification": {},
}

# Initialize data directory
if not DATA_DIR.exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
