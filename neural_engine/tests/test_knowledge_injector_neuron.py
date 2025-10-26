import pytest
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.knowledge_base import KnowledgeBase
from neural_engine.core.knowledge_injector_neuron import KnowledgeInjectorNeuron

@pytest.mark.integration
def test_knowledge_injector_neuron():
    # Arrange
    ollama_client = OllamaClient()
    message_bus = MessageBus()
    knowledge_base = KnowledgeBase()
    knowledge_base.add_knowledge("strava", [
        "Strava is a social fitness network.",
        "An activity is a record of a workout."
    ])

    knowledge_injector = KnowledgeInjectorNeuron(message_bus, ollama_client, knowledge_base)
    goal = "Get my latest Strava activities."
    selected_tools = ["strava"]
    goal_id = message_bus.get_new_goal_id()
    data = {"goal": goal, "selected_tools": selected_tools}

    # Act
    result = knowledge_injector.process(goal_id, data)

    # Assert
    assert isinstance(result, dict)
    assert "enriched_goal" in result
    enriched_goal = result["enriched_goal"]
    assert isinstance(enriched_goal, str)
    assert "workout" in enriched_goal
    assert "social fitness network" in enriched_goal
