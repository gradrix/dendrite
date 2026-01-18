from neural_engine.tools.base_tool import BaseTool
import math

class AddTool(BaseTool):
    """
    This tool takes two numbers and adds them together.
    """

    def get_tool_definition(self):
        return {
            "name": "add",  # snake_case, no "Tool" suffix
            "description": "Adds two numbers.",
            "parameters": [
                {"name": "num1", "type": "float", "description": "First number", "required": True},
                {"name": "num2", "type": "float", "description": "Second number", "required": True}
            ]
        }

    def execute(self, **kwargs):
        """
        Execute the tool with given parameters.
        """
        try:
            num1 = kwargs.get('num1')
            num2 = kwargs.get('num2')

            # Validate required parameters
            if not (num1 and num2):
                return {"error": "Missing required parameter(s) for operation."}

            result = num1 + num2

            # Return result
            return {"result": result}

        except Exception as e:
            return {"error": str(e)}