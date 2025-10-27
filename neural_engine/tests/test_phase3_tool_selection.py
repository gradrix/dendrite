"""
Phase 3: Tool Selection Tests

This phase validates the ToolSelectorNeuron's ability to:
- Analyze user goals and match them to appropriate tools
- Query the ToolRegistry for available tools
- Use LLM to semantically match goals to tool capabilities
- Return tool metadata for code generation

Tests are organized into:
- Phase 3a: Tool Selection Basics (selecting correct tool for clear goals)
- Phase 3b: Tool Metadata Extraction (getting module/class info)
- Phase 3c: Semantic Matching (fuzzy/ambiguous goals)
- Phase 3d: Error Handling (no matching tool, invalid responses)
- Phase 3e: Integration (full pipeline with message bus)
"""

import pytest
import json
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.ollama_client import OllamaClient


@pytest.fixture
def message_bus():
    """Provide a MessageBus for testing"""
    return MessageBus()


@pytest.fixture
def ollama_client():
    """Provide an OllamaClient for testing"""
    return OllamaClient()


@pytest.fixture
def tool_registry():
    """Provide a ToolRegistry with all available tools"""
    return ToolRegistry(tool_directory="neural_engine/tools")


@pytest.fixture
def tool_selector(message_bus, ollama_client, tool_registry):
    """Provide a ToolSelectorNeuron for testing"""
    return ToolSelectorNeuron(message_bus, ollama_client, tool_registry)


class TestPhase3ToolSelectionBasics:
    """Phase 3a: Basic tool selection for clear goals"""
    
    def test_selector_loads_prompt(self, tool_selector):
        """ToolSelectorNeuron should load its prompt template"""
        prompt = tool_selector._load_prompt()
        
        assert prompt is not None, "Prompt should load"
        assert "{goal}" in prompt, "Prompt should have goal placeholder"
        assert "{tools}" in prompt, "Prompt should have tools placeholder"
        assert "JSON" in prompt, "Prompt should mention JSON format"
    
    @pytest.mark.integration
    def test_selector_chooses_hello_world_for_greeting(self, tool_selector, message_bus):
        """Should select hello_world tool for greeting-related goals"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Say hello to the world"
        
        result = tool_selector.process(goal_id, goal, depth=0)
        
        assert result is not None, "Should return result"
        assert "selected_tool_name" in result, "Should have selected tool name"
        assert result["selected_tool_name"] == "hello_world", "Should select hello_world tool"
    
    @pytest.mark.integration
    def test_selector_chooses_memory_read_for_recall(self, tool_selector, message_bus):
        """Should select memory_read tool for memory retrieval goals"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Remember what I told you about my favorite color"
        
        result = tool_selector.process(goal_id, goal, depth=0)
        
        assert result is not None, "Should return result"
        assert result["selected_tool_name"] == "memory_read", "Should select memory_read tool"
    
    @pytest.mark.integration
    def test_selector_chooses_memory_write_for_storage(self, tool_selector, message_bus):
        """Should select memory_write tool for storing information"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Remember that my favorite color is blue"
        
        result = tool_selector.process(goal_id, goal, depth=0)
        
        assert result is not None, "Should return result"
        assert result["selected_tool_name"] == "memory_write", "Should select memory_write tool"


class TestPhase3ToolMetadata:
    """Phase 3b: Test tool metadata extraction for code generation"""
    
    @pytest.mark.integration
    def test_selector_returns_module_name(self, tool_selector, message_bus):
        """Selected tool should include module_name for import"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Say hello"
        
        result = tool_selector.process(goal_id, goal, depth=0)
        
        assert "selected_tool_module" in result, "Should include module name"
        assert "neural_engine.tools" in result["selected_tool_module"], "Should be in tools directory"
        assert "hello_world" in result["selected_tool_module"], "Should reference hello_world module"
    
    @pytest.mark.integration
    def test_selector_returns_class_name(self, tool_selector, message_bus):
        """Selected tool should include class_name for instantiation"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Say hello"
        
        result = tool_selector.process(goal_id, goal, depth=0)
        
        assert "selected_tool_class" in result, "Should include class name"
        assert "Tool" in result["selected_tool_class"], "Class name should end with 'Tool'"
    
    @pytest.mark.integration
    def test_selector_returns_goal(self, tool_selector, message_bus):
        """Result should include the original goal"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Test goal for metadata"
        
        result = tool_selector.process(goal_id, goal, depth=0)
        
        assert result["goal"] == goal, "Should preserve original goal"


class TestPhase3SemanticMatching:
    """Phase 3c: Test semantic matching for ambiguous goals"""
    
    @pytest.mark.integration
    def test_selector_handles_strava_activity_query(self, tool_selector, message_bus):
        """Should select appropriate Strava tool for activity queries"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Show me my recent runs from last week"
        
        result = tool_selector.process(goal_id, goal, depth=0)
        
        assert result is not None, "Should return result"
        # Should select one of the Strava activity tools
        assert "strava" in result["selected_tool_name"], "Should select a Strava tool"
        assert "activities" in result["selected_tool_name"] or "activity" in result["selected_tool_name"], \
            "Should be an activity-related tool"
    
    @pytest.mark.integration
    def test_selector_distinguishes_read_vs_write(self, tool_selector, message_bus):
        """Should distinguish between read and write operations"""
        # Test write operation
        goal_id_write = message_bus.get_new_goal_id()
        goal_write = "Save this information: my favorite food is pizza"
        result_write = tool_selector.process(goal_id_write, goal_write, depth=0)
        
        # Test read operation
        goal_id_read = message_bus.get_new_goal_id()
        goal_read = "What is my favorite food?"
        result_read = tool_selector.process(goal_id_read, goal_read, depth=0)
        
        # Should select different tools for read vs write
        assert result_write["selected_tool_name"] != result_read["selected_tool_name"], \
            "Should select different tools for read vs write"
        assert "write" in result_write["selected_tool_name"], "Write goal should select write tool"
        assert "read" in result_read["selected_tool_name"], "Read goal should select read tool"
    
    @pytest.mark.integration
    def test_selector_handles_script_execution_goal(self, tool_selector, message_bus):
        """Should select python_script tool for code execution goals"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Run a Python script to calculate the sum of 1 to 100"
        
        result = tool_selector.process(goal_id, goal, depth=0)
        
        assert result is not None, "Should return result"
        assert result["selected_tool_name"] == "python_script", "Should select python_script tool"


