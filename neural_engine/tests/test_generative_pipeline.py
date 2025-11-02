import pytest
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.orchestrator import Orchestrator
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.tool_registry import ToolRegistry

@pytest.mark.integration
def test_generative_pipeline():
    # Arrange
    ollama_client = OllamaClient()
    message_bus = MessageBus()
    tool_registry = ToolRegistry()

    neuron_registry = {
        "intent_classifier": IntentClassifierNeuron(message_bus, ollama_client),
        "generative": GenerativeNeuron(message_bus, ollama_client),
    }

    orchestrator = Orchestrator(
        neuron_registry=neuron_registry, 
        tool_registry=tool_registry, 
        message_bus=message_bus
    )

    goal = "Tell me a joke."
    goal_id = message_bus.get_new_goal_id()

    # Act
    result = orchestrator.execute(goal_id, goal)

    # Assert
    assert "response" in result
    assert len(result["response"]) > 5
