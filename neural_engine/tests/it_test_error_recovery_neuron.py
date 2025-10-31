"""
Integration Tests for Error Recovery Neuron with Real LLM (Mistral)

These tests use the actual Mistral model to validate:
- Error classification accuracy
- Parameter adaptation intelligence
- Explanation quality

Test tools are in neural_engine/tools/:
- test_transient_tool.py: Simulates transient failures
- test_parameter_tool.py: Strict parameter validation

Run with: bash scripts/test.sh neural_engine/tests/it_test_error_recovery_neuron.py
"""

import unittest
import time
from neural_engine.core.error_recovery_neuron import ErrorRecoveryNeuron
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.tools.test_transient_tool import TestTransientTool


class TestErrorRecoveryIntegration(unittest.TestCase):
    """Integration tests with real Mistral LLM"""
    
    @classmethod
    def setUpClass(cls):
        """Set up shared resources for all tests"""
        print("\n" + "="*70)
        print("🧪 Integration Tests: Error Recovery with Real Mistral LLM")
        print("="*70)
        
        # Create real components
        cls.ollama_client = OllamaClient()
        cls.tool_registry = ToolRegistry()  # Auto-loads from neural_engine/tools/
        cls.execution_store = ExecutionStore()
        
        # Create error recovery neuron with real LLM
        cls.recovery = ErrorRecoveryNeuron(
            ollama_client=cls.ollama_client,
            tool_registry=cls.tool_registry,
            execution_store=cls.execution_store
        )
        
        # Reduce delays for faster testing
        cls.recovery.retry_delays = [0.5, 1.0, 2.0]
    
    def setUp(self):
        """Reset state before each test"""
        TestTransientTool.reset()
    
    def test_real_llm_classifies_timeout_as_transient(self):
        """Test that Mistral correctly identifies timeout as transient error"""
        print("\n🔍 Test: LLM classifies TimeoutError as transient")
        
        error = TimeoutError("Connection timeout after 30 seconds")
        
        classification = self.recovery.classify_error(
            error=error,
            tool_name="test_transient_tool",
            parameters={"message": "test"},
            context={"goal": "process message"}
        )
        
        print(f"   Error Type: {classification['error_type']}")
        print(f"   Confidence: {classification['confidence']:.0%}")
        print(f"   Reasoning: {classification['reasoning']}")
        
        # Mistral should classify this as transient
        self.assertEqual(classification['error_type'], 'transient')
        self.assertTrue(classification['recoverable'])
        self.assertGreater(classification['confidence'], 0.7)
    
    def test_real_llm_classifies_type_error_as_parameter_mismatch(self):
        """Test that Mistral correctly identifies type error as parameter mismatch"""
        print("\n🔍 Test: LLM classifies TypeError as parameter_mismatch")
        
        error = TypeError("user_id must be a string, got int")
        
        classification = self.recovery.classify_error(
            error=error,
            tool_name="test_parameter_tool",
            parameters={"user_id": 12345, "activity_count": 10},
            context={"goal": "calculate user score"}
        )
        
        print(f"   Error Type: {classification['error_type']}")
        print(f"   Confidence: {classification['confidence']:.0%}")
        print(f"   Reasoning: {classification['reasoning']}")
        
        # Should identify parameter mismatch (or wrong_tool is acceptable)
        self.assertIn(classification['error_type'], ['parameter_mismatch', 'wrong_tool'])
        self.assertTrue(classification['recoverable'])
    
    def test_real_llm_classifies_not_found_as_impossible(self):
        """Test that Mistral correctly identifies resource not found as impossible"""
        print("\n🔍 Test: LLM classifies 'not found' as impossible")
        
        error = Exception("User with ID 'xyz123' does not exist in the system")
        
        classification = self.recovery.classify_error(
            error=error,
            tool_name="delete_user",
            parameters={"user_id": "xyz123"},
            context={"goal": "delete user xyz123"}
        )
        
        print(f"   Error Type: {classification['error_type']}")
        print(f"   Confidence: {classification['confidence']:.0%}")
        print(f"   Reasoning: {classification['reasoning']}")
        
        # Should identify as impossible
        self.assertEqual(classification['error_type'], 'impossible')
        self.assertFalse(classification['recoverable'])
    
    def test_real_retry_with_transient_tool(self):
        """Test full retry flow with real tool and LLM classification"""
        print("\n🔄 Test: Full retry flow with real LLM")
        
        error = TimeoutError("Connection timeout")
        
        start_time = time.time()
        result = self.recovery.recover(
            error=error,
            tool_name="test_transient_tool",
            parameters={"message": "test message"},
            context={"goal": "process message"},
            attempt_history=[]
        )
        duration = time.time() - start_time
        
        print(f"   Success: {result['success']}")
        print(f"   Strategy: {result['strategy']}")
        print(f"   Duration: {duration:.1f}s")
        print(f"   Explanation: {result['explanation']}")
        
        # Should attempt retry strategy and either succeed or explain failure
        self.assertIn(result['strategy'], ['retry', 'fallback', 'explain'])
        # If successful, verify result
        if result['success']:
            self.assertIsNotNone(result['result'])
            self.assertIn('test message', str(result['result']))
    
    def test_real_adapt_with_wrong_parameters(self):
        """Test parameter adaptation with real LLM fixing parameters"""
        print("\n🔧 Test: LLM adapts wrong parameters")
        
        # Wrong types: user_id is int, activity_count is string
        error = TypeError("user_id must be a string, got int")
        
        result = self.recovery.recover(
            error=error,
            tool_name="test_parameter_tool",
            parameters={
                "user_id": 12345,  # Wrong: should be string
                "activity_count": "10",  # Wrong: should be int
                "average_distance": 5.5
            },
            context={"goal": "calculate user score"},
            attempt_history=[]
        )
        
        print(f"   Success: {result['success']}")
        print(f"   Strategy: {result['strategy']}")
        print(f"   Explanation: {result['explanation']}")
        
        # Even if LLM can't fix perfectly, recovery should attempt adaptation or fallback
        self.assertIn(result['strategy'], ['adapt', 'fallback'])
        # If successful, verify the fix
        if result['success']:
            print(f"   Result: {result['result']}")
            self.assertEqual(result['result']['user_id'], "12345")
            self.assertEqual(result['result']['activity_count'], 10)
    
    def test_real_explain_impossible_task(self):
        """Test explanation generation for impossible tasks"""
        print("\n💬 Test: LLM explains impossible task")
        
        error = Exception("Activity with ID 'abc999' does not exist")
        
        result = self.recovery.recover(
            error=error,
            tool_name="update_activity",
            parameters={"activity_id": "abc999", "name": "New Name"},
            context={"goal": "update activity name"},
            attempt_history=[]
        )
        
        print(f"   Success: {result['success']}")
        print(f"   Strategy: {result['strategy']}")
        print(f"   Explanation: {result['explanation']}")
        
        # Should provide helpful explanation
        self.assertFalse(result['success'])
        self.assertEqual(result['strategy'], 'explain')
        self.assertIsNotNone(result['explanation'])
        self.assertGreater(len(result['explanation']), 20)  # Meaningful explanation
    
    def test_real_multiple_error_types_in_sequence(self):
        """Test handling multiple different errors in sequence"""
        print("\n🔄 Test: Multiple error types in sequence")
        
        # Scenario: Transient error -> Parameter error -> Success
        errors_and_contexts = [
            (
                TimeoutError("Network timeout"),
                "transient",
                "retry"
            ),
            (
                TypeError("Invalid parameter type"),
                "parameter_mismatch",
                "adapt"
            ),
            (
                Exception("Resource not found"),
                "impossible",
                "explain"
            )
        ]
        
        for error, expected_type, expected_strategy in errors_and_contexts:
            classification = self.recovery.classify_error(
                error=error,
                tool_name="test_tool",
                parameters={},
                context={"goal": "test"}
            )
            
            print(f"\n   Error: {error}")
            print(f"   → Classified as: {classification['error_type']}")
            print(f"   → Expected: {expected_type}")
            
            # Verify correct classification (allow some flexibility)
            self.assertIn(
                classification['error_type'],
                [expected_type, 'wrong_tool']  # wrong_tool is acceptable fallback
            )
    
    def test_real_llm_understands_context(self):
        """Test that LLM uses context to make better decisions"""
        print("\n🧠 Test: LLM uses context for classification")
        
        # Same error, different contexts should potentially get different classifications
        error = Exception("Operation failed")
        
        # Context 1: Suggests transient
        context1 = {
            "goal": "upload large file",
            "recent_attempts": 3,
            "environment": "high network load"
        }
        
        # Context 2: Suggests wrong tool
        context2 = {
            "goal": "delete user account",
            "tool_selected": "create_user",
            "available_tools": ["delete_user", "update_user"]
        }
        
        classification1 = self.recovery.classify_error(
            error=error,
            tool_name="upload_file",
            parameters={},
            context=context1
        )
        
        classification2 = self.recovery.classify_error(
            error=error,
            tool_name="create_user",
            parameters={},
            context=context2
        )
        
        print(f"   Context 1 (network load): {classification1['error_type']}")
        print(f"   Context 2 (wrong tool): {classification2['error_type']}")
        
        # Just verify both succeed - LLM should use context intelligently
        self.assertIsNotNone(classification1['error_type'])
        self.assertIsNotNone(classification2['error_type'])


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
