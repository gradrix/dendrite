from .neuron import BaseNeuron
from .tool_discovery import ToolDiscovery
from typing import Optional
import json

class ToolSelectorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, tool_registry, tool_discovery: Optional[ToolDiscovery] = None):
        super().__init__(message_bus, ollama_client)
        self.tool_registry = tool_registry
        self.tool_discovery = tool_discovery
        
        # Track usage for performance comparison
        self.selection_stats = {
            "semantic_enabled": tool_discovery is not None,
            "total_selections": 0,
            "avg_candidates_considered": 0
        }

    def _load_prompt(self):
        with open("neural_engine/prompts/tool_selector_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id: str, goal: str, depth: int):
        # Stage 3: LLM Selection from top candidates
        if self.tool_discovery:
            # Use 3-stage filtering (Stages 1+2 already done in discover_tools)
            discovered_tools = self.tool_discovery.discover_tools(
                goal_text=goal,
                semantic_limit=20,  # Stage 1: 1000+ → 20 candidates
                ranking_limit=5      # Stage 2: 20 → 5 top performers
            )
            
            # Build tool definitions for top 5 candidates only
            tool_definitions = {}
            for tool_info in discovered_tools:
                tool_name = tool_info['tool_name']
                tool = self.tool_registry.get_tool(tool_name)
                if tool:
                    tool_def = tool.get_tool_definition()
                    # Add metadata from registry
                    if hasattr(tool, '_module_name'):
                        tool_def["module_name"] = tool._module_name
                    if hasattr(tool, '_class_name'):
                        tool_def["class_name"] = tool._class_name
                    # Add performance score from Stage 2
                    tool_def["performance_score"] = tool_info.get('score', 0.5)
                    tool_def["success_rate"] = tool_info.get('success_rate')
                    tool_definitions[tool_name] = tool_def
            
            self.selection_stats["avg_candidates_considered"] = len(tool_definitions)
        else:
            # Fallback: Use all tools (original behavior)
            tool_definitions = self.tool_registry.get_all_tool_definitions()
            self.selection_stats["avg_candidates_considered"] = len(tool_definitions)
        
        self.selection_stats["total_selections"] += 1
        
        prompt_template = self._load_prompt()
        prompt = prompt_template.format(goal=goal, tools=json.dumps(tool_definitions, indent=2))

        response = self.ollama_client.generate(prompt=prompt)
        # We expect the LLM to return a JSON object with the selected tool's name
        response_json = json.loads(response['response'].strip())
        selected_tool_name = response_json["tool_name"]

        tool = self.tool_registry.get_tool(selected_tool_name)
        if not tool:
            raise ValueError(f"Tool '{selected_tool_name}' not found in registry.")

        # Get enriched tool definition from registry (includes module_name and class_name)
        tool_info = tool_definitions[selected_tool_name]
        
        result_data = {
            "goal": goal,
            "selected_tools": [{
                "name": selected_tool_name,
                "module": tool_info["module_name"],
                "class": tool_info["class_name"]
            }]
        }
        
        # Use new metadata-rich message format
        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="tool_selection",
            data=result_data,
            depth=depth
        )
        
        return result_data
