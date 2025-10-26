import pytest
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.validator_neuron import ValidatorNeuron

@pytest.mark.integration
def test_validator_neuron():
    # Arrange
    ollama_client = OllamaClient()
    message_bus = MessageBus()
    validator = ValidatorNeuron(message_bus, ollama_client)

    original_goal = "Get my latest Strava activities."
    formatted_response = '{ "tasks": ["Connect to Strava API", "Fetch recent activities"] }'
    goal_id = message_bus.get_new_goal_id()

    # Store the original goal in the message bus for the validator to retrieve.
    message_bus.set_data(f"goal_{goal_id}:original_goal", original_goal)

    data = {"formatted_response": formatted_response}

    # Act
    result = validator.process(goal_id, data)

    # Assert
    assert isinstance(result, dict)
    assert "is_valid" in result
    assert result["is_valid"] is True
