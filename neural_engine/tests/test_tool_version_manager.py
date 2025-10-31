"""
Tests for Tool Version Manager

Test version tracking, rollback, comparison, and fast rollback triggers.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import os

from neural_engine.core.tool_version_manager import ToolVersionManager


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
def version_manager(mock_execution_store, mock_tool_registry):
    """Create version manager instance."""
    return ToolVersionManager(
        execution_store=mock_execution_store,
        tool_registry=mock_tool_registry
    )


def test_create_version(version_manager, mock_execution_store):
    """Test creating a new version."""
    # Setup mock
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.fetchone = Mock(return_value=[1])  # version_id
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Create version
    code = "class MyTool:\n    def execute(self, x):\n        return x * 2"
    version_id = version_manager.create_version(
        tool_name='my_tool',
        code=code,
        created_by='human',
        improvement_reason='Initial version'
    )
    
    assert version_id == 1
    mock_cursor.execute.assert_called()
    mock_conn.commit.assert_called()


def test_get_current_version(version_manager, mock_execution_store):
    """Test getting current version."""
    # Setup mock
    mock_conn = Mock()
    mock_cursor = Mock()
    code = "class MyTool:\n    pass"
    mock_cursor.fetchone = Mock(return_value=[
        1,  # version_id
        'my_tool',
        1,  # version_number
        code,
        datetime.now(),
        'human',
        0.9,  # success_rate
        100,  # total_executions
        True  # is_current
    ])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Get current version
    version = version_manager.get_current_version('my_tool')
    
    assert version is not None
    assert version['version_id'] == 1
    assert version['tool_name'] == 'my_tool'
    assert version['version_number'] == 1
    assert version['is_current'] is True


def test_get_version_history(version_manager, mock_execution_store):
    """Test getting version history."""
    # Setup mock
    mock_conn = Mock()
    mock_cursor = Mock()
    
    # Return 3 versions
    mock_cursor.fetchall = Mock(return_value=[
        [3, 'my_tool', 3, 'code3', datetime.now(), 'autonomous', 0.85, 50, True],
        [2, 'my_tool', 2, 'code2', datetime.now() - timedelta(days=1), 'autonomous', 0.80, 30, False],
        [1, 'my_tool', 1, 'code1', datetime.now() - timedelta(days=2), 'human', 0.75, 20, False],
    ])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Get history
    history = version_manager.get_version_history('my_tool')
    
    assert len(history) == 3
    assert history[0]['version_number'] == 3
    assert history[1]['version_number'] == 2
    assert history[2]['version_number'] == 1


def test_rollback_to_version(version_manager, mock_execution_store):
    """Test rollback to previous version."""
    # Setup mocks
    mock_conn = Mock()
    mock_cursor = Mock()
    
    # Mock get version
    code = "class MyTool:\n    def execute(self):\n        return 'old'"
    mock_cursor.fetchone = Mock(return_value=[
        2, 'my_tool', 2, code, datetime.now(), 'human', 0.9, 100, False
    ])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Mock filesystem write
    with patch.object(version_manager, '_write_version_to_filesystem'):
        result = version_manager.rollback_to_version('my_tool', 2, 'Testing rollback')
    
    assert result['success'] is True
    assert result['tool_name'] == 'my_tool'
    assert result['rolled_back_to_version'] == 2


def test_compare_versions(version_manager, mock_execution_store):
    """Test version comparison."""
    # Setup mocks
    mock_conn = Mock()
    mock_cursor = Mock()
    
    old_code = "class MyTool:\n    def execute(self, x):\n        return x"
    new_code = "class MyTool:\n    def execute(self, x, y):\n        return x + y"
    
    # Return two versions
    mock_cursor.fetchone = Mock(side_effect=[
        [1, 'my_tool', 1, old_code, datetime.now(), 'human', 0.75, 100, False],
        [2, 'my_tool', 2, new_code, datetime.now(), 'autonomous', 0.85, 50, True]
    ])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Compare versions
    comparison = version_manager.compare_versions('my_tool', 1, 2)
    
    assert comparison is not None
    assert comparison['from_version'] == 1
    assert comparison['to_version'] == 2
    assert 'code_diff' in comparison
    assert 'metrics_comparison' in comparison


def test_check_immediate_rollback_consecutive_failures(version_manager, mock_execution_store):
    """Test immediate rollback trigger for consecutive failures."""
    # Setup mock - 4 consecutive failures in last 5 minutes
    mock_conn = Mock()
    mock_cursor = Mock()
    
    now = datetime.now()
    mock_cursor.fetchall = Mock(return_value=[
        ['my_tool', now - timedelta(minutes=1), False, 'TypeError: unexpected argument'],
        ['my_tool', now - timedelta(minutes=2), False, 'TypeError: unexpected argument'],
        ['my_tool', now - timedelta(minutes=3), False, 'TypeError: unexpected argument'],
        ['my_tool', now - timedelta(minutes=4), False, 'TypeError: unexpected argument'],
    ])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Check for immediate rollback
    needs_rollback, reason, details = version_manager.check_immediate_rollback_needed('my_tool')
    
    assert needs_rollback is True
    assert 'consecutive failures' in reason.lower() or 'signature change' in reason.lower()


def test_check_immediate_rollback_signature_change(version_manager, mock_execution_store):
    """Test immediate rollback trigger for signature changes."""
    # Setup mock - TypeError indicates signature change
    mock_conn = Mock()
    mock_cursor = Mock()
    
    now = datetime.now()
    mock_cursor.fetchall = Mock(return_value=[
        ['my_tool', now - timedelta(seconds=30), False, "TypeError: execute() got an unexpected keyword argument 'limit'"],
        ['my_tool', now - timedelta(seconds=60), False, "TypeError: execute() got an unexpected keyword argument 'limit'"],
        ['my_tool', now - timedelta(seconds=90), False, "TypeError: execute() missing 1 required positional argument"],
    ])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Check for immediate rollback
    needs_rollback, reason, details = version_manager.check_immediate_rollback_needed('my_tool')
    
    assert needs_rollback is True
    assert 'signature' in reason.lower() or 'typeerror' in reason.lower()


def test_check_immediate_rollback_complete_failure(version_manager, mock_execution_store):
    """Test immediate rollback trigger for 100% failure rate."""
    # Setup mock - 6 failures, 0 successes
    mock_conn = Mock()
    mock_cursor = Mock()
    
    now = datetime.now()
    failures = [
        ['my_tool', now - timedelta(minutes=i), False, f'Error {i}']
        for i in range(1, 7)
    ]
    mock_cursor.fetchall = Mock(return_value=failures)
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Check for immediate rollback
    needs_rollback, reason, details = version_manager.check_immediate_rollback_needed('my_tool')
    
    assert needs_rollback is True
    assert 'failure rate' in reason.lower() or 'complete failure' in reason.lower()


def test_check_immediate_rollback_no_trigger(version_manager, mock_execution_store):
    """Test no immediate rollback when conditions not met."""
    # Setup mock - mix of successes and failures
    mock_conn = Mock()
    mock_cursor = Mock()
    
    now = datetime.now()
    mock_cursor.fetchall = Mock(return_value=[
        ['my_tool', now - timedelta(minutes=1), True, None],
        ['my_tool', now - timedelta(minutes=2), False, 'Timeout'],
        ['my_tool', now - timedelta(minutes=3), True, None],
        ['my_tool', now - timedelta(minutes=4), True, None],
    ])
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Check for immediate rollback
    needs_rollback, reason, details = version_manager.check_immediate_rollback_needed('my_tool')
    
    assert needs_rollback is False


def test_detect_breaking_changes(version_manager):
    """Test detection of breaking changes between versions."""
    old_code = """
