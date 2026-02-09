"""AI-Powered Security Threat Detection.

Модуль обнаружения угроз безопасности с использованием машинного обучения.
Анализирует входящие запросы, обнаруживает аномалии и защищает от атак.

SKILL: AI Threat Detection
Category: Testing & Security, Data & AI
Status: Phase 3 Implementation

Документация: src/utils/SKILL_THREAT_DETECTION.md
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ThreatAnalysis:
    """Result of threat analysis.

    Attributes:
        is_threat: Whether request is classified as threat
        threat_level: Severity level (low, medium, high, critical)
        anomaly_score: Anomaly score (0.0-1.0, higher = more anomalous)
        threat_types: List of detected threat types
        confidence: Detection confidence (0.0-1.0)
        should_block: Whether to block the request
    """

    is_threat: bool
    threat_level: str  # "low", "medium", "high", "critical"
    anomaly_score: float  # 0.0-1.0
    threat_types: list[str]
    confidence: float  # 0.0-1.0
    should_block: bool


class AIThreatDetector:
    """AI-powered security threat detection system.

    Detects and analyzes security threats including:
    - SQL injection attempts
    - XSS attacks
    - Rate limit abuse
    - Anomalous behavior patterns
    - Suspicious payloads

    Attributes:
        anomaly_threshold: Threshold for anomaly detection (0.0-1.0)
        rate_limit_window: Time window for rate limiting (seconds)
        max_requests_per_window: Maximum requests allowed in window
    """

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(?i)(union\s+select)",
        r"(?i)(or\s+1\s*=\s*1)",
        r"(?i)(drop\s+table)",
        r"(?i)(exec\s*\()",
        r"(?i)(;.*--)",
        r"(?i)(\bor\b\s+\d+\s*=\s*\d+)",
    ]

    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript:",
        r"onerror\s*=",
        r"onclick\s*=",
        r"<iframe",
    ]

    def __init__(
        self,
        anomaly_threshold: float = 0.7,
        rate_limit_window: int = 60,
        max_requests_per_window: int = 100,
    ):
        """Initialize AI Threat Detector.

        Args:
            anomaly_threshold: Score above which to flag as anomalous (0.0-1.0)
            rate_limit_window: Time window for rate limiting (seconds)
            max_requests_per_window: Max requests allowed in window
        """
        self.anomaly_threshold = anomaly_threshold
        self.rate_limit_window = rate_limit_window
        self.max_requests_per_window = max_requests_per_window

        # Track request history per user/IP
        self._request_history: dict[str, list[datetime]] = {}

        logger.info(
            "ai_threat_detector_initialized",
            anomaly_threshold=anomaly_threshold,
            rate_limit_window=rate_limit_window,
        )

    async def analyze_request(
        self,
        request_data: dict[str, Any],
        user_id: str | None = None,
        source_ip: str | None = None,
    ) -> ThreatAnalysis:
        """Analyze request for security threats.

        Args:
            request_data: Request data (headers, body, params)
            user_id: User identifier (optional)
            source_ip: Source IP address (optional)

        Returns:
            ThreatAnalysis with detection results

        Example:
            >>> detector = AIThreatDetector()
            >>> analysis = await detector.analyze_request(
            ...     request_data={"text": "Hello world"},
            ...     user_id="user_123",
            ... )
            >>> if analysis.is_threat:
            ...     print(f"Threat detected: {analysis.threat_types}")
        """
        identifier = user_id or source_ip or "unknown"

        logger.debug(
            "analyzing_request",
            user_id=user_id,
            source_ip=source_ip,
        )

        # Collect detected threats
        threats: list[str] = []
        anomaly_score = 0.0

        # Check for SQL injection
        if self._check_sql_injection(request_data):
            threats.append("sql_injection")
            anomaly_score = max(anomaly_score, 0.95)

        # Check for XSS
        if self._check_xss(request_data):
            threats.append("xss")
            anomaly_score = max(anomaly_score, 0.90)

        # Check for rate limit abuse
        if self._check_rate_limit_abuse(identifier):
            threats.append("rate_limit_abuse")
            anomaly_score = max(anomaly_score, 0.70)

        # Check for suspicious patterns
        if self._check_suspicious_patterns(request_data):
            threats.append("suspicious_pattern")
            anomaly_score = max(anomaly_score, 0.60)

        # Determine threat level and blocking
        is_threat = len(threats) > 0 and anomaly_score >= self.anomaly_threshold
        threat_level = self._calculate_threat_level(anomaly_score)
        should_block = anomaly_score >= 0.85  # High threshold for blocking

        # Calculate confidence (simplified)
        confidence = min(1.0, anomaly_score + 0.1)

        logger.info(
            "threat_analysis_complete",
            is_threat=is_threat,
            threat_level=threat_level,
            anomaly_score=anomaly_score,
            threat_count=len(threats),
        )

        return ThreatAnalysis(
            is_threat=is_threat,
            threat_level=threat_level,
            anomaly_score=anomaly_score,
            threat_types=threats,
            confidence=confidence,
            should_block=should_block,
        )

    def _check_sql_injection(self, request_data: dict[str, Any]) -> bool:
        """Check for SQL injection patterns.

        Args:
            request_data: Request data to analyze

        Returns:
            True if SQL injection detected
        """
        # Check all string values in request
        for value in self._extract_strings(request_data):
            for pattern in self.SQL_INJECTION_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE):
                    logger.warning(
                        "sql_injection_detected",
                        pattern=pattern,
                        value=value[:100],  # Log first 100 chars
                    )
                    return True

        return False

    def _check_xss(self, request_data: dict[str, Any]) -> bool:
        """Check for XSS attack patterns.

        Args:
            request_data: Request data to analyze

        Returns:
            True if XSS detected
        """
        for value in self._extract_strings(request_data):
            for pattern in self.XSS_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE):
                    logger.warning(
                        "xss_detected",
                        pattern=pattern,
                        value=value[:100],
                    )
                    return True

        return False

    def _check_rate_limit_abuse(self, identifier: str) -> bool:
        """Check for rate limit abuse.

        Args:
            identifier: User ID or IP address

        Returns:
            True if rate limit exceeded
        """
        now = datetime.now()

        # Initialize history if new identifier
        if identifier not in self._request_history:
            self._request_history[identifier] = []

        # Get request history
        history = self._request_history[identifier]

        # Remove old requests outside window
        cutoff = now - timedelta(seconds=self.rate_limit_window)
        history = [ts for ts in history if ts > cutoff]
        self._request_history[identifier] = history

        # Add current request
        history.append(now)

        # Check if exceeded limit
        if len(history) > self.max_requests_per_window:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                requests=len(history),
                limit=self.max_requests_per_window,
            )
            return True

        return False

    def _check_suspicious_patterns(self, request_data: dict[str, Any]) -> bool:
        """Check for other suspicious patterns.

        Args:
            request_data: Request data to analyze

        Returns:
            True if suspicious patterns found
        """
        for value in self._extract_strings(request_data):
            # Check for excessive length (possible buffer overflow)
            if len(value) > 10000:
                logger.warning("suspicious_length", length=len(value))
                return True

            # Check for encoded payloads
            if "%" in value and value.count("%") > 20:
                logger.warning("suspicious_encoding", percent_count=value.count("%"))
                return True

            # Check for unusual characters
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
                logger.warning("suspicious_characters")
                return True

        return False

    def _extract_strings(self, data: Any) -> list[str]:
        """Recursively extract all string values from data structure.

        Args:
            data: Data to extract strings from

        Returns:
            List of all string values
        """
        strings: list[str] = []

        if isinstance(data, str):
            strings.append(data)
        elif isinstance(data, dict):
            for value in data.values():
                strings.extend(self._extract_strings(value))
        elif isinstance(data, (list, tuple)):
            for item in data:
                strings.extend(self._extract_strings(item))

        return strings

    def _calculate_threat_level(self, anomaly_score: float) -> str:
        """Calculate threat level from anomaly score.

        Args:
            anomaly_score: Anomaly score (0.0-1.0)

        Returns:
            Threat level string
        """
        if anomaly_score >= 0.90:
            return "critical"
        if anomaly_score >= 0.75:
            return "high"
        if anomaly_score >= 0.50:
            return "medium"
        return "low"

    def clear_history(self, identifier: str | None = None) -> None:
        """Clear request history.

        Args:
            identifier: Specific identifier to clear, or None to clear all
        """
        if identifier:
            if identifier in self._request_history:
                del self._request_history[identifier]
                logger.info("history_cleared", identifier=identifier)
        else:
            self._request_history.clear()
            logger.info("all_history_cleared")


# Factory function
def create_ai_threat_detector(
    anomaly_threshold: float = 0.7,
    rate_limit_window: int = 60,
    max_requests_per_window: int = 100,
) -> AIThreatDetector:
    """Create AI Threat Detector with configuration.

    Args:
        anomaly_threshold: Score above which to flag as anomalous
        rate_limit_window: Time window for rate limiting (seconds)
        max_requests_per_window: Max requests allowed in window

    Returns:
        Initialized AIThreatDetector

    Example:
        >>> detector = create_ai_threat_detector(anomaly_threshold=0.8)
        >>> analysis = await detector.analyze_request(request_data)
    """
    return AIThreatDetector(
        anomaly_threshold=anomaly_threshold,
        rate_limit_window=rate_limit_window,
        max_requests_per_window=max_requests_per_window,
    )
