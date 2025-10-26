from .neuron import BaseNeuron

class ValidatorNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/validator_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, data: dict):
        formatted_response = data["formatted_response"]
        original_goal = self.message_bus.get_data(f"goal_{goal_id}:original_goal")

        prompt_template = self._load_prompt()

        prompt = prompt_template.format(
            original_goal=original_goal,
            formatted_response=formatted_response
        )

        response = self.ollama_client.generate(model="mistral", prompt=prompt)

        # We expect a "yes" or "no" response.
        validation_result = response['response'].strip().lower()

        self.message_bus.add_message(goal_id, "validation_result", validation_result)

        if validation_result == "yes":
            return {"final_response": formatted_response, "is_valid": True}
        else:
            return {"final_response": None, "is_valid": False, "reason": "Validation failed"}
