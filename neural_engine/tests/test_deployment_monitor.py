"""
Tests for Post-Deployment Monitoring

Test continuous health tracking and auto-rollback functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import psycopg2

from neural_engine.core.deployment_monitor import DeploymentMonitor


@pytest.fixture
def mock_execution_store():
    """Mock execution store."""
    store = Mock()
    store._get_connection = Mock()
    store._release_connection = Mock()
    return store


@pytest.fixture
def mock_tool_registry():
    """Mock tool registry."""
    return Mock()


@pytest.fixture
def deployment_monitor(mock_execution_store, mock_tool_registry):
    """Create deployment monitor instance."""
    return DeploymentMonitor(
        execution_store=mock_execution_store,
        tool_registry=mock_tool_registry,
        monitoring_window_hours=24,
        baseline_window_days=7,
        regression_threshold=0.15,
        min_executions=10
    )


def test_start_monitoring(deployment_monitor, mock_execution_store):
    """Test starting a monitoring session."""
    # Setup mock connection
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.fetchone = Mock(return_value=['session_123'])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Start monitoring
    deployment_time = datetime.now()
    session_id = deployment_monitor.start_monitoring(
        tool_name='test_tool',
        deployment_time=deployment_time
    )
    
    assert session_id == 'session_123'
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()


def test_get_baseline_metrics_sufficient_data(deployment_monitor, mock_execution_store):
    """Test getting baseline metrics with sufficient data."""
    # Setup mock connection
    mock_conn = Mock()
    mock_cursor = Mock()
    # Return 20 total, 18 successes, 150ms avg duration
    mock_cursor.fetchone = Mock(return_value=[20, 18, 150.0])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Get baseline
    deployment_time = datetime.now()
    baseline = deployment_monitor._get_baseline_metrics('test_tool', deployment_time)
    
    assert baseline['total_executions'] == 20
    assert baseline['successes'] == 18
    assert baseline['success_rate'] == 0.9  # 18/20
    assert baseline['avg_duration_ms'] == 150.0
    assert baseline['sufficient_data'] is True
    assert baseline['period'] == 'baseline'


def test_get_baseline_metrics_insufficient_data(deployment_monitor, mock_execution_store):
    """Test getting baseline metrics with insufficient data."""
    # Setup mock connection
    mock_conn = Mock()
    mock_cursor = Mock()
    # Return only 5 executions (less than min_executions=10)
    mock_cursor.fetchone = Mock(return_value=[5, 4, 200.0])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Get baseline
    deployment_time = datetime.now()
    baseline = deployment_monitor._get_baseline_metrics('test_tool', deployment_time)
    
    assert baseline['total_executions'] == 5
    assert baseline['sufficient_data'] is False


def test_get_current_metrics(deployment_monitor, mock_execution_store):
    """Test getting current metrics after deployment."""
    # Setup mock connection
    mock_conn = Mock()
    mock_cursor = Mock()
    # Return 15 total, 12 successes, 180ms avg duration
    mock_cursor.fetchone = Mock(return_value=[15, 12, 180.0])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Get current
    deployment_time = datetime.now() - timedelta(hours=12)
    current = deployment_monitor._get_current_metrics('test_tool', deployment_time)
    
    assert current['total_executions'] == 15
    assert current['successes'] == 12
    assert current['success_rate'] == 0.8  # 12/15
    assert current['avg_duration_ms'] == 180.0
    assert current['sufficient_data'] is True
    assert current['period'] == 'current'


def test_compare_metrics_no_regression(deployment_monitor):
    """Test comparing metrics when no regression detected."""
    baseline = {
        'success_rate': 0.9,
        'avg_duration_ms': 150.0,
        'total_executions': 20,
        'sufficient_data': True
    }
    
    current = {
        'success_rate': 0.88,  # Only 2% drop
        'avg_duration_ms': 160.0,
        'total_executions': 15,
        'sufficient_data': True
    }
    
    comparison = deployment_monitor._compare_metrics(baseline, current)
    
    assert comparison['has_sufficient_data'] is True
    assert comparison['success_rate_change'] == -0.02
    assert comparison['success_rate_drop'] == 0.02
    assert comparison['baseline_success_rate'] == 0.9
    assert comparison['current_success_rate'] == 0.88
    assert comparison['regression_detected'] is False  # Below 15% threshold


def test_compare_metrics_medium_regression(deployment_monitor):
    """Test comparing metrics with medium regression."""
    baseline = {
        'success_rate': 0.9,
        'avg_duration_ms': 150.0,
        'total_executions': 20,
        'sufficient_data': True
    }
    
    current = {
        'success_rate': 0.72,  # 18% drop - above 15% threshold
        'avg_duration_ms': 160.0,
        'total_executions': 15,
        'sufficient_data': True
    }
    
    comparison = deployment_monitor._compare_metrics(baseline, current)
    
    assert comparison['success_rate_drop'] == 0.18
    assert comparison['regression_detected'] is True
    assert comparison['regression_severity'] == 'medium'


def test_compare_metrics_high_regression(deployment_monitor):
    """Test comparing metrics with high regression."""
    baseline = {
        'success_rate': 0.9,
        'avg_duration_ms': 150.0,
        'total_executions': 20,
        'sufficient_data': True
    }
    
    current = {
        'success_rate': 0.65,  # 25% drop - high severity
        'avg_duration_ms': 160.0,
        'total_executions': 15,
        'sufficient_data': True
    }
    
    comparison = deployment_monitor._compare_metrics(baseline, current)
    
    assert comparison['success_rate_drop'] == 0.25
    assert comparison['regression_detected'] is True
    assert comparison['regression_severity'] == 'high'


def test_compare_metrics_critical_regression(deployment_monitor):
    """Test comparing metrics with critical regression."""
    baseline = {
        'success_rate': 0.9,
        'avg_duration_ms': 150.0,
        'total_executions': 20,
        'sufficient_data': True
    }
    
    current = {
        'success_rate': 0.55,  # 35% drop - critical
        'avg_duration_ms': 160.0,
        'total_executions': 15,
        'sufficient_data': True
    }
    
    comparison = deployment_monitor._compare_metrics(baseline, current)
    
    assert comparison['success_rate_drop'] == 0.35
    assert comparison['regression_detected'] is True
    assert comparison['regression_severity'] == 'critical'


def test_compare_metrics_insufficient_data(deployment_monitor):
    """Test comparing metrics with insufficient data."""
    baseline = {
        'success_rate': 0.9,
        'total_executions': 5,  # Insufficient
        'sufficient_data': False
    }
    
    current = {
        'success_rate': 0.5,
        'total_executions': 3,  # Insufficient
        'sufficient_data': False
    }
    
    comparison = deployment_monitor._compare_metrics(baseline, current)
    
    assert comparison['has_sufficient_data'] is False
    assert 'warning' in comparison


def test_compare_metrics_performance_degradation(deployment_monitor):
    """Test detecting performance degradation (slowdown)."""
    baseline = {
        'success_rate': 0.9,
        'avg_duration_ms': 100.0,
        'total_executions': 20,
        'sufficient_data': True
    }
    
    current = {
        'success_rate': 0.88,  # Success rate OK
        'avg_duration_ms': 350.0,  # 250% slower!
        'total_executions': 15,
        'sufficient_data': True
    }
    
    comparison = deployment_monitor._compare_metrics(baseline, current)
    
    assert comparison['duration_change'] == 2.5  # 250% increase
    assert comparison.get('performance_degradation') is True


def test_needs_rollback_medium_regression(deployment_monitor):
    """Test that medium regression triggers rollback."""
    comparison = {
        'has_sufficient_data': True,
        'regression_detected': True,
        'regression_severity': 'medium'
    }
    
    assert deployment_monitor._needs_rollback(comparison) is True


def test_needs_rollback_high_regression(deployment_monitor):
    """Test that high regression triggers rollback."""
    comparison = {
        'has_sufficient_data': True,
        'regression_detected': True,
        'regression_severity': 'high'
    }
    
    assert deployment_monitor._needs_rollback(comparison) is True


def test_needs_rollback_no_regression(deployment_monitor):
    """Test that no regression doesn't trigger rollback."""
    comparison = {
        'has_sufficient_data': True,
        'regression_detected': False,
        'regression_severity': 'none'
    }
    
    assert deployment_monitor._needs_rollback(comparison) is False


