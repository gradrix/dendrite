from neural_engine.tools.base_tool import BaseTool
import math

class AdditionTool(BaseTool):
    """
    Tool to add two numbers together.
    """

    def get_tool_definition(self):
        return {
            "name": "addition",  # snake_case, no "Tool" suffix
            "description": "Adds two numbers together.",
            "parameters": [
                {"name": "number1", "type": "float", "description": "First number to add", "required": True},
                {"name": "number2", "type": "float", "description": "Second number to add", "required": True}
            ]
        }

    def execute(self, **kwargs):
        """
        Execute the addition tool with given parameters.
        """
        try:
            # Extract parameters
            number1 = kwargs.get('number1')
            number2 = kwargs.get('number2')

            # Validate required parameters
            if not (number1 and number2):
                return {"error": "Missing required parameter(s)."}

            # Do the work
            result = f"Result: {number1 + number2}"

            # Return result
            return {"result": result}

        except Exception as e:
            return {"error": str(e)}