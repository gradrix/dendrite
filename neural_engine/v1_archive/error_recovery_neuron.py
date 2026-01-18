"""
Error Recovery Neuron: Intelligent error handling and recovery strategies.

Phase 10d: Instead of stopping on failure, the system tries to recover intelligently.

Error Classification:
- transient: Temporary issues (timeout, network) → Retry
- wrong_tool: Tool selected but doesn't fit → Fallback to different tool
- parameter_mismatch: Wrong parameters → Adapt parameters
- impossible: Task cannot be completed → Explain why

Recovery Strategies:
1. Retry: For transient errors (with exponential backoff)
2. Fallback: Try alternative tools
3. Adapt: Modify parameters based on error message
4. Chunk: Break large requests into smaller pieces
5. Explain: When recovery impossible, explain clearly

Context Preservation:
- Keep conversation history intact
- Track what was tried and failed
- Learn from recovery patterns
"""

import json
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore


class ErrorRecoveryNeuron:
    """
    Intelligent error recovery - don't stop thinking, try alternatives.
    
    Phase 10d: Core capability for resilient AI system.
    """
    
    def __init__(self,
                 ollama_client: OllamaClient,
                 tool_registry: ToolRegistry,
                 execution_store: Optional[ExecutionStore] = None):
        """
        Initialize ErrorRecoveryNeuron.
        
        Args:
            ollama_client: Client for LLM reasoning
            tool_registry: Registry to find alternative tools
            execution_store: Store for tracking recovery attempts
        """
        self.ollama_client = ollama_client
        self.tool_registry = tool_registry
        self.execution_store = execution_store or ExecutionStore()
        
        # Recovery strategy limits
        self.max_retries = 3
        self.max_fallbacks = 3
        self.max_adaptations = 2
        
        # Exponential backoff for retries
        self.retry_delays = [1, 2, 5]  # seconds
    
    def classify_error(self, 
                      error: Exception,
                      tool_name: str,
                      parameters: Dict,
                      context: Dict) -> Dict:
        """
        Classify error type to determine recovery strategy.
        
        Args:
            error: The exception that occurred
            tool_name: Tool that failed
            parameters: Parameters used
            context: Execution context
        
        Returns:
            {
                "error_type": "transient|wrong_tool|parameter_mismatch|impossible",
                "confidence": 0.0-1.0,
                "reasoning": "why this classification",
                "recoverable": True/False
            }
        """
        error_str = str(error)
        error_type_name = type(error).__name__
        
        # Build classification prompt
        prompt = f"""Classify this error to determine the best recovery strategy.

Error: {error_type_name}: {error_str}
Tool: {tool_name}
Parameters: {json.dumps(parameters, indent=2)}
Context: {json.dumps(context, indent=2)}

Classify into ONE of these categories:

1. **transient**: Temporary issue (timeout, network error, rate limit)
   - Can be solved by retrying
   - Example: TimeoutError, ConnectionError, 429 Too Many Requests

2. **wrong_tool**: Wrong tool selected for the task
   - Tool exists but doesn't fit the need
   - Example: Used "get_activities" but needed "update_activity"

3. **parameter_mismatch**: Right tool, wrong parameters
   - Tool is correct but parameters are invalid/missing/wrong type
   - Example: Missing required field, wrong data type, invalid value

4. **impossible**: Task fundamentally cannot be completed
   - No tool available can solve this
   - Permissions denied, resource doesn't exist
   - Example: "Delete user X" but user doesn't exist

Respond in JSON:
{{
    "error_type": "transient|wrong_tool|parameter_mismatch|impossible",
    "confidence": 0.95,
    "reasoning": "Brief explanation of why",
    "recoverable": true
}}"""

        try:
            response = self.ollama_client.generate(prompt)
            
            # Extract JSON from response (ollama returns dict with 'response' key)
            json_str = response.get('response', response) if isinstance(response, dict) else response
            json_str = json_str.strip() if isinstance(json_str, str) else str(json_str)
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            classification = json.loads(json_str)
            
            # Validate classification
            valid_types = ["transient", "wrong_tool", "parameter_mismatch", "impossible"]
            if classification.get("error_type") not in valid_types:
                # Fallback classification
                return self._fallback_classification(error, error_str, error_type_name)
            
            return classification
            
        except Exception as e:
            print(f"⚠️  Error classification failed: {e}")
            return self._fallback_classification(error, error_str, error_type_name)
    
    def _fallback_classification(self, error: Exception, error_str: str, error_type_name: str) -> Dict:
        """Heuristic-based classification when LLM fails."""
        
        # Transient indicators
        transient_keywords = ["timeout", "connection", "network", "rate limit", "429", "503"]
        if any(kw in error_str.lower() for kw in transient_keywords):
            return {
                "error_type": "transient",
                "confidence": 0.8,
                "reasoning": f"Error message contains transient indicators: {error_type_name}",
                "recoverable": True
            }
        
        # Parameter mismatch indicators
        param_keywords = ["missing", "required", "invalid", "type", "expected", "parameter"]
        if any(kw in error_str.lower() for kw in param_keywords):
            return {
                "error_type": "parameter_mismatch",
                "confidence": 0.7,
                "reasoning": f"Error suggests parameter issues: {error_str[:100]}",
                "recoverable": True
            }
        
        # Permission/impossible indicators
        impossible_keywords = ["permission denied", "not found", "does not exist", "unauthorized", "forbidden"]
        if any(kw in error_str.lower() for kw in impossible_keywords):
            return {
                "error_type": "impossible",
                "confidence": 0.8,
                "reasoning": f"Error suggests task is impossible: {error_str[:100]}",
                "recoverable": False
            }
        
        # Default to wrong_tool (most flexible recovery)
        return {
            "error_type": "wrong_tool",
            "confidence": 0.5,
            "reasoning": f"Uncertain classification, defaulting to wrong_tool: {error_type_name}",
            "recoverable": True
        }
    
    def recover(self,
                error: Exception,
                tool_name: str,
                parameters: Dict,
                context: Dict,
                attempt_history: Optional[List[Dict]] = None) -> Dict:
        """
        Attempt to recover from error using appropriate strategy.
        
        Args:
            error: The exception that occurred
            tool_name: Tool that failed
            parameters: Parameters used
            context: Full execution context (goal, conversation, etc.)
            attempt_history: Previous recovery attempts
        
        Returns:
            {
                "success": True/False,
                "strategy": "retry|fallback|adapt|chunk|explain",
                "result": execution_result or None,
                "explanation": "what was tried",
                "should_continue": True/False,
                "next_action": {...} or None
            }
        """
        attempt_history = attempt_history or []
        
        # Classify error
        classification = self.classify_error(error, tool_name, parameters, context)
        
        print(f"🔍 Error classified as: {classification['error_type']} (confidence: {classification['confidence']:.0%})")
        print(f"   Reasoning: {classification['reasoning']}")
        
        # Check if recoverable
        if not classification['recoverable']:
            return self._explain_failure(error, tool_name, parameters, context, classification)
        
        # Choose recovery strategy based on classification and history
        error_type = classification['error_type']
        
        if error_type == "transient":
            return self._retry_strategy(error, tool_name, parameters, context, attempt_history)
        
        elif error_type == "wrong_tool":
            return self._fallback_strategy(error, tool_name, parameters, context, attempt_history)
        
        elif error_type == "parameter_mismatch":
            return self._adapt_strategy(error, tool_name, parameters, context, attempt_history)
        
        else:
            # Unknown error type - try fallback
            return self._fallback_strategy(error, tool_name, parameters, context, attempt_history)
    
    def _retry_strategy(self,
                       error: Exception,
                       tool_name: str,
                       parameters: Dict,
                       context: Dict,
                       attempt_history: List[Dict]) -> Dict:
        """
        Retry strategy for transient errors.
        
        Use exponential backoff to avoid overwhelming failing service.
        """
        retry_attempts = len([a for a in attempt_history if a.get('strategy') == 'retry'])
        
        if retry_attempts >= self.max_retries:
            print(f"⚠️  Max retries ({self.max_retries}) reached")
            return {
                "success": False,
                "strategy": "retry",
                "result": None,
                "explanation": f"Failed after {retry_attempts} retries: {str(error)}",
                "should_continue": False,
                "next_action": None
            }
        
        # Wait with exponential backoff
        delay = self.retry_delays[retry_attempts] if retry_attempts < len(self.retry_delays) else 5
        print(f"⏳ Retry #{retry_attempts + 1} in {delay}s...")
        time.sleep(delay)
        
        # Try again with same parameters
        try:
            tool = self.tool_registry.get_tool(tool_name)
            if tool is None:
                raise Exception(f"Tool {tool_name} not found in registry")
            
            # Tool registry returns instances, not classes
            result = tool.execute(**parameters)
            
            print(f"✅ Retry succeeded!")
            
            return {
                "success": True,
                "strategy": "retry",
                "result": result,
                "explanation": f"Succeeded on retry #{retry_attempts + 1} after {delay}s delay",
                "should_continue": True,
                "next_action": None
            }
            
        except Exception as e:
            print(f"❌ Retry failed: {e}")
            
            # Record attempt and try again
            attempt_history.append({
                "strategy": "retry",
                "attempt": retry_attempts + 1,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            
            # Recursively try next retry
            return self._retry_strategy(e, tool_name, parameters, context, attempt_history)
    
    def _fallback_strategy(self,
                          error: Exception,
                          tool_name: str,
                          parameters: Dict,
                          context: Dict,
                          attempt_history: List[Dict]) -> Dict:
        """
        Fallback strategy for wrong tool selection.
        
        Find alternative tools that might work better.
        """
        fallback_attempts = len([a for a in attempt_history if a.get('strategy') == 'fallback'])
        
        if fallback_attempts >= self.max_fallbacks:
            print(f"⚠️  Max fallbacks ({self.max_fallbacks}) reached")
            return {
                "success": False,
                "strategy": "fallback",
                "result": None,
                "explanation": f"No alternative tools found after {fallback_attempts} attempts",
                "should_continue": False,
                "next_action": None
            }
        
        # Get goal from context
        goal = context.get('goal', context.get('original_goal', ''))
        
        # Find alternative tools
        print(f"🔄 Finding alternative tools for goal: {goal[:100]}...")
        
        # Get tools already tried
        tried_tools = {tool_name}
        tried_tools.update(a.get('tool_name') for a in attempt_history if a.get('strategy') == 'fallback')
        
        # Ask orchestrator/tool_selector for alternatives
        # For now, suggest re-running tool selection
        return {
            "success": False,
            "strategy": "fallback",
            "result": None,
            "explanation": f"Tool '{tool_name}' failed. Need to re-run tool selection.",
            "should_continue": True,
            "next_action": {
                "type": "reselect_tool",
                "goal": goal,
                "exclude_tools": list(tried_tools),
                "error_context": str(error)
            }
        }
    
    def _adapt_strategy(self,
                       error: Exception,
                       tool_name: str,
                       parameters: Dict,
                       context: Dict,
                       attempt_history: List[Dict]) -> Dict:
        """
        Adapt strategy for parameter mismatches.
        
        Use LLM to fix parameters based on error message.
        """
        adapt_attempts = len([a for a in attempt_history if a.get('strategy') == 'adapt'])
        
        if adapt_attempts >= self.max_adaptations:
            print(f"⚠️  Max adaptations ({self.max_adaptations}) reached")
            return {
                "success": False,
                "strategy": "adapt",
                "result": None,
                "explanation": f"Could not fix parameters after {adapt_attempts} attempts",
                "should_continue": False,
                "next_action": None
            }
        
        print(f"🔧 Adapting parameters based on error...")
        
        # Get tool (registry returns instances, not classes)
        tool = self.tool_registry.get_tool(tool_name)
        if tool is None:
            return {
                "success": False,
                "strategy": "adapt",
                "result": None,
                "explanation": f"Tool {tool_name} not found",
                "should_continue": False,
                "next_action": None
            }
        
        tool_params = getattr(tool, 'parameters', {})
        
        # Ask LLM to fix parameters
        prompt = f"""Fix the parameters for this tool based on the error.

Tool: {tool_name}
Tool Parameters Schema:
{json.dumps(tool_params, indent=2)}

Current Parameters:
{json.dumps(parameters, indent=2)}

Error: {str(error)}

Analyze the error and fix the parameters. Return ONLY valid JSON with corrected parameters.

Example response:
{{
    "parameter1": "fixed_value",
    "parameter2": 123
}}"""

        try:
            response = self.ollama_client.generate(prompt)
            
            # Extract JSON (ollama returns dict with 'response' key)
            json_str = response.get('response', response) if isinstance(response, dict) else response
            json_str = json_str.strip() if isinstance(json_str, str) else str(json_str)
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            fixed_parameters = json.loads(json_str)
            
            print(f"🔧 Adapted parameters: {json.dumps(fixed_parameters, indent=2)}")
            
            # Try with fixed parameters
            try:
                # Tool registry returns instances, not classes
                result = tool.execute(**fixed_parameters)
                
                print(f"✅ Adaptation succeeded!")
                
                return {
                    "success": True,
                    "strategy": "adapt",
                    "result": result,
                    "explanation": f"Fixed parameters based on error. Changed: {json.dumps(fixed_parameters)}",
                    "should_continue": True,
                    "next_action": None
                }
                
            except Exception as e:
                print(f"❌ Adapted parameters still failed: {e}")
                
                # Record attempt
                attempt_history.append({
                    "strategy": "adapt",
                    "attempt": adapt_attempts + 1,
                    "fixed_parameters": fixed_parameters,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                
                # Try adapting again
                return self._adapt_strategy(e, tool_name, fixed_parameters, context, attempt_history)
        
        except Exception as e:
            print(f"❌ Parameter adaptation failed: {e}")
            return {
                "success": False,
                "strategy": "adapt",
                "result": None,
                "explanation": f"Could not fix parameters: {str(e)}",
                "should_continue": False,
                "next_action": None
            }
    
    def _explain_failure(self,
                        error: Exception,
                        tool_name: str,
                        parameters: Dict,
                        context: Dict,
                        classification: Dict) -> Dict:
        """
        Explain why task cannot be completed when recovery is impossible.
        
        Provide clear, helpful explanation to user.
        """
        print(f"❌ Task cannot be completed: {classification['reasoning']}")
        
        # Generate user-friendly explanation
        prompt = f"""Generate a clear, helpful explanation for why this task cannot be completed.

Goal: {context.get('goal', 'Unknown')}
Tool Attempted: {tool_name}
Parameters: {json.dumps(parameters, indent=2)}
Error: {str(error)}
Error Classification: {classification['error_type']}
Reasoning: {classification['reasoning']}

Write a brief, helpful explanation (2-3 sentences) that:
1. Explains what went wrong
2. Suggests alternative approaches if possible
3. Is clear and non-technical

Example: "I cannot complete this task because the resource you're trying to access doesn't exist. Please verify the ID and try again, or use the search function to find the correct resource."
"""

        try:
            response = self.ollama_client.generate(prompt)
            explanation = response.get('response', response) if isinstance(response, dict) else response
            explanation = explanation.strip().strip('"').strip("'") if isinstance(explanation, str) else str(explanation)
        except:
            explanation = f"Cannot complete task: {classification['reasoning']}"
        
        return {
            "success": False,
            "strategy": "explain",
            "result": None,
            "explanation": explanation,
            "should_continue": False,
            "next_action": None,
            "error_classification": classification
        }
    
    def get_recovery_statistics(self, days: int = 30) -> Dict:
        """
        Get statistics about recovery attempts and success rates.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Statistics about recovery patterns
        """
        # TODO: Query execution_store for recovery attempts
        # For now, return placeholder
        return {
            "total_errors": 0,
            "total_recoveries": 0,
            "recovery_rate": 0.0,
            "by_strategy": {
                "retry": {"attempts": 0, "successes": 0},
                "fallback": {"attempts": 0, "successes": 0},
                "adapt": {"attempts": 0, "successes": 0}
            },
            "by_error_type": {
                "transient": {"count": 0, "recovery_rate": 0.0},
                "wrong_tool": {"count": 0, "recovery_rate": 0.0},
                "parameter_mismatch": {"count": 0, "recovery_rate": 0.0},
                "impossible": {"count": 0, "recovery_rate": 0.0}
            }
        }
