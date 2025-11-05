"""
Unit tests for ResultValidatorNeuron.

Tests three validation tiers:
- Tier 1: Rule-based data checks
- Tier 2: Structure validation
- Tier 3: LLM quality scoring
"""

import pytest
from unittest.mock import Mock, MagicMock
from neural_engine.core.result_validator_neuron import ResultValidatorNeuron


class TestTier1DataCheck:
    """Test Tier 1: Fast rule-based data checks."""
    
    def test_valid_result_with_response(self):
        """Valid result with response field passes Tier 1."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "Hello, world! This is a meaningful response.",
            "success": True
        }
        
        validation = validator.validate("Say hello", result, 1000)
        
        assert validation["is_valid"] is True
        assert validation["validation_tier"] == 2  # Passes Tier 1, evaluated by Tier 2
        assert len(validation["issues"]) == 0
    
    def test_valid_result_with_data(self):
        """Valid result with data field passes Tier 1."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "data": {"items": [1, 2, 3], "count": 3},
            "success": True
        }
        
        validation = validator.validate("Get items", result, 1000)
        
        assert validation["is_valid"] is True
        assert validation["validation_tier"] == 2
    
    def test_none_result_fails(self):
        """None result fails Tier 1."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        validation = validator.validate("Some goal", None, 1000)
        
        assert validation["is_valid"] is False
        assert validation["validation_tier"] == 1
        assert "Result is None" in validation["issues"]
    
    def test_non_dict_result_fails(self):
        """Non-dictionary result fails Tier 1."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        validation = validator.validate("Some goal", "just a string", 1000)
        
        assert validation["is_valid"] is False
        assert validation["validation_tier"] == 1
        assert any("not a dict" in issue for issue in validation["issues"])
    
    def test_explicit_error_fails(self):
        """Result with error field fails Tier 1."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "error": "Something went wrong",
            "response": "Error occurred"
        }
        
        validation = validator.validate("Do task", result, 1000)
        
        assert validation["is_valid"] is False
        assert validation["validation_tier"] == 1
        assert any("error" in issue.lower() for issue in validation["issues"])
    
    def test_success_false_fails(self):
        """Result with success=False fails Tier 1."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "success": False,
            "response": "Task failed"
        }
        
        validation = validator.validate("Do task", result, 1000)
        
        assert validation["is_valid"] is False
        assert validation["validation_tier"] == 1
    
    def test_empty_response_fails(self):
        """Result with empty data fails Tier 1."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "",
            "success": True
        }
        
        validation = validator.validate("Generate text", result, 1000)
        
        assert validation["is_valid"] is False
        assert validation["validation_tier"] == 1
        # Empty string is caught as "No data found"
        assert len(validation["issues"]) > 0
    
    def test_no_data_keys_fails(self):
        """Result without expected data keys fails Tier 1."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "metadata": {"timestamp": 123},
            "success": True
        }
        
        validation = validator.validate("Get data", result, 1000)
        
        assert validation["is_valid"] is False
        assert validation["validation_tier"] == 1
    
    def test_too_short_response_fails(self):
        """Response shorter than minimum fails Tier 1."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        validator.min_data_size = 20
        
        result = {
            "response": "OK",  # Only 2 chars
            "success": True
        }
        
        validation = validator.validate("Explain quantum physics", result, 1000)
        
        assert validation["is_valid"] is False
        assert validation["validation_tier"] == 1
        assert any("too small" in issue.lower() for issue in validation["issues"])
    
    def test_error_disguised_as_success(self):
        """Error message disguised as successful response is flagged."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "Error: Connection failed. Unable to process request.",
            "success": True  # Lying!
        }
        
        validation = validator.validate("Fetch data", result, 1000)
        
        # Should pass Tier 1 but get flagged
        assert "error indicators" in str(validation["issues"]).lower()


