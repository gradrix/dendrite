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
from neural_engine.core.key_value_store import KeyValueStore
import datetime

@pytest.mark.integration
def test_tool_use_pipeline(mocker):
    # Arrange
    # Mock the intent classifier to ensure deterministic behavior for this test
    mocker.patch(
        'neural_engine.core.intent_classifier_neuron.IntentClassifierNeuron.process',
        return_value={'intent': 'tool_use', 'goal': 'Say hello'}
    )
    
    # Mock the tool selector to select hello_world tool
    mocker.patch(
        'neural_engine.core.tool_selector_neuron.ToolSelectorNeuron.process',
        return_value={
            'goal': 'Say hello',
            'selected_tools': [{
                'name': 'hello_world',
                'description': 'Outputs Hello World',
                'confidence': 0.95
            }],
            'method': 'mocked'
        }
    )
    
    # Mock Strava credentials to prevent credential errors (in case they're needed)
    kv_store = KeyValueStore()
    kv_store.set('strava_cookies', 'mock_cookies')
    kv_store.set('strava_token', 'mock_token')

    ollama_client = OllamaClient()
    message_bus = MessageBus()
    tool_registry = ToolRegistry()

    neuron_registry = {
        "intent_classifier": IntentClassifierNeuron(message_bus, ollama_client),
        "tool_selector": ToolSelectorNeuron(message_bus, ollama_client, tool_registry),
        "code_generator": CodeGeneratorNeuron(message_bus, ollama_client, tool_registry),
        "sandbox": Sandbox(message_bus),
        "generative": GenerativeNeuron(message_bus, ollama_client)
    }

    orchestrator = Orchestrator(
        neuron_registry=neuron_registry, 
        tool_registry=tool_registry, 
        message_bus=message_bus
    )

    goal = "Say hello"
    goal_id = message_bus.get_new_goal_id()

    # Act
    result = orchestrator.execute(goal_id, goal)

    # Assert
    assert result is not None
    assert result["error"] is None
    assert "result" in result

    # Check if the result contains hello output
    # Result can be either a string or dict
    result_value = result["result"]
    if isinstance(result_value, dict):
        result_str = str(result_value).lower()
    else:
        result_str = result_value.lower()
    
    assert "hello" in result_str, f"Expected 'hello' in result, got: {result_value}"
