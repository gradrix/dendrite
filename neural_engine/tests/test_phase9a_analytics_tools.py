"""
Test suite for Phase 9a Analytics Tools.
Tests QueryExecutionStoreTool, AnalyzeToolPerformanceTool, and GenerateReportTool.

Total: 41 tests covering all query types, analysis types, and report formats.
"""

import pytest
import os
from datetime import datetime, timedelta
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.tools.query_execution_store_tool import QueryExecutionStoreTool
from neural_engine.tools.analyze_tool_performance_tool import AnalyzeToolPerformanceTool
from neural_engine.tools.generate_report_tool import GenerateReportTool


@pytest.fixture
def execution_store():
    """Create a test execution store."""
    store = ExecutionStore()
    yield store
    store.close()


@pytest.fixture
def populated_store():
    """Create an execution store with test data."""
    store = ExecutionStore()
    
    # Clean up test data from previous runs
    conn = store._get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM tool_executions WHERE tool_name LIKE 'test_tool_%'")
            cursor.execute("DELETE FROM tool_statistics WHERE tool_name LIKE 'test_tool_%'")
            cursor.execute("DELETE FROM executions WHERE goal_id LIKE 'goal_%'")
        conn.commit()
    finally:
        store._release_connection(conn)
    
    # Add successful executions
    for i in range(10):
        exec_id = store.store_execution(
            goal_id=f"goal_success_{i}",
            goal_text=f"Test goal {i}",
            intent="tool_use",
            success=True,
            duration_ms=100 + i * 10
        )
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name="test_tool_success",
            parameters={"test": i},
            result={"result": f"success_{i}"},
            duration_ms=100 + i * 10,
            success=True
        )
    
    # Add failed executions
    for i in range(5):
        exec_id = store.store_execution(
            goal_id=f"goal_fail_{i}",
            goal_text=f"Test goal fail {i}",
            intent="tool_use",
            success=False,
            error=f"Test error {i}",
            duration_ms=50 + i * 5
        )
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name="test_tool_failing",
            parameters={"test": i},
            result={"error": f"failure_{i}"},
            duration_ms=50 + i * 5,
            success=False,
            error=f"Test error {i}"
        )
    
    # Add slow executions
    for i in range(3):
        exec_id = store.store_execution(
            goal_id=f"goal_slow_{i}",
            goal_text=f"Test goal slow {i}",
            intent="tool_use",
            success=True,
            duration_ms=6000 + i * 1000
        )
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name="test_tool_slow",
            parameters={"test": i},
            result={"result": f"slow_{i}"},
            duration_ms=6000 + i * 1000,
            success=True
        )
    
    # Add mixed performance tool
    for i in range(8):
        is_success = i % 2 == 0
        exec_id = store.store_execution(
            goal_id=f"goal_mixed_{i}",
            goal_text=f"Test goal mixed {i}",
            intent="tool_use",
            success=is_success,
            duration_ms=200
        )
        store.store_tool_execution(
            execution_id=exec_id,
            tool_name="test_tool_mixed",
            parameters={"test": i},
            result={"result": f"mixed_{i}"},
            duration_ms=200,
            success=is_success
        )
    
    yield store
    store.close()


# ============================================================================
# QueryExecutionStoreTool Tests (12 tests)
# ============================================================================

