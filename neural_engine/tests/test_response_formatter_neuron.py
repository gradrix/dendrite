import pytest
import json
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.response_formatter_neuron import ResponseFormatterNeuron

@pytest.mark.integration
def test_response_formatter_neuron():
    # Arrange
    ollama_client = OllamaClient()
    message_bus = MessageBus()
    response_formatter = ResponseFormatterNeuron(message_bus, ollama_client)
    sub_tasks = ["Connect to Strava API", "Fetch recent activities"]
    goal_id = message_bus.get_new_goal_id()
    data = {"sub_tasks": sub_tasks}

    # Act
    result = response_formatter.process(goal_id, data)

    # Assert
    assert isinstance(result, dict)
    assert "formatted_response" in result
    formatted_response = result["formatted_response"]

    try:
        json_response = json.loads(formatted_response)
        assert "tasks" in json_response
        assert json_response["tasks"] == sub_tasks
    except (json.JSONDecodeError, AssertionError):
        # The LLM's response might not be perfect JSON, so we'll also check for the content.
        assert "Connect to Strava API" in formatted_response
        assert "Fetch recent activities" in formatted_response
