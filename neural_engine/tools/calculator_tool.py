from neural_engine.tools.base_tool import BaseTool
import math

class CalculatorTool(BaseTool):
    """
    Improved calculator tool that fixes identified issues and provides better error handling.
    """

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return tool definition."""
        return {
            "name": "calculator",
            "description": "Perform basic math operations with improved error handling and validation",
            "parameters": [
                {
                    "name": "operation",
                    "type": "string",
                    "description": "The math operation to perform: add, subtract, multiply, or divide",
                    "required": True
                },
                {
                    "name": "a",
                    "type": "number",
                    "description": "First number",
                    "required": True
                },
                {
                    "name": "b",
                    "type": "number",
                    "description": "Second number",
                    "required": True
                }
            ]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute calculator operation with improved error handling and validation.
        """
        try:
            operation = kwargs['operation']
            a = float(kwargs['a'])
            b = float(kwargs['b'])

            if operation not in ['add', 'subtract', 'multiply', 'divide']:
                return {"error": "Invalid operation. Please choose from add, subtract, multiply, or divide."}

            if operation == 'divide' and b == 0:
                return {"error": "Error: Division by zero is not allowed."}

            result = {
                'add': a + b,
                'subtract': a - b,
                'multiply': a * b,
                'divide': a / b
            }[operation]

            return {"result": result}

        except ValueError as e:
            return {"error": f"Error: {e}. Please provide valid numbers for parameters."}