class TestQueryExecutionStoreTool:
    """Test QueryExecutionStoreTool functionality."""
    
    def test_tool_definition(self):
        """Test 1: Tool definition is properly formatted."""
        tool = QueryExecutionStoreTool()
        definition = tool.get_tool_definition()
        
        assert definition["name"] == "query_execution_store"
        assert "description" in definition
        assert "parameters" in definition
        assert "query_type" in definition["parameters"]
        tool.close()
    
    def test_query_tool_stats_success(self, populated_store):
        """Test 2: Query tool statistics for a specific tool."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(
            query_type="tool_stats",
            tool_name="test_tool_success"
        )
        
        assert result["success"] is True
        assert result["results"]["total_executions"] == 10
        assert result["results"]["successful_executions"] == 10
        assert result["results"]["failed_executions"] == 0
        tool.close()
    
    def test_query_tool_stats_missing_name(self, populated_store):
        """Test 3: Query tool stats without tool_name should fail."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(query_type="tool_stats")
        
        assert result["success"] is False
        assert "tool_name is required" in result["error"]
        tool.close()
    
    def test_query_recent_failures(self, populated_store):
        """Test 4: Query recent failed executions."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(
            query_type="recent_failures",
            limit=10
        )
        
        assert result["success"] is True
        assert result["count"] > 0
        assert len(result["results"]) > 0
        # All results should be failures
        for execution in result["results"]:
            assert execution["success"] is False
        tool.close()
    
    def test_query_recent_successes(self, populated_store):
        """Test 5: Query recent successful executions."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(
            query_type="recent_successes",
            limit=10
        )
        
        assert result["success"] is True
        assert result["count"] > 0
        # All results should be successes
        for execution in result["results"]:
            assert execution["success"] is True
        tool.close()
    
    def test_query_slow_executions(self, populated_store):
        """Test 6: Query slow executions above threshold."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(
            query_type="slow_executions",
            threshold_ms=5000,
            limit=10
        )
        
        assert result["success"] is True
        assert result["count"] > 0
        # All results should be above threshold
        for execution in result["results"]:
            assert execution["duration_ms"] >= 5000
        tool.close()
    
    def test_query_recent_executions(self, populated_store):
        """Test 7: Query recent executions (general)."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(
            query_type="recent_executions",
            limit=5
        )
        
        assert result["success"] is True
        assert result["count"] > 0
        assert len(result["results"]) <= 5
        tool.close()
    
    def test_query_top_tools(self, populated_store):
        """Test 8: Query most frequently used tools."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(
            query_type="top_tools",
            limit=5
        )
        
        assert result["success"] is True
        assert result["count"] > 0
        # Should be sorted by execution count
        counts = [t["total_executions"] for t in result["results"]]
        assert counts == sorted(counts, reverse=True)
        tool.close()
    
    def test_query_tool_usage_trend(self, populated_store):
        """Test 9: Query usage trend for a specific tool."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(
            query_type="tool_usage_trend",
            tool_name="test_tool_success"
        )
        
        assert result["success"] is True
        assert result["results"]["tool_name"] == "test_tool_success"
        assert result["results"]["current_stats"]["total_executions"] == 10
        tool.close()
    
    def test_query_execution_by_intent(self, populated_store):
        """Test 10: Query executions grouped by intent type."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(
            query_type="execution_by_intent",
            limit=100
        )
        
        assert result["success"] is True
        # Results should be a dict of intent stats
        assert isinstance(result["results"], dict)
        # Should have tool_use intent from our test data
        assert "tool_use" in result["results"]
        assert result["results"]["tool_use"]["total"] > 0
        tool.close()
    
    def test_invalid_query_type(self, populated_store):
        """Test 11: Invalid query type should return error."""
        tool = QueryExecutionStoreTool(execution_store=populated_store)
        
        result = tool.execute(query_type="invalid_query")
        
        assert result["success"] is False
        assert "Unknown query type" in result["error"] or "Invalid query_type" in result["error"]
        assert "available_queries" in result
        tool.close()
    
    def test_query_empty_store(self):
        """Test 12: Queries on empty store should handle gracefully."""
        store = ExecutionStore()
        tool = QueryExecutionStoreTool(execution_store=store)
        
        # Query for a non-existent tool
        result = tool.execute(
            query_type="tool_stats",
            tool_name="nonexistent_tool_that_definitely_doesnt_exist"
        )
        
        assert result["success"] is True
        # Should return None for non-existent tool or have 0 executions
        if result["results"] is not None and isinstance(result["results"], dict):
            # Has message key
            assert "message" in result["results"] or result["results"].get("total_executions", 0) == 0
        tool.close()
        store.close()


# ============================================================================
# AnalyzeToolPerformanceTool Tests (18 tests)
# ============================================================================

class TestAnalyzeToolPerformanceTool:
    """Test AnalyzeToolPerformanceTool functionality."""
    
    def test_tool_definition(self):
        """Test 13: Tool definition is properly formatted."""
        tool = AnalyzeToolPerformanceTool()
        definition = tool.get_tool_definition()
        
        assert definition["name"] == "analyze_tool_performance"
        assert "description" in definition
        assert "parameters" in definition
        assert "analysis_type" in definition["parameters"]
        tool.close()
    
    def test_health_check_excellent(self, populated_store):
        """Test 14: Health check for excellent tool."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="health_check",
            tool_name="test_tool_success"
        )
        
        assert result["success"] is True
        assert result["results"]["tool_name"] == "test_tool_success"
        assert result["results"]["health_score"] >= 80
        assert result["results"]["health_status"] in ["excellent", "good"]
        assert "recommendations" in result["results"]
        tool.close()
    
    def test_health_check_failing(self, populated_store):
        """Test 15: Health check for failing tool."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="health_check",
            tool_name="test_tool_failing"
        )
        
        assert result["success"] is True
        assert result["results"]["health_score"] < 50
        assert result["results"]["health_status"] in ["failing", "struggling"]
        tool.close()
    
    def test_health_check_mixed(self, populated_store):
        """Test 16: Health check for mixed performance tool."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="health_check",
            tool_name="test_tool_mixed"
        )
        
        assert result["success"] is True
        health_score = result["results"]["health_score"]
        assert 30 < health_score < 80  # Should be in middle range
        tool.close()
    
    def test_health_check_no_tool_name(self, populated_store):
        """Test 17: Health check without tool_name should fail."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(analysis_type="health_check")
        
        assert result["success"] is False
        assert "tool_name is required" in result["error"]
        tool.close()
    
    def test_health_check_unknown_tool(self, populated_store):
        """Test 18: Health check for non-existent tool."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="health_check",
            tool_name="nonexistent_tool"
        )
        
        assert result["success"] is True
        assert result["results"]["health_status"] == "unknown"
        tool.close()
    
    def test_performance_degradation_detected(self, populated_store):
        """Test 19: Degradation detection for failing tool."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="performance_degradation",
            tool_name="test_tool_failing"
        )
        
        assert result["success"] is True
        assert result["results"]["degradation_detected"] is True
        assert len(result["results"]["indicators"]) > 0
        tool.close()
    
    def test_performance_degradation_not_detected(self, populated_store):
        """Test 20: No degradation for healthy tool."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="performance_degradation",
            tool_name="test_tool_success"
        )
        
        assert result["success"] is True
        assert result["results"]["degradation_detected"] is False
        tool.close()
    
    def test_comparative_analysis_all_tools(self, populated_store):
        """Test 21: Comparative analysis across all tools."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(analysis_type="comparative_analysis")
        
        assert result["success"] is True
        assert result["results"]["total_tools_analyzed"] > 0
        assert "categories" in result["results"]
        assert "excellent" in result["results"]["categories"]
        assert "failing" in result["results"]["categories"]
        tool.close()
    
    def test_comparative_analysis_specific_tools(self, populated_store):
        """Test 22: Comparative analysis for specific tools."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="comparative_analysis",
            tool_names=["test_tool_success", "test_tool_failing"]
        )
        
        assert result["success"] is True
        assert result["results"]["total_tools_analyzed"] == 2
        assert result["results"]["best_performer"] is not None
        assert result["results"]["worst_performer"] is not None
        tool.close()
    
    def test_comparative_categories(self, populated_store):
        """Test 23: Comparative analysis categorizes tools correctly."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(analysis_type="comparative_analysis")
        
        categories = result["results"]["categories"]
        
        # test_tool_success should be in excellent
        excellent_tools = [t["tool_name"] for t in categories["excellent"]["tools"]]
        assert "test_tool_success" in excellent_tools
        
        # test_tool_failing should be in failing
        failing_tools = [t["tool_name"] for t in categories["failing"]["tools"]]
        assert "test_tool_failing" in failing_tools
        tool.close()
    
    def test_success_rate_trend(self, populated_store):
        """Test 24: Success rate trend analysis."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="success_rate_trend",
            tool_name="test_tool_success"
        )
        
        assert result["success"] is True
        assert result["results"]["current_success_rate"] == 100.0
        assert result["results"]["trend"] is not None
        tool.close()
    
    def test_failure_patterns_specific_tool(self, populated_store):
        """Test 25: Failure pattern analysis for specific tool."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="failure_patterns",
            tool_name="test_tool_failing"
        )
        
        assert result["success"] is True
        assert result["results"]["total_failures"] > 0
        assert result["results"]["failure_rate"] > 0
        tool.close()
    
    def test_failure_patterns_all_tools(self, populated_store):
        """Test 26: Failure pattern analysis across all tools."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(analysis_type="failure_patterns")
        
        assert result["success"] is True
        assert result["results"]["total_failing_tools"] > 0
        assert len(result["results"]["top_failing_tools"]) > 0
        tool.close()
    
    def test_usage_patterns_specific_tool(self, populated_store):
        """Test 27: Usage pattern analysis for specific tool."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(
            analysis_type="usage_patterns",
            tool_name="test_tool_success"
        )
        
        assert result["success"] is True
        assert result["results"]["usage_stats"] is not None
        tool.close()
    
    def test_usage_patterns_all_tools(self, populated_store):
        """Test 28: Usage pattern analysis for all tools."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(analysis_type="usage_patterns")
        
        assert result["success"] is True
        assert len(result["results"]["most_used_tools"]) > 0
        tool.close()
    
    def test_invalid_analysis_type(self, populated_store):
        """Test 29: Invalid analysis type should return error."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        result = tool.execute(analysis_type="invalid_analysis")
        
        assert result["success"] is False
        assert "Unknown analysis type" in result["error"]
        assert "available_analyses" in result
        tool.close()
    
    def test_health_score_calculation(self, populated_store):
        """Test 30: Health score calculation is reasonable."""
        tool = AnalyzeToolPerformanceTool(execution_store=populated_store)
        
        # Test successful tool (should be high)
        result_success = tool.execute(
            analysis_type="health_check",
            tool_name="test_tool_success"
        )
        score_success = result_success["results"]["health_score"]
        
        # Test failing tool (should be low)
        result_failing = tool.execute(
            analysis_type="health_check",
            tool_name="test_tool_failing"
        )
        score_failing = result_failing["results"]["health_score"]
        
        # Success score should be higher than failing score
        assert score_success > score_failing
        
        # Scores should be in valid range
        assert 0 <= score_success <= 100
        assert 0 <= score_failing <= 100
        tool.close()


# ============================================================================
# GenerateReportTool Tests (11 tests)
# ============================================================================

class TestGenerateReportTool:
    """Test GenerateReportTool functionality."""
    
    def test_tool_definition(self):
        """Test 31: Tool definition is properly formatted."""
        tool = GenerateReportTool()
        definition = tool.get_tool_definition()
        
        assert definition["name"] == "generate_report"
        assert "description" in definition
        assert "parameters" in definition
        assert "report_type" in definition["parameters"]
        tool.close()
    
    def test_health_report_single_tool(self, populated_store):
        """Test 32: Generate health report for single tool."""
        # Get analysis data first
        analyzer = AnalyzeToolPerformanceTool(execution_store=populated_store)
        analysis = analyzer.execute(
            analysis_type="health_check",
            tool_name="test_tool_success"
        )
        
        # Generate report
        reporter = GenerateReportTool()
        result = reporter.execute(
            report_type="health_report",
            data=analysis["results"]
        )
        
        assert result["success"] is True
        assert "# Tool Health Report" in result["report"]
        assert "test_tool_success" in result["report"]
        assert "Health Score:" in result["report"]
        
        analyzer.close()
        reporter.close()
    
    def test_health_report_comparative(self, populated_store):
        """Test 33: Generate comparative health report."""
        # Get comparative analysis
        analyzer = AnalyzeToolPerformanceTool(execution_store=populated_store)
        analysis = analyzer.execute(analysis_type="comparative_analysis")
        
        # Generate report
        reporter = GenerateReportTool()
        result = reporter.execute(
            report_type="health_report",
            data=analysis["results"]
        )
        
        assert result["success"] is True
        assert "Total Tools Analyzed:" in result["report"]
        assert "Health Distribution" in result["report"]
        assert "|" in result["report"]  # Should contain table
        
        analyzer.close()
        reporter.close()
    
    def test_performance_report(self, populated_store):
        """Test 34: Generate performance report."""
        # Get degradation analysis
        analyzer = AnalyzeToolPerformanceTool(execution_store=populated_store)
        analysis = analyzer.execute(
            analysis_type="performance_degradation",
            tool_name="test_tool_failing"
        )
        
        # Generate report
        reporter = GenerateReportTool()
        result = reporter.execute(
            report_type="performance_report",
            data=analysis["results"]
        )
        
        assert result["success"] is True
        assert "Performance Analysis Report" in result["report"]
        assert "test_tool_failing" in result["report"]
        
        analyzer.close()
        reporter.close()
    
    def test_executive_summary(self, populated_store):
        """Test 35: Generate executive summary."""
        # Get comparative analysis
        analyzer = AnalyzeToolPerformanceTool(execution_store=populated_store)
        analysis = analyzer.execute(analysis_type="comparative_analysis")
        
        # Generate report
        reporter = GenerateReportTool()
        result = reporter.execute(
            report_type="executive_summary",
            data=analysis["results"]
        )
        
        assert result["success"] is True
        assert "Executive Summary" in result["report"]
        assert "Key Highlights" in result["report"]
        assert "Status Overview" in result["report"]
        
        analyzer.close()
        reporter.close()
    
    def test_detailed_analysis_report(self, populated_store):
        """Test 36: Generate detailed analysis report."""
        # Get any analysis
        analyzer = AnalyzeToolPerformanceTool(execution_store=populated_store)
        analysis = analyzer.execute(
            analysis_type="health_check",
            tool_name="test_tool_success"
        )
        
        # Generate report
        reporter = GenerateReportTool()
        result = reporter.execute(
            report_type="detailed_analysis",
            data=analysis["results"]
        )
        
        assert result["success"] is True
        assert "Detailed Analysis Report" in result["report"]
        assert "```json" in result["report"]
        
        analyzer.close()
        reporter.close()
    
    def test_comparison_report(self, populated_store):
        """Test 37: Generate comparison report."""
        # Get comparative analysis
        analyzer = AnalyzeToolPerformanceTool(execution_store=populated_store)
        analysis = analyzer.execute(analysis_type="comparative_analysis")
        
        # Generate report
        reporter = GenerateReportTool()
        result = reporter.execute(
            report_type="comparison_report",
            data=analysis["results"]
        )
        
        assert result["success"] is True
        assert "Tool Comparison Report" in result["report"]
        assert "| Tool Name |" in result["report"]
        
        analyzer.close()
        reporter.close()
    
    def test_custom_report(self, populated_store):
        """Test 38: Generate custom report."""
        # Get any data
        data = {
            "metric_1": "value_1",
            "metric_2": 42,
            "recommendations": ["Fix this", "Improve that"]
        }
        
        # Generate report
        reporter = GenerateReportTool()
        result = reporter.execute(
            report_type="custom",
            data=data,
            title="My Custom Report"
        )
        
        assert result["success"] is True
        assert "My Custom Report" in result["report"]
        assert "value_1" in result["report"]
        
        reporter.close()
    
    def test_report_with_recommendations(self, populated_store):
        """Test 39: Report includes recommendations when enabled."""
        analyzer = AnalyzeToolPerformanceTool(execution_store=populated_store)
        analysis = analyzer.execute(
            analysis_type="health_check",
            tool_name="test_tool_success"
        )
        
        reporter = GenerateReportTool()
        result = reporter.execute(
            report_type="health_report",
            data=analysis["results"],
            include_recommendations=True
        )
        
        assert result["success"] is True
        assert "Recommendations" in result["report"]
        
        analyzer.close()
        reporter.close()
    
    def test_report_without_recommendations(self, populated_store):
        """Test 40: Report excludes recommendations when disabled."""
        analyzer = AnalyzeToolPerformanceTool(execution_store=populated_store)
        analysis = analyzer.execute(
            analysis_type="health_check",
            tool_name="test_tool_success"
        )
        
        reporter = GenerateReportTool()
        result = reporter.execute(
            report_type="health_report",
            data=analysis["results"],
            include_recommendations=False
        )
        
        assert result["success"] is True
        # Should not have recommendations section
        assert "📋 Recommendations" not in result["report"]
        
        analyzer.close()
        reporter.close()
    
    def test_invalid_report_type(self):
        """Test 41: Invalid report type should return error."""
        reporter = GenerateReportTool()
        
        result = reporter.execute(
            report_type="invalid_report",
            data={"test": "data"}
        )
        
        assert result["success"] is False
        assert "Unknown report type" in result["error"]
        assert "available_types" in result
        
        reporter.close()


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_pipeline_integration(populated_store):
    """Integration test: Query → Analyze → Report pipeline."""
    # Step 1: Query data
    query_tool = QueryExecutionStoreTool(execution_store=populated_store)
    query_result = query_tool.execute(
        query_type="tool_stats",
        tool_name="test_tool_success"
    )
    assert query_result["success"] is True
    
    # Step 2: Analyze
    analyzer = AnalyzeToolPerformanceTool(execution_store=populated_store)
    analysis_result = analyzer.execute(
        analysis_type="health_check",
        tool_name="test_tool_success"
    )
    assert analysis_result["success"] is True
    
    # Step 3: Generate report
    reporter = GenerateReportTool()
    report_result = reporter.execute(
        report_type="health_report",
        data=analysis_result["results"]
    )
    assert report_result["success"] is True
    assert len(report_result["report"]) > 100  # Should be substantial
    
    query_tool.close()
    analyzer.close()
    reporter.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
