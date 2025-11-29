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
            tool_registry=self.mock_tool_registry,
            use_pattern_cache=False,  # Disable pattern cache for testing
            use_specialists=False,    # Disable specialists for testing
            use_voting=True           # Enable voting
        )

    def test_process_selects_tool_correctly(self):
        # Arrange
        goal = "Get the current time"
        goal_id = "test_goal_123"
        depth = 0

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

        # Mock the LLM response for voting - use chat() format (voting system uses chat, not generate)
        llm_response = {'message': {'content': 'YES\n\nConfidence: 95%\n\nThis tool gets the current time which matches the goal perfectly.'}}
        self.mock_ollama_client.chat.return_value = llm_response

        # Mock the tool registry to return tool instance
        mock_tool = MagicMock()
        mock_tool.get_tool_definition.return_value = tool_definitions["get_time_tool"]
        self.mock_tool_registry.get_tool.return_value = mock_tool

        # Act
        result = self.tool_selector_neuron.process(goal_id, goal, depth)

        # Assert
        # Check that the tool registry was called
        self.mock_tool_registry.get_all_tool_definitions.assert_called_once()

        # Check that the LLM was called (for voting) - use chat() not generate()
        self.assertTrue(self.mock_ollama_client.chat.called)

        # Check that result contains selected tools
        self.assertIsNotNone(result)
        self.assertIn("selected_tools", result)
        self.assertTrue(len(result["selected_tools"]) > 0, "Should select at least one tool")
        
        # Verify the selected tool name is correct
        selected_tool_names = [t['name'] for t in result["selected_tools"]]
        self.assertIn("get_time_tool", selected_tool_names)

if __name__ == '__main__':
    unittest.main()