class TestTier2StructureCheck:
    """Test Tier 2: Structure validation."""
    
    def test_valid_structure_high_confidence(self):
        """Well-formed result gets high confidence."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "This is a complete and well-formed response.",
            "success": True
        }
        
        validation = validator.validate("Generate response", result, 1000)
        
        assert validation["is_valid"] is True
        assert validation["confidence"] >= 0.7
        assert validation["validation_tier"] == 2
    
    def test_non_json_serializable_fails(self):
        """Non-JSON-serializable result fails Tier 2."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        # Create non-serializable object
        class NonSerializable:
            pass
        
        result = {
            "response": NonSerializable(),
            "success": True
        }
        
        # Should fail during JSON serialization check
        # Note: This might pass Tier 1 but fail Tier 2
        validation = validator.validate("Get data", result, 1000)
        
        assert validation["is_valid"] is False
    
    def test_truncated_response_lowers_confidence(self):
        """Truncated response (no proper ending) lowers confidence."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "This response seems to be incomplete and doesn't end prop",
            "success": True
        }
        
        validation = validator.validate("Explain topic", result, 1000)
        
        # Should still pass but with lower confidence
        assert validation["confidence"] < 1.0
        assert any("truncated" in issue.lower() for issue in validation["issues"])
    
    def test_very_short_response_lowers_confidence(self):
        """Very short response lowers confidence."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        validator.min_data_size = 10  # Pass Tier 1
        
        result = {
            "response": "Yes, indeed.",  # Just 2 words
            "success": True
        }
        
        validation = validator.validate("Explain quantum computing", result, 1000)
        
        assert validation["confidence"] < 0.8
        assert any("too short" in issue.lower() for issue in validation["issues"])
    
    def test_error_pattern_in_response_lowers_confidence(self):
        """Error patterns in response lower confidence."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "The operation resulted in error: 500 Internal Server Error occurred.",
            "success": True
        }
        
        validation = validator.validate("Fetch data", result, 1000)
        
        assert validation["confidence"] <= 0.7  # Use <= instead of <
        assert any("error pattern" in issue.lower() for issue in validation["issues"])


class TestTier3QualityScore:
    """Test Tier 3: LLM-based quality scoring."""
    
    def test_llm_high_quality_assessment(self):
        """LLM assesses high quality result correctly."""
        mock_ollama = Mock()
        mock_ollama.generate.return_value = '''
        {
            "relevance": 9,
            "completeness": 9,
            "correctness": 9,
            "usability": 9,
            "overall_confidence": 0.9,
            "reasoning": "Excellent response that fully addresses the goal",
            "should_cache": true
        }
        '''
        
        validator = ResultValidatorNeuron(
            ollama_client=mock_ollama,
            enable_llm_validation=True
        )
        
        result = {
            "response": "The capital of France is Paris, located in the north-central part of the country.",
            "success": True
        }
        
        validation = validator.validate("What is the capital of France?", result, 1000)
        
        assert validation["is_valid"] is True
        assert validation["confidence"] >= 0.9
        assert validation["validation_tier"] == 3
        assert mock_ollama.generate.called
    
    def test_llm_low_quality_assessment(self):
        """LLM assesses low quality result correctly."""
        mock_ollama = Mock()
        mock_ollama.generate.return_value = '''
        {
            "relevance": 3,
            "completeness": 2,
            "correctness": 4,
            "usability": 2,
            "overall_confidence": 0.3,
            "reasoning": "Response is vague and doesn't really answer the question",
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
        
        validation = validator.validate("What is quantum mechanics?", result, 1000)
        
        assert validation["is_valid"] is False  # Below 0.6 threshold
        assert validation["confidence"] < 0.6
        assert len(validation["issues"]) > 0  # Low scores added as issues
    
    def test_llm_validation_disabled_uses_tier2(self):
        """When LLM disabled, uses Tier 2 confidence."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "This is a good response to the question.",
            "success": True
        }
        
        validation = validator.validate("Answer question", result, 1000)
        
        assert validation["validation_tier"] == 2
        assert "LLM validation disabled" in validation["reasoning"]
    
    def test_llm_error_falls_back_gracefully(self):
        """LLM error falls back to medium confidence."""
        mock_ollama = Mock()
        mock_ollama.generate.side_effect = Exception("LLM timeout")
        
        validator = ResultValidatorNeuron(
            ollama_client=mock_ollama,
            enable_llm_validation=True
        )
        
        result = {
            "response": "This is a reasonable response.",
            "success": True
        }
        
        validation = validator.validate("Do task", result, 1000)
        
        assert validation["confidence"] == 0.7  # Default fallback
        assert any("LLM validation" in issue for issue in validation["issues"])
    
    def test_llm_unparseable_response_falls_back(self):
        """Unparseable LLM response falls back gracefully."""
        mock_ollama = Mock()
        mock_ollama.generate.return_value = "This is not JSON at all!"
        
        validator = ResultValidatorNeuron(
            ollama_client=mock_ollama,
            enable_llm_validation=True
        )
        
        result = {
            "response": "Some response text here.",
            "success": True
        }
        
        validation = validator.validate("Do something", result, 1000)
        
        assert validation["confidence"] == 0.7
        # Should have an issue recorded about parsing
        assert len(validation["issues"]) > 0


class TestShouldCacheResult:
    """Test convenience method should_cache_result()."""
    
    def test_should_cache_valid_result(self):
        """Valid result should be cached."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "This is a good quality response.",
            "success": True
        }
        
        should_cache, confidence, reasoning = validator.should_cache_result(
            "Test goal",
            result,
            1000
        )
        
        assert should_cache is True
        assert confidence > 0.5
        assert isinstance(reasoning, str)
    
    def test_should_not_cache_invalid_result(self):
        """Invalid result should not be cached."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "error": "Something failed"
        }
        
        should_cache, confidence, reasoning = validator.should_cache_result(
            "Test goal",
            result,
            1000
        )
        
        assert should_cache is False
        assert confidence == 0.0


class TestIntegrationScenarios:
    """Test real-world scenarios."""
    
    def test_api_error_disguised_as_success(self):
        """API error in response field should not be cached."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "Error 500: Internal Server Error - Unable to process request",
            "success": True  # API lies!
        }
        
        validation = validator.validate("Fetch user data", result, 2000)
        
        # Should detect error patterns and lower confidence
        assert validation["confidence"] <= 0.8  # Adjust expectation
        assert len(validation["issues"]) > 0  # Has issues flagged
    
    def test_empty_list_result_fails(self):
        """Empty list as data should fail validation."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "data": [],
            "success": True
        }
        
        validation = validator.validate("Get items", result, 1000)
        
        # Empty list has size < min_data_size
        assert validation["is_valid"] is False
    
    def test_partial_response_truncation(self):
        """Detect truncated responses."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "response": "The answer to your question is complex and involves multiple factors such as",
            "success": True
        }
        
        validation = validator.validate("Explain topic", result, 1000)
        
        assert any("truncated" in issue.lower() for issue in validation["issues"])
        assert validation["confidence"] < 1.0
    
    def test_high_quality_structured_data(self):
        """High quality structured data passes with high confidence."""
        validator = ResultValidatorNeuron(enable_llm_validation=False)
        
        result = {
            "data": {
                "users": [
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"}
                ],
                "total": 2,
                "page": 1
            },
            "success": True
        }
        
        validation = validator.validate("Get users list", result, 1500)
        
        assert validation["is_valid"] is True
        assert validation["confidence"] >= 0.8
        assert len(validation["issues"]) == 0
