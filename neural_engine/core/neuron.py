from .message_bus import MessageBus
from .ollama_client import OllamaClient

class BaseNeuron:
    def __init__(self, message_bus: MessageBus, ollama_client: OllamaClient):
        self.message_bus = message_bus
        self.ollama_client = ollama_client

    def process(self, goal_id, data, depth=0):
        raise NotImplementedError
