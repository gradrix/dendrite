"""
Phase 2: Tool Registry & Discovery Tests

This phase validates the ToolRegistry's ability to:
- Discover tools from the tools/ directory
- Extract and validate tool metadata (name, description, parameters)
- Register tools properly
- Query tools by name
- List all available tools

Tests are organized into:
- Phase 2a: Tool Discovery (scanning tools/ directory)
- Phase 2b: Tool Metadata (validating tool definitions)
- Phase 2c: Tool Registration (proper storage and retrieval)
- Phase 2d: Tool Querying (finding tools by name/capability)
"""

import pytest
import os
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.tools.base_tool import BaseTool


class TestPhase2ToolDiscovery:
    """Phase 2a: Test tool discovery from filesystem"""

    def test_registry_discovers_tools(self):
        """ToolRegistry should discover all valid tool files in tools/ directory"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        tools = registry.get_all_tools()
        
        # We have at least the hello_world tool
        assert len(tools) > 0, "Registry should discover at least one tool"
        
    def test_registry_ignores_base_tool(self):
        """ToolRegistry should not register the abstract BaseTool class"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        tools = registry.get_all_tools()
        
        # Check that no tool is named 'base_tool' or similar
        for tool_name in tools.keys():
            assert 'base' not in tool_name.lower(), "Registry should skip BaseTool"
    
    def test_registry_discovers_hello_world_tool(self):
        """ToolRegistry should specifically find the HelloWorldTool"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        
        hello_tool = registry.get_tool("hello_world")
        assert hello_tool is not None, "Registry should find hello_world tool"
    
    def test_registry_discovers_multiple_tools(self):
        """ToolRegistry should discover multiple tool files"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        tools = registry.get_all_tools()
        
        # We have hello_world, memory_read, memory_write, python_script, strava tools, etc.
        assert len(tools) >= 5, f"Registry should find at least 5 tools, found {len(tools)}"
        
    def test_registry_refresh_reloads_tools(self):
        """Registry.refresh() should reload all tools"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        
        initial_count = len(registry.get_all_tools())
        registry.refresh()
        refreshed_count = len(registry.get_all_tools())
        
        assert refreshed_count == initial_count, "Refresh should maintain tool count"


class TestPhase2ToolMetadata:
    """Phase 2b: Test tool metadata extraction and validation"""
    
    def test_tool_has_required_fields(self):
        """Each tool definition should have name and description"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        definitions = registry.get_all_tool_definitions()
        
        for tool_name, tool_def in definitions.items():
            assert "name" in tool_def, f"Tool {tool_name} missing 'name' field"
            assert "description" in tool_def, f"Tool {tool_name} missing 'description' field"
            assert isinstance(tool_def["name"], str), f"Tool {tool_name} name should be string"
            assert isinstance(tool_def["description"], str), f"Tool {tool_name} description should be string"
    
    def test_hello_world_metadata(self):
        """HelloWorldTool should have correct metadata"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        hello_tool = registry.get_tool("hello_world")
        
        assert hello_tool is not None, "HelloWorldTool should exist"
        
        definition = hello_tool.get_tool_definition()
        assert definition["name"] == "hello_world"
        assert "greeting" in definition["description"].lower() or "hello" in definition["description"].lower()
        assert "parameters" in definition
    
    def test_tool_definitions_include_module_info(self):
        """Tool definitions should include module_name and class_name for code generation"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        definitions = registry.get_all_tool_definitions()
        
        for tool_name, tool_def in definitions.items():
            assert "module_name" in tool_def, f"Tool {tool_name} missing 'module_name'"
            assert "class_name" in tool_def, f"Tool {tool_name} missing 'class_name'"
            assert "neural_engine.tools" in tool_def["module_name"], f"Tool {tool_name} has invalid module_name"
    
    def test_tool_parameters_structure(self):
        """Tool parameters should be properly structured"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        definitions = registry.get_all_tool_definitions()
        
        for tool_name, tool_def in definitions.items():
            assert "parameters" in tool_def, f"Tool {tool_name} missing 'parameters' field"
            params = tool_def["parameters"]
            assert isinstance(params, (list, dict)), f"Tool {tool_name} parameters should be list or dict"


class TestPhase2ToolRegistration:
    """Phase 2c: Test tool registration and storage"""
    
    def test_get_tool_returns_instance(self):
        """get_tool() should return a BaseTool instance"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        hello_tool = registry.get_tool("hello_world")
        
        assert hello_tool is not None, "Should return tool instance"
        assert isinstance(hello_tool, BaseTool), "Should be instance of BaseTool"
    
    def test_get_tool_returns_none_for_missing(self):
        """get_tool() should return None for non-existent tools"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        fake_tool = registry.get_tool("nonexistent_tool_xyz")
        
        assert fake_tool is None, "Should return None for missing tool"
    
    def test_get_all_tools_returns_dict(self):
        """get_all_tools() should return dictionary of tool_name -> tool_instance"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        tools = registry.get_all_tools()
        
        assert isinstance(tools, dict), "get_all_tools should return dict"
        for tool_name, tool_instance in tools.items():
            assert isinstance(tool_name, str), "Tool name should be string"
            assert isinstance(tool_instance, BaseTool), "Tool value should be BaseTool instance"
    
    def test_get_all_tool_definitions_returns_dict(self):
        """get_all_tool_definitions() should return dictionary of tool_name -> tool_definition"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        definitions = registry.get_all_tool_definitions()
        
        assert isinstance(definitions, dict), "get_all_tool_definitions should return dict"
        for tool_name, tool_def in definitions.items():
            assert isinstance(tool_name, str), "Tool name should be string"
            assert isinstance(tool_def, dict), "Tool definition should be dict"


class TestPhase2ToolQuerying:
    """Phase 2d: Test tool querying and lookup capabilities"""
    
    def test_query_tool_by_exact_name(self):
        """Should be able to query tool by exact name"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        
        hello_tool = registry.get_tool("hello_world")
        assert hello_tool is not None, "Should find tool by exact name"
    
    def test_query_all_tool_names(self):
        """Should be able to get list of all tool names"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        tools = registry.get_all_tools()
        
        tool_names = list(tools.keys())
        assert len(tool_names) > 0, "Should have tool names"
        assert "hello_world" in tool_names, "Should include hello_world in names"
    
    def test_query_tools_by_category(self):
        """Should be able to identify tool categories (strava, memory, etc.)"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        definitions = registry.get_all_tool_definitions()
        
        # Find strava tools
        strava_tools = [name for name in definitions.keys() if "strava" in name]
        assert len(strava_tools) > 0, "Should find strava tools"
        
        # Find memory tools
        memory_tools = [name for name in definitions.keys() if "memory" in name]
        assert len(memory_tools) > 0, "Should find memory tools"
    
    def test_tool_can_be_executed(self):
        """Retrieved tools should be executable"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        hello_tool = registry.get_tool("hello_world")
        
        assert hello_tool is not None, "Tool should exist"
        result = hello_tool.execute()
        
        assert result is not None, "Tool should return result"
        assert isinstance(result, dict), "Tool should return dict"
        assert "message" in result, "HelloWorld should return message"


class TestPhase2ToolIntegration:
    """Phase 2e: Integration tests for complete tool registry flow"""
    
    def test_full_tool_lifecycle(self):
        """Test complete flow: discover -> register -> query -> execute"""
        # 1. Discovery
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        
        # 2. Registration (automatic in __init__)
        tools = registry.get_all_tools()
        assert len(tools) > 0, "Tools should be registered"
        
        # 3. Query
        hello_tool = registry.get_tool("hello_world")
        assert hello_tool is not None, "Tool should be queryable"
        
        # 4. Execute
        result = hello_tool.execute()
        assert "message" in result, "Tool should be executable"
        assert "Hello" in result["message"], "Tool should produce correct output"
    
    def test_registry_tools_are_reusable(self):
        """Tools from registry should be reusable across multiple calls"""
        registry = ToolRegistry(tool_directory="neural_engine/tools")
        hello_tool = registry.get_tool("hello_world")
        
        # Execute multiple times
        result1 = hello_tool.execute()
        result2 = hello_tool.execute()
        result3 = hello_tool.execute()
        
        # All should succeed
        assert result1 == result2 == result3, "Tool should be consistently reusable"
    
    def test_multiple_registries_independent(self):
        """Multiple ToolRegistry instances should be independent"""
        registry1 = ToolRegistry(tool_directory="neural_engine/tools")
        registry2 = ToolRegistry(tool_directory="neural_engine/tools")
        
        tools1 = registry1.get_all_tools()
        tools2 = registry2.get_all_tools()
        
        # Same tool count
        assert len(tools1) == len(tools2), "Registries should find same tools"
        
        # But different instances
        assert registry1 is not registry2, "Registries should be independent"
        assert tools1 is not tools2, "Tool dicts should be independent"


# Batch test for multiple tool types
@pytest.mark.parametrize("expected_tool", [
    "hello_world",
    "memory_read", 
    "memory_write",
    "python_script",
])
def test_specific_tools_exist(expected_tool):
    """Verify specific expected tools are registered"""
    registry = ToolRegistry(tool_directory="neural_engine/tools")
    tool = registry.get_tool(expected_tool)
    
    assert tool is not None, f"Tool '{expected_tool}' should be registered"
    
    definition = tool.get_tool_definition()
    assert definition["name"] == expected_tool, f"Tool name should match '{expected_tool}'"
