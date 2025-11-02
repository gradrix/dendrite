from neural_engine.tools.base_tool import BaseTool
import math

class AdditionTool(BaseTool):
    """
    A simple tool that adds two numbers.
    """

    def get_tool_definition(self):
        return {
            "name": "addition",  # snake_case, no "Tool" suffix
            "description": "Adds two given numbers.",
            "parameters": [
                {"name": "num1", "type": "float", "description": "First number to add.", "required": True},
                {"name": "num2", "type": "float", "description": "Second number to add.", "required": True}
            ]
        }

    def execute(self, **kwargs):
        """
        Execute the addition tool with given parameters.
        """
        try:
            num1 = kwargs.get('num1')
            num2 = kwargs.get('num2')

            if not num1 or not num2:
                return {"error": "Missing required parameters: num1, num2"}

            result = num1 + num2

            return {"result": result}
        except Exception as e:
            return {"error": str(e)}