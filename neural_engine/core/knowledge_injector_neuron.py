from .neuron import BaseNeuron
from .knowledge_base import KnowledgeBase

class KnowledgeInjectorNeuron(BaseNeuron):
    def __init__(self, message_bus, ollama_client, knowledge_base: KnowledgeBase):
        super().__init__(message_bus, ollama_client)
        self.knowledge_base = knowledge_base

    def _load_prompt(self):
        with open("neural_engine/prompts/knowledge_injector_prompt.txt", "r") as f:
            return f.read()

    def process(self, goal_id, data: dict):
        goal = data["goal"]
        selected_tools = data["selected_tools"]

        prompt_template = self._load_prompt()

        knowledge = []
        for tool in selected_tools:
            knowledge.extend(self.knowledge_base.get_knowledge(tool))

        prompt = prompt_template.format(
            goal=goal,
            knowledge=knowledge
        )

        response = self.ollama_client.generate(model="mistral", prompt=prompt)

        enriched_goal = response['response']

        self.message_bus.add_message(goal_id, "enriched_goal", enriched_goal)

        return {"enriched_goal": enriched_goal}
