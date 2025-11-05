"""
Safe Testing Strategy for Autonomous Improvement

Determines how to safely test improved tools based on their characteristics.
"""

from typing import Dict, List, Any, Optional
from enum import Enum


class TestingStrategy(Enum):
    """Testing strategies based on tool characteristics."""
    SHADOW = "shadow"  # Run both versions in parallel, compare outputs
    REPLAY = "replay"  # Replay historical inputs, verify outputs
    SYNTHETIC = "synthetic"  # Use tool's test cases only
    MANUAL = "manual"  # Require human review before deployment


class SafeTestingStrategy:
    """
    Determines appropriate testing strategy based on tool characteristics.
    """
    
    def classify_tool(self, tool) -> Dict[str, Any]:
        """
        Analyze tool to determine testing strategy.
        
        Args:
            tool: Tool instance (BaseTool subclass)
            
        Returns:
            dict: Classification with testing strategy
        """
        # Get tool characteristics
        chars = tool.get_tool_characteristics()
        
        # Determine testing strategy
        strategy = self._determine_strategy(chars)
        
        return {
            **chars,
            "testing_strategy": strategy,
            "safe_for_production": self._is_safe_for_production(chars, strategy),
            "risk_level": self._assess_risk(chars)
        }
    
    def _determine_strategy(self, chars: Dict[str, Any]) -> TestingStrategy:
        """
        Choose appropriate testing strategy.
        
        Logic:
        1. If read-only + idempotent → SHADOW (safest, best data)
        2. If idempotent + test cases → REPLAY (safe, good validation)
        3. If side effects + test cases → SYNTHETIC (controlled environment)
        4. If side effects + no test cases → MANUAL (too risky)
        """
        is_idempotent = chars.get("idempotent", False)
        has_side_effects = len(chars.get("side_effects", ["unknown"])) > 0 and chars["side_effects"][0] != "none"
        safe_for_shadow = chars.get("safe_for_shadow_testing", False)
        has_test_cases = chars.get("test_data_available", False)
        
        # Best case: Read-only, safe for shadow testing
        if safe_for_shadow and not has_side_effects:
            return TestingStrategy.SHADOW
        
        # Good case: Idempotent, can replay
        if is_idempotent and not has_side_effects:
            return TestingStrategy.REPLAY
        
        # Acceptable: Has test cases
        if has_test_cases:
            return TestingStrategy.SYNTHETIC
        
        # Risky: Needs manual review
        return TestingStrategy.MANUAL
    
    def _is_safe_for_production(self, chars: Dict[str, Any], strategy: TestingStrategy) -> bool:
        """
        Determine if tool is safe for production deployment.
        """
        # Manual review required = not safe for auto-deployment
        if strategy == TestingStrategy.MANUAL:
            return False
        
        # Unknown side effects = not safe
        if "unknown" in chars.get("side_effects", []):
            return False
        
        # Everything else can be tested safely
        return True
    
    def _assess_risk(self, chars: Dict[str, Any]) -> str:
        """
        Assess risk level for testing.
        
        Returns:
            "low", "medium", or "high"
        """
        side_effects = chars.get("side_effects", [])
        
        # High risk: destructive operations
        destructive = ["deletes_data", "modifies_database", "sends_email", "makes_payment"]
        if any(effect in side_effects for effect in destructive):
            return "high"
        
        # Medium risk: has side effects but not destructive
        if len(side_effects) > 0 and side_effects[0] != "none":
            return "medium"
        
        # Low risk: read-only
        return "low"
    
    def get_testing_recommendation(self, tool) -> Dict[str, Any]:
        """
        Get complete testing recommendation for a tool.
        
        Args:
            tool: Tool instance
            
        Returns:
            dict: {
                "strategy": TestingStrategy,
                "safe_for_auto_deployment": bool,
                "risk_level": str,
                "steps": List[str],  # What to do
                "warnings": List[str]  # What to watch out for
            }
        """
        classification = self.classify_tool(tool)
        strategy = classification["testing_strategy"]
        
        return {
            "tool_name": tool.get_tool_definition()["name"],
            "strategy": strategy.value,
            "safe_for_auto_deployment": classification["safe_for_production"],
            "risk_level": classification["risk_level"],
            "steps": self._get_testing_steps(strategy, classification),
            "warnings": self._get_warnings(classification),
            "characteristics": classification
        }
    
    def _get_testing_steps(self, strategy: TestingStrategy, classification: Dict) -> List[str]:
        """Get step-by-step testing instructions."""
        if strategy == TestingStrategy.SHADOW:
            return [
                "Run improved version alongside current version",
                "Route same inputs to both versions",
                "Compare outputs for consistency",
                "Monitor for 1-24 hours",
                "Deploy if outputs match >= 95%"
            ]
        elif strategy == TestingStrategy.REPLAY:
            return [
                "Get last 50 successful executions from ExecutionStore",
                "Replay same inputs through improved version",
                "Compare outputs with historical results",
                "Verify no regressions",
                "Deploy if success rate >= current"
            ]
        elif strategy == TestingStrategy.SYNTHETIC:
            return [
                "Run tool's test cases",
                "Verify all test cases pass",
                "Check error handling",
                "Run in sandbox environment",
                "Require human review before deployment"
            ]
        else:  # MANUAL
            return [
                "Generate code review",
                "Show diff to human",
                "Wait for manual approval",
                "Deploy only after approval"
            ]
    
    def _get_warnings(self, classification: Dict) -> List[str]:
        """Get warnings based on classification."""
        warnings = []
        
        if classification["risk_level"] == "high":
            warnings.append("⚠️  HIGH RISK: Tool has destructive side effects")
        
        if "unknown" in classification.get("side_effects", []):
            warnings.append("⚠️  Side effects unknown - assume NOT safe")
        
        if not classification.get("idempotent"):
            warnings.append("ℹ️  Tool is NOT idempotent - cannot run multiple times safely")
        
        if not classification.get("test_data_available"):
            warnings.append("ℹ️  No test cases available - limited validation possible")
        
        return warnings


# Example usage and documentation
if __name__ == "__main__":
    print("Safe Testing Strategy Examples:")
    print("=" * 80)
    print()
    
    print("READ-ONLY TOOL (e.g., calculator, query):")
    print("  Characteristics:")
    print("    - idempotent: True")
    print("    - side_effects: []")
    print("    - safe_for_shadow_testing: True")
    print("  → Strategy: SHADOW")
    print("  → Risk: LOW")
    print("  → Can auto-deploy: YES")
    print()
    
    print("IDEMPOTENT TOOL (e.g., get_user_data):")
    print("  Characteristics:")
    print("    - idempotent: True")
    print("    - side_effects: ['reads_database']")
    print("    - safe_for_shadow_testing: True")
    print("  → Strategy: SHADOW or REPLAY")
    print("  → Risk: LOW")
    print("  → Can auto-deploy: YES")
    print()
    
    print("SIDE-EFFECT TOOL (e.g., update_user):")
    print("  Characteristics:")
    print("    - idempotent: False")
    print("    - side_effects: ['writes_to_database']")
    print("    - test_data_available: True")
    print("  → Strategy: SYNTHETIC")
    print("  → Risk: MEDIUM")
    print("  → Can auto-deploy: WITH CAUTION")
    print()
    
    print("DESTRUCTIVE TOOL (e.g., delete_user):")
    print("  Characteristics:")
    print("    - idempotent: False")
    print("    - side_effects: ['deletes_data']")
    print("    - test_data_available: False")
    print("  → Strategy: MANUAL")
    print("  → Risk: HIGH")
    print("  → Can auto-deploy: NO")
