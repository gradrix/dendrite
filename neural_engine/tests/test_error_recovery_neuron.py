"""
Tests for Phase 10d: Error Recovery Neuron

Tests intelligent error handling and recovery strategies.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import time
from neural_engine.core.error_recovery_neuron import ErrorRecoveryNeuron
from neural_engine.tools.base_tool import BaseTool


class MockTransientTool(BaseTool):
    """Tool that fails transiently then succeeds"""
    name = "mock_transient_tool"
    description = "Fails twice then succeeds"
    parameters = {"value": {"type": "string"}}
    
    call_count = 0
    
    @classmethod
    def get_tool_definition(cls):
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.parameters
        }
    
    def execute(self, value):
        MockTransientTool.call_count += 1
        if MockTransientTool.call_count < 3:
            raise TimeoutError("Connection timeout")
        return {"result": f"success: {value}"}


class MockParameterTool(BaseTool):
    """Tool with strict parameter requirements"""
    name = "mock_parameter_tool"
    description = "Requires specific parameters"
    parameters = {
        "required_field": {"type": "string", "required": True},
        "number_field": {"type": "integer"}
    }
    
    @classmethod
    def get_tool_definition(cls):
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.parameters
        }
    
    def execute(self, required_field, number_field=0):
        if not isinstance(required_field, str):
            raise TypeError("required_field must be a string")
        if not isinstance(number_field, int):
            raise TypeError("number_field must be an integer")
        return {"result": f"{required_field}: {number_field}"}


class TestErrorRecoveryNeuron(unittest.TestCase):
    """Test suite for error recovery functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Reset call count
        MockTransientTool.call_count = 0
        
        # Mock ollama client
        self.mock_ollama = Mock()
        
        # Mock tool registry
        self.mock_registry = Mock()
        self.mock_registry.get_tool = Mock(side_effect=self._mock_get_tool)
        
        # Mock execution store
        self.mock_store = Mock()
        
        # Create error recovery neuron
        self.recovery = ErrorRecoveryNeuron(
            ollama_client=self.mock_ollama,
            tool_registry=self.mock_registry,
            execution_store=self.mock_store
        )
    
    def _mock_get_tool(self, tool_name):
        """Mock tool registry get_tool - returns instances like real registry"""
        tools = {
            "mock_transient_tool": MockTransientTool(),
            "mock_parameter_tool": MockParameterTool()
        }
        return tools.get(tool_name)
    
    def test_classify_error_transient(self):
        """Test classification of transient errors"""
        # Mock LLM response
        self.mock_ollama.generate = Mock(return_value='''```json
{
    "error_type": "transient",
    "confidence": 0.95,
    "reasoning": "TimeoutError indicates temporary network issue",
    "recoverable": true
}
```''')
        
        error = TimeoutError("Connection timeout")
        classification = self.recovery.classify_error(
            error=error,
            tool_name="test_tool",
            parameters={"value": "test"},
            context={"goal": "test goal"}
        )
        
        self.assertEqual(classification['error_type'], 'transient')
        self.assertTrue(classification['recoverable'])
        self.assertGreater(classification['confidence'], 0.8)
    
    def test_classify_error_parameter_mismatch(self):
        """Test classification of parameter errors"""
        self.mock_ollama.generate = Mock(return_value='''```json
{
    "error_type": "parameter_mismatch",
    "confidence": 0.90,
    "reasoning": "TypeError indicates wrong parameter type",
    "recoverable": true
}
```''')
        
        error = TypeError("required_field must be a string")
        classification = self.recovery.classify_error(
            error=error,
            tool_name="test_tool",
            parameters={"required_field": 123},
            context={"goal": "test goal"}
        )
        
        self.assertEqual(classification['error_type'], 'parameter_mismatch')
        self.assertTrue(classification['recoverable'])
    
    def test_classify_error_impossible(self):
        """Test classification of impossible tasks"""
        self.mock_ollama.generate = Mock(return_value='''```json
{
    "error_type": "impossible",
    "confidence": 0.95,
    "reasoning": "Resource does not exist",
    "recoverable": false
}
```''')
        
        error = Exception("User not found")
        classification = self.recovery.classify_error(
            error=error,
            tool_name="delete_user",
            parameters={"user_id": "999"},
            context={"goal": "delete user"}
        )
        
        self.assertEqual(classification['error_type'], 'impossible')
        self.assertFalse(classification['recoverable'])
    
    def test_fallback_classification_transient(self):
        """Test heuristic classification for transient errors"""
        # Make LLM fail
        self.mock_ollama.generate = Mock(side_effect=Exception("LLM error"))
        
        error = TimeoutError("Connection timeout")
        classification = self.recovery.classify_error(
            error=error,
            tool_name="test_tool",
            parameters={},
            context={}
        )
        
        # Should fallback to heuristic classification
        self.assertEqual(classification['error_type'], 'transient')
        self.assertTrue(classification['recoverable'])
    
    def test_fallback_classification_parameter(self):
        """Test heuristic classification for parameter errors"""
        self.mock_ollama.generate = Mock(side_effect=Exception("LLM error"))
        
        error = TypeError("missing required parameter")
        classification = self.recovery.classify_error(
            error=error,
            tool_name="test_tool",
            parameters={},
            context={}
        )
        
        self.assertEqual(classification['error_type'], 'parameter_mismatch')
    
    def test_retry_strategy_success(self):
        """Test retry strategy succeeds after retries"""
        # Reduce delay for testing
        self.recovery.retry_delays = [0.01, 0.02, 0.05]
        
        # First call fails, second succeeds
        error = TimeoutError("Connection timeout")
        
        result = self.recovery._retry_strategy(
            error=error,
            tool_name="mock_transient_tool",
            parameters={"value": "test"},
            context={},
            attempt_history=[]
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['strategy'], 'retry')
        self.assertIsNotNone(result['result'])
        self.assertIn('retry #', result['explanation'].lower())
        self.assertIn('succeeded', result['explanation'].lower())
    
    def test_retry_strategy_max_retries(self):
        """Test retry strategy gives up after max retries"""
        self.recovery.retry_delays = [0.01, 0.02, 0.05]
        self.recovery.max_retries = 2
        
        # Tool that always fails
        self.mock_registry.get_tool = Mock(return_value=None)
        
        error = TimeoutError("Connection timeout")
        
        result = self.recovery._retry_strategy(
            error=error,
            tool_name="nonexistent_tool",
            parameters={},
            context={},
            attempt_history=[
                {"strategy": "retry", "attempt": 1},
                {"strategy": "retry", "attempt": 2}
            ]
        )
        
        self.assertFalse(result['success'])
        self.assertIn('failed after', result['explanation'].lower())
    
    def test_fallback_strategy(self):
        """Test fallback strategy suggests tool reselection"""
        error = Exception("Tool doesn't support this operation")
        
        result = self.recovery._fallback_strategy(
            error=error,
            tool_name="wrong_tool",
            parameters={},
            context={"goal": "update activity"},
            attempt_history=[]
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['strategy'], 'fallback')
        self.assertTrue(result['should_continue'])
        self.assertIsNotNone(result['next_action'])
        self.assertEqual(result['next_action']['type'], 'reselect_tool')
    
    def test_fallback_strategy_max_attempts(self):
        """Test fallback gives up after max attempts"""
        self.recovery.max_fallbacks = 2
        
        error = Exception("Tool error")
        
        result = self.recovery._fallback_strategy(
            error=error,
            tool_name="tool1",
            parameters={},
            context={},
            attempt_history=[
                {"strategy": "fallback", "tool_name": "tool1"},
                {"strategy": "fallback", "tool_name": "tool2"}
            ]
        )
        
        self.assertFalse(result['success'])
        self.assertIn('alternative tools', result['explanation'].lower())
    
    def test_adapt_strategy_success(self):
        """Test adapt strategy fixes parameters"""
        # Mock LLM to return fixed parameters
        self.mock_ollama.generate = Mock(return_value='''```json
{
    "required_field": "fixed_value",
    "number_field": 42
}
```''')
        
        error = TypeError("required_field must be a string")
        
        result = self.recovery._adapt_strategy(
            error=error,
            tool_name="mock_parameter_tool",
            parameters={"required_field": 123, "number_field": "not_a_number"},
            context={},
            attempt_history=[]
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['strategy'], 'adapt')
        self.assertIsNotNone(result['result'])
    
    def test_adapt_strategy_max_adaptations(self):
        """Test adapt gives up after max attempts"""
        self.recovery.max_adaptations = 1
        
        # Mock LLM to always return bad parameters
        self.mock_ollama.generate = Mock(return_value='{"bad": "params"}')
        
        error = TypeError("parameter error")
        
        result = self.recovery._adapt_strategy(
            error=error,
            tool_name="mock_parameter_tool",
            parameters={},
            context={},
            attempt_history=[{"strategy": "adapt", "attempt": 1}]
        )
        
        self.assertFalse(result['success'])
        self.assertIn('could not fix', result['explanation'].lower())
    
    def test_explain_failure(self):
        """Test explanation generation for unrecoverable errors"""
        # Mock LLM explanation
        self.mock_ollama.generate = Mock(return_value=
            "The user you're trying to delete doesn't exist. Please verify the user ID."
        )
        
        error = Exception("User not found")
        classification = {
            "error_type": "impossible",
            "confidence": 0.95,
            "reasoning": "Resource does not exist",
            "recoverable": False
        }
        
        result = self.recovery._explain_failure(
            error=error,
            tool_name="delete_user",
            parameters={"user_id": "999"},
            context={"goal": "delete user 999"},
            classification=classification
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['strategy'], 'explain')
        self.assertIsNotNone(result['explanation'])
        self.assertIn('user', result['explanation'].lower())
    
    def test_recover_transient_error(self):
        """Test full recovery flow for transient error"""
        self.recovery.retry_delays = [0.01, 0.02]
        
        # Mock classification
        self.mock_ollama.generate = Mock(return_value='''```json
{
    "error_type": "transient",
    "confidence": 0.95,
    "reasoning": "Timeout error",
    "recoverable": true
}
```''')
        
        error = TimeoutError("Connection timeout")
        
        result = self.recovery.recover(
            error=error,
            tool_name="mock_transient_tool",
            parameters={"value": "test"},
            context={"goal": "test goal"},
            attempt_history=[]
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['strategy'], 'retry')
    
    def test_recover_impossible_error(self):
        """Test full recovery flow for impossible error"""
        # Mock classification
        self.mock_ollama.generate = Mock(side_effect=[
            # Classification
            '''```json
{
    "error_type": "impossible",
    "confidence": 0.95,
    "reasoning": "Resource not found",
    "recoverable": false
}
```''',
            # Explanation
            "The resource you're looking for doesn't exist."
        ])
        
        error = Exception("Not found")
        
        result = self.recovery.recover(
            error=error,
            tool_name="get_resource",
            parameters={"id": "999"},
            context={"goal": "get resource"},
            attempt_history=[]
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['strategy'], 'explain')
        self.assertIsNotNone(result['explanation'])
    
    def test_recover_parameter_mismatch(self):
        """Test full recovery flow for parameter mismatch"""
        # Mock classification and fix
        self.mock_ollama.generate = Mock(side_effect=[
            # Classification
            '''```json
{
    "error_type": "parameter_mismatch",
    "confidence": 0.90,
    "reasoning": "Type error in parameters",
    "recoverable": true
}
```''',
            # Fixed parameters
            '''```json
{
    "required_field": "fixed",
    "number_field": 123
}
```'''
        ])
        
        error = TypeError("Type error")
        
        result = self.recovery.recover(
            error=error,
            tool_name="mock_parameter_tool",
            parameters={"required_field": 123},
            context={},
            attempt_history=[]
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['strategy'], 'adapt')


if __name__ == '__main__':
    unittest.main()
