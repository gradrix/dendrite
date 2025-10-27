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

        # Use new metadata-rich message format
        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="intent",
            data={"intent": intent, "goal": goal},
            depth=depth
        )

        return {"goal": goal, "intent": intent}