class TestPhase3MessageBusIntegration:
    """Phase 3d: Test message bus integration"""
    
    @pytest.mark.integration
    def test_selector_stores_result_in_message_bus(self, tool_selector, message_bus):
        """ToolSelectorNeuron should store selection in message bus"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Say hello"
        
        tool_selector.process(goal_id, goal, depth=0)
        
        # Retrieve from message bus
        stored_result = message_bus.get_message(goal_id, "tool_selection")
        
        assert stored_result is not None, "Should store result in message bus"
        assert stored_result["selected_tool_name"] == "hello_world", "Should store correct tool"
    
    @pytest.mark.integration
    def test_selector_result_contains_all_fields(self, tool_selector, message_bus):
        """Stored result should have all necessary fields"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Say hello"
        
        tool_selector.process(goal_id, goal, depth=0)
        stored_result = message_bus.get_message(goal_id, "tool_selection")
        
        required_fields = ["goal", "selected_tool_name", "selected_tool_module", "selected_tool_class"]
        for field in required_fields:
            assert field in stored_result, f"Result should have '{field}' field"


class TestPhase3ErrorHandling:
    """Phase 3e: Test error handling"""
    
    def test_selector_raises_error_for_nonexistent_tool(self, tool_selector, message_bus, monkeypatch):
        """Should raise error if LLM selects a tool that doesn't exist"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Test goal"
        
        # Mock LLM to return invalid tool
        def mock_generate(prompt):
            return {"response": '{"tool_name": "nonexistent_tool_xyz"}'}
        
        monkeypatch.setattr(tool_selector.ollama_client, "generate", mock_generate)
        
        with pytest.raises(ValueError, match="not found in registry"):
            tool_selector.process(goal_id, goal, depth=0)
    
    def test_selector_has_access_to_tool_registry(self, tool_selector):
        """ToolSelectorNeuron should have tool_registry attribute"""
        assert hasattr(tool_selector, "tool_registry"), "Should have tool_registry"
        assert tool_selector.tool_registry is not None, "tool_registry should not be None"
    
    def test_selector_can_query_all_tools(self, tool_selector):
        """Should be able to query all available tools from registry"""
        tools = tool_selector.tool_registry.get_all_tool_definitions()
        
        assert len(tools) > 0, "Should have access to tools"
        assert "hello_world" in tools, "Should include hello_world in available tools"


class TestPhase3ToolSelectionIntegration:
    """Phase 3f: Full integration tests"""
    
    @pytest.mark.integration
    def test_full_selection_pipeline(self, tool_selector, message_bus):
        """Test complete flow: goal → selection → metadata → storage"""
        goal_id = message_bus.get_new_goal_id()
        goal = "Say hello to everyone"
        
        # 1. Process goal
        result = tool_selector.process(goal_id, goal, depth=0)
        
        # 2. Verify result structure
        assert result["goal"] == goal, "Should preserve goal"
        assert result["selected_tool_name"] is not None, "Should select a tool"
        assert result["selected_tool_module"] is not None, "Should have module info"
        assert result["selected_tool_class"] is not None, "Should have class info"
        
        # 3. Verify storage
        stored = message_bus.get_message(goal_id, "tool_selection")
        assert stored == result, "Stored result should match returned result"
        
        # 4. Verify tool actually exists in registry
        tool = tool_selector.tool_registry.get_tool(result["selected_tool_name"])
        assert tool is not None, "Selected tool should exist in registry"
    
    @pytest.mark.integration
    def test_selector_with_multiple_tool_options(self, tool_selector, message_bus):
        """Should choose most appropriate tool when multiple options exist"""
        goal_id = message_bus.get_new_goal_id()
        # This goal could match memory_read or other tools - should pick the most appropriate
        goal = "What do you remember about me?"
        
        result = tool_selector.process(goal_id, goal, depth=0)
        
        # Should select a memory-related tool (most appropriate for recall)
        assert "memory" in result["selected_tool_name"] or "read" in result["selected_tool_name"], \
            "Should select memory-related tool for recall query"


# Batch test for specific goal-tool mappings
@pytest.mark.integration
@pytest.mark.parametrize("goal,expected_tool_substring", [
    ("Say hello", "hello"),
    ("Store my name is Alice", "memory_write"),
    ("What did I tell you?", "memory_read"),
])
def test_tool_selection_accuracy(goal, expected_tool_substring, tool_selector, message_bus):
    """Verify tool selection accuracy for various goals"""
    goal_id = message_bus.get_new_goal_id()
    
    result = tool_selector.process(goal_id, goal, depth=0)
    
    assert expected_tool_substring in result["selected_tool_name"], \
        f"Goal '{goal}' should select tool containing '{expected_tool_substring}', got '{result['selected_tool_name']}'"
