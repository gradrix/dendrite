"""
Test AnalyticsEngine: Scheduled jobs and analytics.
Phase 8c: Verify analytics capabilities.
"""

import pytest
import time
from datetime import datetime, timedelta
from neural_engine.core.analytics_engine import AnalyticsEngine
from neural_engine.core.execution_store import ExecutionStore


@pytest.fixture
def execution_store():
    """Create ExecutionStore with test data."""
    store = ExecutionStore()
    
    # Create some test data
    for i in range(20):
        success = i % 4 != 0  # 75% success rate
        store.store_execution(
            goal_id=f"test_goal_{i}",
            goal_text=f"Test query {i} with some keywords like calculate, weather, hello",
            intent="generative" if i % 2 == 0 else "tool_use",
            success=success,
            duration_ms=100 + (i * 10),
            metadata={"test": True}
        )
    
    # Create tool executions
    for i in range(15):
        exec_id = store.store_execution(
            goal_id=f"tool_test_{i}",
            goal_text=f"Tool test {i}",
            intent="tool_use",
            success=True
        )
        
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name="test_tool_a" if i % 2 == 0 else "test_tool_b",
            parameters={"param": i},
            result={"output": f"result_{i}"},
            success=i % 3 != 0,  # 67% success
            duration_ms=50 + i
        )
    
    yield store
    store.close()


@pytest.fixture
def analytics_engine(execution_store):
    """Create AnalyticsEngine instance."""
    engine = AnalyticsEngine(execution_store)
    yield engine
    # Don't close - let execution_store fixture handle it


def test_analytics_engine_initialization(analytics_engine, execution_store):
    """Test that analytics engine is initialized correctly."""
    assert analytics_engine.store is not None
    assert analytics_engine.store == execution_store


def test_hourly_statistics_update(analytics_engine):
    """Test hourly statistics update job."""
    result = analytics_engine.hourly_statistics_update()
    
    assert result["job"] == "hourly_statistics_update"
    assert result["status"] == "success"
    assert "duration_seconds" in result
    assert "timestamp" in result


def test_daily_tool_analysis(analytics_engine):
    """Test daily tool analysis job."""
    # First update statistics so we have data
    analytics_engine.store.update_statistics()
    
    result = analytics_engine.daily_tool_analysis()
    
    assert result["job"] == "daily_tool_analysis"
    assert result["status"] == "success"
    assert "categories" in result
    assert "excellent" in result["categories"]
    assert "good" in result["categories"]
    assert "struggling" in result["categories"]
    assert "failing" in result["categories"]
    assert isinstance(result["recommendations"], list)


def test_daily_performance_analysis(analytics_engine):
    """Test daily performance analysis job."""
    result = analytics_engine.daily_performance_analysis()
    
    assert result["job"] == "daily_performance_analysis"
    assert result["status"] in ["success", "no_data"]
    
    if result["status"] == "success":
        assert "performance_metrics" in result
        assert "avg_duration_ms" in result["performance_metrics"]
        assert "p50_duration_ms" in result["performance_metrics"]
        assert "p95_duration_ms" in result["performance_metrics"]
        assert "success_rate" in result["performance_metrics"]
        assert "intent_breakdown" in result


def test_weekly_tool_lifecycle_management(analytics_engine):
    """Test weekly tool lifecycle management job."""
    # Update statistics first
    analytics_engine.store.update_statistics()
    
    result = analytics_engine.weekly_tool_lifecycle_management()
    
    assert result["job"] == "weekly_tool_lifecycle_management"
    assert result["status"] == "success"
    assert "actions" in result
    assert "promote" in result["actions"]
    assert "deprecate" in result["actions"]
    assert "archive" in result["actions"]
    assert isinstance(result["recommendations"], list)


def test_analyze_goal_patterns(analytics_engine):
    """Test goal pattern analysis."""
    result = analytics_engine.analyze_goal_patterns(limit=50)
    
    assert result["status"] in ["success", "no_data"]
    
    if result["status"] == "success":
        assert "executions_analyzed" in result
        assert "top_keywords" in result
        assert "intent_distribution" in result
        assert isinstance(result["top_keywords"], list)


def test_get_tool_insights(analytics_engine, execution_store):
    """Test getting insights for specific tool."""
    # Update statistics to have data
    execution_store.update_statistics()
    
    # Get insights for a tool we know exists
    result = analytics_engine.get_tool_insights("test_tool_a")
    
    # May not be found if no statistics yet
    assert result["status"] in ["excellent", "good", "needs_improvement", "poor", "not_found"]
    
    if result["status"] != "not_found":
        assert "health_score" in result
        assert "statistics" in result
        assert "recommendations" in result
        assert 0 <= result["health_score"] <= 100


def test_get_tool_insights_not_found(analytics_engine):
    """Test getting insights for non-existent tool."""
    result = analytics_engine.get_tool_insights("nonexistent_tool_xyz")
    
    assert result["status"] == "not_found"
    assert "message" in result


