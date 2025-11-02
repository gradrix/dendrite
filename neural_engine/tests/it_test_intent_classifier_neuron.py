import unittest
import os
import uuid
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from unittest.mock import MagicMock

# This integration test requires a running Ollama instance with a model pulled.
# Set OLLAMA_HOST environment variable to point to your Ollama service.
# Example: export OLLAMA_HOST='http://localhost:11434'

@unittest.skipIf(not os.environ.get("OLLAMA_HOST"), "OLLAMA_HOST environment variable not set. Skipping integration test.")
class TestIntentClassifierNeuronIT(unittest.TestCase):

    def setUp(self):
        """Set up the test case."""
        self.ollama_client = OllamaClient()
        # We don't need a real message bus for this test, so we can mock it.
        self.mock_message_bus = MagicMock()
        self.intent_classifier = IntentClassifierNeuron(
            ollama_client=self.ollama_client,
            message_bus=self.mock_message_bus
        )

    def test_classifies_tool_use_intent_correctly(self):
        """
        Tests that the IntentClassifierNeuron correctly identifies a 'tool_use' intent
        using a live Ollama model.
        """
        # Arrange
        goal = "What is the current time in New York?"
        goal_id = str(uuid.uuid4())

        # Act
        result = self.intent_classifier.process(goal_id, goal)

        # Assert
        self.assertIn("intent", result)
        self.assertEqual(result["intent"], "tool_use")
        
        # Check that add_message was called with correct metadata structure
        self.mock_message_bus.add_message.assert_called_once()
        call_args = self.mock_message_bus.add_message.call_args[0]
        self.assertEqual(call_args[0], goal_id)
        self.assertEqual(call_args[1], "intent")
        # Third arg is now full metadata dict
        metadata = call_args[2]
        self.assertEqual(metadata["data"]["intent"], "tool_use")

if __name__ == '__main__':
    unittest.main()
