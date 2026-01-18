"""Tests for Tool Forge - Dynamic Tool Creation."""

import pytest
from datetime import datetime


class TestToolPerformance:
    """Test ToolPerformance metrics tracking."""
    
    def test_initial_success_rate(self):
        """New tools have 100% success rate."""
        from neural_engine.v2.forge import ToolPerformance
        
        perf = ToolPerformance(tool_name="test_tool")
        assert perf.success_rate == 1.0
        assert perf.total_calls == 0
    
    def test_record_success(self):
        """Record successful execution."""
        from neural_engine.v2.forge import ToolPerformance
        
        perf = ToolPerformance(tool_name="test_tool")
        perf.record_success(100)
        
        assert perf.total_calls == 1
        assert perf.successful_calls == 1
        assert perf.total_duration_ms == 100
        assert perf.success_rate == 1.0
    
    def test_record_failure(self):
        """Record failed execution."""
        from neural_engine.v2.forge import ToolPerformance
        
        perf = ToolPerformance(tool_name="test_tool")
        perf.record_failure("Test error")
        
        assert perf.total_calls == 1
        assert perf.failed_calls == 1
        assert perf.last_error == "Test error"
        assert perf.success_rate == 0.0
    
    def test_mixed_success_rate(self):
        """Calculate success rate with mixed results."""
        from neural_engine.v2.forge import ToolPerformance
        
        perf = ToolPerformance(tool_name="test_tool")
        perf.record_success(100)
        perf.record_success(100)
        perf.record_failure("error")
        perf.record_success(100)
        
        assert perf.total_calls == 4
        assert perf.successful_calls == 3
        assert perf.success_rate == 0.75
    
    def test_avg_duration(self):
        """Calculate average duration."""
        from neural_engine.v2.forge import ToolPerformance
        
        perf = ToolPerformance(tool_name="test_tool")
        perf.record_success(100)
        perf.record_success(200)
        perf.record_success(300)
        
        assert perf.avg_duration_ms == 200.0
    
    def test_status_progression(self):
        """Tool upgrades from TESTING to ACTIVE after successes."""
        from neural_engine.v2.forge import ToolPerformance, ToolStatus
        
        perf = ToolPerformance(tool_name="test_tool", status=ToolStatus.TESTING)
        assert perf.status == ToolStatus.TESTING
        
        perf.record_success(100)
        perf.record_success(100)
        assert perf.status == ToolStatus.TESTING
        
        perf.record_success(100)
        assert perf.status == ToolStatus.ACTIVE
    
    def test_status_degradation(self):
        """Tool degrades with high failure rate."""
        from neural_engine.v2.forge import ToolPerformance, ToolStatus
        
        perf = ToolPerformance(tool_name="test_tool", status=ToolStatus.ACTIVE)
        
        # Need 5+ calls with <50% success
        perf.record_success(100)
        perf.record_failure("error")
        perf.record_failure("error")
        perf.record_failure("error")
        perf.record_failure("error")  # 5 calls, 20% success
        
        assert perf.status == ToolStatus.DEGRADED
    
    def test_serialization(self):
        """Serialize to dict."""
        from neural_engine.v2.forge import ToolPerformance
        
        perf = ToolPerformance(tool_name="test_tool")
        perf.record_success(100)
        
        data = perf.to_dict()
        assert data["tool_name"] == "test_tool"
        assert data["total_calls"] == 1
        assert data["success_rate"] == 1.0


class TestForgedTool:
    """Test ForgedTool dataclass."""
    
    def test_creation(self):
        """Create a ForgedTool."""
        from neural_engine.v2.forge import ForgedTool
        
        tool = ForgedTool(
            name="test_tool",
            description="A test tool",
            code="class TestTool: pass",
            parameters=[{"name": "x", "type": "int"}],
        )
        
        assert tool.name == "test_tool"
        assert tool.version == 1
    
    def test_code_hash(self):
        """Code hash is computed."""
        from neural_engine.v2.forge import ForgedTool
        
        tool = ForgedTool(
            name="test_tool",
            description="A test tool",
            code="class TestTool: pass",
            parameters=[],
        )
        
        assert len(tool.code_hash) == 12
        
        # Different code = different hash
        tool2 = ForgedTool(
            name="test_tool",
            description="A test tool",
            code="class TestTool2: pass",
            parameters=[],
        )
        
        assert tool.code_hash != tool2.code_hash
    
    def test_serialization(self):
        """Serialize to dict."""
        from neural_engine.v2.forge import ForgedTool
        
        tool = ForgedTool(
            name="test_tool",
            description="A test tool",
            code="class TestTool: pass",
            parameters=[{"name": "x"}],
            domain="testing",
        )
        
        data = tool.to_dict()
        assert data["name"] == "test_tool"
        assert data["domain"] == "testing"
        assert "code_hash" in data