class MyTool:
    def execute(self, x, y):
        return x + y
    
    def helper(self):
        pass
"""
    
    new_code = """
class MyTool:
    def execute(self, x, y, z):
        return x + y + z
"""
    
    is_breaking, details = version_manager._detect_breaking_changes(old_code, new_code)
    
    assert is_breaking is True
    assert any('helper' in d for d in details)  # Removed method
    assert any('execute' in d for d in details)  # Signature changed


def test_no_breaking_changes(version_manager):
    """Test when there are no breaking changes."""
    old_code = """
class MyTool:
    def execute(self, x):
        return x * 2
"""
    
    new_code = """
class MyTool:
    def execute(self, x):
        # Improved implementation
        return x * 2 + 1
"""
    
    is_breaking, details = version_manager._detect_breaking_changes(old_code, new_code)
    
    # Same signature, just different implementation
    assert is_breaking is False or len(details) == 0


def test_update_version_metrics(version_manager, mock_execution_store):
    """Test updating version metrics."""
    # Setup mock
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    
    mock_execution_store._get_connection.return_value = mock_conn
    
    # Update metrics
    version_manager.update_version_metrics(
        version_id=1,
        success_rate=0.92,
        total_executions=150
    )
    
    mock_cursor.execute.assert_called()
    mock_conn.commit.assert_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
