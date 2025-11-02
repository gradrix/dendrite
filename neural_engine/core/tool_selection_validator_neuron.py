"""
Tool Selection Validator Neuron: Validates and provides feedback for tool selection.

Similar to CodeValidatorNeuron, this validates that the LLM selected appropriate tools
and provides targeted feedback for retries.
"""

import json
from typing import Dict, List, Optional


class ToolSelectionValidatorNeuron:
    """
    Validates LLM tool selection decisions and provides targeted feedback.
    
    Better than bloating prompts: Validate selection + retry with feedback.
    """
    
    def __init__(self, max_retries: int = 5):
        """
        Initialize Tool Selection Validator.
        
        Args:
            max_retries: Maximum validation retry attempts (default: 5)
        """
        self.max_retries = max_retries
    
    def validate_selection(self, selected_tools: List[Dict], context: Dict) -> Dict:
        """
        Validate tool selection and provide feedback.
        
        Args:
            selected_tools: List of selected tools
            context: Context including goal, available_tools, etc.
        
        Returns:
            {
                "valid": True/False,
                "errors": [...],
                "warnings": [...],
                "feedback": "Targeted feedback for retry"
            }
        """
        errors = []
        warnings = []
        
        goal = context.get("goal", "")
        available_tools = context.get("available_tools", {})
        
        # 1. Check if any tools were selected
        if not selected_tools or len(selected_tools) == 0:
            errors.append({
                "type": "no_selection",
                "message": "No tools were selected"
            })
            return {
                "valid": False,
                "errors": errors,
                "warnings": warnings,
                "feedback": self._build_feedback(errors, warnings, context)
            }
        
        # 2. Check if selected tools exist
        for tool in selected_tools:
            tool_name = tool.get("name", "")
            if tool_name not in available_tools:
                errors.append({
                    "type": "invalid_tool",
                    "tool_name": tool_name,
                    "message": f"Tool '{tool_name}' does not exist in available tools"
                })
        
        # 3. Semantic validation - check if tool makes sense for goal
        semantic_result = self._validate_semantic_match(selected_tools, goal, available_tools)
        if not semantic_result["valid"]:
            errors.append(semantic_result)
        else:
            warnings.extend(semantic_result.get("warnings", []))
        
        # 4. Check tool selection structure
        for i, tool in enumerate(selected_tools):
            if "name" not in tool:
                errors.append({
                    "type": "structure",
                    "message": f"Tool {i} missing 'name' field"
                })
            if "module" not in tool:
                errors.append({
                    "type": "structure",
                    "message": f"Tool '{tool.get('name', i)}' missing 'module' field"
                })
            if "class" not in tool:
                errors.append({
                    "type": "structure",
                    "message": f"Tool '{tool.get('name', i)}' missing 'class' field"
                })
        
        feedback = self._build_feedback(errors, warnings, context)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "feedback": feedback
        }
    
    def _validate_semantic_match(self, selected_tools: List[Dict], goal: str, available_tools: Dict) -> Dict:
        """
        Check if selected tools make semantic sense for the goal.
        
        Uses heuristics and keyword matching.
        """
        warnings = []
        goal_lower = goal.lower()
        
        # Define keyword -> expected tool mappings
        keyword_mappings = {
            "hello": ["hello_world"],
            "greet": ["hello_world"],
            "say hello": ["hello_world"],
            "remember": ["memory_write"],
            "store": ["memory_write"],
            "save": ["memory_write"],
            "recall": ["memory_read"],
            "what did i": ["memory_read"],
            "retrieve": ["memory_read"],
            "strava": ["strava_get_my_activities", "strava_get_activity_kudos", "strava_get_dashboard_feed", "strava_update_activity", "strava_give_kudos"],
            "activity": ["strava_get_my_activities", "strava_get_activity_kudos"],
            "kudos": ["strava_get_activity_kudos", "strava_give_kudos"],
            "add": ["addition", "add_numbers"],
            "sum": ["addition", "add_numbers"],
            "calculate": ["addition", "add_numbers", "buggy_calculator"],
            "script": ["python_script"],
            "python": ["python_script"],
            "prime": ["prime_checker"],
        }
        
        # Check if goal keywords match selected tools
        for keyword, expected_tools in keyword_mappings.items():
            if keyword in goal_lower:
                selected_tool_names = [t.get("name", "") for t in selected_tools]
                
                # Check if any expected tool was selected
                if not any(expected in selected_tool_names for expected in expected_tools):
                    # This is a potential mismatch
                    return {
                        "valid": False,
                        "type": "semantic_mismatch",
                        "message": f"Goal contains '{keyword}' but selected tools {selected_tool_names} don't match expected tools {expected_tools}",
                        "expected_tools": expected_tools,
                        "actual_tools": selected_tool_names
                    }
        
        return {"valid": True, "type": "semantic", "warnings": warnings}
    
    def _build_feedback(self, errors: List[Dict], warnings: List[Dict], context: Dict) -> str:
        """
        Build targeted feedback for retry.
        """
        if not errors:
            return ""
        
        feedback_parts = ["The tool selection has issues:\n"]
        
        goal = context.get("goal", "")
        available_tools = context.get("available_tools", {})
        
        for i, error in enumerate(errors, 1):
            error_type = error.get("type", "unknown")
            
            if error_type == "no_selection":
                feedback_parts.append(
                    f"{i}. **No Tools Selected**: You must select at least one tool.\n"
                    f"   Goal: \"{goal}\"\n"
                    f"   Fix: Choose the most appropriate tool from available tools.\n"
                )
            
            elif error_type == "invalid_tool":
                tool_name = error.get("tool_name", "unknown")
                feedback_parts.append(
                    f"{i}. **Invalid Tool**: Tool '{tool_name}' does not exist.\n"
                    f"   Fix: Choose from available tools: {list(available_tools.keys())[:10]}\n"
                )
            
            elif error_type == "semantic_mismatch":
                expected = error.get("expected_tools", [])
                actual = error.get("actual_tools", [])
                msg = error.get("message", "")
                feedback_parts.append(
                    f"{i}. **Wrong Tool Selected**: {msg}\n"
                    f"   Goal: \"{goal}\"\n"
                    f"   You selected: {actual}\n"
                    f"   Better choices: {expected}\n"
                    f"   Fix: Re-read the goal carefully and choose a tool that matches the intent.\n"
                )
            
            elif error_type == "structure":
                msg = error.get("message", "Structure error")
                feedback_parts.append(
                    f"{i}. **Structure Error**: {msg}\n"
                    f"   Fix: Ensure each tool has 'name', 'module', and 'class' fields.\n"
                )
        
        return "\n".join(feedback_parts)
    
    def should_retry(self, attempt: int) -> bool:
        """Check if we should retry validation."""
        return attempt < self.max_retries
    
    def get_retry_context(self, validation_result: Dict, original_context: Dict, attempt: int) -> Dict:
        """
        Build context for retry with targeted feedback.
        """
        return {
            **original_context,
            "retry_attempt": attempt,
            "previous_selection": validation_result.get("previous_selection", []),
            "validation_errors": validation_result["errors"],
            "feedback": validation_result["feedback"],
            "retry_instruction": (
                f"RETRY #{attempt}: Your previous tool selection was incorrect. "
                f"Generate CORRECTED selection based on this feedback:\n\n{validation_result['feedback']}"
            )
        }