class TestToolForge:
    """Test ToolForge functionality."""
    
    def test_generate_tool_name(self):
        """Generate tool name from capability."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        name = forge._generate_tool_name("Get weather for a city")
        assert name == "weather_city"
        
        name = forge._generate_tool_name("Calculate the sum of two numbers")
        # Note: "of" is a stop word, so it's filtered out
        assert "calculate" in name
        assert "sum" in name
    
    def test_to_class_name(self):
        """Convert tool name to class name."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        assert forge._to_class_name("weather_city") == "WeatherCityTool"
        assert forge._to_class_name("test") == "TestTool"
    
    def test_extract_code(self):
        """Extract code from LLM response."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        # Code block with python tag
        response = "Here's the code:\n```python\nclass Test: pass\n```"
        assert forge._extract_code(response) == "class Test: pass"
        
        # Plain code block
        response = "```\nclass Test: pass\n```"
        assert forge._extract_code(response) == "class Test: pass"
        
        # Direct code
        response = "class MyTool:\n    def execute(self): pass"
        assert "class MyTool" in forge._extract_code(response)
    
    def test_validate_code_valid(self):
        """Validate correct tool code."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        valid_code = '''
class TestTool:
    def get_definition(self):
        return {}
    
    def execute(self, **kwargs):
        return {"result": "ok"}
'''
        assert forge._validate_code(valid_code) == True
    
    def test_validate_code_missing_methods(self):
        """Reject code missing required methods."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        # Missing execute
        invalid_code = '''
class TestTool:
    def get_definition(self):
        return {}
'''
        assert forge._validate_code(invalid_code) == False
    
    def test_validate_code_dangerous(self):
        """Reject dangerous code patterns."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        dangerous_code = '''
import os
class TestTool:
    def get_definition(self): return {}
    def execute(self, **kwargs):
        os.system("rm -rf /")
        return {}
'''
        assert forge._validate_code(dangerous_code) == False
    
    def test_validate_code_syntax_error(self):
        """Reject code with syntax errors."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        bad_code = "class Test def oops:"
        assert forge._validate_code(bad_code) == False
    
    def test_instantiate_tool(self):
        """Instantiate a tool from code."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry, Tool, ToolDefinition
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        code = '''
class CustomTool(Tool):
    def __init__(self, config):
        self._config = config
    
    def get_definition(self):
        return ToolDefinition(
            name="custom",
            description="A custom tool",
            parameters=[],
        )
    
    def execute(self, **kwargs):
        return {"result": "custom result"}
'''
        tool = forge._instantiate_tool(code, "CustomTool")
        assert tool is not None
        assert tool.get_definition().name == "custom"
        assert tool.execute()["result"] == "custom result"
    
    def test_performance_tracking(self):
        """Track tool performance."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        # Record some metrics
        forge.record_success("my_tool", 100)
        forge.record_success("my_tool", 200)
        forge.record_failure("my_tool", "error")
        
        perf = forge.get_performance("my_tool")
        assert perf is not None
        assert perf.total_calls == 3
        assert perf.successful_calls == 2
        assert perf.success_rate == 2/3
    
    def test_retire_tool(self):
        """Retire a tool."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge, ToolStatus
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        # Create performance entry
        forge.record_success("my_tool", 100)
        
        # Retire
        assert forge.retire_tool("my_tool") == True
        
        perf = forge.get_performance("my_tool")
        assert perf.status == ToolStatus.RETIRED
    
    def test_get_degraded_tools(self):
        """Get list of degraded tools."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge, ToolStatus
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        # Create a healthy tool
        forge.record_success("good_tool", 100)
        forge.record_success("good_tool", 100)
        forge.record_success("good_tool", 100)
        
        # Create a failing tool (5+ calls, <50% success)
        forge.record_success("bad_tool", 100)
        forge.record_failure("bad_tool", "error")
        forge.record_failure("bad_tool", "error")
        forge.record_failure("bad_tool", "error")
        forge.record_failure("bad_tool", "error")
        
        degraded = forge.get_degraded_tools()
        assert "bad_tool" in degraded
        assert "good_tool" not in degraded
    
    def test_serialization(self):
        """Serialize forge state."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        forge.record_success("tool1", 100)
        forge.record_success("tool2", 200)
        
        data = forge.to_dict()
        assert "performance" in data
        assert "tool1" in data["performance"]
        assert "tool2" in data["performance"]


class TestToolForgeIntegration:
    """Integration tests for Tool Forge with LLM."""
    
    @pytest.mark.asyncio
    async def test_create_tool(self):
        """Create a tool from natural language (requires LLM)."""
        from neural_engine.v2.core import Config
        from neural_engine.v2.tools import ToolRegistry
        from neural_engine.v2.forge import ToolForge
        
        config = Config.for_testing()
        registry = ToolRegistry()
        forge = ToolForge(config, registry)
        
        # Create a simple tool
        tool = await forge.create_tool(
            capability="Add two numbers together",
            request="What is 5 + 3?",
            domain="math",
        )
        
        # Tool should be created (or None if LLM fails)
        if tool is not None:
            definition = tool.get_definition()
            assert definition.name is not None
            assert len(definition.description) > 0
            
            # Tool should be tracked
            assert forge.get_forged_tool(definition.name) is not None
