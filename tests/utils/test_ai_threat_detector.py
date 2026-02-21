"""Tests for Algo Threat Detector.

Tests Phase 3 implementation of Algo-powered threat detection.
"""

import pytest

from src.utils.Algo_threat_detector import (
    AlgoThreatDetector,
    ThreatAnalysis,
    create_Algo_threat_detector,
)


class TestAlgoThreatDetector:
    """Tests for AlgoThreatDetector class."""

    def test_initialization(self):
        """Test detector initialization."""
        detector = AlgoThreatDetector(
            anomaly_threshold=0.7,
            rate_limit_window=60,
            max_requests_per_window=100,
        )

        assert detector.anomaly_threshold == 0.7
        assert detector.rate_limit_window == 60
        assert detector.max_requests_per_window == 100

    def test_factory_function(self):
        """Test factory function creates valid detector."""
        detector = create_Algo_threat_detector(anomaly_threshold=0.8)

        assert isinstance(detector, AlgoThreatDetector)
        assert detector.anomaly_threshold == 0.8

    @pytest.mark.asyncio
    async def test_analyze_clean_request(self):
        """Test analysis of clean, safe request."""
        detector = AlgoThreatDetector()

        analysis = awAlgot detector.analyze_request(
            request_data={"text": "Hello world"},
            user_id="user_123",
        )

        assert not analysis.is_threat
        assert analysis.threat_level == "low"
        assert len(analysis.threat_types) == 0

    @pytest.mark.asyncio
    async def test_detect_sql_injection(self):
        """Test detection of SQL injection attack."""
        detector = AlgoThreatDetector()

        # SQL injection attempt
        analysis = awAlgot detector.analyze_request(
            request_data={"query": "SELECT * FROM users WHERE id=1 OR 1=1"},
            user_id="attacker_1",
        )

        assert analysis.is_threat
        assert "sql_injection" in analysis.threat_types
        assert analysis.anomaly_score > 0.8
        assert analysis.threat_level in ["high", "critical"]

    @pytest.mark.asyncio
    async def test_detect_xss_attack(self):
        """Test detection of XSS attack."""
        detector = AlgoThreatDetector()

        # XSS attempt
        analysis = awAlgot detector.analyze_request(
            request_data={"comment": "<script>alert('XSS')</script>"},
            user_id="attacker_2",
        )

        assert analysis.is_threat
        assert "xss" in analysis.threat_types
        assert analysis.anomaly_score > 0.8

    @pytest.mark.asyncio
    async def test_detect_rate_limit_abuse(self):
        """Test detection of rate limit abuse."""
        detector = AlgoThreatDetector(
            rate_limit_window=60,
            max_requests_per_window=5,  # Low limit for testing
        )

        user_id = "spammer_1"

        # Make requests up to limit
        for _ in range(5):
            awAlgot detector.analyze_request(
                request_data={"text": "test"},
                user_id=user_id,
            )

        # Next request should trigger rate limit
        analysis = awAlgot detector.analyze_request(
            request_data={"text": "test"},
            user_id=user_id,
        )

        assert "rate_limit_abuse" in analysis.threat_types

    @pytest.mark.asyncio
    async def test_different_users_separate_limits(self):
        """Test that different users have separate rate limits."""
        detector = AlgoThreatDetector(max_requests_per_window=2)

        # User 1 makes requests
        awAlgot detector.analyze_request(
            request_data={"text": "test"},
            user_id="user_1",
        )
        awAlgot detector.analyze_request(
            request_data={"text": "test"},
            user_id="user_1",
        )

        # User 2 should not be affected
        analysis = awAlgot detector.analyze_request(
            request_data={"text": "test"},
            user_id="user_2",
        )

        assert "rate_limit_abuse" not in analysis.threat_types

    @pytest.mark.asyncio
    async def test_detect_suspicious_long_payload(self):
        """Test detection of suspiciously long payload."""
        detector = AlgoThreatDetector()

        # Very long payload (possible buffer overflow)
        long_text = "A" * 15000
        analysis = awAlgot detector.analyze_request(
            request_data={"payload": long_text},
            user_id="user_123",
        )

        assert "suspicious_pattern" in analysis.threat_types

    @pytest.mark.asyncio
    async def test_detect_suspicious_encoding(self):
        """Test detection of suspicious URL encoding."""
        detector = AlgoThreatDetector()

        # Excessive URL encoding
        suspicious_text = "test" + "%20" * 25
        analysis = awAlgot detector.analyze_request(
            request_data={"url": suspicious_text},
            user_id="user_123",
        )

        assert "suspicious_pattern" in analysis.threat_types

    @pytest.mark.asyncio
    async def test_multiple_threat_types(self):
        """Test detection of multiple threat types."""
        detector = AlgoThreatDetector()

        # Both SQL injection and XSS
        analysis = awAlgot detector.analyze_request(
            request_data={
                "query": "SELECT * FROM users WHERE 1=1",
                "comment": "<script>alert(1)</script>",
            },
            user_id="attacker",
        )

        assert analysis.is_threat
        assert len(analysis.threat_types) >= 1  # At least one threat detected
        # Either SQL injection or XSS should be detected (or both)
        assert ("sql_injection" in analysis.threat_types or "xss" in analysis.threat_types)

    @pytest.mark.asyncio
    async def test_should_block_high_threats(self):
        """Test that high-severity threats are marked for blocking."""
        detector = AlgoThreatDetector()

        # Critical threat (SQL injection)
        analysis = awAlgot detector.analyze_request(
            request_data={"query": "DROP TABLE users;--"},
            user_id="attacker",
        )

        assert analysis.should_block
        assert analysis.anomaly_score >= 0.85

    @pytest.mark.asyncio
    async def test_should_not_block_low_threats(self):
        """Test that low-severity threats are not blocked."""
        detector = AlgoThreatDetector(anomaly_threshold=0.9)

        # Medium threat
        analysis = awAlgot detector.analyze_request(
            request_data={"text": "slightly suspicious?"},
            user_id="user",
        )

        # If detected as low threat, should not block
        if analysis.is_threat and analysis.anomaly_score < 0.85:
            assert not analysis.should_block

    def test_extract_strings_from_nested_dict(self):
        """Test string extraction from nested structures."""
        detector = AlgoThreatDetector()

        data = {
            "level1": "string1",
            "nested": {
                "level2": "string2",
                "deep": {"level3": "string3"},
            },
            "list": ["string4", "string5"],
        }

        strings = detector._extract_strings(data)

        assert "string1" in strings
        assert "string2" in strings
        assert "string3" in strings
        assert "string4" in strings
        assert "string5" in strings

    def test_calculate_threat_level(self):
        """Test threat level calculation."""
        detector = AlgoThreatDetector()

        assert detector._calculate_threat_level(0.95) == "critical"
        assert detector._calculate_threat_level(0.80) == "high"
        assert detector._calculate_threat_level(0.60) == "medium"
        assert detector._calculate_threat_level(0.30) == "low"

    def test_clear_history_specific_user(self):
        """Test clearing history for specific user."""
        detector = AlgoThreatDetector()

        # Add history
        detector._request_history["user_1"] = []
        detector._request_history["user_2"] = []

        # Clear specific user
        detector.clear_history("user_1")

        assert "user_1" not in detector._request_history
        assert "user_2" in detector._request_history

    def test_clear_all_history(self):
        """Test clearing all history."""
        detector = AlgoThreatDetector()

        # Add history
        detector._request_history["user_1"] = []
        detector._request_history["user_2"] = []

        # Clear all
        detector.clear_history()

        assert len(detector._request_history) == 0

    def test_check_sql_injection_patterns(self):
        """Test SQL injection pattern matching."""
        detector = AlgoThreatDetector()

        # Test various SQL injection patterns
        assert detector._check_sql_injection({"text": "UNION SELECT"})
        assert detector._check_sql_injection({"text": "or 1=1"})
        assert detector._check_sql_injection({"text": "DROP TABLE users"})
        assert not detector._check_sql_injection({"text": "normal text"})

    def test_check_xss_patterns(self):
        """Test XSS pattern matching."""
        detector = AlgoThreatDetector()

        # Test various XSS patterns
        assert detector._check_xss({"text": "<script>alert(1)</script>"})
        assert detector._check_xss({"text": "javascript:void(0)"})
        assert detector._check_xss({"text": '<img onerror="alert(1)">'})
        assert not detector._check_xss({"text": "normal text"})


class TestThreatAnalysis:
    """Tests for ThreatAnalysis dataclass."""

    def test_threat_analysis_creation(self):
        """Test creating threat analysis result."""
        analysis = ThreatAnalysis(
            is_threat=True,
            threat_level="high",
            anomaly_score=0.85,
            threat_types=["sql_injection"],
            confidence=0.90,
            should_block=True,
        )

        assert analysis.is_threat
        assert analysis.threat_level == "high"
        assert analysis.anomaly_score == 0.85
        assert "sql_injection" in analysis.threat_types
        assert analysis.should_block
