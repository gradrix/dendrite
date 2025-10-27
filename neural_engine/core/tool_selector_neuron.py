from .neuron import BaseNeuron
import json

class ToolSelectorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, tool_registry):
        super().__init__(message_bus, ollama_client)
        self.tool_registry = tool_registry

    def _load_prompt(self):
        with open("neural_engine/prompts/tool_selector_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id: str, goal: str, depth: int):
        tool_definitions = self.tool_registry.get_all_tool_definitions()
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
            "selected_tool_name": selected_tool_name,
            "selected_tool_module": tool_info["module_name"],
            "selected_tool_class": tool_info["class_name"]
        }
        self.message_bus.add_message(goal_id, "tool_selection", result_data)
        return result_data
