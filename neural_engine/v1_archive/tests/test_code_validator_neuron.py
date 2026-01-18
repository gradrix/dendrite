"""
Tests for Code Validator Neuron with retry mechanism.
"""

import pytest
from neural_engine.core.code_validator_neuron import CodeValidatorNeuron


class TestCodeValidatorNeuron:
    """Test validation and retry feedback mechanism."""
    
    def test_validates_correct_code(self):
        """Test that valid code passes validation."""
        validator = CodeValidatorNeuron(max_retries=3)
        
        valid_code = """
from neural_engine.tools.hello_world_tool import HelloWorldTool
tool = HelloWorldTool()
result = tool.execute()
sandbox.set_result(result)
"""
        
        result = validator.validate_code(
            valid_code,
            {"tool_name": "hello_world", "tool_class": "HelloWorldTool"}
        )
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["feedback"] == ""
    
    def test_detects_syntax_error(self):
        """Test detection of syntax errors."""
        validator = CodeValidatorNeuron(max_retries=3)
        
        bad_code = """
from neural_engine.tools.hello_world_tool import HelloWorldTool
tool = HelloWorldTool(
result = tool.execute()
"""
        
        result = validator.validate_code(bad_code, {"tool_name": "hello_world"})
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert result["errors"][0]["type"] == "syntax"
        assert "Syntax Error" in result["feedback"]
        assert "line" in result["feedback"].lower()
    
    def test_detects_missing_set_result(self):
        """Test detection of structural issues."""
        validator = CodeValidatorNeuron(max_retries=3)
        
        incomplete_code = """
from neural_engine.tools.hello_world_tool import HelloWorldTool
tool = HelloWorldTool()
result = tool.execute()
"""
        
        result = validator.validate_code(incomplete_code, {"tool_name": "hello_world"})
        
        assert result["valid"] is False
        assert any(e["type"] == "structure" for e in result["errors"])
        assert "set_result" in result["feedback"]
    
    def test_retry_context_includes_feedback(self):
        """Test that retry context includes targeted feedback."""
        validator = CodeValidatorNeuron(max_retries=5)
        
        bad_code = """
from neural_engine.tools.hello_world_tool import HelloWorldTool
tool = HelloWorldTool(
result = tool.execute()
"""
        
        validation_result = validator.validate_code(
            bad_code,
            {"tool_name": "hello_world", "goal": "Say hello"}
        )
        
        retry_context = validator.get_retry_context(
            validation_result,
            {"tool_name": "hello_world", "goal": "Say hello"},
            attempt=1
        )
        
        assert "retry_attempt" in retry_context
        assert retry_context["retry_attempt"] == 1
        assert "previous_code" in retry_context
        assert "validation_errors" in retry_context
        assert "feedback" in retry_context
        assert "retry_instruction" in retry_context
        assert "RETRY #1" in retry_context["retry_instruction"]
    
    def test_should_retry_logic(self):
        """Test retry decision logic."""
        validator = CodeValidatorNeuron(max_retries=5)
        
        assert validator.should_retry(1) is True
        assert validator.should_retry(3) is True
        assert validator.should_retry(5) is False  # At max
        assert validator.should_retry(6) is False  # Over max
    
    def test_detects_missing_tool_import(self):
        """Test detection of missing tool imports."""
        validator = CodeValidatorNeuron(max_retries=3)
        
        code_without_import = """
tool = HelloWorldTool()
result = tool.execute()
sandbox.set_result(result)
"""
        
        result = validator.validate_code(
            code_without_import,
            {"tool_name": "hello_world"}
        )
        
        assert result["valid"] is False
        assert any(e["type"] == "tool_usage" for e in result["errors"])
        assert "import" in result["feedback"].lower()


class TestCodeValidatorIntegration:
    """Integration tests with CodeGeneratorNeuron."""
    
    @pytest.mark.integration
    def test_code_generator_uses_validation(self):
        """Test that code generator uses validation."""
        from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
        from neural_engine.core.message_bus import MessageBus
        from neural_engine.core.ollama_client import OllamaClient
        from neural_engine.core.tool_registry import ToolRegistry
        
        message_bus = MessageBus()
        ollama_client = OllamaClient()
        tool_registry = ToolRegistry()
        
        # Create with validation enabled
        generator = CodeGeneratorNeuron(
            message_bus,
            ollama_client,
            tool_registry,
            enable_validation=True,
            max_retries=3
        )
        
        assert generator.enable_validation is True
        assert generator.validator is not None
        assert generator.validator.max_retries == 3
    
    @pytest.mark.integration  
    def test_code_generator_can_disable_validation(self):
        """Test that validation can be disabled."""
        from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
        from neural_engine.core.message_bus import MessageBus
        from neural_engine.core.ollama_client import OllamaClient
        from neural_engine.core.tool_registry import ToolRegistry
        
        message_bus = MessageBus()
        ollama_client = OllamaClient()
        tool_registry = ToolRegistry()
        
        # Create with validation disabled
        generator = CodeGeneratorNeuron(
            message_bus,
            ollama_client,
            tool_registry,
            enable_validation=False
        )
        
        assert generator.enable_validation is False
        assert generator.validator is None
