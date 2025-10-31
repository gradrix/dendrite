"""
Test tool for integration testing: simulates transient failures
"""
from neural_engine.tools.base_tool import BaseTool


class TestTransientTool(BaseTool):
    """Tool that fails transiently then succeeds - for testing retry strategy"""
    
    name = "test_transient_tool"
    description = "A tool that fails transiently then succeeds"
    parameters = {
        "message": {"type": "string", "description": "Message to process"}
    }
    
    # Track calls across instances for testing
    _call_count = 0
    
    @classmethod
    def get_tool_definition(cls):
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.parameters
        }
    
    @classmethod
    def reset(cls):
        """Reset call count for testing"""
        cls._call_count = 0
    
    def execute(self, message):
        TestTransientTool._call_count += 1
        if TestTransientTool._call_count < 2:
            raise TimeoutError("Connection timeout - please retry")
        return {
            "result": f"Processed: {message}",
            "attempts": TestTransientTool._call_count
        }
