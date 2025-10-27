from math import sqrt
from neural_engine.tools.base_tool import BaseTool

class PrimeCheckerTool(BaseTool):
    """
    Checks whether an input number is prime or not.
    """

    def get_tool_definition(self):
        return {
            "name": "prime_checker",  # snake_case, no "Tool" suffix
            "description": "Checks if a given number is prime.",
            "parameters": [
                {"name": "number", "type": "int", "description": "The number to check for primality.", "required": True}
            ]
        }

    def execute(self, **kwargs):
        """
        Checks if the given number is prime or not.
        """
        try:
            number = kwargs.get('number')

            # Validate required parameters
            if not number:
                return {"error": "Missing required parameter: number"}

            # Ensure the number is greater than one
            if number <= 1:
                return {"error": "The input number must be greater than 1 to check for primality."}

            # Check for prime numbers up to sqrt of the input number
            for i in range(2, int(sqrt(number)) + 1):
                if number % i == 0:
                    return {"error": f"The input number {number} is not a prime number."}

            # If no divisors found up to sqrt of the input number, it's prime
            return {"result": f"The input number {number} is a prime number."}
        except Exception as e:
            return {"error": str(e)}