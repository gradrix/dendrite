import pytest
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.knowledge_base import KnowledgeBase
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.knowledge_injector_neuron import KnowledgeInjectorNeuron
from neural_engine.core.task_splitter_neuron import TaskSplitterNeuron
from neural_engine.core.response_formatter_neuron import ResponseFormatterNeuron
from neural_engine.core.validator_neuron import ValidatorNeuron
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.tools.strava_tool import StravaTool
from neural_engine.tools.python_script_tool import PythonScriptTool

@pytest.mark.integration
def test_full_pipeline():
    # Arrange
    ollama_client = OllamaClient()
    message_bus = MessageBus()
    knowledge_base = KnowledgeBase()
    knowledge_base.add_knowledge("strava", [
        "Strava is a social fitness network.",
        "An activity is a record of a workout."
    ])

    tools = [StravaTool(), PythonScriptTool()]

    tool_selector = ToolSelectorNeuron(message_bus, ollama_client, knowledge_base, tools)
    knowledge_injector = KnowledgeInjectorNeuron(message_bus, ollama_client, knowledge_base)
    task_splitter = TaskSplitterNeuron(message_bus, ollama_client)
    response_formatter = ResponseFormatterNeuron(message_bus, ollama_client)
    validator = ValidatorNeuron(message_bus, ollama_client)

    neurons = [tool_selector, knowledge_injector, task_splitter, response_formatter, validator]
    orchestrator = Orchestrator(neurons)

    goal = "Get my latest Strava activities."
    goal_id = message_bus.get_new_goal_id()
    message_bus.set_data(f"goal_{goal_id}:original_goal", goal)

    # Act
    result = orchestrator.execute(goal_id, goal)

    # Assert
    assert isinstance(result, dict)
    assert "is_valid" in result
    assert result["is_valid"] is True
    assert "final_response" in result
    assert result["final_response"] is not None
