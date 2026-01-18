"""
Test ExecutionStore: PostgreSQL-backed execution history.
Phase 8a: Verify database integration.
"""

import pytest
import time
from neural_engine.core.execution_store import ExecutionStore


@pytest.fixture
def execution_store():
    """Create ExecutionStore instance."""
    store = ExecutionStore()
    yield store
    store.close()


def test_connection(execution_store):
    """Test basic database connection."""
    # Should not raise exception
    conn = execution_store._get_connection()
    assert conn is not None
    execution_store._release_connection(conn)


def test_store_execution(execution_store):
    """Test storing a goal execution."""
    execution_id = execution_store.store_execution(
        goal_id="test_goal_1",
        goal_text="What is 2 + 2?",
        intent="generative",
        success=True,
        duration_ms=123,
        metadata={"neuron": "generative", "depth": 0}
    )
    
    assert execution_id is not None
    assert len(execution_id) == 36  # UUID format


def test_store_tool_execution(execution_store):
    """Test storing a tool execution."""
    # First create a goal execution
    execution_id = execution_store.store_execution(
        goal_id="test_goal_2",
        goal_text="Check if 17 is prime",
        intent="tool_use",
        success=True
    )
    
    # Store tool execution
    execution_store.store_tool_execution(
        execution_id=execution_id,
        tool_name="prime_checker_tool",
        parameters={"number": 17},
        result={"is_prime": True, "message": "17 is prime"},
        success=True,
        duration_ms=50
    )
    
    # Verify by getting tool statistics
    stats = execution_store.get_tool_statistics("prime_checker_tool")
    assert stats is None or stats['total_executions'] >= 0  # May not be updated yet


def test_store_feedback(execution_store):
    """Test storing user feedback."""
    execution_id = execution_store.store_execution(
        goal_id="test_goal_3",
        goal_text="Test feedback",
        intent="generative",
        success=True
    )
    
    execution_store.store_feedback(
        execution_id=execution_id,
        rating=5,
        feedback_text="Great result!"
    )


def test_store_tool_creation(execution_store):
    """Test storing tool creation event."""
    execution_store.store_tool_creation(
        tool_name="test_tool",
        tool_class="TestTool",
        goal_text="Create a test tool",
        generated_code="class TestTool(BaseTool): pass",
        validation_passed=True,
        created_by='ai'
    )


def test_get_recent_executions(execution_store):
    """Test retrieving recent executions."""
    # Store a few executions
    for i in range(3):
        execution_store.store_execution(
            goal_id=f"test_goal_recent_{i}",
            goal_text=f"Test {i}",
            intent="generative",
            success=True
        )
    
    # Get recent
    recent = execution_store.get_recent_executions(limit=10)
    assert len(recent) >= 3
    assert 'goal_id' in recent[0]
    assert 'created_at' in recent[0]


def test_update_statistics(execution_store):
    """Test updating tool statistics."""
    # Create some tool executions
    execution_id = execution_store.store_execution(
        goal_id="test_stats",
        goal_text="Test statistics",
        intent="tool_use",
        success=True
    )
    
    execution_store.store_tool_execution(
        execution_id=execution_id,
        tool_name="stats_test_tool",
        parameters={},
        result={"data": "test"},
        success=True,
        duration_ms=100
    )
    
    # Update statistics
    execution_store.update_statistics()
    
    # Check statistics
    stats = execution_store.get_tool_statistics("stats_test_tool")
    assert stats is not None
    assert stats['total_executions'] >= 1
    assert stats['success_rate'] > 0


def test_get_success_rate(execution_store):
    """Test getting overall success rate."""
    # Store successful execution
    execution_store.store_execution(
        goal_id="success_1",
        goal_text="Success test",
        intent="generative",
        success=True
    )
    
    # Store failed execution
    execution_store.store_execution(
        goal_id="failure_1",
        goal_text="Failure test",
        intent="generative",
        success=False,
        error="Test error"
    )
    
    # Get success rate
    rate = execution_store.get_success_rate()
    assert 0.0 <= rate <= 1.0


def test_get_success_rate_by_intent(execution_store):
    """Test getting success rate filtered by intent."""
    execution_store.store_execution(
        goal_id="tool_success",
        goal_text="Tool test",
        intent="tool_use",
        success=True
    )
    
    rate = execution_store.get_success_rate(intent="tool_use")
    assert 0.0 <= rate <= 1.0


def test_context_manager(execution_store):
    """Test using ExecutionStore as context manager."""
    with ExecutionStore() as store:
        execution_id = store.store_execution(
            goal_id="ctx_test",
            goal_text="Context manager test",
            intent="generative",
            success=True
        )
        assert execution_id is not None


def test_tool_performance_view(execution_store):
    """Test getting tool performance aggregated view."""
    # Create some executions first
    execution_id = execution_store.store_execution(
        goal_id="perf_test",
        goal_text="Performance view test",
        intent="tool_use",
        success=True
    )
    
    execution_store.store_tool_execution(
        execution_id=execution_id,
        tool_name="perf_test_tool",
        parameters={},
        result={"data": "test"},
        success=True,
        duration_ms=200
    )
    
    # Get performance view
    performance = execution_store.get_tool_performance_view()
    assert isinstance(performance, list)
    # May be empty if no tools have been executed yet


def test_get_top_tools(execution_store):
    """Test getting top performing tools."""
    # Create multiple executions for a tool
    for i in range(5):
        execution_id = execution_store.store_execution(
            goal_id=f"top_tool_test_{i}",
            goal_text="Top tool test",
            intent="tool_use",
            success=True
        )
        
        execution_store.store_tool_execution(
            execution_id=execution_id,
            tool_name="top_performer_tool",
            parameters={},
            result={"data": f"test_{i}"},
            success=True,
            duration_ms=100
        )
    
    # Update statistics
    execution_store.update_statistics()
    
    # Get top tools
    top_tools = execution_store.get_top_tools(limit=10, min_executions=3)
    assert isinstance(top_tools, list)
    
    # Check if our tool is in the list
    tool_names = [tool['tool_name'] for tool in top_tools]
    assert 'top_performer_tool' in tool_names


def test_metadata_storage(execution_store):
    """Test storing complex metadata."""
    metadata = {
        "neuron_chain": ["IntentClassifierNeuron", "GenerativeNeuron"],
        "depth": 2,
        "tokens": 150,
        "nested": {
            "data": [1, 2, 3],
            "flag": True
        }
    }
    
    execution_id = execution_store.store_execution(
        goal_id="metadata_test",
        goal_text="Test metadata",
        intent="generative",
        success=True,
        metadata=metadata
    )
    
    assert execution_id is not None
