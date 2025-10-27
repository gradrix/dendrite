from typing import List
from .neuron import BaseNeuron
from ..core.tool_registry import ToolRegistry
import re

class ToolSelectorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, tool_registry: ToolRegistry):
        super().__init__(message_bus, ollama_client)
        self.tool_registry = tool_registry
        self.tool_names = [tool["name"] for tool in self.tool_registry.get_all_tool_definitions()]

    def _load_prompt(self):
        with open("neural_engine/prompts/tool_selector_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, data: dict):
        goal = data["goal"]
        prompt_template = self._load_prompt()
        tool_definitions = self.tool_registry.get_all_tool_definitions()

        prompt = prompt_template.format(goal=goal, tool_definitions=tool_definitions)

        response = self.ollama_client.generate(prompt=prompt)
        selected_tools_text = response['response']

        selected_tools = []
        for tool_name in self.tool_names:
            if re.search(r'\b' + re.escape(tool_name) + r'\b', selected_tools_text):
                selected_tools.append(tool_name)

        data["selected_tools"] = selected_tools
        self.message_bus.add_message(goal_id, "selected_tools", selected_tools)

        return data
