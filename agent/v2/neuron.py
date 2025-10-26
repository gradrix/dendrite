"""
V2 Architecture: Individual Neuron with Validation

Each neuron is a self-contained unit with:
- Specific goal/responsibility
- Input validation neuron
- Execution logic
- Output validation neuron
- Retry mechanism with prompt modification
"""

import logging
import json
import re
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def clean_json_response(response: str) -> str:
    """Clean LLM response to extract JSON content and handle expressions."""
    # Remove markdown code blocks
    response = re.sub(r'```\w*\n?', '', response)
    response = response.strip()

    # Handle simple arithmetic expressions in JSON values
    # Replace expressions like 123456 - 604800 with their evaluated result
    def replace_expr(match):
        expr = match.group(0)
        # Extract just the expression part
        expr_part = re.search(r'(\d+\s*[-+*/]\s*\d+)', expr)
        if expr_part:
            try:
                result = eval(expr_part.group(1))
                return expr.replace(expr_part.group(1), str(result))
            except:
                pass
        return expr

    response = re.sub(r'"[^"]*"\s*:\s*[^,}]+', replace_expr, response)

    return response


@dataclass
class ValidationResult:
    """Result of input/output validation."""
    is_valid: bool
    error_message: str = ""
    suggestions: List[str] = field(default_factory=list)


@dataclass
class NeuronResult:
    """Result from a neuron execution."""
    success: bool
    data: Any = None
    error: str = ""
    prompt_used: str = ""
    response_received: str = ""
    validation_errors: List[str] = field(default_factory=list)
    retry_count: int = 0


class ValidationNeuron:
    """Neuron responsible for validating inputs or outputs."""

    def __init__(self, ollama_client, validation_type: str = "input"):
        self.ollama = ollama_client
        self.validation_type = validation_type

    def validate(self, data: Any, context: Dict, neuron_goal: str) -> ValidationResult:
        """Validate input or output data."""

        if self.validation_type == "input":
            prompt = f"""Validate if this input data is suitable for the neuron goal.

Neuron Goal: {neuron_goal}
Input Data: {json.dumps(data, indent=2, default=str)}

Check if:
1. All required data is present (empty input is OK for initial steps that will gather data via tools)
2. Data types are correct if data is present
3. Data makes sense for the goal if data is present

If input is empty, that's usually fine - the neuron can gather data using tools.
Only reject if the input data contradicts the goal or contains incorrect data types.

Output JSON:
{{
  "is_valid": true/false,
  "error_message": "description if invalid",
  "suggestions": ["fix suggestion 1", "fix suggestion 2"]
}}"""
        else:  # output validation
            prompt = f"""Validate if this output data successfully fulfills the neuron goal.

Neuron Goal: {neuron_goal}
Output Data: {json.dumps(data, indent=2, default=str)}

Check if:
1. Output matches expected format/structure
2. Output contains required information
3. Output makes sense for the goal

If invalid, provide specific error message and suggestions for fixing.

Output JSON:
{{
  "is_valid": true/false,
  "error_message": "description if invalid",
  "suggestions": ["fix suggestion 1", "fix suggestion 2"]
}}"""

        try:
            response = self.ollama.generate(prompt, system="Validate data quality.", temperature=0.1)
            cleaned_response = clean_json_response(response)
            result = json.loads(cleaned_response)

            return ValidationResult(
                is_valid=result.get("is_valid", False),
                error_message=result.get("error_message", ""),
                suggestions=result.get("suggestions", [])
            )
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse validation JSON: {e}. Response: {response[:200]}...")
            # Fallback: assume valid if we can't validate
            return ValidationResult(
                is_valid=True,
                error_message="Could not validate due to JSON parsing error",
                suggestions=["Manual review recommended"]
            )
        except Exception as e:
            logger.warning(f"Validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                error_message=f"Validation error: {str(e)}",
                suggestions=["Retry validation", "Check data format"]
            )