def test_needs_rollback_insufficient_data(deployment_monitor):
    """Test that insufficient data doesn't trigger rollback."""
    comparison = {
        'has_sufficient_data': False,
        'regression_detected': True,
        'regression_severity': 'high'
    }
    
    assert deployment_monitor._needs_rollback(comparison) is False


def test_check_health(deployment_monitor, mock_execution_store):
    """Test full health check workflow."""
    # Setup mocks for deployment, baseline, and current queries
    mock_conn = Mock()
    mock_cursor = Mock()
    
    # Mock responses in sequence
    mock_cursor.fetchone.side_effect = [
        ['session_123', datetime.now() - timedelta(hours=6)],  # deployment info
        [20, 18, 150.0],  # baseline metrics
        [15, 12, 180.0]   # current metrics
    ]
    
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Check health
    report = deployment_monitor.check_health('test_tool')
    
    assert report['tool_name'] == 'test_tool'
    assert report['session_id'] == 'session_123'
    assert 'baseline' in report
    assert 'current' in report
    assert 'comparison' in report
    assert 'needs_rollback' in report
    
    # Should not need rollback (only 2% drop from 0.9 to 0.8)
    assert report['baseline']['success_rate'] == 0.9
    assert report['current']['success_rate'] == 0.8
    assert report['needs_rollback'] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
