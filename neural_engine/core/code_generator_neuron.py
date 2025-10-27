from .neuron import BaseNeuron
import re

class CodeGeneratorNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/code_generator_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, data: dict):
        goal = data["goal"]
        data_handle = data.get("data_handle")
        schema = data.get("schema")

        prompt_template = self._load_prompt()
        prompt = prompt_template.format(
            goal=goal,
            data_handle=data_handle,
            schema=schema
        )

        response = self.ollama_client.generate(prompt=prompt)
        code = response['response']

        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]

        data["code"] = code
        self.message_bus.add_message(goal_id, "generated_code", code)

        return data
