from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseTool(ABC):
    """
    Base class for all tools.
    
    Tools can declare their characteristics for safe testing:
    - idempotent: Can be run multiple times with same inputs safely
    - side_effects: What external changes the tool makes
    - safe_for_shadow_testing: Can run alongside old version without issues
    """
    
    @abstractmethod
    def get_tool_definition(self):
        """
        Return tool definition with name, description, and parameters.
        
        Returns:
            dict: {
                "name": str,
                "description": str,
                "parameters": List[dict]
            }
        """
        pass

    @abstractmethod
    def execute(self, **kwargs):
        """
        Execute the tool with given parameters.
        
        Returns:
            dict: Execution result
        """
        pass
    
    def get_tool_characteristics(self) -> Dict[str, Any]:
        """
        Declare tool characteristics for safe testing.
        
        Override this in subclasses to specify tool behavior.
        
        Returns:
            dict: {
                "idempotent": bool,  # Can run multiple times safely?
                "side_effects": List[str],  # ['writes_to_db', 'sends_email', etc.]
                "safe_for_shadow_testing": bool,  # Can test on real traffic?
                "requires_mocking": List[str],  # ['database', 'api', etc.]
                "test_data_available": bool  # Has synthetic test cases?
            }
        """
        # Default: Assume tools are NOT safe (conservative)
        return {
            "idempotent": False,
            "side_effects": ["unknown"],
            "safe_for_shadow_testing": False,
            "requires_mocking": [],
            "test_data_available": False
        }
    
    def get_test_cases(self) -> List[Dict[str, Any]]:
        """
        Provide synthetic test cases for non-idempotent tools.
        
        Override this to provide test data for validation.
        
        Returns:
            List[dict]: [
                {
                    "input": dict,  # Parameters to pass to execute()
                    "expected_output": dict,  # Expected result
                    "should_raise": Optional[Exception],  # Expected exception
                    "description": str  # What this test verifies
                },
                ...
            ]
        """
        return []

