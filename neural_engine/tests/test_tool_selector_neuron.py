import unittest
import json
from unittest.mock import MagicMock, patch
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron

class TestToolSelectorNeuron(unittest.TestCase):

    def setUp(self):
        self.mock_message_bus = MagicMock()
        self.mock_ollama_client = MagicMock()
        self.mock_tool_registry = MagicMock()

        self.tool_selector_neuron = ToolSelectorNeuron(
            message_bus=self.mock_message_bus,
            ollama_client=self.mock_ollama_client,
            tool_registry=self.mock_tool_registry
        )

    def test_process_selects_tool_correctly(self):
        # Arrange
        goal = "Get the current time"
        goal_id = "test_goal_123"
        depth = 0
        prompt_template = "Goal: {goal}, Tools: {tools}"

        # Mock the tool registry to return a sample tool definition (as dict, not list!)
        tool_definitions = {
            "get_time_tool": {
                "name": "get_time_tool",
                "description": "Gets the current time",
                "module_name": "time_tool",
                "class_name": "TimeTool"
            }
        }
        self.mock_tool_registry.get_all_tool_definitions.return_value = tool_definitions

        # Mock the LLM response (per-tool voting format)
        llm_response = {'response': 'YES'}
        self.mock_ollama_client.generate.return_value = llm_response

        # Mock the tool registry to return tool instance
        mock_tool = MagicMock()
        mock_tool.get_tool_definition.return_value = tool_definitions["get_time_tool"]
        self.mock_tool_registry.get_tool.return_value = mock_tool

        # Patch the _load_prompt method
        with patch.object(self.tool_selector_neuron, '_load_prompt', return_value=prompt_template):

            # Act
            result = self.tool_selector_neuron.process(goal_id, goal, depth)

            # Assert
            # Check that the tool registry was called
            self.mock_tool_registry.get_all_tool_definitions.assert_called_once()
            self.mock_tool_registry.get_tool_definition.assert_called_once_with("get_time_tool")

            # Check that the LLM was called with the correct prompt
            self.mock_ollama_client.generate.assert_called_once()
            prompt_arg = self.mock_ollama_client.generate.call_args[1]['prompt']
            self.assertIn(goal, prompt_arg)
            self.assertIn(json.dumps(tool_definitions, indent=2), prompt_arg)

            # Check that the message bus was updated
            expected_message = {
                "goal": goal,
                "selected_tool_name": "get_time_tool",
                "selected_tool_module": "time_tool",
                "selected_tool_class": "TimeTool"
            }
            self.mock_message_bus.add_message.assert_called_once_with(goal_id, "tool_selection", expected_message)

            # Check the final result
            self.assertEqual(result, expected_message)

if __name__ == '__main__':
    unittest.main()