class Neuron:
    """V2 Neuron: Self-contained unit with validation and retry logic."""

    def __init__(self, goal: str, ollama_client, tool_registry=None, max_retries: int = 3):
        self.goal = goal
        self.ollama = ollama_client
        self.tool_registry = tool_registry
        self.max_retries = max_retries

        # Create validation neurons
        self.input_validator = ValidationNeuron(ollama_client, "input")
        self.output_validator = ValidationNeuron(ollama_client, "output")

        # Execution state
        self.execution_history: List[NeuronResult] = []

    def execute(self, input_data: Any, context: Dict) -> NeuronResult:
        """Execute the neuron with validation and retries."""

        logger.info(f"🎯 Executing Neuron: {self.goal[:50]}...")

        # Step 1: Input Validation
        input_validation = self.input_validator.validate(input_data, context, self.goal)
        if not input_validation.is_valid:
            logger.warning(f"❌ Input validation failed: {input_validation.error_message}")
            return NeuronResult(
                success=False,
                error=f"Input validation failed: {input_validation.error_message}",
                validation_errors=[input_validation.error_message]
            )

        # Step 2: Execute with retries
        for attempt in range(self.max_retries):
            try:
                result = self._execute_core(input_data, context, attempt)
                self.execution_history.append(result)

                # Step 3: Output Validation
                if result.success:
                    output_validation = self.output_validator.validate(result.data, context, self.goal)
                    if output_validation.is_valid:
                        logger.info(f"✅ Neuron completed successfully (attempt {attempt + 1})")
                        return result
                    else:
                        logger.warning(f"⚠️ Output validation failed: {output_validation.error_message}")
                        result.validation_errors.append(output_validation.error_message)

                        # If validation failed, try to fix with suggestions
                        if attempt < self.max_retries - 1:
                            logger.info(f"🔄 Retrying with validation suggestions...")
                            continue

                # If we get here, execution or validation failed
                if attempt < self.max_retries - 1:
                    logger.info(f"🔄 Retrying execution (attempt {attempt + 1})...")
                    continue
                else:
                    logger.error(f"❌ Neuron failed after {self.max_retries} attempts")
                    return result

            except Exception as e:
                logger.error(f"💥 Execution error: {e}")
                if attempt == self.max_retries - 1:
                    return NeuronResult(
                        success=False,
                        error=f"Execution failed: {str(e)}",
                        retry_count=attempt + 1
                    )

        # Should not reach here
        return NeuronResult(success=False, error="Unexpected execution failure")

    def _execute_core(self, input_data: Any, context: Dict, attempt: int) -> NeuronResult:
        """Core execution logic - to be implemented by subclasses."""

        # Base implementation: Use LLM to determine what to do
        prompt = f"""Execute this neuron goal: {self.goal}

Input Data: {json.dumps(input_data, indent=2, default=str)}
Context: {json.dumps(context, indent=2, default=str)[:500]}...

Available tools: {[f"{tool.name}({', '.join([p['name'] for p in tool.parameters])})" for tool in self.tool_registry.list_tools()] if self.tool_registry else []}

Determine what action to take. If you need to call a tool, specify the EXACT tool name and parameters from the list above.
If you need to process data, provide Python code.
If you need to return data, specify what to return.

IMPORTANT: All parameter values must be actual values, not expressions. Calculate numbers yourself.
For timestamps, use actual Unix timestamp numbers, not expressions like "123456 - 604800".

CRITICAL: You MUST respond with VALID JSON only. No explanations, no markdown, no extra text.

Output JSON:
{{
  "action": "tool_call|python_code|return_data",
  "tool_name": "tool_name_if_applicable",
  "parameters": {{}},
  "python_code": "code_if_applicable",
  "return_data": "data_if_applicable",
  "reasoning": "why this action"
}}"""

        if attempt > 0:
            prompt += f"\n\nPrevious attempts failed. Attempt {attempt + 1}/{self.max_retries}. Try a different approach."

        response = self.ollama.generate(prompt, system="Execute neuron goal.", temperature=0.3)

        try:
            cleaned_response = clean_json_response(response)
            decision = json.loads(cleaned_response)

            # Execute the decision
            if decision["action"] == "tool_call":
                return self._execute_tool_call(decision, context)
            elif decision["action"] == "python_code":
                return self._execute_python_code(decision, context)
            elif decision["action"] == "return_data":
                return NeuronResult(
                    success=True,
                    data=decision["return_data"],
                    prompt_used=prompt,
                    response_received=response
                )
            else:
                return NeuronResult(
                    success=False,
                    error=f"Unknown action: {decision['action']}",
                    prompt_used=prompt,
                    response_received=response
                )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse neuron decision JSON: {e}. Response: {response[:200]}...")
            return NeuronResult(
                success=False,
                error=f"Failed to parse LLM response as JSON: {str(e)}",
                prompt_used=prompt,
                response_received=response
            )
        except Exception as e:
            return NeuronResult(
                success=False,
                error=f"Failed to parse LLM response: {str(e)}",
                prompt_used=prompt,
                response_received=response
            )

    def _execute_tool_call(self, decision: Dict, context: Dict) -> NeuronResult:
        """Execute a tool call."""
        if not self.tool_registry:
            return NeuronResult(success=False, error="No tool registry available")

        tool_name = decision.get("tool_name")
        parameters = decision.get("parameters", {})

        try:
            tool = self.tool_registry.get(tool_name)
            if not tool:
                return NeuronResult(success=False, error=f"Tool not found: {tool_name}")

            # Set current tool name for parameter enhancement
            self._current_tool_name = tool_name

            # Add context data to parameters if needed
            enhanced_params = self._enhance_parameters(parameters, context)

            result = tool.execute(**enhanced_params)

            return NeuronResult(
                success=result.get("success", True),
                data=result,
                prompt_used=json.dumps(decision),
                response_received=json.dumps(result)
            )

        except Exception as e:
            return NeuronResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                prompt_used=json.dumps(decision)
            )

    def _execute_python_code(self, decision: Dict, context: Dict) -> NeuronResult:
        """Execute Python code with special validation."""
        code = decision.get("python_code", "")

        # Enhanced validation for Python code
        if not self._validate_python_code(code):
            return NeuronResult(
                success=False,
                error="Python code failed security validation",
                prompt_used=json.dumps(decision)
            )

        try:
            # Create execution environment with helpers
            exec_globals = {
                "context": context,
                "result": None,
                "__builtins__": __builtins__
            }

            # Add helper functions
            exec_globals.update(self._get_python_helpers())

            exec(code, exec_globals)
            result_data = exec_globals.get("result")

            return NeuronResult(
                success=True,
                data=result_data,
                prompt_used=json.dumps(decision),
                response_received=str(result_data)
            )

        except Exception as e:
            return NeuronResult(
                success=False,
                error=f"Python execution failed: {str(e)}",
                prompt_used=json.dumps(decision)
            )

    def _validate_python_code(self, code: str) -> bool:
        """Basic security validation for Python code."""
        dangerous_patterns = [
            "import os", "import sys", "import subprocess",
            "exec(", "eval(", "open(", "file(",
            "__import__", "globals()", "locals()"
        ]

        for pattern in dangerous_patterns:
            if pattern in code:
                return False
        return True

    def _enhance_parameters(self, parameters: Dict, context: Dict) -> Dict:
        """Enhance tool parameters with context data and fix common parameter name issues."""
        enhanced = parameters.copy()

        # Parameter name mapping for common LLM mistakes
        param_mappings = {
            "getMyActivities": {
                "start_date": "after_unix",
                "end_date": "before_unix",
                "start_time": "after_unix", 
                "end_time": "before_unix",
                "since": "after_unix",
                "until": "before_unix"
            },
            "getActivityKudos": {
                "activity_id": "activity_id",
                "id": "activity_id"
            }
        }

        # Apply parameter mapping if this is a known tool
        tool_name = None
        if hasattr(self, '_current_tool_name'):
            tool_name = self._current_tool_name
        # Try to infer from context or parameters
        for key in enhanced.keys():
            if key in ["tool_name"]:
                tool_name = enhanced[key]
                break

        if tool_name and tool_name in param_mappings:
            mapping = param_mappings[tool_name]
            for old_param, new_param in mapping.items():
                if old_param in enhanced and new_param not in enhanced:
                    enhanced[new_param] = enhanced.pop(old_param)

        # Convert relative time strings to Unix timestamps
        for key, value in enhanced.items():
            if isinstance(value, str):
                # Handle context references
                if value.startswith("context."):
                    context_key = value[8:]  # Remove "context."
                    if context_key in context:
                        enhanced[key] = context[context_key]
                # Handle relative time strings for timestamp parameters
                elif key in ["after_unix", "before_unix"] and not isinstance(value, (int, float)):
                    if value in ["now", "today"]:
                        enhanced[key] = int(time.time())
                    elif "days ago" in value:
                        try:
                            days = int(value.split()[0])
                            enhanced[key] = int(time.time()) - (days * 24 * 60 * 60)
                        except:
                            pass  # Keep original value if parsing fails
            # Handle arithmetic expressions in parameter values
            elif isinstance(value, str) and any(op in value for op in ['+', '-', '*', '/']):
                try:
                    # Simple arithmetic evaluation (only with numbers and basic operators)
                    import ast
                    # Check if it's a safe expression (only numbers and operators)
                    if all(c.isdigit() or c in '+-*/. ' for c in value):
                        enhanced[key] = eval(value)
                except:
                    pass  # Keep original value if evaluation fails

        return enhanced

    def _get_python_helpers(self) -> Dict:
        """Get helper functions for Python execution."""
        def get_context_data(key: str):
            """Get data from context by key."""
            return context.get(key)

        def get_context_list(key: str):
            """Get list data from context, handling disk references."""
            data = context.get(key)
            if isinstance(data, dict) and "_ref_id" in data:
                # Load from disk if needed
                try:
                    import json
                    from pathlib import Path
                    data_file = data.get("_data_file")
                    if data_file and Path(data_file).exists():
                        with open(data_file, "r") as f:
                            return json.load(f)
                except Exception:
                    pass
            return data if isinstance(data, list) else []

        def get_context_field(key: str, field: str):
            """Get specific field from context data."""
            data = get_context_data(key)
            if isinstance(data, dict):
                return data.get(field)
            return None

        return {
            "get_context_data": get_context_data,
            "get_context_list": get_context_list,
            "get_context_field": get_context_field
        }

    def get_debug_info(self) -> Dict:
        """Get debugging information about this neuron."""
        return {
            "goal": self.goal,
            "execution_count": len(self.execution_history),
            "last_result": self.execution_history[-1] if self.execution_history else None,
            "validation_errors": [
                result.validation_errors for result in self.execution_history
                if result.validation_errors
            ]
        }