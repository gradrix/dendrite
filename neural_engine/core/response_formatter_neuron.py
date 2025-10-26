from .neuron import BaseNeuron

class ResponseFormatterNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/response_formatter_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, data: dict):
        sub_tasks = data["sub_tasks"]

        prompt_template = self._load_prompt()

        prompt = prompt_template.format(
            sub_tasks=sub_tasks
        )

        response = self.ollama_client.generate(model="mistral", prompt=prompt)

        formatted_response = response['response']

        self.message_bus.add_message(goal_id, "formatted_response", formatted_response)

        return {"formatted_response": formatted_response}
