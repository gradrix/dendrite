from neural_engine.tools.base_tool import BaseTool
import math

class AddNumbersTool(BaseTool):
    """
    Tool to add two numbers provided as input parameters.
    """

    def get_tool_definition(self):
        return {
            "name": "add_numbers",  # snake_case, no "Tool" suffix
            "description": "Adds two numbers provided in the parameters.",
            "parameters": [
                {"name": "num1", "type": "float", "description": "First number to add", "required": True},
                {"name": "num2", "type": "float", "description": "Second number to add", "required": True}
            ]
        }

    def execute(self, **kwargs):
        """
        Execute the tool with given parameters.
        """
        try:
            num1 = kwargs.get('num1') or 0.0  # Optional with default
            num2 = kwargs.get('num2') or 0.0  # Optional with default

            if not (num1 and num2):
                return {"error": "Missing required parameters: num1 and num2"}

            result = f"Result: {num1 + num2}"

            return {"result": result}

        except Exception as e:
            return {"error": str(e)}