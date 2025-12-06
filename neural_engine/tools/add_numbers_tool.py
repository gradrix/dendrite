from neural_engine.tools.base_tool import BaseTool
from typing import Optional, Dict, Any

class AddNumbersTool(BaseTool):
    """
    This tool adds two given numbers.
    """

    def get_tool_definition(self):
        return {
            "name": "add_numbers",  # snake_case, no "Tool" suffix
            "description": "Adds two provided numbers",
            "parameters": [
                {"name": "num1", "type": "float", "description": "First number to add", "required": True},
                {"name": "num2", "type": "float", "description": "Second number to add", "required": True}
            ]
        }
    
    def get_semantic_metadata(self) -> Dict[str, Any]:
        """Semantic metadata for intelligent discovery."""
        return {
            "domain": "math",
            "concepts": ["arithmetic", "addition", "numbers", "calculation", "sum"],
            "actions": ["add", "calculate", "compute", "sum"],
            "data_sources": ["user_input"],
            "synonyms": ["plus", "add up", "total", "combine"]
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
                return {"error": "Missing required parameters: num1, num2"}

            # Do the work
            result = f"Added {num1} + {num2} = {num1 + num2}"

            # Return result
            return {"result": result}

        except Exception as e:
            return {"error": str(e)}