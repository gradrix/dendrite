from .message_bus import MessageBus
from .ollama_client import OllamaClient
import time

class BaseNeuron:
    def __init__(self, message_bus: MessageBus, ollama_client: OllamaClient):
        self.message_bus = message_bus
        self.ollama_client = ollama_client
        # Get neuron class name for logging
        self.neuron_name = self.__class__.__name__.replace("Neuron", "").lower()
        # Convert CamelCase to snake_case for neuron name
        import re
        self.neuron_name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', self.__class__.__name__).lower().replace("_neuron", "")

    def add_message_with_metadata(self, goal_id, message_type, data, depth=0):
        """Add a message with full metadata for tracking."""
        message = {
            "goal_id": goal_id,
            "neuron": self.neuron_name,
            "message_type": message_type,
            "timestamp": time.time(),
            "depth": depth,
            "data": data
        }
        self.message_bus.add_message(goal_id, message_type, message)

    def process(self, goal_id, data, depth=0):
        raise NotImplementedError
