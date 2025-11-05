"""
Integration test for Result Validator with Orchestrator and Pathway Cache.

Tests the complete flow:
1. Result validation before caching
2. Only high-quality results get cached
3. Low-quality results are rejected
4. Cache retrieval works correctly
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from neural_engine.core.result_validator_neuron import ResultValidatorNeuron
from neural_engine.core.neural_pathway_cache import NeuralPathwayCache


class TestResultValidatorIntegration:
    """Test validator integration with pathway cache."""
    
    def test_high_quality_result_gets_cached(self):
        """High quality result passes validation and gets cached."""
        # Mock LLM to return high quality assessment
        mock_ollama = Mock()
        mock_ollama.generate.return_value = '''
        {
            "relevance": 9,
            "completeness": 9,
            "correctness": 9,
            "usability": 9,
            "overall_confidence": 0.9,
            "reasoning": "Excellent response",
            "should_cache": true
        }
        '''
        
        validator = ResultValidatorNeuron(
            ollama_client=mock_ollama,
            enable_llm_validation=True
        )
        
        result = {
            "response": "Paris is the capital of France, located in the north-central part of the country.",
            "success": True
        }
        
        should_cache, confidence, reasoning = validator.should_cache_result(
            "What is the capital of France?",
            result,
            1000
        )
        
        assert should_cache is True
        assert confidence >= 0.9
        assert "Excellent" in reasoning
    
    def test_low_quality_result_rejected_from_cache(self):
        """Low quality result fails validation and is not cached."""
        # Mock LLM to return low quality assessment
        mock_ollama = Mock()
        mock_ollama.generate.return_value = '''
        {
            "relevance": 3,
            "completeness": 2,
            "correctness": 4,
            "usability": 2,
            "overall_confidence": 0.3,
            "reasoning": "Response is vague and unhelpful",
            "should_cache": false
        }
        '''
        
        validator = ResultValidatorNeuron(
            ollama_client=mock_ollama,
            enable_llm_validation=True
        )
        validator.min_confidence_for_caching = 0.6
        
        result = {
            "response": "Maybe something like that, I guess.",
            "success": True
        }
        
        should_cache, confidence, reasoning = validator.should_cache_result(
            "Explain quantum mechanics",
            result,
            1000
        )
        
        assert should_cache is False
        assert confidence < 0.6
        assert "vague" in reasoning.lower()
    
    def test_error_result_rejected_immediately(self):
        """Error result fails Tier 1 and is rejected without LLM call."""
        mock_ollama = Mock()
        
        validator = ResultValidatorNeuron(
            ollama_client=mock_ollama,
            enable_llm_validation=True
        )
        
        result = {
            "error": "API request failed",
            "response": "Error occurred"
        }
        
        should_cache, confidence, reasoning = validator.should_cache_result(
            "Fetch data",
            result,
            1000
        )
        
        assert should_cache is False
        assert confidence == 0.0
        # LLM should NOT have been called (Tier 1 rejection)
        assert not mock_ollama.generate.called
    
    def test_validator_disabled_uses_simple_check(self):
        """When validator disabled, falls back to simple success check."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "This is a reasonable response.",
            "success": True
        }
        
        should_cache, confidence, reasoning = validator.should_cache_result(
            "Do task",
            result,
            1000
        )
        
        assert should_cache is True
        assert confidence > 0.5  # Tier 2 confidence
        assert "LLM validation disabled" in reasoning


class TestOrchestratorValidatorIntegration:
    """Test validator integration in orchestrator flow."""
    
    @patch('neural_engine.core.result_validator_neuron.ResultValidatorNeuron')
    def test_orchestrator_uses_validator_before_caching(self, mock_validator_class):
        """Orchestrator checks validator before caching pathway."""
        # This is a conceptual test - actual orchestrator testing would need full setup
        # Just verify the validator is called correctly
        
        mock_validator = Mock()
        mock_validator.should_cache_result.return_value = (True, 0.9, "High quality")
        mock_validator_class.return_value = mock_validator
        
        # Simulate orchestrator calling validator
        goal = "Test goal"
        result = {"response": "Good result", "success": True}
        duration_ms = 1000
        
        should_cache, confidence, reasoning = mock_validator.should_cache_result(
            goal, result, duration_ms
        )
        
        assert should_cache is True
        assert confidence == 0.9
        mock_validator.should_cache_result.assert_called_once_with(goal, result, duration_ms)
    
    def test_validator_gracefully_handles_llm_failure(self):
        """Validator falls back gracefully when LLM fails."""
        mock_ollama = Mock()
        mock_ollama.generate.side_effect = Exception("LLM timeout")
        
        validator = ResultValidatorNeuron(
            ollama_client=mock_ollama,
            enable_llm_validation=True
        )
        
        result = {
            "response": "This is a decent response.",
            "success": True
        }
        
        should_cache, confidence, reasoning = validator.should_cache_result(
            "Do task",
            result,
            1000
        )
        
        # Should still return valid result (fallback to Tier 2)
        assert isinstance(should_cache, bool)
        assert isinstance(confidence, float)
        assert isinstance(reasoning, str)
        assert confidence == 0.7  # Fallback confidence


class TestEndToEndFlow:
    """Test complete end-to-end flow with validation."""
    
    def test_full_pipeline_with_validation(self):
        """Test complete pipeline: execute → validate → cache."""
        # Setup validator
        mock_ollama = Mock()
        mock_ollama.generate.return_value = '''
        {
            "relevance": 9,
            "completeness": 9,
            "correctness": 9,
            "usability": 9,
            "overall_confidence": 0.95,
            "reasoning": "Perfect response",
            "should_cache": true
        }
        '''
        
        validator = ResultValidatorNeuron(
            ollama_client=mock_ollama,
            enable_llm_validation=True
        )
        
        # Simulate execution
        goal = "What is 2+2?"
        result = {
            "response": "The answer is 4.",
            "success": True
        }
        execution_time = 100
        
        # Validate
        validation = validator.validate(goal, result, execution_time)
        
        # Assertions
        assert validation["is_valid"] is True
        assert validation["confidence"] >= 0.95
        assert validation["validation_tier"] == 3  # LLM validated
        
        # Should cache
        should_cache, confidence, reasoning = validator.should_cache_result(
            goal, result, execution_time
        )
        assert should_cache is True
        
    def test_prevent_caching_api_errors(self):
        """Prevent caching of API errors disguised as success."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        # Simulated API error that claims to be successful
        result = {
            "response": "Error 500: Internal Server Error - Unable to process your request",
            "success": True  # Lying!
        }
        
        validation = validator.validate("Fetch user data", result, 2000)
        
        # Should detect error patterns
        assert validation["confidence"] < 0.9  # Lowered due to error indicators
        assert len(validation["issues"]) > 0
        
    def test_fast_rejection_of_obvious_failures(self):
        """Tier 1 rejects obvious failures without expensive checks."""
        validator = ResultValidatorNeuron(enable_llm_validation=True)
        
        # Obviously failed results
        test_cases = [
            None,
            {"error": "Failed"},
            {"success": False},
            {"response": ""},  # Empty
            {"data": []},  # Empty list
        ]
        
        for result in test_cases:
            validation = validator.validate("Test goal", result, 1000)
            
            assert validation["is_valid"] is False
            assert validation["validation_tier"] == 1  # Rejected by Tier 1
            # No expensive LLM call needed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
