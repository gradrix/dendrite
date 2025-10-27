from .neuron import BaseNeuron

class IntentClassifierNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/intent_classifier_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, goal: str, depth=0):
        prompt_template = self._load_prompt()
        prompt = prompt_template.format(goal=goal)

        response = self.ollama_client.generate(prompt=prompt)

        intent = response['response'].strip().lower()

        self.message_bus.add_message(goal_id, "intent", intent)

        return {"goal": goal, "intent": intent}
