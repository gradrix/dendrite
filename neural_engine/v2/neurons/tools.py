"""
Tool Neuron - Execute tools to perform actions.

Flow:
1. Search for matching tools in registry
2. Select best tool using LLM
3. Extract parameters using LLM
4. Execute tool
5. Return result

Uses ToolRegistry for discovery and execution.
"""

import json
from typing import Any, Dict, List, Optional

from ..core.base import Neuron
from ..core.memory import GoalContext
from ..tools import ToolRegistry, ToolDefinition, create_builtin_tools


# Tool selection prompt
TOOL_SELECTION_PROMPT = """Select the best tool for this task.

Available tools:
{tools}

Task: {goal}

Respond with JSON:
{{"tool": "tool_name", "reason": "why this tool"}}"""


# Parameter extraction prompt
PARAM_EXTRACTION_PROMPT = """Extract parameters for this tool call.

Tool: {tool_name}
Description: {description}
Parameters:
{parameters}

User Request: {goal}

Respond with JSON containing the parameter values. Example:
{{"param1": "value1", "param2": "value2"}}

Extract the values from the user request:"""


class ToolNeuron(Neuron):
    """
    Execute tools to perform actions.
    
    Uses ToolRegistry for tool discovery and management.
    
    Usage:
        neuron = ToolNeuron(config)
        
        # Optionally load tools from directory
        neuron.load_tools("path/to/tools")
        
        # Process
        result = await neuron.run(ctx, "Calculate 2+2")
    """
    
    name = "tool"
    
    def __init__(self, config, registry: ToolRegistry = None):
        super().__init__(config)
        
        # Use provided registry or create new one
        self.registry = registry or ToolRegistry()
        
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
            Tool execution result as string
        """
        goal = input_data if isinstance(input_data, str) else ctx.goal_text
        
        # Step 1: Search for candidate tools
        candidates = self.registry.search(goal, limit=5)
        
        if not candidates:
            # Fall back to all tools if no matches
            candidates = list(self.registry.get_all_definitions().values())[:5]
        
        if not candidates:
            return f"No tools available for: {goal}"
        
        # Step 2: Select best tool using LLM
        tool_name = await self._select_tool(goal, candidates)
        ctx.tool_name = tool_name
        
        tool = self.registry.get(tool_name)
        if not tool:
            return f"Tool not found: {tool_name}"
        
        definition = tool.get_definition()
        
        # Step 3: Extract parameters using LLM
        params = await self._extract_params(goal, definition)
        ctx.parameters = params
        
        # Step 4: Execute tool
        result = tool.execute(**params)
        
        # Step 5: Format result
        if isinstance(result, dict):
            if "error" in result:
                return f"Error: {result['error']}"
            elif "result" in result:
                return str(result["result"])
            else:
                return json.dumps(result, indent=2)
        
        return str(result)
    
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
    
    async def _extract_params(self, goal: str, definition: ToolDefinition) -> Dict[str, Any]:
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
        )
        
        try:
            return await self.llm.generate_json(prompt)
        except Exception:
            return {}
