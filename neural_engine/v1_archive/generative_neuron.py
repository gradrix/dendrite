from .neuron import BaseNeuron, fractal_process

class GenerativeNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/generative_prompt.txt", "r") as f:
            return f.read()

    @fractal_process
    def process(self, goal_id, data: dict, depth=0):
        goal = data["goal"]
        prompt_template = self._load_prompt()
        prompt = prompt_template.format(goal=goal)
        response = self.ollama_client.generate(prompt=prompt)
        result = response['response']
        
        # Use new metadata-rich message format
        self.add_message_with_metadata(
            goal_id=goal_id,
            message_type="generative_response",
            data={"response": result},
            depth=depth
        )
        
        return {"response": result}