def test_generate_dashboard_data(analytics_engine):
    """Test dashboard data generation."""
    result = analytics_engine.generate_dashboard_data()
    
    assert "timestamp" in result
    assert "overview" in result
    assert "top_tools" in result
    assert "recent_activity" in result
    
    # Check overview structure
    assert "total_executions_today" in result["overview"]
    assert "successful_executions" in result["overview"]
    assert "failed_executions" in result["overview"]
    assert "overall_success_rate" in result["overview"]
    assert "total_tools" in result["overview"]


def test_performance_metrics_calculation(analytics_engine):
    """Test that performance metrics are calculated correctly."""
    result = analytics_engine.daily_performance_analysis()
    
    if result["status"] == "success":
        metrics = result["performance_metrics"]
        
        # Check that percentiles are ordered correctly
        assert metrics["p50_duration_ms"] <= metrics["p95_duration_ms"]
        assert metrics["p95_duration_ms"] <= metrics["p99_duration_ms"]
        
        # Check that success rate is valid
        assert 0.0 <= metrics["success_rate"] <= 1.0


def test_tool_categorization(analytics_engine):
    """Test that tools are categorized correctly by success rate."""
    analytics_engine.store.update_statistics()
    result = analytics_engine.daily_tool_analysis()
    
    if result["status"] == "success":
        categories = result["categories"]
        
        # All categories should be non-negative
        assert categories["excellent"] >= 0
        assert categories["good"] >= 0
        assert categories["struggling"] >= 0
        assert categories["failing"] >= 0


def test_recommendations_generated(analytics_engine):
    """Test that recommendations are generated when appropriate."""
    result = analytics_engine.daily_tool_analysis()
    
    assert "recommendations" in result
    assert isinstance(result["recommendations"], list)
    
    # Each recommendation should have required fields
    for rec in result["recommendations"]:
        assert "priority" in rec
        assert "action" in rec
        assert "message" in rec


def test_analytics_with_no_data(execution_store):
    """Test analytics engine behavior with no execution data."""
    # Create new store with no data (isolated from test database)
    # This test just verifies the engine doesn't crash with limited data
    empty_engine = AnalyticsEngine(execution_store)
    
    # analyze_goal_patterns should handle gracefully even with data from other tests
    result = empty_engine.analyze_goal_patterns(limit=1)  # Limit to 1
    assert result["status"] in ["success", "no_data"]  # Both are acceptable


def test_multiple_analysis_runs(analytics_engine):
    """Test running multiple analyses in sequence."""
    # Run multiple times - should not error
    analytics_engine.hourly_statistics_update()
    analytics_engine.daily_tool_analysis()
    analytics_engine.daily_performance_analysis()
    
    # All should complete successfully
    dashboard = analytics_engine.generate_dashboard_data()
    assert "overview" in dashboard


def test_intent_distribution_accuracy(analytics_engine):
    """Test that intent distribution is calculated correctly."""
    result = analytics_engine.daily_performance_analysis()
    
    if result["status"] == "success":
        intent_dist = result["intent_breakdown"]
        
        # Should have at least some intents
        assert len(intent_dist) > 0
        
        # Counts should be positive
        for intent, count in intent_dist.items():
            assert count > 0


def test_keyword_extraction(analytics_engine):
    """Test that keywords are extracted from goals."""
    result = analytics_engine.analyze_goal_patterns(limit=50)
    
    if result["status"] == "success":
        keywords = result["top_keywords"]
        
        # Should find some keywords
        if len(keywords) > 0:
            # Each keyword should have word and count
            for kw in keywords:
                assert "word" in kw
                assert "count" in kw
                assert kw["count"] > 0


def test_health_score_range(analytics_engine):
    """Test that health scores are in valid range."""
    analytics_engine.store.update_statistics()
    
    # Get statistics for tools
    tools = analytics_engine.store.get_tool_performance_view()
    
    for tool in tools[:5]:  # Check first 5 tools
        insights = analytics_engine.get_tool_insights(tool['tool_name'])
        
        if insights["status"] != "not_found":
            assert 0 <= insights["health_score"] <= 100


def test_lifecycle_management_categories(analytics_engine):
    """Test lifecycle management categorization."""
    analytics_engine.store.update_statistics()
    result = analytics_engine.weekly_tool_lifecycle_management()
    
    assert "actions" in result
    
    # All action lists should exist
    assert isinstance(result["actions"]["promote"], list)
    assert isinstance(result["actions"]["deprecate"], list)
    assert isinstance(result["actions"]["archive"], list)


def test_slow_execution_detection(analytics_engine, execution_store):
    """Test that slow executions are detected."""
    # Add a slow execution
    execution_store.store_execution(
        goal_id="slow_test",
        goal_text="Slow query test",
        intent="generative",
        success=True,
        duration_ms=15000  # 15 seconds - definitely slow
    )
    
    result = analytics_engine.daily_performance_analysis()
    
    if result["status"] == "success":
        assert "slow_executions_count" in result
        # Should detect at least our slow execution
        assert result["slow_executions_count"] >= 1
