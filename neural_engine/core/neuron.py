from .message_bus import MessageBus
from .ollama_client import OllamaClient

class BaseNeuron:
    def __init__(self, message_bus: MessageBus, ollama_client: OllamaClient, next_neuron: 'BaseNeuron' = None):
        self.message_bus = message_bus
        self.ollama_client = ollama_client
        self.next_neuron = next_neuron

    def process(self, goal_id, data):
        raise NotImplementedError

    def execute(self, goal_id, data):
        processed_data = self.process(goal_id, data)
        if self.next_neuron:
            return self.next_neuron.execute(goal_id, processed_data)
        return processed_data
