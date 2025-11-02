from .base_tool import BaseTool

class HelloWorldTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "hello_world",
            "description": "Outputs or says 'Hello, World!' greeting message. Use when user asks to say hello, print hello, or display hello world.",
            "parameters": []
        }

    def execute(self, **kwargs):
        return {"message": "Hello, World!"}
    
    def get_tool_characteristics(self):
        """HelloWorld is perfectly safe - read-only, no side effects."""
        return {
            "idempotent": True,  # Always returns same result
            "side_effects": [],  # No external changes
            "safe_for_shadow_testing": True,  # Completely safe
            "requires_mocking": [],
            "test_data_available": True
        }
    
    def get_test_cases(self):
        """Provide test cases."""
        return [
            {
                "input": {},
                "expected_output": {"message": "Hello, World!"},
                "should_raise": None,
                "description": "Returns greeting"
            }
        ]

