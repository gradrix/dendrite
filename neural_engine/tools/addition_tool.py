from neural_engine.tools.base_tool import BaseTool
from typing import Optional

class AdditionTool(BaseTool):
    """
    A tool for adding two numbers together.
    """

    def get_tool_definition(self):
        return {
            "name": "addition",  # snake_case, no "Tool" suffix
            "description": "Adds two given numbers",
            "parameters": [
                {"name": "num1", "type": "float", "description": "First number to add", "required": True},
                {"name": "num2", "type": "float", "description": "Second number to add", "required": True}
            ]
        }

    def execute(self, **kwargs):
        """
        Execute the addition tool with given parameters.
        """
        try:
            # Extract parameters
            num1 = kwargs.get('num1')
            num2 = kwargs.get('num2')

            # Validate required parameters
            if not (num1 and num2):
                return {"error": "Missing required parameters: num1, num2"}

            # Do the work
            result = f"Result of addition: {num1 + num2}"

            # Return result
            return {"result": result}

        except Exception as e:
            return {"error": str(e)}