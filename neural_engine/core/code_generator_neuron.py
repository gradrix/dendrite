from .neuron import BaseNeuron
import json

class CodeGeneratorNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/code_generator_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id: str, data: dict, depth: int):
        goal = data["goal"]
        tool_name = data["selected_tool_name"]
        module_name = data["selected_tool_module"]
        class_name = data["selected_tool_class"]

        prompt_template = self._load_prompt()
        prompt = prompt_template.format(
            goal=goal,
            tool_name=tool_name,
            module_name=module_name,
            class_name=class_name
        )

        response = self.ollama_client.generate(prompt=prompt)
        generated_code = response['response'].strip()

        # Clean up the code if it's wrapped in markdown
        if generated_code.startswith("```python"):
            generated_code = generated_code[9:]
        if generated_code.endswith("```"):
            generated_code = generated_code[:-3]

        result_data = {
            "goal": goal,
            "tool_name": tool_name,
            "code": generated_code
        }
        self.message_bus.add_message(goal_id, "code_generation", result_data)
        return result_data
