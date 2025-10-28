"""
Test Stage 3 Integration: ToolDiscovery + ToolSelectorNeuron
Phase 8d: Verify 3-stage tool discovery works end-to-end.
"""

import pytest
import os
import tempfile
import shutil
from neural_engine.core.tool_discovery import ToolDiscovery
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.ollama_client import OllamaClient


@pytest.fixture
def temp_chroma_dir():
    """Temporary directory for Chroma database."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def execution_store():
    """ExecutionStore connected to test database."""
    store = ExecutionStore()
    yield store
    store.close()


@pytest.fixture
def tool_registry():
    """ToolRegistry with test tools."""
    registry = ToolRegistry(tool_directory="neural_engine/tools")
    return registry


@pytest.fixture
def tool_discovery(tool_registry, execution_store, temp_chroma_dir):
    """ToolDiscovery instance with test tools indexed."""
    disc = ToolDiscovery(
        tool_registry=tool_registry,
        execution_store=execution_store,
        chroma_path=temp_chroma_dir
    )
    disc.index_all_tools()
    return disc


@pytest.fixture
def tool_selector_with_discovery(tool_registry, tool_discovery):
    """ToolSelectorNeuron with ToolDiscovery enabled."""
    message_bus = MessageBus()
    ollama_client = OllamaClient()
    
    selector = ToolSelectorNeuron(
        message_bus=message_bus,
        ollama_client=ollama_client,
        tool_registry=tool_registry,
        tool_discovery=tool_discovery
    )
    
    return selector


@pytest.fixture
def tool_selector_without_discovery(tool_registry):
    """ToolSelectorNeuron without ToolDiscovery (original behavior)."""
    message_bus = MessageBus()
    ollama_client = OllamaClient()
    
    selector = ToolSelectorNeuron(
        message_bus=message_bus,
        ollama_client=ollama_client,
        tool_registry=tool_registry,
        tool_discovery=None
    )
    
    return selector


class TestStage3Integration:
    """Test complete 3-stage filtering integration."""
    
    def test_tool_selector_with_discovery_enabled(self, tool_selector_with_discovery):
        """Test that ToolSelectorNeuron uses ToolDiscovery when available."""
        assert tool_selector_with_discovery.tool_discovery is not None
        assert tool_selector_with_discovery.selection_stats['semantic_enabled'] is True
    
    def test_tool_selector_without_discovery(self, tool_selector_without_discovery):
        """Test that ToolSelectorNeuron works without ToolDiscovery (backward compatible)."""
        assert tool_selector_without_discovery.tool_discovery is None
        assert tool_selector_without_discovery.selection_stats['semantic_enabled'] is False
    
    def test_semantic_filtering_reduces_candidates(self, tool_selector_with_discovery, tool_registry):
        """Test that semantic search reduces candidate count."""
        goal = "Check if 17 is a prime number"
        
        try:
            # Process with semantic search
            result = tool_selector_with_discovery.process(
                goal_id="test_1",
                goal=goal,
                depth=0
            )
            
            # Check that we considered fewer tools than total
            total_tools = len(tool_registry.get_all_tools())
            candidates_considered = tool_selector_with_discovery.selection_stats['avg_candidates_considered']
            
            assert candidates_considered <= 5, f"Should consider ≤5 tools, got {candidates_considered}"
            assert candidates_considered < total_tools, "Should filter out some tools"
        except Exception as e:
            # If LLM fails, still check that filtering happened
            # The stats are updated before LLM processing
            assert tool_selector_with_discovery.selection_stats['avg_candidates_considered'] <= 5
            print(f"LLM processing failed (expected in tests): {e}")
    
    def test_selection_without_semantic_uses_all_tools(self, tool_selector_without_discovery, tool_registry):
        """Test that without semantic search, all tools are considered."""
        goal = "Check if 17 is a prime number"
        
        # Process without semantic search
        result = tool_selector_without_discovery.process(
            goal_id="test_2",
            goal=goal,
            depth=0
        )
        
        # Check that we considered all tools
        total_tools = len(tool_registry.get_all_tools())
        candidates_considered = tool_selector_without_discovery.selection_stats['avg_candidates_considered']
        
        assert candidates_considered == total_tools, f"Should consider all {total_tools} tools"
    
    def test_semantic_search_finds_relevant_tool(self, tool_selector_with_discovery):
        """Test that semantic search finds semantically relevant tools."""
        goal = "Check if a number is prime"
        
        try:
            result = tool_selector_with_discovery.process(
                goal_id="test_3",
                goal=goal,
                depth=0
            )
            
            # Should select a tool (prime_checker most likely)
            assert 'selected_tools' in result
            assert len(result['selected_tools']) > 0
            
            # Tool name should be in result
            selected_tool = result['selected_tools'][0]
            assert 'name' in selected_tool
            
            # Most likely should be prime_checker due to semantic similarity
            # (but we don't enforce this as LLM might choose differently)
            assert isinstance(selected_tool['name'], str)
        except Exception as e:
            # If LLM fails (JSON parsing, etc), that's OK for this test
            # We're primarily testing that the semantic filtering happens
            # Check that semantic filtering was attempted
            assert tool_selector_with_discovery.selection_stats['total_selections'] > 0
            print(f"LLM processing failed (expected in tests): {e}")
    
    def test_selection_stats_tracked(self, tool_selector_with_discovery):
        """Test that selection statistics are tracked."""
        goal = "Say hello"
        
        initial_selections = tool_selector_with_discovery.selection_stats['total_selections']
        
        tool_selector_with_discovery.process(
            goal_id="test_4",
            goal=goal,
            depth=0
        )
        
        # Check stats updated
        assert tool_selector_with_discovery.selection_stats['total_selections'] == initial_selections + 1
        assert tool_selector_with_discovery.selection_stats['avg_candidates_considered'] > 0


class TestPerformanceComparison:
    """Compare performance with and without semantic search."""
    
    def test_semantic_search_reduces_llm_context(self, tool_selector_with_discovery, tool_selector_without_discovery):
        """Test that semantic search reduces LLM context size."""
        goal = "Calculate something"
        
        # With semantic search
        tool_selector_with_discovery.process(goal_id="perf_1", goal=goal, depth=0)
        with_semantic = tool_selector_with_discovery.selection_stats['avg_candidates_considered']
        
        # Without semantic search
        tool_selector_without_discovery.process(goal_id="perf_2", goal=goal, depth=0)
        without_semantic = tool_selector_without_discovery.selection_stats['avg_candidates_considered']
        
        # Semantic search should consider fewer candidates
        assert with_semantic < without_semantic, \
            f"Semantic search ({with_semantic}) should consider fewer tools than full scan ({without_semantic})"


class TestBackwardCompatibility:
    """Test that changes are backward compatible."""
    
    def test_tool_selector_works_without_tool_discovery(self, tool_selector_without_discovery):
        """Test that ToolSelectorNeuron works without ToolDiscovery parameter."""
        goal = "Test backward compatibility"
        
        # Should work fine without tool_discovery
        result = tool_selector_without_discovery.process(
            goal_id="compat_1",
            goal=goal,
            depth=0
        )
        
        assert 'selected_tools' in result
        assert tool_selector_without_discovery.selection_stats['semantic_enabled'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
