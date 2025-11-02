"""
Tests for Task Simplifier - Helping small LLMs by clarifying tasks.
"""

import pytest
from neural_engine.core.task_simplifier import TaskSimplifier


class TestTaskSimplifier:
    """Test task simplification for small LLMs."""
    
    def test_simplify_greeting_intent(self):
        """Test greeting is correctly classified as generative."""
        simplifier = TaskSimplifier()
        
        result = simplifier.simplify_for_intent_classification("Say hello")
        
        assert result["intent"] == "generative"
        assert result["confidence"] > 0.9
        assert "hello" in result["reasoning"].lower()
    
    def test_simplify_memory_write_intent(self):
        """Test storage is correctly classified as tool_use."""
        simplifier = TaskSimplifier()
        
        result = simplifier.simplify_for_intent_classification("Store my name is Alice")
        
        assert result["intent"] == "tool_use"
        assert result["confidence"] > 0.9
        assert result["keyword_matched"] == "store"
        assert "memory_write" in result["hints"]
    
    def test_simplify_memory_read_intent(self):
        """Test recall is correctly classified as tool_use."""
        simplifier = TaskSimplifier()
        
        result = simplifier.simplify_for_intent_classification("What did I tell you?")
        
        assert result["intent"] == "tool_use"
        assert result["confidence"] > 0.9
        assert result["keyword_matched"] == "what did i"
        assert "memory_read" in result["hints"]
    
    def test_narrow_tools_for_greeting(self):
        """Test tool narrowing for greeting."""
        simplifier = TaskSimplifier()
        all_tools = ["hello_world", "memory_write", "addition", "strava_get_activities"]
        
        result = simplifier.simplify_for_tool_selection("Say hello", all_tools)
        
        assert len(result["narrowed_tools"]) == 1
        assert "hello_world" in result["narrowed_tools"]
        assert result["confidence"] > 0.8
        assert "Use 'hello_world' tool" in result["explicit_hint"]
    
    def test_narrow_tools_for_memory_write(self):
        """Test tool narrowing for memory write."""
        simplifier = TaskSimplifier()
        all_tools = ["hello_world", "memory_write", "memory_read", "addition"]
        
        result = simplifier.simplify_for_tool_selection("Store my name is Alice", all_tools)
        
        assert "memory_write" in result["narrowed_tools"]
        assert "memory_write" in result["explicit_hint"]
        # Hint includes tool name at minimum
        assert len(result["explicit_hint"]) > 0
    
    def test_narrow_tools_for_memory_read(self):
        """Test tool narrowing for memory read."""
        simplifier = TaskSimplifier()
        all_tools = ["hello_world", "memory_write", "memory_read", "addition"]
        
        result = simplifier.simplify_for_tool_selection("What did I tell you?", all_tools)
        
        assert "memory_read" in result["narrowed_tools"]
        assert "memory_read" in result["explicit_hint"]
        # Hint includes tool name at minimum
        assert len(result["explicit_hint"]) > 0
    
    def test_narrow_tools_for_calculation(self):
        """Test tool narrowing for calculations."""
        simplifier = TaskSimplifier()
        all_tools = ["hello_world", "memory_write", "addition", "add_numbers"]
        
        result = simplifier.simplify_for_tool_selection("Add 5 and 3", all_tools)
        
        assert any(t in result["narrowed_tools"] for t in ["addition", "add_numbers"])
        assert "calculation" in result["explicit_hint"].lower()
    
    def test_narrow_tools_no_keywords(self):
        """Test behavior when no keywords match."""
        simplifier = TaskSimplifier()
        all_tools = ["hello_world", "memory_write", "addition"]
        
        result = simplifier.simplify_for_tool_selection("Do something weird", all_tools)
        
        # Even without clear keywords, simplifier tries to help
        # (it found "do" keyword which maps to hello_world)
        assert len(result["narrowed_tools"]) > 0
        assert result["confidence"] > 0  # Some confidence based on fuzzy matching
    
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
    
    def test_stats(self):
        """Test statistics reporting."""
        simplifier = TaskSimplifier()
        
        stats = simplifier.get_stats()
        
        assert stats["total_tool_mappings"] > 0
        assert stats["total_keywords"] > 0
        assert stats["mapped_tools"] > 0


class TestTaskSimplifierIntegration:
    """Integration tests showing how simplifier helps."""
    
    def test_greeting_flow(self):
        """Show complete flow for greeting."""
        simplifier = TaskSimplifier()
        
        # Step 1: Intent classification
        intent = simplifier.simplify_for_intent_classification("Say hello")
        assert intent["intent"] == "generative"
        
        # For generative, no tool selection needed
        # This bypasses the tool selection problem entirely!
    
    def test_memory_write_flow(self):
        """Show complete flow for memory write."""
        simplifier = TaskSimplifier()
        all_tools = ["hello_world", "memory_write", "memory_read", "addition"]
        
        # Step 1: Intent classification
        intent = simplifier.simplify_for_intent_classification("Store my name is Alice")
        assert intent["intent"] == "tool_use"
        assert intent["confidence"] > 0.9
        
        # Step 2: Tool narrowing (20 tools → 1 tool)
        tool_selection = simplifier.simplify_for_tool_selection("Store my name is Alice", all_tools)
        assert len(tool_selection["narrowed_tools"]) == 1
        assert tool_selection["narrowed_tools"][0] == "memory_write"
        
        # Small LLM now only needs to choose from 1 option!
        # Success rate should be ~100%
    
    def test_memory_read_flow(self):
        """Show complete flow for memory read."""
        simplifier = TaskSimplifier()
        all_tools = ["hello_world", "memory_write", "memory_read", "addition"]
        
        # Step 1: Intent
        intent = simplifier.simplify_for_intent_classification("What did I tell you?")
        assert intent["intent"] == "tool_use"
        
        # Step 2: Narrow tools
        tool_selection = simplifier.simplify_for_tool_selection("What did I tell you?", all_tools)
        assert "memory_read" in tool_selection["narrowed_tools"]
        assert len(tool_selection["narrowed_tools"]) <= 2  # Very focused
        
        # Small LLM gets explicit hint: "Use memory_read for retrieval"
        assert "memory_read" in tool_selection["explicit_hint"]
