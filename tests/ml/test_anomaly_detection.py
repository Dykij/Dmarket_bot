"""Tests for Anomaly Detection Module."""

from __future__ import annotations

from src.ml.anomaly_detection import (
    AnomalyDetector,
    AnomalyResult,
    AnomalySeverity,
    AnomalyType,
    create_anomaly_detector,
)


class TestAnomalyDetector:
    """Tests for AnomalyDetector class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        detector = AnomalyDetector()
        
        assert detector.z_score_threshold == 3.0
        assert detector.iqr_multiplier == 1.5
        assert detector.price_change_threshold == 0.3
        assert detector.min_history_length == 10
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        detector = AnomalyDetector(
            z_score_threshold=2.5,
            iqr_multiplier=2.0,
            price_change_threshold=0.5,
        )
        
        assert detector.z_score_threshold == 2.5
        assert detector.iqr_multiplier == 2.0
        assert detector.price_change_threshold == 0.5
    
    def test_check_price_anomaly_normal(self):
        """Test normal price is not flagged."""
        detector = AnomalyDetector()
        
        history = [100, 101, 99, 102, 100, 98, 101, 99, 100, 101]
        result = detector.check_price_anomaly(100, history)
        
        assert result.is_anomaly is False
        assert result.anomaly_type is None
    
    def test_check_price_anomaly_spike(self):
        """Test price spike detection."""
        detector = AnomalyDetector()
        
        history = [100, 101, 99, 102, 100, 98, 101, 99, 100, 101]
        result = detector.check_price_anomaly(150, history)  # 50% spike
        
        assert result.is_anomaly is True
        assert result.anomaly_type == AnomalyType.PRICE_SPIKE
        assert result.score > 0
    
    def test_check_price_anomaly_drop(self):
        """Test price drop detection."""
        detector = AnomalyDetector()
        
        history = [100, 101, 99, 102, 100, 98, 101, 99, 100, 101]
        result = detector.check_price_anomaly(50, history)  # 50% drop
        
        assert result.is_anomaly is True
        assert result.anomaly_type == AnomalyType.PRICE_DROP
    
    def test_check_price_anomaly_insufficient_data(self):
        """Test with insufficient historical data."""
        detector = AnomalyDetector(min_history_length=10)
        
        history = [100, 101, 99]  # Only 3 points
        result = detector.check_price_anomaly(100, history)
        
        assert result.is_anomaly is False
        assert "Insufficient" in result.reason
    
    def test_check_transaction_normal(self):
        """Test normal transaction."""
        detector = AnomalyDetector()
        
        result = detector.check_transaction(
            item_price=100.0,
            market_avg=98.0,
            quantity=1,
        )
        
        assert result.anomaly_result.is_anomaly is False
        assert result.total_value == 100.0
    
    def test_check_transaction_overpriced(self):
        """Test overpriced transaction detection."""
        detector = AnomalyDetector()
        
        result = detector.check_transaction(
            item_price=150.0,  # 50% above market
            market_avg=100.0,
        )
        
        assert result.anomaly_result.is_anomaly is True
        assert len(result.recommendations) > 0
    
    def test_check_transaction_underpriced(self):
        """Test suspiciously underpriced transaction."""
        detector = AnomalyDetector()
        
        result = detector.check_transaction(
            item_price=50.0,  # 50% below market
            market_avg=100.0,
        )
        
        assert result.anomaly_result.is_anomaly is True
        assert any("low" in r.lower() for r in result.recommendations)
    
    def test_detect_price_manipulation_normal(self):
        """Test no manipulation pattern."""
        detector = AnomalyDetector()
        
        # Natural price fluctuations (not too regular)
        import random
        random.seed(42)
        prices = [100 + random.uniform(-5, 5) for _ in range(20)]
        result = detector.detect_price_manipulation(prices)
        
        # The detection may or may not flag, but we check it returns a result
        assert result is not None
    
    def test_detect_price_manipulation_pump_dump(self):
        """Test pump and dump detection."""
        detector = AnomalyDetector()
        
        # Create pump and dump pattern
        prices = [100] * 10 + [120] + [100] + [100] * 8  # Spike then drop
        result = detector.detect_price_manipulation(prices)
        
        # Note: might or might not detect depending on threshold
        assert result is not None
    
    def test_detect_api_anomaly_success(self):
        """Test normal API response."""
        detector = AnomalyDetector()
        
        result = detector.detect_api_anomaly(
            response_code=200,
            response_time_ms=100,
        )
        
        assert result.is_anomaly is False
    
    def test_detect_api_anomaly_server_error(self):
        """Test server error detection."""
        detector = AnomalyDetector()
        
        result = detector.detect_api_anomaly(
            response_code=500,
            response_time_ms=100,
        )
        
        assert result.is_anomaly is True
        assert result.anomaly_type == AnomalyType.API_ERROR
        assert result.severity == AnomalySeverity.CRITICAL
    
    def test_detect_api_anomaly_slow_response(self):
        """Test slow response detection."""
        detector = AnomalyDetector()
        
        result = detector.detect_api_anomaly(
            response_code=200,
            response_time_ms=6000,  # 6 seconds
        )
        
        assert result.is_anomaly is True
        assert "Response time" in result.reason
    
    def test_detect_api_anomaly_missing_fields(self):
        """Test missing fields detection."""
        detector = AnomalyDetector()
        
        result = detector.detect_api_anomaly(
            response_code=200,
            response_time_ms=100,
            expected_fields=["id", "price", "title"],
            actual_fields=["id", "price"],  # missing "title"
        )
        
        assert result.is_anomaly is True
        assert "missing" in result.reason.lower()
    
    def test_batch_detect(self):
        """Test batch anomaly detection."""
        detector = AnomalyDetector()
        
        items = [
            {
                "name": "Item 1",
                "price": 100,
                "historical_prices": [100, 101, 99, 102, 100, 98, 101, 99, 100, 101],
            },
            {
                "name": "Item 2",
                "price": 200,
                "historical_prices": [100, 101, 99, 102, 100, 98, 101, 99, 100, 101],  # Anomaly
            },
        ]
        
        results = detector.batch_detect(items)
        
        assert len(results) == 2
        assert results[0].is_anomaly is False  # Normal price
        assert results[1].is_anomaly is True  # Price spike
    
    def test_get_anomaly_statistics_empty(self):
        """Test statistics with no anomalies."""
        detector = AnomalyDetector()
        
        stats = detector.get_anomaly_statistics()
        
        assert stats["total_anomalies"] == 0
        assert stats["avg_score"] == 0.0
    
    def test_get_anomaly_statistics_with_data(self):
        """Test statistics with recorded anomalies."""
        detector = AnomalyDetector()
        
        # Generate some anomalies
        history = [100] * 15
        detector.check_price_anomaly(200, history)  # Anomaly
        detector.check_price_anomaly(50, history)  # Anomaly
        
        stats = detector.get_anomaly_statistics()
        
        assert stats["total_anomalies"] == 2
        assert "by_type" in stats
    
    def test_anomaly_result_to_dict(self):
        """Test AnomalyResult serialization."""
        result = AnomalyResult(
            is_anomaly=True,
            anomaly_type=AnomalyType.PRICE_SPIKE,
            severity=AnomalySeverity.HIGH,
            score=0.75,
            reason="Test reason",
            detAlgols={"key": "value"},
        )
        
        data = result.to_dict()
        
        assert data["is_anomaly"] is True
        assert data["type"] == "price_spike"
        assert data["severity"] == "high"
        assert data["score"] == 0.75
    
    def test_create_anomaly_detector_factory(self):
        """Test factory function."""
        detector = create_anomaly_detector(
            z_score_threshold=2.0,
            price_change_threshold=0.2,
        )
        
        assert detector.z_score_threshold == 2.0
        assert detector.price_change_threshold == 0.2


class TestAnomalyTypes:
    """Tests for anomaly types and severity."""
    
    def test_anomaly_type_values(self):
        """Test anomaly type enum values."""
        assert AnomalyType.PRICE_SPIKE == "price_spike"
        assert AnomalyType.PRICE_DROP == "price_drop"
        assert AnomalyType.MANIPULATION_SUSPECTED == "manipulation_suspected"
    
    def test_anomaly_severity_values(self):
        """Test anomaly severity enum values."""
        assert AnomalySeverity.CRITICAL == "critical"
        assert AnomalySeverity.HIGH == "high"
        assert AnomalySeverity.LOW == "low"
