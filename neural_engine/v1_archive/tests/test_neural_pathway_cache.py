"""
Tests for Neural Pathway Cache (System 1 vs System 2)

Tests caching, invalidation, confidence scoring, and tool dependency tracking.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4
import json

from neural_engine.core.neural_pathway_cache import NeuralPathwayCache


def get_mock_cursor(mock_execution_store):
    """Helper to get the mock cursor from execution store."""
    mock_conn = mock_execution_store._get_connection.return_value
    return mock_conn.cursor.return_value.__enter__.return_value


@pytest.fixture
def mock_execution_store():
    """Mock ExecutionStore with database connection."""
    store = Mock()
    
    # Mock connection object with cursor context manager
    mock_conn = Mock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock the _get_db_connection and _release_db_connection methods
    store._get_connection.return_value = mock_conn
    store._release_connection = Mock()
    
    return store


@pytest.fixture
def mock_chroma_client():
    """Mock Chroma client."""
    client = Mock()
    collection = Mock()
    client.get_or_create_collection.return_value = collection
    return client


@pytest.fixture
def pathway_cache(mock_execution_store, mock_chroma_client):
    """Create NeuralPathwayCache instance."""
    return NeuralPathwayCache(
        execution_store=mock_execution_store,
        chroma_client=mock_chroma_client,
        similarity_threshold=0.85,
        min_success_count=2,
        confidence_threshold=0.70
    )


def test_initialization(pathway_cache, mock_chroma_client):
    """Test cache initialization."""
    assert pathway_cache.similarity_threshold == 0.85
    assert pathway_cache.min_success_count == 2
    assert pathway_cache.confidence_threshold == 0.70
    
    mock_chroma_client.get_or_create_collection.assert_called_once()


def test_store_pathway_success(pathway_cache, mock_execution_store, mock_chroma_client):
    """Test storing a successful execution pathway."""
    pathway_id = str(uuid4())
    
    # Mock database insert - access cursor through _get_connection
    mock_conn = mock_execution_store._get_connection.return_value
    cursor = mock_conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (pathway_id,)
    
    goal_text = "Get my recent Strava activities"
    goal_embedding = [0.1] * 384
    execution_steps = [
        {"step": 1, "action": "get_activities", "tool": "strava_get_my_activities_tool", "params": {}, "result": "success"}
    ]
    final_result = {"activities": [{"id": 1, "name": "Morning Run"}]}
    tool_names = ["strava_get_my_activities_tool"]
    
    result = pathway_cache.store_pathway(
        goal_text=goal_text,
        goal_embedding=goal_embedding,
        execution_steps=execution_steps,
        final_result=final_result,
        tool_names=tool_names,
        goal_type="data_retrieval",
        execution_time_ms=250
    )
    
    assert result == pathway_id
    
    # Verify database insert
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "INSERT INTO neural_pathways" in sql
    
    # Verify Chroma insert
    pathway_cache.collection.add.assert_called_once()
    call_args = pathway_cache.collection.add.call_args[1]
    assert call_args['ids'] == [pathway_id]
    assert call_args['embeddings'] == [goal_embedding]


def test_find_cached_pathway_hit(pathway_cache, mock_execution_store):
    """Test finding a cached pathway (cache hit)."""
    pathway_id = str(uuid4())
    goal_embedding = [0.1] * 384
    
    # Mock Chroma query
    pathway_cache.collection.query.return_value = {
        'ids': [[pathway_id]],
        'distances': [[0.1]]  # High similarity (1 - 0.1 = 0.9)
    }
    
    # Mock database query
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchall.return_value = [
        (
            pathway_id,
            "Get my recent Strava activities",
            json.dumps([{"step": 1, "action": "get_activities"}]),
            ["strava_get_my_activities_tool"],
            json.dumps({"activities": []}),
            5,  # success_count
            0,  # failure_count
            250,  # execution_time_ms
            True,  # is_valid
            None  # invalidation_reason
        )
    ]
    cursor.fetchone.return_value = (0.85,)  # confidence_score
    
    result = pathway_cache.find_cached_pathway(
        goal_text="Get my Strava activities",
        goal_embedding=goal_embedding,
        available_tools=["strava_get_my_activities_tool"]
    )
    
    assert result is not None
    assert result['pathway_id'] == pathway_id
    assert result['system'] == 1  # System 1 (cached)
    assert result['confidence_score'] == 0.85
    assert result['similarity_score'] == 0.9
    assert result['success_rate'] == 1.0


def test_find_cached_pathway_miss_no_results(pathway_cache):
    """Test cache miss when no similar pathways found."""
    goal_embedding = [0.1] * 384
    
    # Mock Chroma query with no results
    pathway_cache.collection.query.return_value = {
        'ids': [[]],
        'distances': [[]]
    }
    
    result = pathway_cache.find_cached_pathway(
        goal_text="Some new goal",
        goal_embedding=goal_embedding
    )
    
    assert result is None  # Cache miss


def test_find_cached_pathway_invalidated(pathway_cache, mock_execution_store):
    """Test that invalidated pathways are skipped."""
    pathway_id = str(uuid4())
    goal_embedding = [0.1] * 384
    
    # Mock Chroma query
    pathway_cache.collection.query.return_value = {
        'ids': [[pathway_id]],
        'distances': [[0.1]]
    }
    
    # Mock database query - pathway is invalid
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchall.return_value = [
        (
            pathway_id,
            "Get activities",
            json.dumps([{"step": 1}]),
            ["removed_tool"],
            json.dumps({}),
            5, 0, 250,
            False,  # is_valid = False
            "Tool removed"  # invalidation_reason
        )
    ]
    
    result = pathway_cache.find_cached_pathway(
        goal_text="Get activities",
        goal_embedding=goal_embedding
    )
    
    assert result is None  # Invalid pathway skipped


def test_find_cached_pathway_missing_tools(pathway_cache, mock_execution_store):
    """Test automatic invalidation when required tools are missing."""
    pathway_id = str(uuid4())
    goal_embedding = [0.1] * 384
    
    # Mock Chroma query
    pathway_cache.collection.query.return_value = {
        'ids': [[pathway_id]],
        'distances': [[0.1]]
    }
    
    # Mock database query - pathway uses tool that's now missing
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchall.return_value = [
        (
            pathway_id,
            "Get activities",
            json.dumps([{"step": 1}]),
            ["missing_tool", "available_tool"],  # One tool is missing
            json.dumps({}),
            5, 0, 250,
            True,  # is_valid = True (initially)
            None
        )
    ]
    
    result = pathway_cache.find_cached_pathway(
        goal_text="Get activities",
        goal_embedding=goal_embedding,
        available_tools=["available_tool"]  # missing_tool not in list
    )
    
    assert result is None  # Pathway skipped and invalidated
    
    # Verify invalidation was called
    assert any(
        "UPDATE neural_pathways" in str(call) and "is_valid = FALSE" in str(call)
        for call in cursor.execute.call_args_list
    )


def test_find_cached_pathway_low_confidence(pathway_cache, mock_execution_store):
    """Test that low confidence pathways are not used."""
    pathway_id = str(uuid4())
    goal_embedding = [0.1] * 384
    
    # Mock Chroma query
    pathway_cache.collection.query.return_value = {
        'ids': [[pathway_id]],
        'distances': [[0.1]]
    }
    
    # Mock database query - good similarity but low confidence
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchall.return_value = [
        (
            pathway_id,
            "Get activities",
            json.dumps([{"step": 1}]),
            ["tool1"],
            json.dumps({}),
            2, 3,  # success_count=2, failure_count=3 (40% success rate)
            250,
            True, None
        )
    ]
    cursor.fetchone.return_value = (0.40,)  # Low confidence (below 0.70 threshold)
    
    result = pathway_cache.find_cached_pathway(
        goal_text="Get activities",
        goal_embedding=goal_embedding,
        available_tools=["tool1"]
    )
    
    assert result is None  # Low confidence pathway not used


def test_update_pathway_result_success(pathway_cache, mock_execution_store):
    """Test updating pathway with successful execution."""
    pathway_id = str(uuid4())
    
    # Mock database function call
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchone.return_value = (True,)  # Function returns True
    
    result = pathway_cache.update_pathway_result(
        pathway_id=str(pathway_id),
        success=True,
        execution_time_ms=200
    )
    
    assert result is True
    
    # Verify database function was called
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "update_pathway_usage" in sql


def test_update_pathway_result_failure(pathway_cache, mock_execution_store):
    """Test updating pathway with failed execution."""
    pathway_id = str(uuid4())
    
    # Mock database function call
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchone.return_value = (True,)
    
    result = pathway_cache.update_pathway_result(
        pathway_id=str(pathway_id),
        success=False
    )
    
    assert result is True
    
    # Verify database function was called with success=False
    cursor.execute.assert_called_once()
    call_args = cursor.execute.call_args[0]
    # Check that False is in the parameters tuple
    assert call_args[1][1] == False  # Second parameter is success


def test_invalidate_pathways_for_tool(pathway_cache, mock_execution_store):
    """Test invalidating all pathways that use a specific tool."""
    tool_name = "removed_tool"
    
    # Mock database function call
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchone.return_value = (3,)  # 3 pathways invalidated
    
    result = pathway_cache.invalidate_pathways_for_tool(
        tool_name=tool_name,
        reason="Tool deprecated"
    )
    
    assert result == 3
    
    # Verify database function was called
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "invalidate_pathways_for_tool" in sql


def test_get_cache_stats(pathway_cache, mock_execution_store):
    """Test getting cache statistics."""
    # Mock database queries
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchone.return_value = (
        10,  # total_pathways
        8,   # valid_pathways
        2,   # invalid_pathways
        0.85,  # avg_success_rate
        300.0,  # avg_execution_time_ms
        100,  # total_successes
        15   # total_failures
    )
    cursor.fetchall.return_value = [
        ("data_retrieval", 5),
        ("data_analysis", 3)
    ]
    
    stats = pathway_cache.get_cache_stats()
    
    assert stats['total_pathways'] == 10
    assert stats['valid_pathways'] == 8
    assert stats['invalid_pathways'] == 2
    assert stats['avg_success_rate'] == 0.85
    assert stats['total_successes'] == 100
    assert stats['pathways_by_type']['data_retrieval'] == 5


def test_cleanup_old_pathways(pathway_cache, mock_execution_store):
    """Test cleaning up old invalidated pathways."""
    # Mock database function call
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchone.return_value = (5,)  # 5 pathways deleted
    
    result = pathway_cache.cleanup_old_pathways(days_old=90)
    
    assert result == 5
    
    # Verify database function was called
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "cleanup_old_invalidated_pathways" in sql


def test_calculate_context_hash(pathway_cache):
    """Test context hash calculation."""
    context1 = {"user": "alice", "limit": 10}
    context2 = {"limit": 10, "user": "alice"}  # Same content, different order
    context3 = {"user": "bob", "limit": 10}  # Different content
    
    hash1 = pathway_cache._calculate_context_hash(context1)
    hash2 = pathway_cache._calculate_context_hash(context2)
    hash3 = pathway_cache._calculate_context_hash(context3)
    
    assert hash1 == hash2  # Same content = same hash
    assert hash1 != hash3  # Different content = different hash
    assert len(hash1) == 64  # SHA256 hex length


def test_calculate_complexity_score(pathway_cache):
    """Test complexity score calculation."""
    # Simple pathway (1 step, 1 tool)
    simple_steps = [
        {"step": 1, "tool": "tool1", "action": "get_data"}
    ]
    simple_score = pathway_cache._calculate_complexity_score(simple_steps)
    assert 0.0 < simple_score < 0.3
    
    # Complex pathway (10 steps, 3 tools)
    complex_steps = [
        {"step": i, "tool": f"tool{i%3}", "action": "do_something"}
        for i in range(10)
    ]
    complex_score = pathway_cache._calculate_complexity_score(complex_steps)
    assert complex_score > simple_score
    assert complex_score <= 1.0


def test_store_pathway_with_all_parameters(pathway_cache, mock_execution_store):
    """Test storing pathway with all optional parameters."""
    pathway_id = str(uuid4())
    
    # Mock database insert
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchone.return_value = (pathway_id,)
    
    result = pathway_cache.store_pathway(
        goal_text="Complex goal",
        goal_embedding=[0.5] * 384,
        execution_steps=[{"step": 1}, {"step": 2}],
        final_result={"success": True},
        tool_names=["tool1", "tool2"],
        goal_type="data_analysis",
        context={"user": "alice", "limit": 20},
        execution_time_ms=500
    )
    
    assert result == pathway_id
    
    # Verify all parameters were passed to database
    call_args = cursor.execute.call_args[0]
    assert "data_analysis" in str(call_args)  # goal_type
    assert 500 in call_args[1]  # execution_time_ms


def test_find_cached_pathway_with_goal_type_filter(pathway_cache, mock_execution_store):
    """Test finding cached pathway with goal type filter."""
    pathway_id = str(uuid4())
    goal_embedding = [0.1] * 384
    
    # Mock Chroma query
    pathway_cache.collection.query.return_value = {
        'ids': [[pathway_id]],
        'distances': [[0.1]]
    }
    
    # Mock database query
    cursor = get_mock_cursor(mock_execution_store)
    cursor.fetchall.return_value = [
        (
            pathway_id, "Goal", json.dumps([{"step": 1}]),
            ["tool1"], json.dumps({}),
            3, 0, 250, True, None
        )
    ]
    cursor.fetchone.return_value = (0.90,)
    
    result = pathway_cache.find_cached_pathway(
        goal_text="Goal",
        goal_embedding=goal_embedding,
        goal_type="data_retrieval",
        available_tools=["tool1"]
    )
    
    # Verify Chroma query included goal_type filter
    pathway_cache.collection.query.assert_called_once()
    call_args = pathway_cache.collection.query.call_args[1]
    assert call_args['where'] == {"goal_type": "data_retrieval"}


def test_invalidate_pathway_directly(pathway_cache, mock_execution_store):
    """Test directly invalidating a specific pathway."""
    pathway_id = str(uuid4())
    
    result = pathway_cache._invalidate_pathway(
        pathway_id=str(pathway_id),
        reason="Test invalidation"
    )
    
    assert result is True
    
    # Verify database update
    cursor = get_mock_cursor(mock_execution_store)
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "UPDATE neural_pathways" in sql
    assert "is_valid = FALSE" in sql


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
