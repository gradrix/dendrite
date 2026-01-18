"""
Integration tests for the Mind Map (thought tree storage).

These tests verify that neurons can record and retrieve thoughts.
"""

import pytest
import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


# Check if we can import mind_map
try:
    from neural_engine.core.mind_map import (
        MindMap,
        ThoughtNode,
    )
    MIND_MAP_AVAILABLE = True
except ImportError as e:
    MIND_MAP_AVAILABLE = False
    IMPORT_ERROR = str(e)


def check_redis_available() -> bool:
    """Check if Redis is reachable."""
    try:
        import redis
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", 6379))
        r = redis.Redis(host=host, port=port, socket_timeout=2)
        r.ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def redis_available():
    """Skip tests if Redis is not available."""
    if not check_redis_available():
        pytest.skip("Redis not available")
    yield True


@pytest.fixture
def mind_map(redis_available):
    """Create a MindMap instance for testing."""
    if not MIND_MAP_AVAILABLE:
        pytest.skip(f"MindMap not available: {IMPORT_ERROR}")
    
    mm = MindMap()
    # Use test-specific key prefixes
    mm.NODE_PREFIX = "test:mind:node:"
    mm.TREE_PREFIX = "test:mind:tree:"
    mm.GOAL_PREFIX = "test:mind:goal:"
    mm.INDEX_KEY = "test:mind:index"
    return mm


@pytest.fixture
async def clean_map(mind_map):
    """MindMap with cleanup after test."""
    yield mind_map
    # Cleanup: delete test keys
    r = await mind_map._get_redis()
    keys = await r.keys("test:mind:*")
    if keys:
        await r.delete(*keys)


# =============================================================================
# Root Node Tests
# =============================================================================

class TestRootNode:
    """Test creating root nodes for goals."""
    
    @pytest.mark.asyncio
    async def test_create_root_node(self, clean_map):
        """Test creating a root thought node."""
        mm = clean_map
        
        node = await mm.create_root(
            goal_id="goal-123",
            goal_text="Create a REST API for user management",
        )
        
        assert node is not None
        assert node.node_id == "root_goal-123"
        assert node.goal_id == "goal-123"
    
    @pytest.mark.asyncio
    async def test_get_root_node(self, clean_map):
        """Test retrieving a root node."""
        mm = clean_map
        goal_id = "goal-get-root"
        
        await mm.create_root(
            goal_id=goal_id,
            goal_text="Build a CLI tool",
        )
        
        root = await mm.get_node(f"root_{goal_id}")
        
        assert root is not None
        assert root.goal_id == goal_id
        assert root.neuron_type == "Goal"
        assert "CLI tool" in root.input_data.get("goal", "")
    
    @pytest.mark.asyncio
    async def test_root_has_no_parent(self, clean_map):
        """Test that root nodes have no parent."""
        mm = clean_map
        goal_id = "goal-no-parent"
        
        await mm.create_root(goal_id=goal_id, goal_text="Test goal")
        root = await mm.get_node(f"root_{goal_id}")
        
        assert root.parent_id is None
        assert root.depth == 0


# =============================================================================
# Adding Thoughts Tests
# =============================================================================

class TestAddingThoughts:
    """Test adding child thoughts to the tree."""
    
    @pytest.mark.asyncio
    async def test_add_thought(self, clean_map):
        """Test adding a thought."""
        mm = clean_map
        goal_id = "goal-add-thought"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Test goal")
        
        node = await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="IntentClassifier",
            neuron_id="ic-123",
            input_data={"query": "test"},
            output_data={"intent": "tool_use"},
        )
        
        assert node is not None
        assert node.node_id != root.node_id
        assert node.parent_id == root.node_id
        assert node.depth == 1
    
    @pytest.mark.asyncio
    async def test_add_thought_with_reasoning(self, clean_map):
        """Test adding a thought with intermediate reasoning."""
        mm = clean_map
        goal_id = "goal-reasoning"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Test goal")
        
        node = await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="CodeGenerator",
            neuron_id="cg-123",
            input_data={"request": "create function"},
            thoughts=["Analyzing request", "Generating code", "Validating output"],
        )
        
        assert len(node.thoughts) == 3
        assert "Analyzing request" in node.thoughts
    
    @pytest.mark.asyncio
    async def test_add_nested_thoughts(self, clean_map):
        """Test adding deeply nested thoughts."""
        mm = clean_map
        goal_id = "goal-nested"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Build API")
        
        # Level 1
        level1 = await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="IntentClassifier",
            neuron_id="ic-1",
            input_data={"step": 1},
        )
        
        # Level 2
        level2 = await mm.add_thought(
            goal_id=goal_id,
            parent_id=level1.node_id,
            neuron_type="ToolSelector",
            neuron_id="ts-1",
            input_data={"step": 2},
        )
        
        # Level 3
        level3 = await mm.add_thought(
            goal_id=goal_id,
            parent_id=level2.node_id,
            neuron_type="CodeGenerator",
            neuron_id="cg-1",
            input_data={"step": 3},
        )
        
        # Verify depths
        assert level1.depth == 1
        assert level2.depth == 2
        assert level3.depth == 3
        
        # Verify parent links
        assert level3.parent_id == level2.node_id
        assert level2.parent_id == level1.node_id
        assert level1.parent_id == root.node_id
    
    @pytest.mark.asyncio
    async def test_add_failed_thought(self, clean_map):
        """Test adding a failed thought."""
        mm = clean_map
        goal_id = "goal-failed"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Test")
        
        node = await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="CodeGenerator",
            neuron_id="cg-fail",
            input_data={"code": "test"},
            status="failed",
            error="Syntax error on line 5",
        )
        
        assert node.status == "failed"
        assert "Syntax error" in node.error


