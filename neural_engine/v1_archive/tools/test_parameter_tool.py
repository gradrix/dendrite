"""
Test tool for integration testing: strict parameter validation
"""
from neural_engine.tools.base_tool import BaseTool


class TestParameterTool(BaseTool):
    """Tool with strict parameter validation - for testing adapt strategy"""
    
    name = "test_parameter_tool"
    description = "Calculate user score based on activity data"
    parameters = {
        "user_id": {"type": "string", "description": "User identifier", "required": True},
        "activity_count": {"type": "integer", "description": "Number of activities", "required": True},
        "average_distance": {"type": "number", "description": "Average distance in km"}
    }
    
    @classmethod
    def get_tool_definition(cls):
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.parameters
        }
    
    def execute(self, user_id, activity_count, average_distance=0.0):
        # Validate types strictly
        if not isinstance(user_id, str):
            raise TypeError(f"user_id must be a string, got {type(user_id).__name__}")
        if not isinstance(activity_count, int):
            raise TypeError(f"activity_count must be an integer, got {type(activity_count).__name__}")
        if not isinstance(average_distance, (int, float)):
            raise TypeError(f"average_distance must be a number, got {type(average_distance).__name__}")
        
        # Calculate score
        score = activity_count * 10 + average_distance * 5
        return {
            "user_id": user_id,
            "score": score,
            "activity_count": activity_count,
            "average_distance": average_distance
        }
