"""
Tool Neuron - Execute tools to perform actions.

Flow:
1. Search for matching tools in registry
2. Check if any tool can handle this request (capability detection)
3. Select best tool using LLM
4. Extract parameters using LLM
5. Execute tool with error recovery
6. Return result or trigger recovery action

Uses ToolRegistry for discovery and RecoveryEngine for error handling.
"""

import json
from typing import Any, Dict, List, Optional

from ..core.base import Neuron
from ..core.memory import GoalContext
from ..core.recovery import RecoveryEngine, RecoveryAction, FailureType
from ..tools import ToolRegistry, ToolDefinition, create_builtin_tools


# Tool capability check prompt - can any of these tools handle the request?
TOOL_CAPABILITY_PROMPT = """Can any of these tools handle this request?

Available tools:
{tools}

User request: {goal}

Think carefully:
1. Does the request require a specific capability (API call, data lookup, calculation)?
2. Do any of the available tools provide that capability?
3. Would using a tool be better than just answering the question directly?

Respond with JSON:
{{"can_handle": true/false, "reason": "brief explanation", "best_tool": "tool_name or null"}}"""


# Tool selection prompt
TOOL_SELECTION_PROMPT = """Select the best tool for this task.

Available tools:
{tools}

Task: {goal}

Respond with JSON:
{{"tool": "tool_name", "reason": "why this tool"}}"""


# Parameter extraction prompt - with error context if retrying
PARAM_EXTRACTION_PROMPT = """Extract parameters for this tool call.

Tool: {tool_name}
Description: {description}
Parameters:
{parameters}

User Request: {goal}
{error_context}
Respond with JSON containing the parameter values. Example:
{{"param1": "value1", "param2": "value2"}}

Extract the values from the user request:"""


