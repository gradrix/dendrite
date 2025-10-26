import re
from typing import List
from .neuron import BaseNeuron
from .knowledge_base import KnowledgeBase
from ..tools.base_tool import BaseTool

class ToolSelectorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, knowledge_base: KnowledgeBase, tools: List[BaseTool]):
        super().__init__(message_bus, ollama_client)
        self.knowledge_base = knowledge_base
        self.tools = tools
        self.tool_names = [tool.get_tool_definition()['name'] for tool in self.tools]

    def _load_prompt(self):
        with open("neural_engine/prompts/tool_selector_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, goal: str):
        prompt_template = self._load_prompt()

        tool_definitions = [tool.get_tool_definition() for tool in self.tools]

        prompt = prompt_template.format(
            goal=goal,
            tool_definitions=tool_definitions
        )

        response = self.ollama_client.generate(model="mistral", prompt=prompt)

        selected_tools_text = response['response']

        # Use regex to find all occurrences of the tool names in the response.
        selected_tools = []
        for tool_name in self.tool_names:
            if re.search(r'\b' + re.escape(tool_name) + r'\b', selected_tools_text):
                selected_tools.append(tool_name)

        self.message_bus.add_message(goal_id, "selected_tools", selected_tools)

        return {"goal": goal, "selected_tools": selected_tools}
