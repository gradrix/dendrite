from neural_engine.tools.base_tool import BaseTool
import math

class AdditionTool(BaseTool):
    """
    Tool for adding two numbers provided as input parameters.
    """

    def get_tool_definition(self):
        return {
            "name": "addition",  # snake_case, no "Tool" suffix
            "description": "Adds two provided numbers.",
            "parameters": [
                {"name": "number1", "type": "float", "description": "First number to be added.", "required": True},
                {"name": "number2", "type": "float", "description": "Second number to be added.", "required": True}
            ]
        }

    def execute(self, **kwargs):
        try:
            # Extract parameters with defaults for optional ones
            number1 = kwargs.get('number1', 0.0)
            number2 = kwargs.get('number2', 0.0)

            # Validate required parameters
            if not (number1 and number2):
                return {"error": "Missing required parameter(s)."}

            # Do the work
            result = f"Added {number1} and {number2}: {number1 + number2}"

            # Return result
            return {"result": result}

        except Exception as e:
            return {"error": str(e)}