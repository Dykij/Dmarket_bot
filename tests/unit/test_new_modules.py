"""Unit tests for knowledge_base.py, query_profiler.py, incident_manager.py (v15.7)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analytics.knowledge_base import (
    AdaptiveThreshold,
    Insight,
    InsightCategory,
    KnowledgeBase,
)
from src.utils.query_profiler import QueryProfiler, QueryStats, get_query_profiler
from src.risk.incident_manager import (
    Incident,
    IncidentManager,
    IncidentType,
    Severity,
)


# =====================================================================
# KnowledgeBase Tests
# =====================================================================


class TestInsight:
    """Tests for Insight dataclass."""

    def test_is_active_when_not_expired(self) -> None:
        i = Insight(category="test", key="k", value=1.0, confidence=0.5, sample_size=1)
        assert i.is_active is True

    def test_is_active_when_expired(self) -> None:
        i = Insight(
            category="test", key="k", value=1.0, confidence=0.5, sample_size=1,
            expires_at=time.time() - 1,
        )
        assert i.is_active is False

    def test_is_active_low_confidence(self) -> None:
        i = Insight(category="test", key="k", value=1.0, confidence=0.2, sample_size=1)
        assert i.is_active is False


class TestKnowledgeBase:
    """Tests for KnowledgeBase."""

    def test_init(self) -> None:
        kb = KnowledgeBase()
        assert kb.insight_count == 0
        assert kb.threshold_count == 0

    def test_record_insight(self) -> None:
        kb = KnowledgeBase()
        insight = kb.record_insight(
            InsightCategory.PRICE_PATTERN, "test_pattern", 1.5, confidence=0.7, sample_size=5
        )
        assert insight.value == 1.5
        assert kb.insight_count == 1

    def test_record_insight_update_existing(self) -> None:
        kb = KnowledgeBase()
        kb.record_insight(InsightCategory.PRICE_PATTERN, "test", 1.0, confidence=0.5, sample_size=1)
        kb.record_insight(InsightCategory.PRICE_PATTERN, "test", 2.0, confidence=0.8, sample_size=1)
        insight = kb.get_insight("test")
        assert insight is not None
        assert insight.sample_size == 2
        # Weighted average: (1.0*1 + 2.0*1) / 2 = 1.5
        assert insight.value == pytest.approx(1.5)

    def test_get_insight_not_found(self) -> None:
        kb = KnowledgeBase()
        assert kb.get_insight("nonexistent") is None

    def test_get_insight_value_with_default(self) -> None:
        kb = KnowledgeBase()
        assert kb.get_insight_value("nonexistent", default=42.0) == 42.0

    def test_get_insights_by_category(self) -> None:
        kb = KnowledgeBase()
        kb.record_insight(InsightCategory.PRICE_PATTERN, "p1", 1.0)
        kb.record_insight(InsightCategory.PRICE_PATTERN, "p2", 2.0)
        kb.record_insight(InsightCategory.TIMING, "t1", 3.0)
        patterns = kb.get_insights_by_category(InsightCategory.PRICE_PATTERN)
        assert len(patterns) == 2

    def test_set_adaptive_threshold(self) -> None:
        kb = KnowledgeBase()
        threshold = kb.set_adaptive_threshold("min_spread", 3.0, adjustment_factor=1.2)
        assert threshold.current_value == pytest.approx(3.6)
        assert kb.threshold_count == 1

    def test_get_threshold(self) -> None:
        kb = KnowledgeBase()
        kb.set_adaptive_threshold("test", 10.0, adjustment_factor=0.8)
        assert kb.get_threshold("test") == pytest.approx(8.0)

    def test_get_threshold_default(self) -> None:
        kb = KnowledgeBase()
        assert kb.get_threshold("nonexistent", default=99.0) == 99.0

    def test_record_trade_outcome(self) -> None:
        kb = KnowledgeBase()
        # Record enough trades to build confidence above 0.3 threshold
        for _ in range(10):
            kb.record_trade_outcome("AK-47 | Redline", 10.0, 12.0, 24.0, "intra_spread")
        # The win_rate insight (confidence=0.5) should be active
        win = kb.get_insight("win_rate")
        assert win is not None
        assert win.value == pytest.approx(1.0)
        # The strategy ROI insight exists in internal store
        assert "strategy_roi_intra_spread" in kb._insights

    def test_record_price_pattern(self) -> None:
        kb = KnowledgeBase()
        kb.record_price_pattern("stickers_post_major", 1.15, confidence=0.8, sample_size=5)
        insight = kb.get_insight("stickers_post_major")
        assert insight is not None
        assert insight.value == pytest.approx(1.15)

    def test_record_event_impact(self) -> None:
        kb = KnowledgeBase()
        kb.record_event_impact("new_case", -5.0, confidence=0.6)
        insight = kb.get_insight("event_new_case")
        assert insight is not None
        assert insight.value == pytest.approx(-5.0)

    def test_expire_old_insights(self) -> None:
        kb = KnowledgeBase()
        kb.record_insight(InsightCategory.PRICE_PATTERN, "expired", 1.0, ttl_seconds=0.01)
        time.sleep(0.02)
        count = kb.expire_old_insights()
        assert count == 1
        assert kb.insight_count == 0

    def test_clear(self) -> None:
        kb = KnowledgeBase()
        kb.record_insight(InsightCategory.PRICE_PATTERN, "test", 1.0)
        kb.set_adaptive_threshold("test", 10.0)
        kb.clear()
        assert kb.insight_count == 0
        assert kb.threshold_count == 0

    def test_get_stats(self) -> None:
        kb = KnowledgeBase()
        kb.record_insight(InsightCategory.PRICE_PATTERN, "test", 1.0)
        stats = kb.get_stats()
        assert stats["active_insights"] == 1
        assert stats["total_insights_recorded"] == 1

    def test_get_summary(self) -> None:
        kb = KnowledgeBase()
        kb.record_insight(InsightCategory.PRICE_PATTERN, "test", 1.0)
        summary = kb.get_summary()
        assert "1 insights" in summary


# =====================================================================
# QueryProfiler Tests
# =====================================================================


class TestQueryStats:
    """Tests for QueryStats dataclass."""

    def test_avg_time(self) -> None:
        qs = QueryStats(query_name="test")
        qs.record(10.0)
        qs.record(20.0)
        assert qs.avg_time_ms == pytest.approx(15.0)

    def test_min_max(self) -> None:
        qs = QueryStats(query_name="test")
        qs.record(10.0)
        qs.record(50.0)
        assert qs.min_time_ms == 10.0
        assert qs.max_time_ms == 50.0

    def test_slow_count(self) -> None:
        qs = QueryStats(query_name="test")
        qs.record(10.0, slow_threshold_ms=100.0)
        qs.record(150.0, slow_threshold_ms=100.0)
        assert qs.slow_count == 1


class TestQueryProfiler:
    """Tests for QueryProfiler."""

    def test_init(self) -> None:
        profiler = QueryProfiler()
        assert profiler.is_enabled is True

    def test_enable_disable(self) -> None:
        profiler = QueryProfiler()
        profiler.disable()
        assert profiler.is_enabled is False
        profiler.enable()
        assert profiler.is_enabled is True

    def test_profile_context_manager(self) -> None:
        profiler = QueryProfiler()
        with profiler.profile("test_query"):
            time.sleep(0.01)
        stats = profiler.get_query_stats("test_query")
        assert stats is not None
        assert stats.call_count == 1
        assert stats.avg_time_ms >= 10.0

    def test_profile_disabled(self) -> None:
        profiler = QueryProfiler(enabled=False)
        with profiler.profile("test"):
            pass
        assert profiler._total_queries == 0

    def test_record_manual(self) -> None:
        profiler = QueryProfiler()
        profiler.record_manual("test", 42.0)
        stats = profiler.get_query_stats("test")
        assert stats is not None
        assert stats.avg_time_ms == 42.0

    def test_slow_query_detection(self) -> None:
        profiler = QueryProfiler(slow_threshold_ms=50.0)
        profiler.record_manual("slow", 100.0)
        slow = profiler.get_slow_queries()
        assert len(slow) == 1
        assert slow[0][0] == "slow"

    def test_get_stats(self) -> None:
        profiler = QueryProfiler()
        profiler.record_manual("test", 10.0)
        stats = profiler.get_stats()
        assert stats["total_queries"] == 1
        assert stats["enabled"] is True

    def test_get_report(self) -> None:
        profiler = QueryProfiler()
        profiler.record_manual("test", 10.0)
        report = profiler.get_report()
        assert "Total queries: 1" in report
        assert "test" in report

    def test_reset(self) -> None:
        profiler = QueryProfiler()
        profiler.record_manual("test", 10.0)
        profiler.reset()
        assert profiler._total_queries == 0

    def test_get_all_query_stats_sorted(self) -> None:
        profiler = QueryProfiler()
        profiler.record_manual("a", 10.0)
        profiler.record_manual("b", 30.0)
        profiler.record_manual("c", 20.0)
        all_stats = profiler.get_all_query_stats()
        assert all_stats[0].query_name == "b"  # highest total time

    def test_singleton(self) -> None:
        p1 = get_query_profiler()
        p2 = get_query_profiler()
        assert p1 is p2


# =====================================================================
# IncidentManager Tests
# =====================================================================


class TestIncident:
    """Tests for Incident dataclass."""

    def test_age_seconds(self) -> None:
        i = Incident(incident_type="test", severity="info", title="t", timestamp=time.time() - 60)
        assert i.age_seconds >= 59.0

    def test_age_minutes(self) -> None:
        i = Incident(incident_type="test", severity="info", title="t", timestamp=time.time() - 120)
        assert i.age_minutes >= 1.9


class TestIncidentManager:
    """Tests for IncidentManager."""

    def test_init(self) -> None:
        im = IncidentManager()
        assert im._stats["total_incidents"] == 0

    def test_record_incident(self) -> None:
        im = IncidentManager()
        incident = im.record(
            IncidentType.API_FAILURE, Severity.WARNING,
            "Test incident", "Description",
        )
        assert incident.title == "Test incident"
        assert im._stats["total_incidents"] == 1
        assert im._stats["warning_count"] == 1

    def test_record_critical(self) -> None:
        im = IncidentManager()
        im.record(IncidentType.API_AUTH_ERROR, Severity.CRITICAL, "Auth failed")
        assert im._stats["critical_count"] == 1

    def test_record_api_failure_500(self) -> None:
        im = IncidentManager()
        incident = im.record_api_failure("/api/test", 500, "Internal Server Error")
        assert incident.incident_type == IncidentType.API_FAILURE
        assert incident.severity == Severity.WARNING

    def test_record_api_failure_429(self) -> None:
        im = IncidentManager()
        incident = im.record_api_failure("/api/test", 429)
        assert incident.incident_type == IncidentType.RATE_LIMIT

    def test_record_api_failure_401(self) -> None:
        im = IncidentManager()
        incident = im.record_api_failure("/api/test", 401)
        assert incident.incident_type == IncidentType.API_AUTH_ERROR
        assert incident.severity == Severity.CRITICAL

    def test_record_price_crash(self) -> None:
        im = IncidentManager()
        incident = im.record_price_crash("AK-47", 10.0, 8.0, -20.0)
        assert incident.incident_type == IncidentType.PRICE_CRASH
        assert "-20.0" in incident.description

    def test_record_drawdown(self) -> None:
        im = IncidentManager()
        incident = im.record_drawdown(80.0, 100.0, 20.0)
        assert incident.incident_type == IncidentType.DRAWDOWN_EVENT
        assert incident.severity == Severity.CRITICAL

    def test_record_drawdown_warning(self) -> None:
        im = IncidentManager()
        incident = im.record_drawdown(92.0, 100.0, 8.0)
        assert incident.severity == Severity.WARNING

    def test_record_circuit_breaker(self) -> None:
        im = IncidentManager()
        incident = im.record_circuit_breaker("DMarket API", "OPEN", "3 failures")
        assert incident.incident_type == IncidentType.CIRCUIT_BREAKER

    def test_record_trade_failure(self) -> None:
        im = IncidentManager()
        incident = im.record_trade_failure("AK-47 | Redline", "Insufficient balance", 10.0)
        assert incident.incident_type == IncidentType.TRADE_FAILURE

    def test_get_recent_incidents(self) -> None:
        im = IncidentManager()
        im.record(IncidentType.API_FAILURE, Severity.INFO, "1")
        im.record(IncidentType.API_FAILURE, Severity.INFO, "2")
        im.record(IncidentType.API_FAILURE, Severity.INFO, "3")
        recent = im.get_recent_incidents(count=2)
        assert len(recent) == 2
        assert recent[-1].title == "3"

    def test_get_incidents_by_type(self) -> None:
        im = IncidentManager()
        im.record(IncidentType.API_FAILURE, Severity.INFO, "api")
        im.record(IncidentType.PRICE_CRASH, Severity.WARNING, "crash")
        api_incidents = im.get_incidents_by_type(IncidentType.API_FAILURE)
        assert len(api_incidents) == 1

    def test_get_incidents_by_severity(self) -> None:
        im = IncidentManager()
        im.record(IncidentType.API_FAILURE, Severity.INFO, "info")
        im.record(IncidentType.API_FAILURE, Severity.CRITICAL, "critical")
        critical = im.get_incidents_by_severity(Severity.CRITICAL)
        assert len(critical) == 1

    def test_alert_cooldown(self) -> None:
        im = IncidentManager(alert_cooldown_seconds=60.0)
        im.record(IncidentType.API_FAILURE, Severity.CRITICAL, "1", alert=True)
        im.record(IncidentType.API_FAILURE, Severity.CRITICAL, "2", alert=True)
        # Second alert should be suppressed (within cooldown)
        assert im._stats["alerts_suppressed"] == 1

    def test_get_stats(self) -> None:
        im = IncidentManager()
        im.record(IncidentType.API_FAILURE, Severity.WARNING, "test")
        stats = im.get_stats()
        assert stats["total_incidents"] == 1
        assert stats["warning_count"] == 1

    def test_get_summary(self) -> None:
        im = IncidentManager()
        im.record(IncidentType.API_FAILURE, Severity.WARNING, "test")
        summary = im.get_summary()
        assert "1 total" in summary
        assert "Warning: 1" in summary
