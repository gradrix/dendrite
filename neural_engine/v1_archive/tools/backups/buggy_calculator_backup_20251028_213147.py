"""
Deliberately buggy calculator tool for autonomous improvement demo.

This tool has several intentional bugs:
1. Division by zero not handled
2. No input validation
3. Missing error messages
4. String inputs cause crashes
"""

from typing import Any, Dict
from neural_engine.tools.base_tool import BaseTool


class BuggyCalculatorTool(BaseTool):
    """
    A calculator tool with intentional bugs for demonstration.
    """
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return tool definition."""
        return {
            "name": "buggy_calculator",
            "description": "Perform basic math operations (INTENTIONALLY BUGGY VERSION)",
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
        Execute calculator operation.
        
        BUGS:
        - No division by zero check
        - No input validation
        - No type checking
        - Poor error handling
        """
        operation = kwargs['operation']
        a = kwargs['a']
        b = kwargs['b']
        
        # BUG: No input validation - will crash if a or b are not numbers
        # BUG: No division by zero check
        if operation == 'add':
            result = a + b
        elif operation == 'subtract':
            result = a - b
        elif operation == 'multiply':
            result = a * b
        elif operation == 'divide':
            result = a / b  # BUG: Will crash on divide by zero!
        else:
            result = None
        
        return {
            'success': True,
            'result': result,
            'operation': operation
        }
