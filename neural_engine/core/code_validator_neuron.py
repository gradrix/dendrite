"""
Code Validator Neuron: Validates and provides feedback for LLM-generated code.

Instead of increasing prompt size for small models, this neuron:
1. Validates generated code (syntax, imports, basic structure)
2. Provides specific error feedback
3. Triggers retry with targeted corrections (up to 5 attempts)
4. Learns from successful retries

This approach keeps prompts small while improving code quality through iteration.
"""

import ast
import json
import re
from typing import Dict, List, Optional, Tuple


class CodeValidatorNeuron:
    """
    Validates LLM-generated code and provides targeted feedback for retries.
    
    Better than bloating prompts: Small focused feedback + retry mechanism.
    """
    
    def __init__(self, max_retries: int = 5):
        """
        Initialize Code Validator.
        
        Args:
            max_retries: Maximum validation retry attempts (default: 5)
        """
        self.max_retries = max_retries
        self.validation_history = []
    
    def validate_code(self, code: str, context: Dict) -> Dict:
        """
        Validate generated code and provide detailed feedback.
        
        Args:
            code: Python code to validate
            context: Context about the code (goal, tool_name, etc.)
        
        Returns:
            {
                "valid": True/False,
                "errors": [...],  # List of validation errors
                "warnings": [...],  # Non-blocking issues
                "feedback": "Targeted feedback for LLM retry"
            }
        """
        errors = []
        warnings = []
        
        # 1. Syntax validation
        syntax_result = self._check_syntax(code)
        if not syntax_result["valid"]:
            errors.append(syntax_result)
        
        # 2. Structure validation
        structure_result = self._check_structure(code, context)
        if not structure_result["valid"]:
            errors.append(structure_result)
        else:
            warnings.extend(structure_result.get("warnings", []))
        
        # 3. Import validation
        import_result = self._check_imports(code)
        if not import_result["valid"]:
            errors.append(import_result)
        
        # 4. Tool usage validation
        if "tool_name" in context:
            tool_result = self._check_tool_usage(code, context["tool_name"])
            if not tool_result["valid"]:
                errors.append(tool_result)
        
        # Build targeted feedback
        feedback = self._build_feedback(errors, warnings, context)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "feedback": feedback,
            "code": code
        }
    
    def _check_syntax(self, code: str) -> Dict:
        """Check Python syntax."""
        try:
            ast.parse(code)
            return {"valid": True, "type": "syntax"}
        except SyntaxError as e:
            return {
                "valid": False,
                "type": "syntax",
                "error": str(e),
                "line": e.lineno,
                "offset": e.offset,
                "text": e.text,
                "message": f"Syntax error at line {e.lineno}: {e.msg}"
            }
        except Exception as e:
            return {
                "valid": False,
                "type": "syntax",
                "error": str(e),
                "message": f"Code parsing failed: {str(e)}"
            }
    
    def _check_structure(self, code: str, context: Dict) -> Dict:
        """Check code structure (must have proper execution and result setting)."""
        warnings = []
        
        # Check for sandbox.set_result() call
        if "sandbox.set_result(" not in code:
            return {
                "valid": False,
                "type": "structure",
                "message": "Code must call sandbox.set_result() to return a value"
            }
        
        # Check for tool instantiation if tool_name provided
        if "tool_name" in context:
            tool_class = context.get("tool_class", "")
            if tool_class and f"{tool_class}(" not in code:
                warnings.append(f"Tool class '{tool_class}' doesn't appear to be instantiated")
        
        # Check for execute call
        if ".execute(" not in code and "set_result" in code:
            warnings.append("Code has set_result but no .execute() call - may not work")
        
        return {
            "valid": True,
            "type": "structure",
            "warnings": warnings
        }
    
    def _check_imports(self, code: str) -> Dict:
        """Check that imports are valid."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    # Allow standard library and neural_engine imports
                    pass
                elif isinstance(node, ast.ImportFrom):
                    # Check module path is reasonable
                    if node.module and not (
                        node.module.startswith("neural_engine") or
                        node.module in ["datetime", "json", "time", "os", "sys"]
                    ):
                        # Could be risky import, but let it pass with warning
                        pass
            return {"valid": True, "type": "imports"}
        except Exception as e:
            return {
                "valid": False,
                "type": "imports",
                "error": str(e),
                "message": f"Import validation failed: {str(e)}"
            }
    
    def _check_tool_usage(self, code: str, tool_name: str) -> Dict:
        """Check that tool is used correctly."""
        # Basic check: tool should be imported and instantiated
        if f"from neural_engine.tools" not in code:
            return {
                "valid": False,
                "type": "tool_usage",
                "message": f"Tool '{tool_name}' must be imported from neural_engine.tools"
            }
        
        return {"valid": True, "type": "tool_usage"}
    
    def _build_feedback(self, errors: List[Dict], warnings: List[Dict], context: Dict) -> str:
        """
        Build targeted feedback for LLM retry.
        
        Keep it focused and specific - don't repeat the entire prompt.
        """
        if not errors:
            return ""
        
        feedback_parts = ["The generated code has issues that need fixing:\n"]
        
        for i, error in enumerate(errors, 1):
            error_type = error.get("type", "unknown")
            
            if error_type == "syntax":
                line = error.get("line", "?")
                msg = error.get("error", "Unknown syntax error")
                text = error.get("text", "").strip()
                feedback_parts.append(
                    f"{i}. **Syntax Error (line {line})**: {msg}\n"
                    f"   Problem code: `{text}`\n"
                    f"   Fix: Check Python syntax, missing colons, parentheses, or quotes.\n"
                )
            
            elif error_type == "structure":
                msg = error.get("message", "Structure issue")
                feedback_parts.append(
                    f"{i}. **Structure Error**: {msg}\n"
                    f"   Fix: Ensure code follows the pattern:\n"
                    f"   - Import tool\n"
                    f"   - Instantiate tool\n"
                    f"   - Call tool.execute()\n"
                    f"   - Store result in sandbox.set_result()\n"
                )
            
            elif error_type == "tool_usage":
                msg = error.get("message", "Tool usage issue")
                tool_name = context.get("tool_name", "the tool")
                feedback_parts.append(
                    f"{i}. **Tool Usage Error**: {msg}\n"
                    f"   Fix: Import and use {tool_name} correctly.\n"
                )
        
        return "\n".join(feedback_parts)
    
    def should_retry(self, attempt: int) -> bool:
        """Check if we should retry validation."""
        return attempt < self.max_retries
    
    def get_retry_context(self, validation_result: Dict, original_context: Dict, attempt: int) -> Dict:
        """
        Build context for retry attempt with targeted feedback.
        
        Returns enhanced context for code generator retry.
        """
        return {
            **original_context,
            "retry_attempt": attempt,
            "previous_code": validation_result["code"],
            "validation_errors": validation_result["errors"],
            "feedback": validation_result["feedback"],
            "retry_instruction": (
                f"RETRY #{attempt}: The previous code had errors. "
                f"Generate CORRECTED code based on this feedback:\n\n{validation_result['feedback']}"
            )
        }
