"""
Result Validator Neuron - Validates execution results before caching.

Phase 2 Enhancement: Ensures only high-quality, successful results get cached.

Validation Strategy:
1. Data Check (Rule-based): Fast checks for data presence
2. Structure Validation (Rule-based + optional LLM): Verify response format
3. Confidence Scoring (LLM-assisted): Assess result quality

This prevents caching of:
- Empty responses
- Error messages disguised as success
- Malformed data
- Low-quality outputs
"""

import json
from typing import Dict, Any, Optional, Tuple
from neural_engine.core.ollama_client import OllamaClient


class ResultValidatorNeuron:
    """
    Validates execution results to ensure quality before caching.
    
    Three-tier validation:
    - Tier 1: Fast rule-based checks (no LLM)
    - Tier 2: Structure validation (optional LLM)
    - Tier 3: Quality scoring (LLM for confidence)
    """
    
    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        enable_llm_validation: bool = True
    ):
        """
        Initialize ResultValidatorNeuron.
        
        Args:
            ollama_client: Client for LLM-based validation (optional)
            enable_llm_validation: If False, uses only rule-based checks (faster)
        """
        self.ollama_client = ollama_client
        self.enable_llm_validation = enable_llm_validation
        
        # Validation thresholds
        self.min_confidence_for_caching = 0.6
        self.min_data_size = 10  # Minimum characters in meaningful response
        
    def validate(
        self,
        goal: str,
        result: Dict[str, Any],
        execution_time_ms: int
    ) -> Dict[str, Any]:
        """
        Validate execution result with three-tier approach.
        
        Args:
            goal: Original goal/prompt
            result: Execution result to validate
            execution_time_ms: Execution time
            
        Returns:
            {
                "is_valid": bool,
                "confidence": 0.0-1.0,
                "validation_tier": 1-3,
                "issues": [list of issues found],
                "reasoning": str
            }
        """
        issues = []
        
        # Tier 1: Rule-based data checks (FAST)
        tier1_result = self._tier1_data_check(result, issues)
        if not tier1_result["passed"]:
            return {
                "is_valid": False,
                "confidence": 0.0,
                "validation_tier": 1,
                "issues": issues,
                "reasoning": tier1_result["reason"]
            }
        
        # Tier 2: Structure validation (MEDIUM)
        tier2_result = self._tier2_structure_check(result, issues)
        if not tier2_result["passed"]:
            return {
                "is_valid": False,
                "confidence": tier2_result["confidence"],
                "validation_tier": 2,
                "issues": issues,
                "reasoning": tier2_result["reason"]
            }
        
        # Tier 3: Quality scoring (SLOW - LLM)
        if self.enable_llm_validation and self.ollama_client:
            tier3_result = self._tier3_quality_score(goal, result, issues)
            return {
                "is_valid": tier3_result["confidence"] >= self.min_confidence_for_caching,
                "confidence": tier3_result["confidence"],
                "validation_tier": 3,
                "issues": issues,
                "reasoning": tier3_result["reasoning"]
            }
        else:
            # Skip LLM validation - use Tier 2 confidence
            return {
                "is_valid": True,
                "confidence": tier2_result["confidence"],
                "validation_tier": 2,
                "issues": issues,
                "reasoning": "Passed structure validation (LLM validation disabled)"
            }
    
    def _tier1_data_check(
        self,
        result: Dict[str, Any],
        issues: list
    ) -> Dict[str, Any]:
        """
        Tier 1: Fast rule-based checks for data presence.
        
        Checks:
        - Result is not None/empty
        - Contains expected keys
        - No obvious error indicators
        - Has meaningful content
        """
        # Check 1.1: Result exists
        if result is None:
            issues.append("Result is None")
            return {"passed": False, "reason": "Result is None"}
        
        # Check 1.2: Result is dict
        if not isinstance(result, dict):
            issues.append(f"Result is not a dict (got {type(result).__name__})")
            return {"passed": False, "reason": "Result must be a dictionary"}
        
        # Check 1.3: Not explicitly marked as error
        if result.get("error"):
            issues.append(f"Result contains error: {result.get('error')}")
            return {"passed": False, "reason": "Result marked as error"}
        
        if result.get("success") is False:
            issues.append("Result marked success=False")
            return {"passed": False, "reason": "Result explicitly failed"}
        
        # Check 1.4: Contains data (not empty)
        # Look for common data keys
        data_keys = ["response", "data", "result", "output", "value", "content"]
        has_data = False
        data_size = 0
        
        for key in data_keys:
            if key in result and result[key]:
                has_data = True
                # Check data size
                if isinstance(result[key], str):
                    data_size = len(result[key])
                elif isinstance(result[key], (list, dict)):
                    data_size = len(json.dumps(result[key]))
                break
        
        if not has_data:
            issues.append("Result contains no data in expected keys")
            return {"passed": False, "reason": "No data found in result"}
        
        if data_size < self.min_data_size:
            issues.append(f"Data too small ({data_size} chars < {self.min_data_size})")
            return {"passed": False, "reason": f"Data too small: {data_size} chars"}
        
        # Check 1.5: Not just an error message disguised
        response_text = str(result.get("response", result.get("data", "")))
        error_indicators = [
            "error", "failed", "exception", "could not",
            "unable to", "invalid", "not found", "forbidden",
            "unauthorized", "timeout", "connection refused"
        ]
        
        response_lower = response_text.lower()
        error_count = sum(1 for indicator in error_indicators if indicator in response_lower)
        
        if error_count >= 2:  # Multiple error indicators
            issues.append(f"Response contains {error_count} error indicators")
            # Don't fail immediately, but flag for Tier 2
        
        return {"passed": True, "reason": "Tier 1 checks passed"}
    
    def _tier2_structure_check(
        self,
        result: Dict[str, Any],
        issues: list
    ) -> Dict[str, Any]:
        """
        Tier 2: Structure validation with confidence scoring.
        
        Checks:
        - Response format is valid
        - Data types are correct
        - No suspicious patterns
        """
        confidence = 1.0  # Start high, deduct for issues
        
        # Check 2.1: JSON structure integrity
        try:
            # Ensure result is JSON-serializable
            json.dumps(result)
        except (TypeError, ValueError) as e:
            issues.append(f"Result not JSON-serializable: {e}")
            return {"passed": False, "confidence": 0.0, "reason": "Invalid JSON structure"}
        
        # Check 2.2: Response type consistency
        response_data = result.get("response") or result.get("data")
        if response_data:
            # If it's supposed to be structured data but is just a string error
            if isinstance(response_data, str):
                error_patterns = [
                    r"error:.*",
                    r"exception:.*",
                    r"\d{3}\s+error",  # HTTP error codes
                    r"failed to.*"
                ]
                import re
                for pattern in error_patterns:
                    if re.search(pattern, response_data, re.IGNORECASE):
                        confidence -= 0.3
                        issues.append(f"Response matches error pattern: {pattern}")
        
        # Check 2.3: Completeness
        # Check if response seems truncated or incomplete
        response_text = str(result.get("response", ""))
        if response_text and len(response_text) > 50:
            # Check for incomplete sentences
            if not response_text.rstrip().endswith((".", "!", "?", '"', "}", "]")):
                confidence -= 0.2
                issues.append("Response appears truncated (no proper ending)")
        
        # Check 2.4: Meaningful content ratio
        if response_text:
            # Ratio of meaningful words vs total length
            words = response_text.split()
            if len(words) < 3:
                confidence -= 0.3
                issues.append(f"Response too short: {len(words)} words")
        
        # Decide if passed
        passed = confidence >= 0.5
        reason = "Structure validation passed" if passed else "Structure validation failed"
        
        return {
            "passed": passed,
            "confidence": max(0.0, confidence),
            "reason": reason
        }
    
    def _tier3_quality_score(
        self,
        goal: str,
        result: Dict[str, Any],
        issues: list
    ) -> Dict[str, Any]:
        """
        Tier 3: LLM-based quality assessment.
        
        Uses LLM to assess:
        - Does result actually answer the goal?
        - Is the quality acceptable?
        - Should this be cached for reuse?
        """
        response_text = str(result.get("response", result.get("data", "")))
        
        prompt = f"""Evaluate if this execution result is high-quality and should be cached for future use.

GOAL:
{goal}

RESULT:
{response_text[:500]}  # Limit to avoid token overflow

Evaluate on these criteria:
1. **Relevance**: Does the result address the goal? (0-10)
2. **Completeness**: Is the answer complete? (0-10)
3. **Correctness**: Does it seem correct? (0-10)
4. **Usability**: Would this be useful to cache? (0-10)

Respond in JSON:
{{
    "relevance": <score 0-10>,
    "completeness": <score 0-10>,
    "correctness": <score 0-10>,
    "usability": <score 0-10>,
    "overall_confidence": <0.0-1.0>,
    "reasoning": "<1 sentence explanation>",
    "should_cache": <true/false>
}}"""

        try:
            response = self.ollama_client.generate(prompt)
            
            # Parse JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                evaluation = json.loads(response[json_start:json_end])
                
                confidence = float(evaluation.get("overall_confidence", 0.5))
                reasoning = evaluation.get("reasoning", "LLM quality assessment")
                
                # Add any low scores to issues
                for criterion in ["relevance", "completeness", "correctness", "usability"]:
                    score = evaluation.get(criterion, 5)
                    if score < 5:
                        issues.append(f"Low {criterion} score: {score}/10")
                
                return {
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "evaluation": evaluation
                }
            else:
                # Failed to parse JSON
                issues.append("LLM validation failed to parse response")
                return {
                    "confidence": 0.7,  # Default to medium confidence
                    "reasoning": "LLM validation response unparseable, defaulting to structure validation"
                }
                
        except Exception as e:
            issues.append(f"LLM validation error: {e}")
            return {
                "confidence": 0.7,  # Fall back to medium confidence
                "reasoning": f"LLM validation failed: {e}"
            }
    
    def should_cache_result(
        self,
        goal: str,
        result: Dict[str, Any],
        execution_time_ms: int
    ) -> Tuple[bool, float, str]:
        """
        Convenience method: Should this result be cached?
        
        Returns:
            (should_cache, confidence, reasoning)
        """
        validation = self.validate(goal, result, execution_time_ms)
        
        return (
            validation["is_valid"],
            validation["confidence"],
            validation["reasoning"]
        )
