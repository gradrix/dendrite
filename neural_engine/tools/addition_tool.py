from neural_engine.tools.base_tool import BaseTool
import math

class AdditionTool(BaseTool):
    """
    A simple tool for adding two numbers.
    """

    def get_tool_definition(self):
        return {
            "name": "addition",  # snake_case, no "Tool" suffix
            "description": "Adds two given numbers",
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
            # Extract parameters
            num1 = kwargs.get('num1')
            num2 = kwargs.get('num2')

            # Validate required parameters
            if not num1 or not num2:
                return {"error": "Missing required parameters: num1 and num2"}

            # Do the work
            result = f"The sum of {num1} and {num2} is {num1 + num2}"

            # Return result
            return {"result": result}

        except Exception as e:
            return {"error": str(e)}