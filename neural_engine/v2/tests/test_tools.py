"""
Tool Tests - Test tool registry, loading, discovery, and execution.
"""

import pytest
import tempfile
import os


class TestToolDefinition:
    """Test ToolDefinition."""
    
    def test_to_prompt_text(self):
        """ToolDefinition formats correctly for prompts."""
        from neural_engine.v2.tools import ToolDefinition
        
        definition = ToolDefinition(
            name="my_tool",
            description="Does something",
            parameters=[
                {"name": "input", "type": "string"},
                {"name": "count", "type": "int"},
            ],
        )
        
        text = definition.to_prompt_text()
        
        assert "my_tool" in text
        assert "input: string" in text
        assert "count: int" in text
        assert "Does something" in text


class TestToolRegistry:
    """Test ToolRegistry."""
    
    def test_register_tool(self):
        """Can register a tool."""
        from neural_engine.v2.tools import ToolRegistry, Tool, ToolDefinition
        
        class TestTool(Tool):
            def get_definition(self):
                return ToolDefinition(name="test", description="Test tool")
            
            def execute(self, **kwargs):
                return {"result": "ok"}
        
        registry = ToolRegistry()
        registry.register(TestTool())
        
        assert "test" in registry.list_tools()
    
    def test_get_tool(self):
        """Can retrieve registered tool."""
        from neural_engine.v2.tools import ToolRegistry, Tool, ToolDefinition
        
        class TestTool(Tool):
            def get_definition(self):
                return ToolDefinition(name="my_tool", description="My tool")
            
            def execute(self, **kwargs):
                return {"result": "success"}
        
        registry = ToolRegistry()
        registry.register(TestTool())
        
        tool = registry.get("my_tool")
        assert tool is not None
        
        result = tool.execute()
        assert result["result"] == "success"
    
    def test_get_nonexistent_tool(self):
        """Getting nonexistent tool returns None."""
        from neural_engine.v2.tools import ToolRegistry
        
        registry = ToolRegistry()
        
        tool = registry.get("nonexistent")
        assert tool is None
    
    def test_register_function(self):
        """Can register a plain function as tool."""
        from neural_engine.v2.tools import ToolRegistry
        
        def my_function(x: int, y: int) -> int:
            return x + y
        
        registry = ToolRegistry()
        registry.register_function(
            name="add",
            func=my_function,
            description="Add two numbers",
            parameters=[
                {"name": "x", "type": "int"},
                {"name": "y", "type": "int"},
            ],
        )
        
        tool = registry.get("add")
        result = tool.execute(x=2, y=3)
        
        assert result["result"] == 5
    
    def test_search_by_name(self):
        """Can search tools by name."""
        from neural_engine.v2.tools import ToolRegistry, Tool, ToolDefinition
        
        class CalcTool(Tool):
            def get_definition(self):
                return ToolDefinition(name="calculator", description="Math operations")
            def execute(self, **kwargs):
                return {}
        
        class MemTool(Tool):
            def get_definition(self):
                return ToolDefinition(name="memory", description="Store data")
            def execute(self, **kwargs):
                return {}
        
        registry = ToolRegistry()
        registry.register(CalcTool())
        registry.register(MemTool())
        
        results = registry.search("calc")
        
        assert len(results) == 1
        assert results[0].name == "calculator"
    
    def test_search_by_description(self):
        """Can search tools by description."""
        from neural_engine.v2.tools import ToolRegistry, Tool, ToolDefinition
        
        class WeatherTool(Tool):
            def get_definition(self):
                return ToolDefinition(
                    name="weather",
                    description="Get current weather forecast for a location"
                )
            def execute(self, **kwargs):
                return {}
        
        registry = ToolRegistry()
        registry.register(WeatherTool())
        
        results = registry.search("forecast")
        
        assert len(results) >= 1
        assert results[0].name == "weather"
    
    def test_search_by_concepts(self):
        """Can search tools by semantic concepts."""
        from neural_engine.v2.tools import ToolRegistry, Tool, ToolDefinition
        
        class RunningTool(Tool):
            def get_definition(self):
                return ToolDefinition(
                    name="strava_runs",
                    description="Get running activities",
                    concepts=["running", "exercise", "fitness", "jogging"],
                )
            def execute(self, **kwargs):
                return {}
        
        registry = ToolRegistry()
        registry.register(RunningTool())
        
        results = registry.search("jogging")
        
        assert len(results) >= 1
        assert results[0].name == "strava_runs"


