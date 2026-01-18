"""
Tests for Task Simplifier - Helping small LLMs by clarifying tasks.

REFACTORED: Uses semantic tool discovery instead of keywords.
"""

import pytest
from neural_engine.core.task_simplifier import TaskSimplifier
from neural_engine.core.tool_discovery import ToolDiscovery
from neural_engine.core.tool_registry import ToolRegistry


@pytest.fixture
def tool_registry():
    """Provide a ToolRegistry with all tools."""
    return ToolRegistry(tool_directory="neural_engine/tools")


@pytest.fixture
def tool_discovery(tool_registry):
    """Provide a ToolDiscovery with indexed tools."""
    discovery = ToolDiscovery(tool_registry)
    discovery.index_all_tools()
    return discovery


class TestTaskSimplifier:
    """Test task simplification for small LLMs using semantic discovery."""
    
    def test_simplify_greeting_intent(self, tool_discovery):
        """Test greeting is correctly classified - semantic matching."""
        simplifier = TaskSimplifier(tool_discovery)
        
        result = simplifier.simplify_for_intent_classification("Say hello")
        
        # With semantic search, "Say hello" matches hello_world tool
        assert result["intent"] == "tool_use"
        assert result["confidence"] > 0.5
        assert "hints" in result
        assert "hello_world" in result["hints"]
    
    def test_simplify_memory_write_intent(self, tool_discovery):
        """Test storage is correctly classified as tool_use."""
        simplifier = TaskSimplifier(tool_discovery)
        
        result = simplifier.simplify_for_intent_classification("Store my name is Alice")
        
        assert result["intent"] == "tool_use"
        assert result["confidence"] > 0.5
        assert "memory_write" in result["hints"]
    
    def test_simplify_memory_read_intent(self, tool_discovery):
        """Test recall is correctly classified as tool_use."""
        simplifier = TaskSimplifier(tool_discovery)
        
        # Use a query that clearly matches memory_read semantics
        result = simplifier.simplify_for_intent_classification("Recall what I stored earlier")
        
        assert result["intent"] == "tool_use"
        assert result["confidence"] > 0.5
        assert any("memory" in hint for hint in result["hints"])
    
    def test_narrow_tools_for_greeting(self, tool_discovery):
        """Test tool narrowing for greeting using semantic search."""
        simplifier = TaskSimplifier(tool_discovery)
        all_tools = ["hello_world", "memory_write", "addition", "strava_get_my_activities"]
        
        result = simplifier.simplify_for_tool_selection("Say hello", all_tools)
        
        assert "hello_world" in result["narrowed_tools"]
        assert result["confidence"] > 0.5
        assert len(result["explicit_hint"]) > 0
    
    def test_narrow_tools_for_memory_write(self, tool_discovery):
        """Test tool narrowing for memory write."""
        simplifier = TaskSimplifier(tool_discovery)
        all_tools = ["hello_world", "memory_write", "memory_read", "addition"]
        
        result = simplifier.simplify_for_tool_selection("Store my name is Alice", all_tools)
        
        assert "memory_write" in result["narrowed_tools"]
        assert len(result["explicit_hint"]) > 0
    
    def test_narrow_tools_for_memory_read(self, tool_discovery):
        """Test tool narrowing for memory read."""
        simplifier = TaskSimplifier(tool_discovery)
        all_tools = ["hello_world", "memory_write", "memory_read", "addition"]
        
        result = simplifier.simplify_for_tool_selection("What did I tell you?", all_tools)
        
        # Semantic search should find memory-related tools
        assert any("memory" in t for t in result["narrowed_tools"])
        assert len(result["explicit_hint"]) > 0
    
    def test_narrow_tools_for_calculation(self, tool_discovery):
        """Test tool narrowing for calculations."""
        simplifier = TaskSimplifier(tool_discovery)
        all_tools = ["hello_world", "memory_write", "addition", "add_numbers", "add"]
        
        result = simplifier.simplify_for_tool_selection("Add 5 and 3", all_tools)
        
        # Semantic search should find math/calculation tools
        assert any(t in result["narrowed_tools"] for t in ["addition", "add_numbers", "add"])
        assert len(result["explicit_hint"]) > 0
    
    def test_narrow_tools_no_match(self, tool_discovery):
        """Test behavior when no semantic match found."""
        simplifier = TaskSimplifier(tool_discovery)
        all_tools = ["hello_world", "memory_write", "addition"]
        
        result = simplifier.simplify_for_tool_selection("xyz123 gibberish query", all_tools)
        
        # Should still return tools (either semantic guesses or all tools)
        assert len(result["narrowed_tools"]) > 0
    
    def test_code_generation_simplification(self):
        """Test code generation simplification."""
        simplifier = TaskSimplifier()
        
        tool_def = {
            "module_name": "hello_world_tool",
            "class_name": "HelloWorldTool"
        }
        
        result = simplifier.simplify_for_code_generation(
            "Say hello",
            "hello_world",
            tool_def
        )
        
        assert "template_hint" in result
        assert "HelloWorldTool" in result["template_hint"]
        assert "sandbox.set_result" in result["template_hint"]
    
    def test_stats_semantic_mode(self, tool_discovery):
        """Test statistics reporting in semantic mode."""
        simplifier = TaskSimplifier(tool_discovery)
        
        stats = simplifier.get_stats()
        
        assert stats["mode"] == "semantic"
        assert stats["tool_discovery_available"] is True
    
    def test_stats_fallback_mode(self):
        """Test statistics reporting in fallback mode."""
        simplifier = TaskSimplifier()  # No tool discovery
        
        stats = simplifier.get_stats()
        
        assert stats["mode"] == "fallback"
        assert stats["tool_discovery_available"] is False


class TestTaskSimplifierIntegration:
    """Integration tests showing how simplifier helps with semantic search."""
    
    def test_greeting_flow(self, tool_discovery):
        """Show complete flow for greeting with semantic matching."""
        simplifier = TaskSimplifier(tool_discovery)
        
        # Intent classification - "Say hello" matches hello_world semantically
        intent = simplifier.simplify_for_intent_classification("Say hello")
        
        # Semantic search finds hello_world tool
        assert intent["intent"] == "tool_use"
        assert "hello_world" in intent.get("hints", [])
    
    def test_memory_write_flow(self, tool_discovery):
        """Show complete flow for memory write."""
        simplifier = TaskSimplifier(tool_discovery)
        all_tools = ["hello_world", "memory_write", "memory_read", "addition"]
        
        # Step 1: Intent classification
        intent = simplifier.simplify_for_intent_classification("Store my name is Alice")
        assert intent["intent"] == "tool_use"
        
        # Step 2: Tool narrowing via semantic search
        tool_selection = simplifier.simplify_for_tool_selection("Store my name is Alice", all_tools)
        assert "memory_write" in tool_selection["narrowed_tools"]
    
    def test_memory_read_flow(self, tool_discovery):
        """Show complete flow for memory read."""
        simplifier = TaskSimplifier(tool_discovery)
        all_tools = ["hello_world", "memory_write", "memory_read", "addition"]
        
        # Step 1: Intent - use a query that matches memory semantics
        intent = simplifier.simplify_for_intent_classification("Recall my stored information")
        assert intent["intent"] == "tool_use"
        
        # Step 2: Narrow tools via semantic search
        tool_selection = simplifier.simplify_for_tool_selection("Recall my stored information", all_tools)
        assert any("memory" in t for t in tool_selection["narrowed_tools"])
