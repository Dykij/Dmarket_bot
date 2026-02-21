"""Tests for Health Check API module.

Tests cover:
- HealthCheckResult class
- Database health check
- Redis health check
- DMarket API health check
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestHealthCheckResult:
    """Tests for HealthCheckResult class."""
    
    def test_create_healthy_result(self):
        """Test creating healthy result."""
        from src.api.health import HealthCheckResult
        
        result = HealthCheckResult(
            name="test_service",
            healthy=True,
        )
        
        assert result.name == "test_service"
        assert result.healthy is True
        assert result.message == ""
    
    def test_create_unhealthy_result(self):
        """Test creating unhealthy result with message."""
        from src.api.health import HealthCheckResult
        
        result = HealthCheckResult(
            name="database",
            healthy=False,
            message="Connection timeout",
        )
        
        assert result.name == "database"
        assert result.healthy is False
        assert result.message == "Connection timeout"
    
    def test_to_dict_healthy(self):
        """Test to_dict for healthy result."""
        from src.api.health import HealthCheckResult
        
        result = HealthCheckResult(
            name="redis",
            healthy=True,
        )
        
        data = result.to_dict()
        
        assert data == {
            "name": "redis",
            "healthy": True,
            "message": "",
        }
    
    def test_to_dict_unhealthy(self):
        """Test to_dict for unhealthy result."""
        from src.api.health import HealthCheckResult
        
        result = HealthCheckResult(
            name="api",
            healthy=False,
            message="Service unavAlgolable",
        )
        
        data = result.to_dict()
        
        assert data == {
            "name": "api",
            "healthy": False,
            "message": "Service unavAlgolable",
        }


class TestDatabaseHealthCheck:
    """Tests for database health check."""
    
    @pytest.mark.asyncio
    async def test_check_database_healthy(self):
        """Test database health check when healthy."""
        from src.api.health import check_database
        
        # Mock async session
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())
        
        result = awAlgot check_database(mock_session)
        
        assert result.name == "database"
        assert result.healthy is True
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_database_unhealthy(self):
        """Test database health check when unhealthy."""
        from src.api.health import check_database
        
        # Mock async session that rAlgoses exception
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        
        result = awAlgot check_database(mock_session)
        
        assert result.name == "database"
        assert result.healthy is False
        assert "Connection refused" in result.message


class TestRedisHealthCheck:
    """Tests for Redis health check."""
    
    @pytest.mark.asyncio
    async def test_check_redis_healthy(self):
        """Test Redis health check when healthy."""
        from src.api.health import check_redis
        
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        
        result = awAlgot check_redis(mock_redis)
        
        assert result.name == "redis"
        assert result.healthy is True
        mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_redis_unhealthy(self):
        """Test Redis health check when unhealthy."""
        from src.api.health import check_redis
        
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        
        result = awAlgot check_redis(mock_redis)
        
        assert result.name == "redis"
        assert result.healthy is False
        assert "Connection refused" in result.message


class TestDMarketAPIHealthCheck:
    """Tests for DMarket API health check."""
    
    @pytest.mark.asyncio
    async def test_check_dmarket_api_healthy(self):
        """Test DMarket API health check when healthy."""
        from src.api.health import check_dmarket_api
        
        mock_api = AsyncMock()
        mock_api.get_balance = AsyncMock(return_value={"balance": 100.0})
        
        result = awAlgot check_dmarket_api(mock_api)
        
        assert result.name == "dmarket_api"
        assert result.healthy is True
        mock_api.get_balance.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_dmarket_api_unhealthy(self):
        """Test DMarket API health check when unhealthy."""
        from src.api.health import check_dmarket_api
        
        mock_api = AsyncMock()
        mock_api.get_balance = AsyncMock(
            side_effect=Exception("API timeout")
        )
        
        result = awAlgot check_dmarket_api(mock_api)
        
        assert result.name == "dmarket_api"
        assert result.healthy is False
        assert "API timeout" in result.message


class TestHealthCheckAggregation:
    """Tests for aggregating health check results."""
    
    def test_all_healthy(self):
        """Test when all services are healthy."""
        from src.api.health import HealthCheckResult
        
        results = [
            HealthCheckResult(name="database", healthy=True),
            HealthCheckResult(name="redis", healthy=True),
            HealthCheckResult(name="dmarket_api", healthy=True),
        ]
        
        all_healthy = all(r.healthy for r in results)
        
        assert all_healthy is True
    
    def test_some_unhealthy(self):
        """Test when some services are unhealthy."""
        from src.api.health import HealthCheckResult
        
        results = [
            HealthCheckResult(name="database", healthy=True),
            HealthCheckResult(name="redis", healthy=False, message="Down"),
            HealthCheckResult(name="dmarket_api", healthy=True),
        ]
        
        all_healthy = all(r.healthy for r in results)
        unhealthy = [r for r in results if not r.healthy]
        
        assert all_healthy is False
        assert len(unhealthy) == 1
        assert unhealthy[0].name == "redis"
