from .neuron import BaseNeuron
import json
import re

class SchemaAnalyzerNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/schema_analyzer_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, data: dict):
        data_handle = data.get("data_handle")
        if not data_handle:
            return data

        redis_key = data_handle.split("redis:")[1]
        json_data_str = self.message_bus.get_data(redis_key)

        try:
            json_data = json.loads(json_data_str)
        except (json.JSONDecodeError, TypeError):
            return data

        sample = json_data[0] if isinstance(json_data, list) and json_data else json_data

        prompt_template = self._load_prompt()
        prompt = prompt_template.format(json_sample=json.dumps(sample, indent=2))

        response = self.ollama_client.generate(prompt=prompt)
        schema_text = response['response']

        match = re.search(r'\{.*\}', schema_text, re.DOTALL)
        if match:
            schema = match.group(0)
        else:
            schema = ""

        data["schema"] = schema
        self.message_bus.add_message(goal_id, "schema", schema)

        return data
