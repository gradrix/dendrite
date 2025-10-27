from .neuron import BaseNeuron

class GenerativeNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/generative_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, data: dict):
        goal = data["goal"]
        prompt_template = self._load_prompt()
        prompt = prompt_template.format(goal=goal)
        response = self.ollama_client.generate(prompt=prompt)
        result = response['response']
        self.message_bus.add_message(goal_id, "generative_response", result)
        return {"response": result}
