"""
Phase 4: Code Generation Tests

This phase validates the CodeGeneratorNeuron's ability to:
- Generate executable Python code for tool invocation
- Extract parameters from natural language goals
- Handle different parameter types (strings, integers, booleans, optional)
- Generate syntactically correct Python
- Pass tool definitions to guide parameter extraction

Tests are organized into:
- Phase 4a: Basic Code Generation (simple tools, no parameters)
- Phase 4b: Parameter Extraction (extracting values from goals)
- Phase 4c: Code Quality (syntax, imports, structure)
- Phase 4d: Complex Parameters (multiple parameters, optional parameters)
- Phase 4e: Integration (full pipeline from tool selection to code)
"""

import pytest
import json
import ast
from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
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
def code_generator(message_bus, ollama_client, tool_registry):
    """Provide a CodeGeneratorNeuron for testing"""
    return CodeGeneratorNeuron(message_bus, ollama_client, tool_registry)


class TestPhase4BasicCodeGeneration:
    """Phase 4a: Basic code generation for simple tools"""
    
    def test_generator_loads_prompt(self, code_generator):
        """CodeGeneratorNeuron should load its prompt template"""
        prompt = code_generator._load_prompt()
        
        assert prompt is not None, "Prompt should load"
        assert "{goal}" in prompt, "Prompt should have goal placeholder"
        assert "{tool_name}" in prompt, "Prompt should have tool_name placeholder"
        assert "{tool_definition}" in prompt, "Prompt should have tool_definition placeholder"
    
    @pytest.mark.integration
    def test_generates_code_for_hello_world(self, code_generator, message_bus):
        """Should generate code to call HelloWorldTool"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Say hello to the world",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        
        assert result is not None, "Should return result"
        assert "generated_code" in result, "Should have generated code"
        assert len(result["generated_code"]) > 0, "Code should not be empty"
    
    @pytest.mark.integration
    def test_generated_code_is_valid_python(self, code_generator, message_bus):
        """Generated code should be syntactically valid Python"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Say hello",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        code = result["generated_code"]
        
        # Should be able to parse as valid Python
        try:
            ast.parse(code)
            syntax_valid = True
        except SyntaxError:
            syntax_valid = False
        
        assert syntax_valid, f"Generated code should be valid Python. Code:\n{code}"
    
    @pytest.mark.integration
    def test_generated_code_has_import(self, code_generator, message_bus):
        """Generated code should import the tool class"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Say hello",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        code = result["generated_code"]
        
        assert "import" in code or "from" in code, "Code should have import statement"
        assert "HelloWorldTool" in code, "Code should reference HelloWorldTool"
    
    @pytest.mark.integration
    def test_generated_code_calls_execute(self, code_generator, message_bus):
        """Generated code should call the tool's execute() method"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Say hello",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        code = result["generated_code"]
        
        assert "execute()" in code or "execute(" in code, "Code should call execute method"
    
    @pytest.mark.integration
    def test_generated_code_uses_sandbox(self, code_generator, message_bus):
        """Generated code should call sandbox.set_result()"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Say hello",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        code = result["generated_code"]
        
        assert "sandbox.set_result" in code, "Code should call sandbox.set_result()"


class TestPhase4ParameterExtraction:
    """Phase 4b: Test parameter extraction from goals"""
    
    @pytest.mark.integration
    def test_extracts_simple_string_parameter(self, code_generator, message_bus):
        """Should extract string parameters from goal"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Remember that my favorite color is blue",
            "selected_tool_name": "memory_write",
            "selected_tool_module": "neural_engine.tools.memory_write_tool",
            "selected_tool_class": "MemoryWriteTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        code = result["generated_code"]
        
        # Code should attempt to pass parameters to execute()
        assert "execute(" in code, "Should call execute with parameters"
        # Should extract key and value
        assert "key" in code.lower() or "value" in code.lower(), "Should reference parameters"
    
    @pytest.mark.integration
    def test_handles_tool_with_no_parameters(self, code_generator, message_bus):
        """Should handle tools that don't need parameters"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Say hello",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        code = result["generated_code"]
        
        # Should call execute() with no arguments or empty arguments
        assert "execute()" in code, "Should call execute() with no arguments"


class TestPhase4CodeQuality:
    """Phase 4c: Test code quality and structure"""
    
    @pytest.mark.integration
    def test_code_is_clean_no_markdown(self, code_generator, message_bus):
        """Generated code should not contain markdown formatting"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Say hello",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        code = result["generated_code"]
        
        assert not code.startswith("```"), "Code should not start with markdown"
        assert not code.endswith("```"), "Code should not end with markdown"
        assert "```python" not in code, "Code should not contain python markdown"
    
    @pytest.mark.integration
    def test_code_structure_is_logical(self, code_generator, message_bus):
        """Code should follow logical structure: import → instantiate → call → set_result"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Say hello",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        code = result["generated_code"]
        
        # Find positions of key elements
        import_pos = code.find("import")
        if import_pos == -1:
            import_pos = code.find("from")
        
        execute_pos = code.find("execute")
        sandbox_pos = code.find("sandbox")
        
        # Import should come before execute
        assert import_pos < execute_pos, "Import should come before execute call"
        # Execute should come before sandbox.set_result
        assert execute_pos < sandbox_pos, "Execute should come before sandbox.set_result"


class TestPhase4MessageBusIntegration:
    """Phase 4d: Test message bus integration"""
    
    @pytest.mark.integration
    def test_stores_code_in_message_bus(self, code_generator, message_bus):
        """Should store generated code in message bus"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Say hello",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        code_generator.process(goal_id, data, depth=0)
        
        # Retrieve from message bus
        stored_message = message_bus.get_message(goal_id, "code_generation")
        
        assert stored_message is not None, "Should store result in message bus"
        # Extract data from new metadata format
        stored_result = stored_message["data"] if "data" in stored_message else stored_message
        assert "code" in stored_result or "generated_code" in stored_result, "Stored result should have code"
        code = stored_result.get("generated_code", stored_result.get("code", ""))
        assert len(code) > 0, "Stored code should not be empty"
    
    @pytest.mark.integration
    def test_result_contains_all_fields(self, code_generator, message_bus):
        """Result should have goal, tool_name, and code"""
        goal_id = message_bus.get_new_goal_id()
        
        data = {
            "goal": "Test goal",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        result = code_generator.process(goal_id, data, depth=0)
        
        assert "goal" in result, "Result should have goal"
        assert "tool_name" in result, "Result should have tool_name"
        assert "code" in result or "generated_code" in result, "Result should have code"
        assert result["goal"] == "Test goal", "Goal should be preserved"
        assert result["tool_name"] == "hello_world", "Tool name should be preserved"


class TestPhase4FullPipeline:
    """Phase 4e: Test full pipeline integration"""
    
    @pytest.mark.integration
    def test_pipeline_from_selection_to_code(self, code_generator, message_bus, tool_registry):
        """Test complete flow: tool selection data → code generation"""
        goal_id = message_bus.get_new_goal_id()
        
        # Simulate tool selection output
        selection_data = {
            "goal": "Say hello to everyone",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }
        
        # Generate code
        result = code_generator.process(goal_id, selection_data, depth=0)
        
        # Validate code generation
        assert result["generated_code"] is not None, "Should generate code"
        
        # Code should be executable Python
        try:
            ast.parse(result["generated_code"])
            syntax_valid = True
        except:
            syntax_valid = False
        
        assert syntax_valid, "Generated code should be syntactically valid"
        
        # Code should reference the correct tool
        assert "HelloWorldTool" in result["generated_code"], "Code should use correct tool class"
    
    @pytest.mark.integration
    def test_different_tools_generate_different_code(self, code_generator, message_bus):
        """Different tools should generate different code"""
        goal_id_1 = message_bus.get_new_goal_id()
        goal_id_2 = message_bus.get_new_goal_id()
        
        # Generate code for hello_world
        result_1 = code_generator.process(goal_id_1, {
            "goal": "Say hello",
            "selected_tool_name": "hello_world",
            "selected_tool_module": "neural_engine.tools.hello_world_tool",
            "selected_tool_class": "HelloWorldTool"
        }, depth=0)
        
        # Generate code for memory_read
        result_2 = code_generator.process(goal_id_2, {
            "goal": "What do I remember?",
            "selected_tool_name": "memory_read",
            "selected_tool_module": "neural_engine.tools.memory_read_tool",
            "selected_tool_class": "MemoryReadTool"
        }, depth=0)
        
        # Codes should be different
        assert result_1["code"] != result_2["code"], "Different tools should generate different code"
        assert "HelloWorldTool" in result_1["code"], "First code should use HelloWorldTool"
        assert "MemoryReadTool" in result_2["code"], "Second code should use MemoryReadTool"


# Batch test for multiple tools
@pytest.mark.integration
@pytest.mark.parametrize("tool_name,tool_module,tool_class", [
    ("hello_world", "neural_engine.tools.hello_world_tool", "HelloWorldTool"),
    ("memory_read", "neural_engine.tools.memory_read_tool", "MemoryReadTool"),
    ("memory_write", "neural_engine.tools.memory_write_tool", "MemoryWriteTool"),
])
def test_code_generation_for_multiple_tools(tool_name, tool_module, tool_class, code_generator, message_bus):
    """Verify code generation works for multiple different tools"""
    goal_id = message_bus.get_new_goal_id()
    
    data = {
        "goal": f"Use the {tool_name} tool",
        "selected_tool_name": tool_name,
        "selected_tool_module": tool_module,
        "selected_tool_class": tool_class
    }
    
    result = code_generator.process(goal_id, data, depth=0)
    
    # Should generate valid code
    assert result["generated_code"] is not None, f"Should generate code for {tool_name}"
    assert len(result["generated_code"]) > 0, f"Code for {tool_name} should not be empty"
    
    # Code should reference the correct class
    assert tool_class in result["generated_code"], f"Code should reference {tool_class}"
    
    # Code should be syntactically valid
    try:
        ast.parse(result["generated_code"])
        syntax_valid = True
    except:
        syntax_valid = False
    
    assert syntax_valid, f"Generated code for {tool_name} should be valid Python"
