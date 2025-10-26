import pytest
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.message_bus import MessageBus
from neural_engine.core.task_splitter_neuron import TaskSplitterNeuron

@pytest.mark.integration
def test_task_splitter_neuron():
    # Arrange
    ollama_client = OllamaClient()
    message_bus = MessageBus()
    task_splitter = TaskSplitterNeuron(message_bus, ollama_client)
    enriched_goal = "Get my latest activities, which are records of my workouts, from the Strava social fitness network."
    goal_id = message_bus.get_new_goal_id()
    data = {"enriched_goal": enriched_goal}

    # Act
    result = task_splitter.process(goal_id, data)

    # Assert
    assert isinstance(result, dict)
    assert "sub_tasks" in result
    sub_tasks = result["sub_tasks"]
    assert isinstance(sub_tasks, list)
    assert len(sub_tasks) > 1