class ToolNeuron(Neuron):
    """
    Execute tools to perform actions.
    
    Uses ToolRegistry for tool discovery and management.
    Uses RecoveryEngine for error handling and learning.
    
    Features:
    - Capability detection (can we handle this?)
    - Error recovery with retry
    - Fallback to generative if no tool matches
    - Execution history for learning
    
    Usage:
        neuron = ToolNeuron(config)
        
        # Optionally load tools from directory
        neuron.load_tools("path/to/tools")
        
        # Process
        result = await neuron.run(ctx, "Calculate 2+2")
    """
    
    name = "tool"
    
    def __init__(self, config, registry: ToolRegistry = None, recovery: RecoveryEngine = None):
        super().__init__(config)
        
        # Use provided registry or create new one
        self.registry = registry or ToolRegistry()
        
        # Recovery engine for error handling
        self.recovery = recovery or RecoveryEngine()
        
        # Register built-in tools
        for tool in create_builtin_tools(config):
            self.registry.register(tool)
    
    def load_tools(self, directory: str) -> int:
        """
        Load tools from a directory.
        
        Returns number of tools loaded.
        """
        return self.registry.load_from_directory(directory)
    
    async def process(self, ctx: GoalContext, input_data: Any = None) -> str:
        """
        Execute a tool based on the goal.
        
        Args:
            ctx: Goal context
            input_data: Goal text or tool spec
        
        Returns:
            Tool execution result as string, or recovery action indicator
        """
        goal = input_data if isinstance(input_data, str) else ctx.goal_text
        
        # Step 1: Search for candidate tools
        candidates = self.registry.search(goal, limit=5)
        
        if not candidates:
            # Fall back to all tools if no matches
            candidates = list(self.registry.get_all_definitions().values())[:5]
        
        if not candidates:
            # No tools at all - signal for fallback
            ctx.recovery_action = "fallback_generative"
            ctx.recovery_reason = "No tools available in registry"
            return "NO_TOOLS_AVAILABLE"
        
        # Step 2: Check if any tool can actually handle this request
        capability_check = await self._check_capability(goal, candidates)
        
        if not capability_check["can_handle"]:
            # No tool can handle this - signal for fallback
            ctx.recovery_action = "fallback_generative"
            ctx.recovery_reason = capability_check["reason"]
            return f"NO_MATCHING_TOOL:{capability_check['reason']}"
        
        # Step 3: Select best tool (use capability check result if available)
        tool_name = capability_check.get("best_tool")
        if not tool_name:
            tool_name = await self._select_tool(goal, candidates)
        
        ctx.tool_name = tool_name
        
        tool = self.registry.get(tool_name)
        if not tool:
            # Tool was suggested but doesn't exist - signal forge
            ctx.recovery_action = "forge_tool"
            ctx.recovery_reason = f"Suggested tool '{tool_name}' not found"
            return f"TOOL_NOT_FOUND:{tool_name}"
        
        definition = tool.get_definition()
        
        # Step 4: Extract parameters using LLM (with retry context if applicable)
        error_context = ""
        if hasattr(ctx, 'retry_error'):
            error_context = f"\nPrevious attempt failed: {ctx.retry_error}\nPlease fix the parameters.\n"
        
        params = await self._extract_params(goal, definition, error_context)
        ctx.parameters = params
        
        # Step 5: Execute tool with error handling
        try:
            result = tool.execute(**params)
            
            # Check for tool-level errors
            if isinstance(result, dict) and "error" in result:
                error_msg = result["error"]
                
                # Analyze failure and determine recovery action
                recovery = self.recovery.analyze_failure(
                    goal=goal,
                    tool_name=tool_name,
                    error=error_msg,
                    parameters=params,
                )
                
                ctx.recovery_action = recovery.action
                ctx.recovery_reason = recovery.reason
                ctx.recovery_context = recovery.context
                
                return f"TOOL_ERROR:{error_msg}"
            
            # Success - record for learning
            result_str = self._format_result(result)
            self.recovery.record_success(
                goal=goal,
                tool_name=tool_name,
                parameters=params,
                result=result_str,
                duration_ms=ctx.duration_ms or 0,
            )
            
            return result_str
            
        except Exception as e:
            # Execution threw exception
            recovery = self.recovery.analyze_failure(
                goal=goal,
                tool_name=tool_name,
                error=str(e),
                parameters=params,
            )
            
            ctx.recovery_action = recovery.action
            ctx.recovery_reason = recovery.reason
            ctx.recovery_context = recovery.context
            
            return f"TOOL_EXCEPTION:{str(e)}"
    
    def _format_result(self, result: Any) -> str:
        """Format tool result as string."""
        if isinstance(result, dict):
            if "result" in result:
                return str(result["result"])
            else:
                return json.dumps(result, indent=2)
        return str(result)
    
    async def _check_capability(self, goal: str, candidates: List[ToolDefinition]) -> Dict[str, Any]:
        """Check if any tool can handle this request."""
        tools_text = "\n".join([d.to_prompt_text() for d in candidates])
        
        prompt = TOOL_CAPABILITY_PROMPT.format(tools=tools_text, goal=goal)
        
        try:
            response = await self.llm.generate_json(prompt)
            can_handle = response.get("can_handle", False)
            reason = response.get("reason", "Unknown")
            best_tool = response.get("best_tool")
            
            # Validate best_tool is in candidates
            if best_tool:
                valid_names = [d.name for d in candidates]
                if best_tool not in valid_names:
                    best_tool = None
            
            return {
                "can_handle": can_handle,
                "reason": reason,
                "best_tool": best_tool,
            }
            
        except Exception as e:
            # On error, assume we can try (let execution fail instead)
            return {"can_handle": True, "reason": f"Capability check failed: {e}", "best_tool": None}
    
    async def _select_tool(self, goal: str, candidates: List[ToolDefinition]) -> str:
        """Select the best tool from candidates."""
        # If only one candidate, use it
        if len(candidates) == 1:
            return candidates[0].name
        
        # Format tools for prompt
        tools_text = "\n".join([d.to_prompt_text() for d in candidates])
        
        prompt = TOOL_SELECTION_PROMPT.format(tools=tools_text, goal=goal)
        
        try:
            response = await self.llm.generate_json(prompt)
            selected = response.get("tool", candidates[0].name)
            
            # Validate selection is in candidates
            valid_names = [d.name for d in candidates]
            if selected in valid_names:
                return selected
            
            # Default to first candidate
            return candidates[0].name
            
        except Exception:
            return candidates[0].name
    
    async def _extract_params(self, goal: str, definition: ToolDefinition, error_context: str = "") -> Dict[str, Any]:
        """Extract parameters for tool call using LLM."""
        # If no parameters needed, return empty
        if not definition.parameters:
            return {}
        
        # Format parameters
        params_text = "\n".join([
            f"- {p['name']}: {p.get('description', p.get('type', 'any'))}"
            for p in definition.parameters
        ])
        
        prompt = PARAM_EXTRACTION_PROMPT.format(
            tool_name=definition.name,
            description=definition.description,
            parameters=params_text,
            goal=goal,
            error_context=error_context,
        )
        
        try:
            return await self.llm.generate_json(prompt)
        except Exception:
            return {}
