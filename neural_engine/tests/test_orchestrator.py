import unittest
from unittest.mock import MagicMock, patch
from neural_engine.core.orchestrator import Orchestrator

class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        self.neuron_registry = {
            "intent_classifier": MagicMock(),
            "generative": MagicMock(),
            "tool_selector": MagicMock(),
            "code_generator": MagicMock(),
            "sandbox": MagicMock()
        }
        self.tool_registry = MagicMock()
        self.message_bus = MagicMock()
        self.orchestrator = Orchestrator(
            neuron_registry=self.neuron_registry,
            tool_registry=self.tool_registry,
            message_bus=self.message_bus
        )

    def test_execute_dispatches_to_tool_use_pipeline(self):
        # Arrange
        goal = "What is the weather in London?"
        goal_id = "test_goal_123"
        intent_data = {"goal": goal, "intent": "tool_use"}

        # Mock the intent classifier to return 'tool_use'
        self.neuron_registry["intent_classifier"].process.return_value = intent_data

        # Patch the pipeline methods to track their calls
        with patch.object(self.orchestrator, '_execute_tool_use_pipeline', return_value="tool_use_result") as mock_tool_pipeline, \
             patch.object(self.orchestrator, '_execute_generative_pipeline') as mock_generative_pipeline:

            # Act
            result = self.orchestrator.execute(goal_id, goal)

            # Assert
            # Check that the intent classifier was called correctly
            self.neuron_registry["intent_classifier"].process.assert_called_once_with(goal_id, goal, 0)

            # Check that the correct pipeline was called
            mock_tool_pipeline.assert_called_once_with(goal_id, intent_data, 0)
            mock_generative_pipeline.assert_not_called()

            # Check that the final result is correct
            self.assertEqual(result, "tool_use_result")

if __name__ == '__main__':
    unittest.main()
