"""
Phase 5: Sandbox Execution Tests

This phase validates the Sandbox's ability to:
- Execute AI-generated Python code safely
- Provide sandbox.set_result() interface to code
- Handle code execution errors gracefully
- Execute tool invocations from generated code
- Return results from executed code
- Isolate execution environment

Tests are organized into:
- Phase 5a: Basic Execution (running simple code)
- Phase 5b: Tool Execution (running code that calls tools)
- Phase 5c: Result Handling (sandbox.set_result interface)
- Phase 5d: Error Handling (catching exceptions, invalid code)
- Phase 5e: Integration (full pipeline: selection → generation → execution)
"""

import pytest
from neural_engine.core.sandbox import Sandbox
from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.ollama_client import OllamaClient


@pytest.fixture
def message_bus():
    """Provide a MessageBus for testing"""
    return MessageBus()


@pytest.fixture
def sandbox(message_bus):
    """Provide a Sandbox for testing"""
    return Sandbox(message_bus)


@pytest.fixture
def ollama_client():
    """Provide an OllamaClient for testing"""
    return OllamaClient()


@pytest.fixture
def tool_registry():
    """Provide a ToolRegistry with all available tools"""
    return ToolRegistry(tool_directory="neural_engine/tools")


@pytest.fixture
def code_generator(message_bus, ollama_client, tool_registry):
    """Provide a CodeGeneratorNeuron for testing"""
    return CodeGeneratorNeuron(message_bus, ollama_client, tool_registry)


class TestPhase5BasicExecution:
    """Phase 5a: Basic code execution"""
    
    def test_sandbox_exists(self, sandbox):
        """Sandbox should be instantiated"""
        assert sandbox is not None, "Sandbox should exist"
    
    def test_execute_simple_code(self, sandbox):
        """Should execute simple Python code"""
        code = """
x = 5 + 3
sandbox.set_result(x)
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, "Should execute without error"
        assert result["result"] == 8, "Should return correct result"
    
    def test_execute_string_manipulation(self, sandbox):
        """Should execute string operations"""
        code = """
message = "Hello, " + "World!"
sandbox.set_result(message)
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, "Should execute without error"
        assert result["result"] == "Hello, World!", "Should return correct string"
    
    def test_execute_with_imports(self, sandbox):
        """Should handle standard library imports"""
        code = """
import json
data = {"key": "value"}
json_str = json.dumps(data)
sandbox.set_result(json_str)
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, "Should execute without error"
        assert '"key": "value"' in result["result"], "Should serialize to JSON"


class TestPhase5ToolExecution:
    """Phase 5b: Executing code that calls tools"""
    
    def test_execute_hello_world_tool(self, sandbox):
        """Should execute code that calls HelloWorldTool"""
        code = """
from neural_engine.tools.hello_world_tool import HelloWorldTool

tool = HelloWorldTool()
result = tool.execute()
sandbox.set_result(result)
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, f"Should execute without error. Error: {result.get('error')}"
        assert result["result"] is not None, "Should return result"
        assert "message" in result["result"], "HelloWorld should return message"
        assert "Hello" in result["result"]["message"], "Should contain greeting"
    
    def test_execute_memory_write_tool(self, sandbox):
        """Should execute code that writes to memory"""
        code = """
from neural_engine.tools.memory_write_tool import MemoryWriteTool

tool = MemoryWriteTool()
result = tool.execute(key="test_key", value="test_value")
sandbox.set_result(result)
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, f"Should execute without error. Error: {result.get('error')}"
        assert result["result"] is not None, "Should return result"
    
    def test_execute_memory_read_tool(self, sandbox, message_bus):
        """Should execute code that reads from memory"""
        # First, write something to memory
        message_bus.redis.set("read_test_key", "read_test_value")
        
        code = """
from neural_engine.tools.memory_read_tool import MemoryReadTool

tool = MemoryReadTool()
result = tool.execute(key="read_test_key")
sandbox.set_result(result)
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, f"Should execute without error. Error: {result.get('error')}"
        assert result["result"] is not None, "Should return result"


class TestPhase5ResultHandling:
    """Phase 5c: Test sandbox.set_result interface"""
    
    def test_set_result_with_dict(self, sandbox):
        """Should handle dict results"""
        code = """
sandbox.set_result({"status": "success", "data": [1, 2, 3]})
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, "Should execute without error"
        assert isinstance(result["result"], dict), "Result should be dict"
        assert result["result"]["status"] == "success", "Should preserve dict structure"
    
    def test_set_result_with_list(self, sandbox):
        """Should handle list results"""
        code = """
sandbox.set_result([1, 2, 3, 4, 5])
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, "Should execute without error"
        assert isinstance(result["result"], list), "Result should be list"
        assert len(result["result"]) == 5, "Should preserve list length"
    
    def test_set_result_with_none(self, sandbox):
        """Should handle None results"""
        code = """
sandbox.set_result(None)
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, "Should execute without error"
        assert result["result"] is None, "Result should be None"
    
    def test_multiple_set_result_calls(self, sandbox):
        """Last set_result call should win"""
        code = """
