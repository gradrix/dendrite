from .neuron import BaseNeuron

class TaskSplitterNeuron(BaseNeuron):
    def _load_prompt(self):
        with open("neural_engine/prompts/task_splitter_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, data: dict):
        enriched_goal = data["enriched_goal"]

        prompt_template = self._load_prompt()

        prompt = prompt_template.format(
            enriched_goal=enriched_goal
        )

        response = self.ollama_client.generate(model="mistral", prompt=prompt)

        # For simplicity, we'll assume the LLM returns a comma-separated list of tasks.
        sub_tasks_text = response['response']
        sub_tasks = [task.strip() for task in sub_tasks_text.split(',')]

        self.message_bus.add_message(goal_id, "sub_tasks", sub_tasks)

        return {"sub_tasks": sub_tasks}
