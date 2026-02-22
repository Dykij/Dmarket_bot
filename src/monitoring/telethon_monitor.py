"""Telethon Monitor Module.

Provides Telegram monitoring capabilities via Telethon:
- Channel/chat monitoring for trade signals
- Automatic notification forwarding
- Pattern detection for arbitrage mentions
- Background daemon support

Based on SkillsMP `telegram-telethon` skill best practices.

IMPORTANT: Requires separate Telegram API credentials (api_id, api_hash)
Get them from https://my.telegram.org

Usage:
    ```python
    from src.monitoring.telethon_monitor import TelethonMonitor

    monitor = TelethonMonitor(
        api_id=12345, api_hash="your_hash", session_name="dmarket_monitor"
    )

    # Add channels to monitor
    monitor.add_channel("@dmarket_deals", keywords=["арбитраж", "скидка"])

    # Start monitoring
    await monitor.start()
    ```

Created: January 23, 2026
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# Check if telethon is avAlgolable
try:
    from telethon import TelegramClient, events

    # Types imported for type hints when telethon is avAlgolable
    from telethon.tl.types import Channel, Chat, Message, User  # noqa: F401

    TELETHON_AVAlgoLABLE = True
except ImportError:
    TELETHON_AVAlgoLABLE = False
    TelegramClient = None  # type: ignore
    events = None  # type: ignore


class SignalType(StrEnum):
    """Type of detected signal."""

    ARBITRAGE = "arbitrage"
    PRICE_DROP = "price_drop"
    NEW_LISTING = "new_listing"
    TRADE_SIGNAL = "trade_signal"
    NEWS = "news"
    OTHER = "other"


@dataclass
class DetectedSignal:
    """Detected trading signal from message."""

    signal_type: SignalType
    message_text: str
    source_channel: str
    source_username: str | None
    timestamp: datetime
    confidence: float = 0.0

    # Extracted data
    item_name: str | None = None
    price: float | None = None
    discount_percent: float | None = None
    url: str | None = None

    # Metadata
    message_id: int = 0
    keywords_matched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal_type": self.signal_type.value,
            "source_channel": self.source_channel,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "item_name": self.item_name,
            "price": self.price,
            "discount_percent": self.discount_percent,
            "url": self.url,
            "keywords_matched": self.keywords_matched,
            "message_preview": self.message_text[:200] if self.message_text else None,
        }


@dataclass
class MonitoredChannel:
    """Configuration for monitored channel."""

    channel_id: str  # Username or ID
    keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    signal_types: list[SignalType] = field(default_factory=list)
    is_active: bool = True
    last_message_id: int = 0
    messages_processed: int = 0


class SignalPatterns:
    """Regex patterns for signal detection."""

    PRICE_PATTERN = re.compile(
        r"(?:(?:\$|USD|€|EUR|₽|руб\.?)\s*)(\d+[.,]?\d*)|(\d+[.,]?\d*)\s*(?:\$|USD|€|EUR|₽|руб\.?)",
        re.IGNORECASE,
    )

    DISCOUNT_PATTERN = re.compile(
        r"(-?\d+[.,]?\d*)\s*%|скидк[аи]\s*(\d+)|discount\s*(\d+)", re.IGNORECASE
    )

    URL_PATTERN = re.compile(
        r"https?://(?:www\.)?(?:dmarket\.com|waxpeer\.com|buff\.163\.com|skinport\.com)[^\s]*",
        re.IGNORECASE,
    )

    CSGO_ITEM_PATTERN = re.compile(
        r"([A-Z][a-zA-Z0-9-]+\s*\|\s*[A-Za-z0-9\s\-']+(?:\s*\([A-Za-z\s]+\))?)",
        re.IGNORECASE,
    )


class MessageAnalyzer:
    """Analyzes messages for trading signals."""

    SIGNAL_KEYWORDS: dict[SignalType, list[str]] = {
        SignalType.ARBITRAGE: [
            "арбитраж",
            "arbitrage",
            "профит",
            "profit",
            "маржа",
            "margin",
            "перепродажа",
            "flip",
            "quick flip",
            "выгодно",
        ],
        SignalType.PRICE_DROP: [
            "скидка",
            "discount",
            "снижение цены",
            "price drop",
            "дешево",
            "cheap",
            "распродажа",
            "sale",
            "ниже рынка",
            "below market",
        ],
        SignalType.NEW_LISTING: [
            "новый лот",
            "new listing",
            "только выставлен",
            "just listed",
            "fresh",
            "свежий",
            "just dropped",
        ],
        SignalType.TRADE_SIGNAL: [
            "покупать",
            "buy",
            "продавать",
            "sell",
            "сигнал",
            "signal",
            "рекомендация",
            "recommendation",
            "alert",
        ],
        SignalType.NEWS: [
            "новость",
            "news",
            "обновление",
            "update",
            "анонс",
            "announcement",
        ],
    }

    @classmethod
    def analyze_message(
        cls,
        text: str,
        keywords_filter: list[str] | None = None,
    ) -> DetectedSignal | None:
        """Analyze message for trading signals."""
        if not text or len(text) < 10:
            return None

        text_lower = text.lower()
        signal_type = SignalType.OTHER
        matched_keywords: list[str] = []
        confidence = 0.0

        for sig_type, keywords in cls.SIGNAL_KEYWORDS.items():
            matches = [kw for kw in keywords if kw.lower() in text_lower]
            if matches:
                if len(matches) > len(matched_keywords):
                    signal_type = sig_type
                    matched_keywords = matches
                    confidence = min(1.0, len(matches) * 0.3)

        if keywords_filter:
            custom_matches = [kw for kw in keywords_filter if kw.lower() in text_lower]
            if custom_matches:
                matched_keywords.extend(custom_matches)
                confidence = min(1.0, confidence + len(custom_matches) * 0.2)

        if not matched_keywords:
            return None

        price = cls._extract_price(text)
        discount = cls._extract_discount(text)
        url = cls._extract_url(text)
        item_name = cls._extract_item_name(text)

        if price:
            confidence = min(1.0, confidence + 0.1)
        if discount:
            confidence = min(1.0, confidence + 0.1)
        if item_name:
            confidence = min(1.0, confidence + 0.15)

        return DetectedSignal(
            signal_type=signal_type,
            message_text=text,
            source_channel="",
            source_username=None,
            timestamp=datetime.now(UTC),
            confidence=confidence,
            item_name=item_name,
            price=price,
            discount_percent=discount,
            url=url,
            keywords_matched=matched_keywords,
        )

    @classmethod
    def _extract_price(cls, text: str) -> float | None:
        """Extract price from text."""
        match = SignalPatterns.PRICE_PATTERN.search(text)
        if match:
            price_str = match.group(1) or match.group(2)
            if price_str:
                try:
                    return float(price_str.replace(",", "."))
                except ValueError:
                    pass
        return None

    @classmethod
    def _extract_discount(cls, text: str) -> float | None:
        """Extract discount percentage."""
        match = SignalPatterns.DISCOUNT_PATTERN.search(text)
        if match:
            discount_str = match.group(1) or match.group(2) or match.group(3)
            if discount_str:
                try:
                    return abs(float(discount_str.replace(",", ".")))
                except ValueError:
                    pass
        return None

    @classmethod
    def _extract_url(cls, text: str) -> str | None:
        """Extract marketplace URL."""
        match = SignalPatterns.URL_PATTERN.search(text)
        return match.group(0) if match else None

    @classmethod
    def _extract_item_name(cls, text: str) -> str | None:
        """Extract item name."""
        match = SignalPatterns.CSGO_ITEM_PATTERN.search(text)
        return match.group(1).strip() if match else None


class TelethonMonitor:
    """Telegram channel monitor using Telethon."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str = "dmarket_monitor",
        signal_callback: Callable[[DetectedSignal], Awaitable[None]] | None = None,
    ) -> None:
        """Initialize monitor."""
        if not TELETHON_AVAlgoLABLE:
            raise ImportError(
                "Telethon is not installed. Install with: pip install telethon"
            )

        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.signal_callback = signal_callback

        self._client: TelegramClient | None = None
        self._channels: dict[str, MonitoredChannel] = {}
        self._is_running = False
        self._signals_detected: list[DetectedSignal] = []
        self._start_time: datetime | None = None

    def add_channel(
        self,
        channel_id: str,
        keywords: list[str] | None = None,
        negative_keywords: list[str] | None = None,
        signal_types: list[SignalType] | None = None,
    ) -> MonitoredChannel:
        """Add channel to monitor."""
        channel = MonitoredChannel(
            channel_id=channel_id,
            keywords=keywords or [],
            negative_keywords=negative_keywords or [],
            signal_types=signal_types or list(SignalType),
        )
        self._channels[channel_id] = channel
        logger.info("channel_added", channel=channel_id, keywords=keywords)
        return channel

    def remove_channel(self, channel_id: str) -> bool:
        """Remove channel from monitoring."""
        if channel_id in self._channels:
            del self._channels[channel_id]
            return True
        return False

    async def start(self) -> None:
        """Start monitoring."""
        if self._is_running:
            return

        self._client = TelegramClient(
            self.session_name,
            self.api_id,
            self.api_hash,
        )

        await self._client.start()
        self._is_running = True
        self._start_time = datetime.now(UTC)

        @self._client.on(events.NewMessage())
        async def handle_new_message(event: Any) -> None:
            await self._process_message(event)

        logger.info("telethon_monitor_started", channels=list(self._channels.keys()))
        await self._client.run_until_disconnected()

    async def stop(self) -> None:
        """Stop monitoring."""
        self._is_running = False
        if self._client:
            await self._client.disconnect()
            self._client = None
        logger.info("telethon_monitor_stopped")

    async def _process_message(self, event: Any) -> None:
        """Process incoming message."""
        try:
            message = event.message
            if not message or not message.text:
                return

            chat = await event.get_chat()
            chat_id = self._get_chat_identifier(chat)

            channel_config = None
            for config in self._channels.values():
                if config.channel_id in (chat_id, str(chat.id)):
                    channel_config = config
                    break

            if not channel_config or not channel_config.is_active:
                return

            text_lower = message.text.lower()
            if any(nk.lower() in text_lower for nk in channel_config.negative_keywords):
                return

            signal = MessageAnalyzer.analyze_message(
                message.text,
                keywords_filter=channel_config.keywords,
            )

            if signal:
                signal.source_channel = chat_id
                signal.source_username = self._get_sender_username(event)
                signal.message_id = message.id

                if (
                    channel_config.signal_types
                    and signal.signal_type not in channel_config.signal_types
                ):
                    return

                self._signals_detected.append(signal)
                channel_config.messages_processed += 1
                channel_config.last_message_id = message.id

                logger.info(
                    "signal_detected",
                    signal_type=signal.signal_type.value,
                    channel=chat_id,
                    confidence=signal.confidence,
                )

                if self.signal_callback:
                    await self.signal_callback(signal)

        except Exception as e:
            logger.exception(f"Error processing message: {e}")

    def _get_chat_identifier(self, chat: Any) -> str:
        """Get chat identifier."""
        if hasattr(chat, "username") and chat.username:
            return f"@{chat.username}"
        return str(chat.id)

    def _get_sender_username(self, event: Any) -> str | None:
        """Get sender username."""
        try:
            sender = event.sender
            if sender and hasattr(sender, "username"):
                return sender.username
        except Exception:
            pass
        return None

    def get_stats(self) -> dict[str, Any]:
        """Get monitoring statistics."""
        uptime = None
        if self._start_time:
            uptime = str(datetime.now(UTC) - self._start_time)

        return {
            "is_running": self._is_running,
            "uptime": uptime,
            "channels_count": len(self._channels),
            "channels": [
                {
                    "id": ch.channel_id,
                    "is_active": ch.is_active,
                    "messages_processed": ch.messages_processed,
                    "keywords": ch.keywords,
                }
                for ch in self._channels.values()
            ],
            "signals_detected": len(self._signals_detected),
            "recent_signals": [s.to_dict() for s in self._signals_detected[-10:]],
        }

    def get_recent_signals(
        self,
        limit: int = 50,
        signal_type: SignalType | None = None,
        min_confidence: float = 0.0,
    ) -> list[DetectedSignal]:
        """Get recent detected signals."""
        signals = self._signals_detected

        if signal_type:
            signals = [s for s in signals if s.signal_type == signal_type]

        if min_confidence > 0:
            signals = [s for s in signals if s.confidence >= min_confidence]

        return signals[-limit:]