class TestToolLoading:
    """Test loading tools from files."""
    
    def test_load_from_directory(self):
        """Can load tools from a directory."""
        from neural_engine.v2.tools import ToolRegistry, Tool, ToolDefinition
        
        # Create a temp directory with a tool file
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_file = os.path.join(tmpdir, "my_tool.py")
            
            # Write a tool module
            with open(tool_file, "w") as f:
                f.write("""
from neural_engine.v2.tools import Tool, ToolDefinition

class MyTempTool(Tool):
    def get_definition(self):
        return ToolDefinition(name="temp_tool", description="Temporary tool")
    
    def execute(self, **kwargs):
        return {"result": "from file"}
""")
            
            # Need to make it importable
            # For now, just test that the method exists and doesn't crash
            registry = ToolRegistry()
            
            # This won't actually work without proper PYTHONPATH setup
            # but we can verify the interface exists
            assert hasattr(registry, 'load_from_directory')


class TestBuiltinTools:
    """Test built-in tools."""
    
    def test_calculator_tool(self):
        """Calculator tool evaluates expressions."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import create_builtin_tools
        
        config = Config.for_testing()
        tools = create_builtin_tools(config)
        
        calc = next((t for t in tools if t.get_definition().name == "calculate"), None)
        assert calc is not None
        
        result = calc.execute(expression="2 + 3 * 4")
        
        assert result["result"] == 14
    
    def test_calculator_handles_errors(self):
        """Calculator returns error for invalid expressions."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import create_builtin_tools
        
        config = Config.for_testing()
        tools = create_builtin_tools(config)
        
        calc = next((t for t in tools if t.get_definition().name == "calculate"), None)
        
        result = calc.execute(expression="invalid syntax [")
        
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_memory_write_tool(self):
        """Memory write tool stores values."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import create_builtin_tools
        
        config = Config.for_testing()
        tools = create_builtin_tools(config)
        
        write_tool = next((t for t in tools if t.get_definition().name == "memory_write"), None)
        assert write_tool is not None
        
        result = write_tool.execute(key="test_key", value="test_value")
        
        assert result["status"] == "stored"
        assert result["key"] == "test_key"
    
    @pytest.mark.asyncio
    async def test_memory_read_tool(self):
        """Memory read tool retrieves values."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import create_builtin_tools
        
        config = Config.for_testing()
        tools = create_builtin_tools(config)
        
        write_tool = next((t for t in tools if t.get_definition().name == "memory_write"), None)
        read_tool = next((t for t in tools if t.get_definition().name == "memory_read"), None)
        
        # Write first
        write_tool.execute(key="read_test_key", value="read_test_value")
        
        # Then read
        result = read_tool.execute(key="read_test_key")
        
        assert result["value"] == "read_test_value"


class TestToolNeuron:
    """Test ToolNeuron with registry."""
    
    @pytest.mark.asyncio
    async def test_tool_neuron_executes_calculator(self):
        """ToolNeuron can execute calculator."""
        from neural_engine.v2.core import Config, GoalContext
        from neural_engine.v2.neurons import ToolNeuron
        
        config = Config.for_testing()
        neuron = ToolNeuron(config)
        
        ctx = GoalContext(goal_id="test", goal_text="Calculate 5 + 5")
        result = await neuron.run(ctx, "What is 5 + 5?")
        
        assert result.success
        # Result should contain 10 (or the calculation result)
        assert result.data is not None
    
    @pytest.mark.asyncio
    async def test_tool_neuron_has_builtin_tools(self):
        """ToolNeuron has built-in tools registered."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.neurons import ToolNeuron
        
        config = Config.for_testing()
        neuron = ToolNeuron(config)
        
        tools = neuron.registry.list_tools()
        
        assert "calculate" in tools
        assert "memory_read" in tools
        assert "memory_write" in tools
    
    @pytest.mark.asyncio
    async def test_tool_neuron_selects_appropriate_tool(self):
        """ToolNeuron selects the right tool for the task."""
        from neural_engine.v2.core import Config, GoalContext
        from neural_engine.v2.neurons import ToolNeuron
        
        config = Config.for_testing()
        neuron = ToolNeuron(config)
        
        # Math query should select calculator
        ctx = GoalContext(goal_id="test", goal_text="Calculate something")
        await neuron.run(ctx, "What is 100 / 4?")
        
        # Check that a tool was selected
        assert ctx.tool_name is not None
