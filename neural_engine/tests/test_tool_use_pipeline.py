import pytest
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.tool_selector_neuron import ToolSelectorNeuron
from neural_engine.core.code_generator_neuron import CodeGeneratorNeuron
from neural_engine.core.sandbox import Sandbox
import datetime

@pytest.mark.integration
def test_tool_use_pipeline(mocker):
    # Arrange
    # Mock the intent classifier to ensure deterministic behavior for this test
    mocker.patch(
        'neural_engine.core.intent_classifier_neuron.IntentClassifierNeuron.process',
        return_value={'intent': 'tool_use', 'goal': 'What time is it?'}
    )

    ollama_client = OllamaClient()
    message_bus = MessageBus()
    tool_registry = ToolRegistry()

    neuron_registry = {
        "intent_classifier": IntentClassifierNeuron(message_bus, ollama_client),
        "tool_selector": ToolSelectorNeuron(message_bus, ollama_client, tool_registry),
        "code_generator": CodeGeneratorNeuron(message_bus, ollama_client),
        "sandbox": Sandbox(message_bus),
        "generative": GenerativeNeuron(message_bus, ollama_client)
    }

    orchestrator = Orchestrator(neuron_registry, tool_registry, message_bus)

    goal = "What time is it?"
    goal_id = message_bus.get_new_goal_id()

    # Act
    result = orchestrator.execute(goal_id, goal)

    # Assert
    assert result is not None
    assert result["error"] is None
    assert "result" in result

    # Check if the result is a valid ISO 8601 datetime string
    try:
        datetime.datetime.fromisoformat(result["result"])
    except (ValueError, TypeError):
        pytest.fail("The result is not a valid ISO 8601 datetime string.")
