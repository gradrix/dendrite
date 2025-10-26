import pytest
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.knowledge_base import KnowledgeBase
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.tools.strava_tool import StravaTool
from neural_engine.tools.python_script_tool import PythonScriptTool

@pytest.mark.integration
def test_tool_selector_neuron():
    # Arrange
    ollama_client = OllamaClient()
    message_bus = MessageBus()
    knowledge_base = KnowledgeBase()
    tools = [StravaTool(), PythonScriptTool()]

    tool_selector = ToolSelectorNeuron(message_bus, ollama_client, knowledge_base, tools)
    goal = "Get my latest Strava activities and then write a Python script to analyze them."
    goal_id = message_bus.get_new_goal_id()

    # Act
    result = tool_selector.process(goal_id, goal)

    # Assert
    assert isinstance(result, dict)
    assert "selected_tools" in result
    selected_tools = result["selected_tools"]
    assert isinstance(selected_tools, list)
    assert "strava" in selected_tools
    assert "python_script" in selected_tools