# =============================================================================
# Tree Retrieval Tests
# =============================================================================

class TestTreeRetrieval:
    """Test retrieving the thought tree."""
    
    @pytest.mark.asyncio
    async def test_get_tree_flat(self, clean_map):
        """Test retrieving flat tree structure."""
        mm = clean_map
        goal_id = "goal-tree-flat"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Main goal")
        
        # Add multiple children
        await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="IntentClassifier",
            neuron_id="ic-1",
            input_data={"child": 1},
        )
        await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="ToolSelector",
            neuron_id="ts-1",
            input_data={"child": 2},
        )
        
        tree = await mm.get_tree(goal_id)
        
        assert len(tree) == 3  # root + 2 children
    
    @pytest.mark.asyncio
    async def test_get_tree_structured(self, clean_map):
        """Test getting nested tree structure."""
        mm = clean_map
        goal_id = "goal-tree-nested"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Main goal")
        
        child = await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="IntentClassifier",
            neuron_id="ic-1",
            input_data={},
        )
        
        await mm.add_thought(
            goal_id=goal_id,
            parent_id=child.node_id,
            neuron_type="ToolSelector",
            neuron_id="ts-1",
            input_data={},
        )
        
        tree = await mm.get_tree_structured(goal_id)
        
        assert tree is not None
        assert tree["neuron_type"] == "Goal"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["neuron_type"] == "IntentClassifier"
        assert len(tree["children"][0]["children"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_tree_empty_goal(self, clean_map):
        """Test getting tree for non-existent goal."""
        mm = clean_map
        
        tree = await mm.get_tree("nonexistent-goal")
        
        assert tree == []


# =============================================================================
# Short-Term Memory Tests
# =============================================================================

class TestShortTermMemory:
    """Test short-term memory (recent context) retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_short_term_memory(self, clean_map):
        """Test getting recent thoughts for context."""
        mm = clean_map
        goal_id = "goal-stm"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="STM test goal")
        
        # Add thoughts with summaries
        for i in range(5):
            await mm.add_thought(
                goal_id=goal_id,
                parent_id=root.node_id,
                neuron_type="IntentClassifier",
                neuron_id=f"ic-{i}",
                input_data={"index": i},
                thoughts=[f"Reasoning step {i}"],
            )
            await asyncio.sleep(0.01)  # Ensure ordering
        
        memory = await mm.get_short_term_memory(goal_id, max_thoughts=3)
        
        assert memory is not None
        assert len(memory) > 0
        assert "STM test goal" in memory or "IntentClassifier" in memory
    
    @pytest.mark.asyncio
    async def test_short_term_memory_empty(self, clean_map):
        """Test STM for goal with no thoughts."""
        mm = clean_map
        
        memory = await mm.get_short_term_memory("empty-goal")
        
        assert memory == ""


# =============================================================================
# Goal Status Tests
# =============================================================================

class TestGoalStatus:
    """Test marking goals as complete/failed."""
    
    @pytest.mark.asyncio
    async def test_mark_goal_completed(self, clean_map):
        """Test marking a goal as completed."""
        mm = clean_map
        goal_id = "goal-complete"
        
        await mm.create_root(goal_id=goal_id, goal_text="Complete me")
        await mm.complete_goal(goal_id, result={"output": "success"})
        
        root = await mm.get_node(f"root_{goal_id}")
        assert root.status == "completed"
        assert root.output_data.get("result", {}).get("output") == "success"
    
    @pytest.mark.asyncio
    async def test_mark_goal_failed(self, clean_map):
        """Test marking a goal as failed."""
        mm = clean_map
        goal_id = "goal-fail"
        
        await mm.create_root(goal_id=goal_id, goal_text="Fail me")
        await mm.fail_goal(goal_id, error="Timeout exceeded")
        
        root = await mm.get_node(f"root_{goal_id}")
        assert root.status == "failed"
        assert "Timeout" in root.error


# =============================================================================
# Node Update Tests
# =============================================================================

class TestNodeUpdate:
    """Test updating existing nodes."""
    
    @pytest.mark.asyncio
    async def test_update_node_output(self, clean_map):
        """Test updating node output after completion."""
        mm = clean_map
        goal_id = "goal-update"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Test")
        
        node = await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="CodeGenerator",
            neuron_id="cg-1",
            input_data={"request": "generate"},
            status="pending",
        )
        
        # Update with output
        updated = await mm.update_node(
            node.node_id,
            output_data={"code": "def hello(): pass"},
            status="completed",
            duration_ms=150.5,
        )
        
        assert updated.output_data.get("code") == "def hello(): pass"
        assert updated.status == "completed"
        assert updated.duration_ms == 150.5
    
    @pytest.mark.asyncio
    async def test_update_node_thoughts(self, clean_map):
        """Test adding thoughts to existing node."""
        mm = clean_map
        goal_id = "goal-thoughts"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Test")
        
        node = await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="CodeGenerator",
            neuron_id="cg-1",
            input_data={},
            thoughts=["Initial thought"],
        )
        
        # Update with more thoughts
        updated = await mm.update_node(
            node.node_id,
            thoughts=["Initial thought", "Second thought", "Final thought"],
        )
        
        assert len(updated.thoughts) == 3


# =============================================================================
# Stats and Recent Goals Tests
# =============================================================================

class TestStatsAndRecent:
    """Test statistics and recent goals."""
    
    @pytest.mark.asyncio
    async def test_get_recent_goals(self, clean_map):
        """Test getting recent goals."""
        mm = clean_map
        
        # Create several goals
        for i in range(5):
            await mm.create_root(
                goal_id=f"recent-goal-{i}",
                goal_text=f"Recent goal {i}",
            )
        
        recent = await mm.get_recent_goals(limit=10)
        
        assert len(recent) >= 5
    
    @pytest.mark.asyncio
    async def test_get_stats(self, clean_map):
        """Test getting mind map statistics."""
        mm = clean_map
        
        # Create some goals with different statuses
        await mm.create_root(goal_id="stats-1", goal_text="Test 1")
        await mm.create_root(goal_id="stats-2", goal_text="Test 2")
        await mm.complete_goal("stats-1", result="done")
        await mm.fail_goal("stats-2", error="oops")
        
        stats = await mm.get_stats()
        
        assert "total_goals" in stats
        assert stats["total_goals"] >= 2


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_node(self, clean_map):
        """Test getting a node that doesn't exist."""
        mm = clean_map
        
        node = await mm.get_node("nonexistent-node-id")
        
        assert node is None
    
    @pytest.mark.asyncio
    async def test_large_input_data(self, clean_map):
        """Test storing large input data."""
        mm = clean_map
        goal_id = "goal-large"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Large data test")
        
        large_data = {"code": "x" * 50000}  # 50KB
        
        node = await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="CodeGenerator",
            neuron_id="cg-1",
            input_data=large_data,
        )
        
        retrieved = await mm.get_node(node.node_id)
        assert len(retrieved.input_data.get("code", "")) == 50000
    
    @pytest.mark.asyncio
    async def test_unicode_content(self, clean_map):
        """Test storing unicode content."""
        mm = clean_map
        goal_id = "goal-unicode"
        
        root = await mm.create_root(
            goal_id=goal_id,
            goal_text="Unicode: 你好世界 🎉"
        )
        
        node = await mm.add_thought(
            goal_id=goal_id,
            parent_id=root.node_id,
            neuron_type="IntentClassifier",
            neuron_id="ic-1",
            input_data={"text": "Émojis: 🚀🔥💻 and ñ characters"},
        )
        
        retrieved = await mm.get_node(node.node_id)
        assert "🚀" in retrieved.input_data.get("text", "")
    
    @pytest.mark.asyncio
    async def test_concurrent_writes(self, clean_map):
        """Test concurrent writes to same goal."""
        mm = clean_map
        goal_id = "goal-concurrent"
        
        root = await mm.create_root(goal_id=goal_id, goal_text="Concurrent test")
        
        # Create many thoughts concurrently
        tasks = [
            mm.add_thought(
                goal_id=goal_id,
                parent_id=root.node_id,
                neuron_type="IntentClassifier",
                neuron_id=f"ic-{i}",
                input_data={"index": i},
            )
            for i in range(20)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 20
        assert all(r is not None for r in results)
        
        # Verify all stored
        tree = await mm.get_tree(goal_id)
        assert len(tree) >= 20
    
    @pytest.mark.asyncio
    async def test_clear(self, clean_map):
        """Test clearing all mind map data."""
        mm = clean_map
        
        # Create some data
        await mm.create_root(goal_id="clear-test", goal_text="To be cleared")
        
        # Clear
        await mm.clear()
        
        # Verify cleared
        tree = await mm.get_tree("clear-test")
        assert tree == []