class MockTelethonMonitor:
    """Mock monitor for testing without Telethon."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize mock monitor."""
        self._channels: dict[str, MonitoredChannel] = {}
        self._signals: list[DetectedSignal] = []
        self._is_running = False

    def add_channel(
        self,
        channel_id: str,
        keywords: list[str] | None = None,
        **kwargs: Any,
    ) -> MonitoredChannel:
        """Add channel."""
        channel = MonitoredChannel(channel_id=channel_id, keywords=keywords or [])
        self._channels[channel_id] = channel
        return channel

    def remove_channel(self, channel_id: str) -> bool:
        """Remove channel."""
        if channel_id in self._channels:
            del self._channels[channel_id]
            return True
        return False

    async def start(self) -> None:
        """Start (no-op)."""
        self._is_running = True
        logger.info("mock_monitor_started")

    async def stop(self) -> None:
        """Stop (no-op)."""
        self._is_running = False

    def simulate_message(
        self, text: str, channel: str = "test"
    ) -> DetectedSignal | None:
        """Simulate receiving a message."""
        signal = MessageAnalyzer.analyze_message(text)
        if signal:
            signal.source_channel = channel
            self._signals.append(signal)
        return signal

    def get_stats(self) -> dict[str, Any]:
        """Get stats."""
        return {
            "is_running": self._is_running,
            "is_mock": True,
            "channels_count": len(self._channels),
            "signals_detected": len(self._signals),
        }

    def get_recent_signals(
        self, limit: int = 50, **kwargs: Any
    ) -> list[DetectedSignal]:
        """Get recent signals."""
        return self._signals[-limit:]


def create_telethon_monitor(
    api_id: int | None = None,
    api_hash: str | None = None,
    session_name: str = "dmarket_monitor",
    signal_callback: Callable[[DetectedSignal], Awaitable[None]] | None = None,
    use_mock: bool = False,
) -> TelethonMonitor | MockTelethonMonitor:
    """Create Telethon monitor instance."""
    if use_mock or not TELETHON_AVAlgoLABLE or not api_id or not api_hash:
        logger.warning(
            "Using MockTelethonMonitor",
            reason="mock_requested" if use_mock else "telethon_unavAlgolable",
        )
        return MockTelethonMonitor()

    return TelethonMonitor(
        api_id=api_id,
        api_hash=api_hash,
        session_name=session_name,
        signal_callback=signal_callback,
    )
