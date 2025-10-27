from .neuron import BaseNeuron
import re

class ToolForgeNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/tool_forge_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, data: dict):
        goal = data["goal"]

        prompt_template = self._load_prompt()
        prompt = prompt_template.format(goal=goal)

        response = self.ollama_client.generate(prompt=prompt)
        code = response['response']

        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]

        # Extract the tool name from the code
        match = re.search(r'class\s+(\w+Tool)', code)
        if not match:
            return {"error": "Could not determine tool name from generated code."}

        tool_name = match.group(1)
        file_path = f"neural_engine/tools/{tool_name.lower()}.py"

        with open(file_path, "w") as f:
            f.write(code)

        # We would then need to re-scan the tool directory or dynamically load the new tool.
        # For now, we'll just return the path to the new tool.
        return {"status": "success", "tool_path": file_path}
