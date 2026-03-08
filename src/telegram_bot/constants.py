"""Константы и типы для системы уведомлений.

Этот модуль содержит все константы, используемые в системе уведомлений,
включая типы уведомлений и настSwarmки кэширования.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

# Типы уведомлений
NOTIFICATION_TYPES: Final[dict[str, str]] = {
    "price_drop": "📉 Падение цены",
    "price_rise": "📈 Рост цены",
    "volume_increase": "📊 Увеличение объема торгов",
    "good_deal": "💰 Выгодная сделка",
    "arbitrage": "🔄 Арбитраж",
    "trend_change": "📊 Изменение тренда",
    "buy_intent": "🛒 Намерение купить",
    "buy_success": "✅ Успешная покупка",
    "buy_failed": "❌ Ошибка покупки",
    "sell_success": "✅ Успешная продажа",
    "sell_failed": "❌ Ошибка продажи",
    "critical_shutdown": "🛑 Критическая остановка",
}

# TTL кэша цен в секундах
_PRICE_CACHE_TTL: Final[int] = 300  # 5 минут

# НастSwarmки по умолчанию для пользователей
DEFAULT_USER_SETTINGS: Final[dict[str, object]] = {
    "enabled": True,
    "language": "ru",
    "min_interval": 300,  # 5 минут между уведомлениями
    "quiet_hours": {"start": 23, "end": 7},  # Тихие часы
    "max_alerts_per_day": 50,
}

# Приоритеты уведомлений
NOTIFICATION_PRIORITIES: Final[dict[str, int]] = {
    "critical_shutdown": 100,
    "buy_success": 90,
    "buy_failed": 90,
    "sell_success": 85,
    "sell_failed": 85,
    "buy_intent": 80,
    "arbitrage": 70,
    "good_deal": 60,
    "price_drop": 50,
    "price_rise": 50,
    "volume_increase": 40,
    "trend_change": 30,
}

# Path constants
DATA_DIR: Final[Path] = Path("data")
ENV_PATH: Final[Path] = Path(".env")
USER_PROFILES_FILE: Final[Path] = DATA_DIR / "user_profiles.json"

# Pagination
DEFAULT_PAGE_SIZE: Final[int] = 10
MAX_ITEMS_PER_PAGE: Final[int] = 50
MAX_MESSAGE_LENGTH: Final[int] = 4096

# Languages
LANGUAGES: Final[dict[str, str]] = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "es": "🇪🇸 Español",
    "de": "🇩🇪 Deutsch",
}

# Arbitrage modes
ARBITRAGE_MODES: Final[dict[str, str]] = {
    "boost": "🚀 Разгон баланса ($0.5-$3)",
    "standard": "📊 Стандартный ($3-$10)",
    "medium": "💎 Средний ($10-$30)",
    "advanced": "🏆 Продвинутый ($30-$100)",
    "pro": "👑 Профессионал ($100+)",
}

# Price alerts storage keys
PRICE_ALERT_STORAGE_KEY: Final[str] = "price_alerts"
PRICE_ALERT_HISTORY_KEY: Final[str] = "price_alert_history"

__all__ = [
    "ARBITRAGE_MODES",
    "DATA_DIR",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_USER_SETTINGS",
    "ENV_PATH",
    "LANGUAGES",
    "MAX_ITEMS_PER_PAGE",
    "MAX_MESSAGE_LENGTH",
    "NOTIFICATION_PRIORITIES",
    "NOTIFICATION_TYPES",
    "PRICE_ALERT_HISTORY_KEY",
    "PRICE_ALERT_STORAGE_KEY",
    "USER_PROFILES_FILE",
    "_PRICE_CACHE_TTL",
]