sandbox.set_result("first")
sandbox.set_result("second")
sandbox.set_result("final")
"""
        result = sandbox.execute(code)
        
        assert result["error"] is None, "Should execute without error"
        assert result["result"] == "final", "Should use last set_result value"


class TestPhase5ErrorHandling:
    """Phase 5d: Test error handling"""
    
    def test_handles_syntax_error(self, sandbox):
        """Should catch syntax errors"""
        code = """
this is not valid python syntax!!!
"""
        result = sandbox.execute(code)
        
        assert result["error"] is not None, "Should report error"
        assert result["result"] is None, "Should not have result on error"
    
    def test_handles_runtime_error(self, sandbox):
        """Should catch runtime errors"""
        code = """
x = 1 / 0  # Division by zero
sandbox.set_result(x)
"""
        result = sandbox.execute(code)
        
        assert result["error"] is not None, "Should report error"
        assert "division" in result["error"].lower() or "zero" in result["error"].lower(), \
            "Error should mention division by zero"
    
    def test_handles_import_error(self, sandbox):
        """Should catch import errors"""
        code = """
import nonexistent_module_xyz
sandbox.set_result("success")
"""
        result = sandbox.execute(code)
        
        assert result["error"] is not None, "Should report error"
        assert "import" in result["error"].lower() or "module" in result["error"].lower(), \
            "Error should mention import/module"
    
    def test_handles_undefined_variable(self, sandbox):
        """Should catch undefined variable errors"""
        code = """
sandbox.set_result(undefined_variable)
"""
        result = sandbox.execute(code)
        
        assert result["error"] is not None, "Should report error"
        assert "name" in result["error"].lower() or "defined" in result["error"].lower(), \
            "Error should mention undefined name"


class TestPhase5Integration:
    """Phase 5e: Full pipeline integration tests"""
    
    @pytest.mark.integration
    def test_full_pipeline_hello_world(self, code_generator, sandbox, message_bus):
        """Test complete flow: generate code → execute → return result"""
        goal_id = message_bus.get_new_goal_id()
        
        # Step 1: Generate code (simulating Phase 4 output)
        selection_data = {
            "goal": "Say hello to the world",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        code_result = code_generator.process(goal_id, selection_data, depth=0)
        
        # Step 2: Execute generated code
        execution_result = sandbox.execute(code_result["generated_code"])
        
        # Step 3: Verify result
        assert execution_result["error"] is None, \
            f"Execution should succeed. Error: {execution_result['error']}\nCode:\n{code_result['code']}"
        assert execution_result["result"] is not None, "Should have result"
        assert "message" in execution_result["result"], "HelloWorld should return message"
    
    @pytest.mark.integration
    def test_generated_code_executes_successfully(self, code_generator, sandbox, message_bus):
        """AI-generated code should execute without errors"""
        goal_id = message_bus.get_new_goal_id()
        
        # Generate code for memory write
        selection_data = {
            "goal": "Remember that my favorite food is pizza",
            "selected_tool_name": "memory_write",
            "selected_tool_module": "neural_engine.tools.memory_write_tool",
            "selected_tool_class": "MemoryWriteTool"
        }
        
        code_result = code_generator.process(goal_id, selection_data, depth=0)
        execution_result = sandbox.execute(code_result["generated_code"])
        
        # Should execute successfully (even if parameters aren't perfect)
        assert execution_result["error"] is None, \
            f"Generated code should execute. Error: {execution_result['error']}\nCode:\n{code_result['code']}"
    
    @pytest.mark.integration
    def test_end_to_end_user_goal_to_result(self, code_generator, sandbox, message_bus):
        """Complete user journey: goal → code → execution → result"""
        goal_id = message_bus.get_new_goal_id()
        user_goal = "Say hello"
        
        # Phase 3 output (tool selection) - simulated
        selection_data = {
            "goal": user_goal,
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        # Phase 4: Code generation
        code_result = code_generator.process(goal_id, selection_data, depth=0)
        assert code_result["generated_code"] is not None, "Should generate code"
        
        # Phase 5: Execution
        execution_result = sandbox.execute(code_result["generated_code"])
        assert execution_result["error"] is None, "Should execute successfully"
        
        # Verify final result
        final_result = execution_result["result"]
        assert final_result is not None, "Should have final result"
        
        # Result should be meaningful
        assert isinstance(final_result, dict), "Tool results are typically dicts"


# Batch test for multiple tools
@pytest.mark.integration
@pytest.mark.parametrize("tool_name,tool_module,tool_class", [
    ("hello_world", "neural_engine.tools.hello_world_tool", "HelloWorldTool"),
])
def test_execution_for_multiple_tools(tool_name, tool_module, tool_class, code_generator, sandbox, message_bus):
    """Verify execution works for different tools"""
    goal_id = message_bus.get_new_goal_id()
    
    # Generate code
    selection_data = {
        "goal": f"Use the {tool_name} tool",
        "selected_tool_name": tool_name,
        "selected_tool_module": tool_module,
        "selected_tool_class": tool_class
    }
    
    code_result = code_generator.process(goal_id, selection_data, depth=0)
    
    # Execute code
    execution_result = sandbox.execute(code_result["generated_code"])
    
    # Should execute successfully
    assert execution_result["error"] is None, \
        f"Execution of {tool_name} should succeed. Error: {execution_result['error']}\nCode:\n{code_result['code']}"
    assert execution_result["result"] is not None, f"Should have result for {tool_name}"
